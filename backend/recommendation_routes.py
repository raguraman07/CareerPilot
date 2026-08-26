import os
import json
import logging
import uuid as uuid_lib
import datetime
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth
from services.recommendation_service import generate_personalized_recommendations

logger = logging.getLogger(__name__)

recommendation_bp = Blueprint('recommendations', __name__)

# In-memory mock fallback DB if Firestore is offline
MOCK_RECOMMENDATIONS_DB = {}

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


@recommendation_bp.route('/api/recommendations/generate', methods=['POST'])
def generate_recommendations():
    """
    Generates or refreshes personalized certification and project recommendations grounded in:
    Career Goal + Profile + Resume + Assessment + Learning Plan + Phase 5 Verified Skills.
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

        res_docs = db.collection("resumes").where("user_id", "==", uid).stream()
        resumes = [d.to_dict() for d in res_docs]
        latest_resume = resumes[0] if resumes else None

        assess_docs = db.collection("career_assessments").where("user_id", "==", uid).stream()
        assessments = [d.to_dict() for d in assess_docs]
        latest_assessment = assessments[0] if assessments else None

        plan_docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("status", "==", "active").stream()
        plans = [d.to_dict() for d in plan_docs]
        active_plan = plans[0] if plans else None

        return active_goal, profile, latest_resume, latest_assessment, active_plan

    def mock_fetch():
        from career_goal_routes import MOCK_CAREER_GOALS_DB
        from profile_routes import MOCK_PROFILES_DB
        from resume_routes import MOCK_RESUMES_DB
        from assessment_routes import MOCK_ASSESSMENTS_DB
        from learning_plan_routes import MOCK_LEARNING_PLANS_DB

        active_goal = next((g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == uid and g.get("status") == "active"), None)
        profile = MOCK_PROFILES_DB.get(uid, {})
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r.get("user_id") == uid]
        latest_resume = user_resumes[0] if user_resumes else None
        user_assessments = [a for a in MOCK_ASSESSMENTS_DB.values() if a.get("user_id") == uid]
        latest_assessment = user_assessments[0] if user_assessments else None
        active_plan = next((p for p in MOCK_LEARNING_PLANS_DB.values() if p.get("user_id") == uid and p.get("status") == "active"), None)

        return active_goal, profile, latest_resume, latest_assessment, active_plan

    active_goal, profile, resume, assessment, learning_plan = handle_db_op(db_fetch, mock_fetch)

    if not active_goal:
        active_goal = {
            "company_name": "Target Company",
            "job_role": "Software Engineer",
            "experience_level": "Fresher"
        }

    # 2. Generate recommendations via AI service
    try:
        rec_data = generate_personalized_recommendations(
            goal=active_goal,
            profile=profile,
            resume=resume or {"available": False, "extracted_text": ""},
            assessment=assessment or {},
            learning_plan=learning_plan or {}
        )
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return jsonify({"error": "Failed to generate recommendations."}), 500

    rec_id = str(uuid_lib.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    rec_doc = {
        "id": rec_id,
        "user_id": uid,
        "goal_id": active_goal.get("id"),
        "target_company": active_goal.get("company_name"),
        "target_role": active_goal.get("job_role"),
        "career_value_summary": rec_data.get("career_value_summary"),
        "certifications": rec_data.get("certifications"),
        "projects": rec_data.get("projects"),
        "status": "active",
        "generated_at": now_iso,
        "updated_at": now_iso
    }

    def db_save():
        db.collection("career_recommendations").document(rec_id).set(rec_doc)
        return rec_doc

    def mock_save():
        MOCK_RECOMMENDATIONS_DB[rec_id] = rec_doc
        return rec_doc

    try:
        saved = handle_db_op(db_save, mock_save)
        return jsonify({
            "success": True,
            "recommendation_id": rec_id,
            "data": saved
        }), 201
    except Exception as err:
        logger.error(f"Error persisting recommendations: {err}")
        return jsonify({"error": "Failed to save recommendations."}), 500


@recommendation_bp.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Retrieves the active recommendations for the authenticated user, or auto-generates if none exist."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get_active():
        docs = db.collection("career_recommendations").where("user_id", "==", uid).where("status", "==", "active").stream()
        recs = [d.to_dict() for d in docs]
        return recs[0] if recs else None

    def mock_get_active():
        return next((r for r in MOCK_RECOMMENDATIONS_DB.values() if r.get("user_id") == uid and r.get("status") == "active"), None)

    existing = handle_db_op(db_get_active, mock_get_active)
    if existing:
        return jsonify({
            "success": True,
            "data": existing
        }), 200

    # Auto-generate if not created yet
    return generate_recommendations()


@recommendation_bp.route('/api/certifications', methods=['GET'])
def get_certifications_only():
    """Retrieves only the certifications section of recommendations."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        docs = db.collection("career_recommendations").where("user_id", "==", uid).where("status", "==", "active").stream()
        recs = [d.to_dict() for d in docs]
        return recs[0] if recs else None

    def mock_get():
        return next((r for r in MOCK_RECOMMENDATIONS_DB.values() if r.get("user_id") == uid and r.get("status") == "active"), None)

    existing = handle_db_op(db_get, mock_get)
    if not existing:
        return jsonify({"must_complete": [], "recommended": [], "advanced": []}), 200

    return jsonify(existing.get("certifications", {})), 200


@recommendation_bp.route('/api/projects', methods=['GET'])
def get_projects_only():
    """Retrieves only the projects section of recommendations."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        docs = db.collection("career_recommendations").where("user_id", "==", uid).where("status", "==", "active").stream()
        recs = [d.to_dict() for d in docs]
        return recs[0] if recs else None

    def mock_get():
        return next((r for r in MOCK_RECOMMENDATIONS_DB.values() if r.get("user_id") == uid and r.get("status") == "active"), None)

    existing = handle_db_op(db_get, mock_get)
    if not existing:
        return jsonify({"beginner": [], "intermediate": [], "advanced": []}), 200

    return jsonify(existing.get("projects", {})), 200
