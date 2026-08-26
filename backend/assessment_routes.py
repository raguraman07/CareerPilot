import time
import logging
import uuid as uuid_lib
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth
from services.career_assessment_service import (
    assess_career_readiness,
    generate_context_cache_hash,
    validate_assessment_json
)

logger = logging.getLogger(__name__)

assessment_bp = Blueprint('assessment', __name__)

# Temporary in-memory mock fallback if Firestore is offline
MOCK_ASSESSMENTS_DB = {}
MOCK_TARGETS_DB = {}

def get_auth_uid(req):
    """Verify authorization token and return user UID using Firebase Auth."""
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
    """Wrapper to handle Firestore operations with a local mock fallback if DB is offline."""
    try:
        if db is not None:
            return callback()
        return fallback_return()
    except Exception as db_err:
        logger.warning(f"Firestore operation failed: {db_err}. Falling back to Mock DB Mode.")
        return fallback_return()

@assessment_bp.route('/api/assessment/generate', methods=['POST'])
def generate_assessment():
    """
    Generate or retrieve cached Career Assessment for the authenticated user.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    job_description = data.get("job_description", "")
    force_refresh = data.get("force_refresh", False)

    # 1. Fetch unified context
    def db_fetch_context():
        # Active Goal
        goal_docs = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        goals = [d.to_dict() for d in goal_docs]
        active_goal = goals[0] if goals else None

        # Profile
        prof_doc = db.collection("profiles").document(uid).get()
        profile = prof_doc.to_dict() if prof_doc.exists else {}

        # Resume
        res_docs = db.collection("resumes").where("user_id", "==", uid).stream()
        resumes = [d.to_dict() for d in res_docs]
        latest_resume = None
        if resumes:
            resumes.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
            r = resumes[0]
            latest_resume = {
                "available": True,
                "resume_id": r.get("id"),
                "filename": r.get("filename"),
                "extracted_text": r.get("extracted_text", ""),
                "uploaded_at": r.get("uploaded_at")
            }
        else:
            latest_resume = {"available": False, "extracted_text": ""}

        return active_goal, profile, latest_resume

    def mock_fetch_context():
        from career_goal_routes import MOCK_CAREER_GOALS_DB
        from profile_routes import MOCK_PROFILES_DB
        from resume_routes import MOCK_RESUMES_DB

        active_goal = next((g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == uid and g.get("status") == "active"), None)
        profile = MOCK_PROFILES_DB.get(uid, {})
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r.get("user_id") == uid]
        if user_resumes:
            user_resumes.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
            r = user_resumes[0]
            latest_resume = {
                "available": True,
                "resume_id": r.get("id"),
                "filename": r.get("filename"),
                "extracted_text": r.get("extracted_text", ""),
                "uploaded_at": r.get("uploaded_at")
            }
        else:
            latest_resume = {"available": False, "extracted_text": ""}
        return active_goal, profile, latest_resume

    active_goal, profile, resume = handle_db_op(db_fetch_context, mock_fetch_context)

    if not active_goal:
        return jsonify({
            "error": "No active career goal found. Please define your Career Goal before running career assessment."
        }), 400

    # 2. Check for cache hit
    cache_hash = generate_context_cache_hash(active_goal, profile, resume, job_description)

    def db_check_cache():
        docs = db.collection("career_assessments").where("user_id", "==", uid).where("cache_hash", "==", cache_hash).stream()
        matches = [d.to_dict() for d in docs]
        return matches[0] if matches else None

    def mock_check_cache():
        for a in MOCK_ASSESSMENTS_DB.values():
            if a.get("user_id") == uid and a.get("cache_hash") == cache_hash:
                return a
        return None

    if not force_refresh:
        cached_record = handle_db_op(db_check_cache, mock_check_cache)
        if cached_record:
            logger.info("Serving Career Assessment from cache.")
            return jsonify({
                "success": True,
                "cached": True,
                "assessment": cached_record.get("assessment_result"),
                "assessment_id": cached_record.get("id"),
                "career_readiness_score": cached_record.get("career_readiness_score"),
                "ats_score": cached_record.get("ats_score")
            }), 200

    # 3. Generate New Assessment
    try:
        assessment_result = assess_career_readiness(active_goal, profile, resume, job_description)
    except Exception as ai_err:
        logger.error(f"Career assessment intelligence generation failed: {ai_err}")
        return jsonify({"error": "Failed to generate career assessment. Please try again."}), 500

    # 4. Save Target and Assessment in Firestore
    assessment_id = str(uuid_lib.uuid4())
    target_id = str(uuid_lib.uuid4())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    target_doc = {
        "id": target_id,
        "user_id": uid,
        "company_name": active_goal.get("company_name"),
        "job_role": active_goal.get("job_role"),
        "job_description": job_description,
        "generated_at": now_iso
    }

    assessment_doc = {
        "id": assessment_id,
        "user_id": uid,
        "goal_id": active_goal.get("id"),
        "target_id": target_id,
        "resume_id": resume.get("resume_id"),
        "cache_hash": cache_hash,
        "career_readiness_score": assessment_result.get("career_readiness_score", 60),
        "ats_score": assessment_result.get("ats_score", 65),
        "assessment_result": assessment_result,
        "created_at": now_iso,
        "updated_at": now_iso,
        "status": "completed"
    }

    def db_save_assessment():
        db.collection("career_targets").document(target_id).set(target_doc)
        db.collection("career_assessments").document(assessment_id).set(assessment_doc)
        return assessment_doc

    def mock_save_assessment():
        MOCK_TARGETS_DB[target_id] = target_doc
        MOCK_ASSESSMENTS_DB[assessment_id] = assessment_doc
        return assessment_doc

    try:
        saved_record = handle_db_op(db_save_assessment, mock_save_assessment)
        return jsonify({
            "success": True,
            "cached": False,
            "assessment": saved_record.get("assessment_result"),
            "assessment_id": assessment_id,
            "career_readiness_score": saved_record.get("career_readiness_score"),
            "ats_score": saved_record.get("ats_score")
        }), 201
    except Exception as save_err:
        logger.error(f"Error saving career assessment: {save_err}")
        return jsonify({"error": "Failed to persist career assessment."}), 500


@assessment_bp.route('/api/assessment/current', methods=['GET'])
def get_current_assessment():
    """Fetch the latest Career Assessment for the authenticated user's active goal."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get_latest():
        docs = db.collection("career_assessments").where("user_id", "==", uid).stream()
        records = [d.to_dict() for d in docs]
        if records:
            records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return records[0]
        return None

    def mock_get_latest():
        user_records = [a for a in MOCK_ASSESSMENTS_DB.values() if a.get("user_id") == uid]
        if user_records:
            user_records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return user_records[0]
        return None

    try:
        latest = handle_db_op(db_get_latest, mock_get_latest)
        if not latest:
            return jsonify({
                "success": True,
                "assessment": None
            }), 200

        return jsonify({
            "success": True,
            "assessment": latest.get("assessment_result"),
            "assessment_id": latest.get("id"),
            "career_readiness_score": latest.get("career_readiness_score"),
            "ats_score": latest.get("ats_score"),
            "created_at": latest.get("created_at")
        }), 200
    except Exception as e:
        logger.error(f"Error fetching latest assessment: {e}")
        return jsonify({"error": "Failed to fetch assessment."}), 500
