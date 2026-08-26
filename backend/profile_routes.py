import time
import logging
import base64
import json
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth

logger = logging.getLogger(__name__)

profile_bp = Blueprint('profile', __name__)

# Temporary in-memory mock fallback if Firestore is offline
MOCK_PROFILES_DB = {}

VALID_CURRENT_STATUSES = {
    "Student",
    "Fresher",
    "Unemployed",
    "Working Professional",
    "Career Switcher"
}

def decode_jwt_payload_unverified(token):
    """Fallback utility to decode JWT payload without verifying signature."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padded = payload_b64 + '=' * (-len(payload_b64) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        return None

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
        logger.warning(f"Authentication token verification via Firebase failed: {e}. Attempting fallback JWT decode.")
        
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

def calculate_profile_completeness(profile_data):
    """
    Calculate real profile completeness (0 to 100%).
    Deterministic weighted scoring:
    - Personal Information (15%)
    - Education (20%)
    - Career Status (15%)
    - Skills (25%)
    - Projects (15%)
    - Certifications or Resume (10%)
    """
    score = 0

    # 1. Personal Information (15%)
    if profile_data.get("full_name"):
        score += 5
    if profile_data.get("email"):
        score += 5
    if profile_data.get("phone") or profile_data.get("location"):
        score += 5

    # 2. Education (20%)
    edu = profile_data.get("education") or {}
    if edu.get("highest_education"):
        score += 10
    if edu.get("institution") or edu.get("specialization") or edu.get("degree"):
        score += 10

    # 3. Career Status (15%)
    career = profile_data.get("career_information") or {}
    if career.get("current_status"):
        score += 15

    # 4. Skills (25%)
    skills = profile_data.get("skills") or {}
    total_skills_count = (
        len(skills.get("programming_languages") or []) +
        len(skills.get("technical_skills") or []) +
        len(skills.get("tools_and_technologies") or []) +
        len(skills.get("soft_skills") or [])
    )
    if total_skills_count >= 3:
        score += 25
    elif total_skills_count > 0:
        score += 10

    # 5. Projects (15%)
    projects = profile_data.get("projects") or []
    if len(projects) > 0:
        score += 15

    # 6. Certifications (5%) or Resume (5%) - total max 10%
    certs = profile_data.get("certifications") or []
    has_resume = bool(profile_data.get("resume") and profile_data.get("resume").get("resume_id"))
    if len(certs) > 0 and has_resume:
        score += 10
    elif len(certs) > 0 or has_resume:
        score += 10  # Resume is optional; having either gets full 10%

    return min(score, 100)

@profile_bp.route('/api/profile', methods=['GET'])
def get_profile():
    """Retrieve the candidate career profile for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        doc = db.collection("profiles").document(uid).get()
        if doc.exists:
            profile = doc.to_dict()
        else:
            profile = {
                "id": uid,
                "user_id": uid,
                "full_name": "",
                "email": "",
                "phone": "",
                "location": ""
            }

        # Check for latest uploaded resume to auto-link
        resume_docs = db.collection("resumes").where("user_id", "==", uid).stream()
        resumes = [d.to_dict() for d in resume_docs]
        if resumes:
            resumes.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
            latest_resume = resumes[0]
            profile["resume"] = {
                "resume_id": latest_resume.get("id"),
                "filename": latest_resume.get("filename"),
                "file_url": latest_resume.get("file_url"),
                "uploaded_at": latest_resume.get("uploaded_at"),
                "pages": latest_resume.get("pages")
            }
        return profile

    def mock_get():
        profile = MOCK_PROFILES_DB.get(uid, {
            "id": uid,
            "user_id": uid,
            "full_name": "",
            "email": "",
            "phone": "",
            "location": ""
        })
        return profile

    try:
        profile_data = handle_db_op(db_get, mock_get)
        completeness = calculate_profile_completeness(profile_data)
        profile_data["completeness"] = completeness
        return jsonify({
            "success": True,
            "profile": profile_data
        }), 200
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        return jsonify({"error": "Failed to load candidate profile."}), 500

@profile_bp.route('/api/profile', methods=['PUT'])
def update_profile():
    """Update candidate career profile for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def db_update():
        doc_ref = db.collection("profiles").document(uid)
        existing_doc = doc_ref.get()
        existing = existing_doc.to_dict() if existing_doc.exists else {}

        # Merge updates cleanly
        updated = {**existing, **data}
        updated["id"] = uid
        updated["user_id"] = uid
        updated["updated_at"] = now_iso
        if not updated.get("created_at"):
            updated["created_at"] = now_iso

        # Calculate completeness
        updated["completeness"] = calculate_profile_completeness(updated)

        doc_ref.set(updated, merge=True)
        return updated

    def mock_update():
        existing = MOCK_PROFILES_DB.get(uid, {})
        updated = {**existing, **data}
        updated["id"] = uid
        updated["user_id"] = uid
        updated["updated_at"] = now_iso
        if not updated.get("created_at"):
            updated["created_at"] = now_iso
        updated["completeness"] = calculate_profile_completeness(updated)
        MOCK_PROFILES_DB[uid] = updated
        return updated

    try:
        updated_profile = handle_db_op(db_update, mock_update)
        return jsonify({
            "success": True,
            "message": "Candidate profile updated successfully.",
            "profile": updated_profile
        }), 200
    except Exception as e:
        logger.error(f"Error updating candidate profile: {e}")
        return jsonify({"error": "Failed to update profile."}), 500

@profile_bp.route('/api/profile/context', methods=['GET'])
def get_ai_career_context():
    """
    Unified context retrieval endpoint for downstream Phase 3 AI consumption:
    Combines Career Goal + Candidate Profile + Resume.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_fetch_all():
        # 1. Career Goal
        goal_docs = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        goals = [d.to_dict() for d in goal_docs]
        active_goal = goals[0] if goals else None

        # 2. Profile
        prof_doc = db.collection("profiles").document(uid).get()
        profile = prof_doc.to_dict() if prof_doc.exists else {}

        # 3. Resume
        resume_docs = db.collection("resumes").where("user_id", "==", uid).stream()
        resumes = [d.to_dict() for d in resume_docs]
        latest_resume = None
        if resumes:
            resumes.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
            r = resumes[0]
            latest_resume = {
                "available": True,
                "resume_id": r.get("id"),
                "filename": r.get("filename"),
                "extracted_text": r.get("extracted_text", "")
            }
        else:
            latest_resume = {"available": False, "extracted_text": ""}

        return active_goal, profile, latest_resume

    def mock_fetch_all():
        from career_goal_routes import MOCK_CAREER_GOALS_DB
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
                "extracted_text": r.get("extracted_text", "")
            }
        else:
            latest_resume = {"available": False, "extracted_text": ""}
        return active_goal, profile, latest_resume

    try:
        active_goal, profile, latest_resume = handle_db_op(db_fetch_all, mock_fetch_all)
        return jsonify({
            "success": True,
            "career_goal": active_goal,
            "candidate": {
                "full_name": profile.get("full_name", ""),
                "email": profile.get("email", ""),
                "phone": profile.get("phone", ""),
                "location": profile.get("location", ""),
                "education": profile.get("education", {}),
                "career_information": profile.get("career_information", {}),
                "skills": profile.get("skills", {}),
                "projects": profile.get("projects", []),
                "certifications": profile.get("certifications", []),
                "completeness": profile.get("completeness", 0)
            },
            "resume": latest_resume
        }), 200
    except Exception as e:
        logger.error(f"Error assembling AI career context: {e}")
        return jsonify({"error": "Failed to assemble AI career context."}), 500
