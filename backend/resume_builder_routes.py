import os
import json
import logging
import uuid as uuid_lib
import datetime
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth
from services.resume_builder_service import (
    generate_targeted_resume_ai,
    rewrite_section_content_ai,
    calculate_resume_scores
)

logger = logging.getLogger(__name__)

resume_builder_bp = Blueprint('resume_builder', __name__)

# In-memory mock fallback DB if Firestore is offline
MOCK_BUILDER_RESUMES_DB = {}

def get_auth_uid(req):
    """Verify authorization token and return user UID."""
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("Unauthorized. Missing or invalid Authorization header.")
    
    token = auth_header.split(" ")[1]
    try:
        if firebase_auth:
            decoded_token = firebase_auth.verify_id_token(token)
            return decoded_token.get("uid") or decoded_token.get("user_id")
    except Exception as e:
        logger.warning(f"Auth token verification via Firebase failed: {e}. Falling back to unverified decode.")
        
    from career_goal_routes import decode_jwt_payload_unverified
    jwt_payload = decode_jwt_payload_unverified(token)
    if jwt_payload and (jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")):
        return jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")
    raise ValueError("Unauthorized. Invalid session token.")

def handle_db_op(callback, fallback_return):
    """Wrapper to handle Firestore operations with a local mock fallback."""
    try:
        if db is not None:
            return callback()
        return fallback_return()
    except Exception as db_err:
        logger.warning(f"Firestore operation failed: {db_err}. Falling back to Mock DB.")
        return fallback_return()


@resume_builder_bp.route('/api/resume-builder/generate-targeted', methods=['POST'])
def generate_targeted_resume_endpoint():
    """
    Compiles a target-job optimized resume using profile, verified skills, and recommendations.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    # 1. Fetch user context
    def db_fetch():
        goal_docs = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        goals = [d.to_dict() for d in goal_docs]
        active_goal = goals[0] if goals else None

        prof_doc = db.collection("profiles").document(uid).get()
        profile = prof_doc.to_dict() if prof_doc.exists else {}

        plan_docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("status", "==", "active").stream()
        plans = [d.to_dict() for d in plan_docs]
        active_plan = plans[0] if plans else None

        rec_docs = db.collection("career_recommendations").where("user_id", "==", uid).where("status", "==", "active").stream()
        recs = [d.to_dict() for d in rec_docs]
        active_recs = recs[0] if recs else None

        return active_goal, profile, active_plan, active_recs

    def mock_fetch():
        from career_goal_routes import MOCK_CAREER_GOALS_DB
        from profile_routes import MOCK_PROFILES_DB
        from learning_plan_routes import MOCK_LEARNING_PLANS_DB
        from recommendation_routes import MOCK_RECOMMENDATIONS_DB

        active_goal = next((g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == uid and g.get("status") == "active"), None)
        profile = MOCK_PROFILES_DB.get(uid, {})
        active_plan = next((p for p in MOCK_LEARNING_PLANS_DB.values() if p.get("user_id") == uid and p.get("status") == "active"), None)
        active_recs = next((r for r in MOCK_RECOMMENDATIONS_DB.values() if r.get("user_id") == uid and r.get("status") == "active"), None)

        return active_goal, profile, active_plan, active_recs

    active_goal, profile, learning_plan, recommendations = handle_db_op(db_fetch, mock_fetch)

    if not active_goal or not active_goal.get("company_name") or not active_goal.get("job_role"):
        return jsonify({
            "error": "Please set your Target Company and Dream Job Role in Career Goal (Step 1) before compiling your targeted resume."
        }), 400

    # Extract verified skills from learning plan
    verified_skills = []
    if learning_plan:
        for phase in learning_plan.get("phases", []):
            for sk in phase.get("skills", []):
                if sk.get("status") == "VERIFIED":
                    verified_skills.append(sk.get("name"))

    projects_pool = []
    certs_pool = []
    if recommendations:
        projs = recommendations.get("projects", {})
        projects_pool = projs.get("intermediate", []) + projs.get("beginner", [])
        certs = recommendations.get("certifications", {})
        certs_pool = certs.get("must_complete", []) + certs.get("recommended", [])

    # 2. Generate targeted resume
    try:
        resume_data = generate_targeted_resume_ai(
            goal=active_goal,
            profile=profile,
            verified_skills=verified_skills,
            projects_pool=projects_pool,
            certs_pool=certs_pool
        )
    except Exception as e:
        logger.error(f"Error compiling targeted resume: {e}")
        return jsonify({"error": "Failed to compile targeted resume."}), 500

    resume_id = str(uuid_lib.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    doc = {
        "id": resume_id,
        "user_id": uid,
        "version_type": "TARGETED",
        "status": "active",
        "created_at": now_iso,
        "updated_at": now_iso
    }
    doc.update(resume_data)

    def db_save():
        db.collection("builder_resumes").document(resume_id).set(doc)
        return doc

    def mock_save():
        MOCK_BUILDER_RESUMES_DB[resume_id] = doc
        return doc

    try:
        saved = handle_db_op(db_save, mock_save)
        return jsonify({
            "success": True,
            "resume_id": resume_id,
            "resume": saved
        }), 201
    except Exception as err:
        logger.error(f"Error persisting builder resume: {err}")
        return jsonify({"error": "Failed to save builder resume."}), 500


@resume_builder_bp.route('/api/resume-builder/active', methods=['GET'])
def get_active_builder_resume():
    """Retrieves the active targeted resume for the authenticated user, or compiles one automatically."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        docs = db.collection("builder_resumes").where("user_id", "==", uid).where("status", "==", "active").stream()
        resumes = [d.to_dict() for d in docs]
        return resumes[0] if resumes else None

    def mock_get():
        return next((r for r in MOCK_BUILDER_RESUMES_DB.values() if r.get("user_id") == uid and r.get("status") == "active"), None)

    existing = handle_db_op(db_get, mock_get)
    if existing:
        return jsonify({
            "success": True,
            "resume": existing
        }), 200

    # Auto-compile if not existing yet
    return generate_targeted_resume_endpoint()


@resume_builder_bp.route('/api/resume-builder/save', methods=['POST'])
def save_builder_resume():
    """Saves user modifications to their targeted or master resume."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("id") or str(uuid_lib.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Recalculate scores
    scores = calculate_resume_scores(
        data,
        target_role=data.get("target_role", "Software Engineer"),
        target_company=data.get("target_company", "Target Company")
    )
    data.update(scores)
    data["user_id"] = uid
    data["id"] = resume_id
    data["updated_at"] = now_iso

    def db_save():
        db.collection("builder_resumes").document(resume_id).set(data)
        return data

    def mock_save():
        MOCK_BUILDER_RESUMES_DB[resume_id] = data
        return data

    try:
        saved = handle_db_op(db_save, mock_save)
        return jsonify({
            "success": True,
            "resume": saved
        }), 200
    except Exception as e:
        logger.error(f"Error saving resume: {e}")
        return jsonify({"error": "Failed to save resume."}), 500


@resume_builder_bp.route('/api/resume-builder/rewrite-section', methods=['POST'])
def rewrite_section_endpoint():
    """AI rewriter for professional summary or individual bullet points."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    section_type = data.get("section_type", "summary")
    content = (data.get("content") or "").strip()
    target_role = data.get("target_role", "Software Engineer")
    target_company = data.get("target_company", "Target Company")

    if not content:
        return jsonify({"error": "No content provided to rewrite."}), 400

    rewritten = rewrite_section_content_ai(
        section_type=section_type,
        content=content,
        target_role=target_role,
        target_company=target_company
    )

    return jsonify({
        "success": True,
        "original": content,
        "improved": rewritten
    }), 200


@resume_builder_bp.route('/api/resume-builder/history', methods=['GET'])
def get_builder_history():
    """Retrieves all resume versions for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get_all():
        docs = db.collection("builder_resumes").where("user_id", "==", uid).stream()
        return [d.to_dict() for d in docs]

    def mock_get_all():
        return [r for r in MOCK_BUILDER_RESUMES_DB.values() if r.get("user_id") == uid]

    resumes = handle_db_op(db_get_all, mock_get_all)
    resumes.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    summary_list = []
    for r in resumes:
        summary_list.append({
            "id": r.get("id"),
            "version_type": r.get("version_type", "TARGETED"),
            "target_company": r.get("target_company"),
            "target_role": r.get("target_role"),
            "ats_score": r.get("ats_score", 0),
            "role_alignment_score": r.get("role_alignment_score", 0),
            "updated_at": r.get("updated_at")
        })

    return jsonify(summary_list), 200


@resume_builder_bp.route('/api/generate-pdf', methods=['POST'])
@resume_builder_bp.route('/api/resume-builder/generate-pdf', methods=['POST'])
def generate_pdf_endpoint():
    """
    Accepts raw styled HTML content and converts it into a downloadable PDF stream via xhtml2pdf.
    """
    try:
        from services.pdf_generator import html_to_pdf
        import io
        from flask import send_file

        data = request.get_json() or {}
        html_content = data.get('html')
        filename = data.get('filename', 'CareerPilot_Resume.pdf')

        if not html_content:
            return jsonify({'error': 'Missing HTML content'}), 400

        if not filename.endswith('.pdf'):
            filename += '.pdf'

        styled_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
        <style>
            @page {{ size: letter; margin: 0.35in; }}
            body {{ font-family: Helvetica, sans-serif; font-size: 9.5pt; line-height: 1.35; color: #2D3748; }}
            .pdf-row {{ display: block; width: 100%; clear: both; }}
            .pdf-col-12 {{ width: 100%; float: left; }}
            .pdf-col-8 {{ width: 66.66%; float: left; }}
            .pdf-col-4 {{ width: 33.33%; float: left; }}
            .pdf-col-6 {{ width: 50%; float: left; }}
            .pdf-col-3 {{ width: 25%; float: left; }}
            table {{ width: 100%; border-collapse: collapse; }}
        </style></head><body>{html_content}</body></html>"""

        pdf_bytes = html_to_pdf(styled_html)

        if pdf_bytes is None:
            logger.error("PDF generation returned None. Check HTML/CSS formatting.")
            return jsonify({'error': 'PDF generation failed on server.'}), 500

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Server error during PDF export: {e}", exc_info=True)
        return jsonify({'error': str(e), 'message': 'Server error during PDF export'}), 500


@resume_builder_bp.route('/api/ai-suggest', methods=['POST'])
@resume_builder_bp.route('/api/resume-builder/ai-suggest', methods=['POST'])
def ai_suggest_endpoint():
    """
    Accepts current section text, type, and target context to return optimized statements.
    """
    try:
        data = request.get_json() or {}
        prompt_type = data.get('type')  # 'summary', 'experience', 'skills'
        current_text = (data.get('text') or '').strip()
        target_role = data.get('target_role') or data.get('platform') or 'Software Engineer'
        target_company = data.get('target_company') or 'Target Company'

        if not prompt_type:
            return jsonify({'error': 'Missing suggestion type'}), 400

        improved = rewrite_section_content_ai(
            section_type=prompt_type,
            content=current_text,
            target_role=target_role,
            target_company=target_company
        )

        return jsonify({
            'success': True,
            'suggestion': improved,
            'source': 'CareerPilot AI'
        }), 200
    except Exception as e:
        logger.error(f"Error generating AI suggestion: {e}")
        return jsonify({'error': str(e), 'message': 'Failed to generate AI suggestion'}), 500

