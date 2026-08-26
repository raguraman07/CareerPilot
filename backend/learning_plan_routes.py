import time
import logging
import uuid as uuid_lib
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth
from services.learning_plan_service import (
    generate_personalized_learning_plan,
    generate_learning_plan_cache_hash,
    validate_learning_plan_json,
    clean_and_normalize_learning_plan
)

logger = logging.getLogger(__name__)

learning_plan_bp = Blueprint('learning_plan', __name__)

# In-memory mock fallback if Firestore is offline
MOCK_LEARNING_PLANS_DB = {}

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

@learning_plan_bp.route('/api/learning-plan/generate', methods=['POST'])
def generate_learning_plan_endpoint():
    """
    Generate or retrieve cached Personalized Learning Plan for the authenticated user.
    Prerequisites:
      1. Active Career Goal (Phase 1)
      2. Candidate Profile (Phase 2)
      3. Completed Career Assessment (Phase 3)
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    force_refresh = data.get("force_refresh", False)
    requested_timeline = data.get("timeline")

    # 1. Fetch prerequisite context (Goal, Profile, Assessment, Resume)
    def db_fetch_prerequisites():
        # Active Goal
        goal_docs = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        goals = [d.to_dict() for d in goal_docs]
        active_goal = goals[0] if goals else None

        # Profile
        prof_doc = db.collection("profiles").document(uid).get()
        profile = prof_doc.to_dict() if prof_doc.exists else {}

        # Latest Assessment (Phase 3)
        assess_docs = db.collection("career_assessments").where("user_id", "==", uid).stream()
        assessments = [d.to_dict() for d in assess_docs]
        latest_assessment = None
        if assessments:
            assessments.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            latest_assessment = assessments[0]

        # Resume
        res_docs = db.collection("resumes").where("user_id", "==", uid).stream()
        resumes = [d.to_dict() for d in res_docs]
        latest_resume = None
        if resumes:
            resumes.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
            latest_resume = resumes[0]

        return active_goal, profile, latest_assessment, latest_resume

    def mock_fetch_prerequisites():
        from career_goal_routes import MOCK_CAREER_GOALS_DB
        from profile_routes import MOCK_PROFILES_DB
        from assessment_routes import MOCK_ASSESSMENTS_DB
        from resume_routes import MOCK_RESUMES_DB

        active_goal = next((g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == uid and g.get("status") == "active"), None)
        profile = MOCK_PROFILES_DB.get(uid, {})
        
        user_assessments = [a for a in MOCK_ASSESSMENTS_DB.values() if a.get("user_id") == uid]
        latest_assessment = None
        if user_assessments:
            user_assessments.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            latest_assessment = user_assessments[0]

        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r.get("user_id") == uid]
        latest_resume = None
        if user_resumes:
            user_resumes.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
            latest_resume = user_resumes[0]

        return active_goal, profile, latest_assessment, latest_resume

    active_goal, profile, assessment, resume = handle_db_op(db_fetch_prerequisites, mock_fetch_prerequisites)

    if not active_goal:
        return jsonify({
            "error": "No active career goal found. Please set your Career Goal (Phase 1) before generating a learning plan."
        }), 400

    if not assessment:
        return jsonify({
            "error": "Complete your Career Assessment (Phase 3) before generating a personalized learning plan."
        }), 400

    timeline = requested_timeline or active_goal.get("target_timeline", "6 Months")

    # 2. Check for cache hit
    cache_hash = generate_learning_plan_cache_hash(active_goal, profile, assessment, timeline)

    def db_check_cache():
        docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("cache_hash", "==", cache_hash).where("status", "==", "active").stream()
        matches = [d.to_dict() for d in docs]
        return matches[0] if matches else None

    def mock_check_cache():
        for p in MOCK_LEARNING_PLANS_DB.values():
            if p.get("user_id") == uid and p.get("cache_hash") == cache_hash and p.get("status") == "active":
                return p
        return None

    if not force_refresh:
        cached_plan = handle_db_op(db_check_cache, mock_check_cache)
        if cached_plan:
            logger.info("Serving Career Learning Plan from cache.")
            return jsonify({
                "success": True,
                "cached": True,
                "learning_plan": cached_plan
            }), 200

    # 3. Generate New Learning Plan via AI Service
    try:
        plan_result = generate_personalized_learning_plan(
            active_goal,
            profile,
            assessment,
            resume=resume,
            timeline=timeline
        )
    except Exception as ai_err:
        logger.error(f"Personalized Learning Plan generation failed: {ai_err}")
        return jsonify({"error": "Failed to generate learning plan. Please try again."}), 500

    # 4. Save Learning Plan in Firestore
    plan_id = str(uuid_lib.uuid4())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    plan_doc = {
        "id": plan_id,
        "user_id": uid,
        "goal_id": active_goal.get("id"),
        "assessment_id": assessment.get("id"),
        "target_company": active_goal.get("company_name"),
        "target_role": active_goal.get("job_role"),
        "timeline": timeline,
        "cache_hash": cache_hash,
        "plan_summary": plan_result.get("plan_summary", ""),
        "overall_learning_priority": plan_result.get("overall_learning_priority", "HIGH"),
        "overall_progress": plan_result.get("overall_progress", 0),
        "phases": plan_result.get("phases", []),
        "status": "active",
        "created_at": now_iso,
        "updated_at": now_iso
    }

    def db_save_plan():
        # Deactivate any previous plans for this user to keep a clean active state
        prev_docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("status", "==", "active").stream()
        for doc in prev_docs:
            db.collection("career_learning_plans").document(doc.id).update({"status": "archived"})
        db.collection("career_learning_plans").document(plan_id).set(plan_doc)
        return plan_doc

    def mock_save_plan():
        for p in MOCK_LEARNING_PLANS_DB.values():
            if p.get("user_id") == uid and p.get("status") == "active":
                p["status"] = "archived"
        MOCK_LEARNING_PLANS_DB[plan_id] = plan_doc
        return plan_doc

    try:
        saved_plan = handle_db_op(db_save_plan, mock_save_plan)
        return jsonify({
            "success": True,
            "cached": False,
            "learning_plan": saved_plan
        }), 201
    except Exception as save_err:
        logger.error(f"Error saving learning plan: {save_err}")
        return jsonify({"error": "Failed to persist learning plan."}), 500


@learning_plan_bp.route('/api/learning-plan/current', methods=['GET'])
def get_current_learning_plan():
    """Fetch the active Learning Plan for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get_active_plan():
        docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("status", "==", "active").stream()
        records = [d.to_dict() for d in docs]
        if records:
            records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return records[0]
        return None

    def mock_get_active_plan():
        active_plans = [p for p in MOCK_LEARNING_PLANS_DB.values() if p.get("user_id") == uid and p.get("status") == "active"]
        if active_plans:
            active_plans.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return active_plans[0]
        return None

    try:
        plan = handle_db_op(db_get_active_plan, mock_get_active_plan)
        return jsonify({
            "success": True,
            "learning_plan": plan
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving current learning plan: {e}")
        return jsonify({"error": "Failed to retrieve learning plan."}), 500


@learning_plan_bp.route('/api/learning-plan/progress', methods=['PUT'])
def update_learning_progress():
    """
    Update progress for a specific skill inside the active learning plan.
    Supported statuses: NOT_STARTED, IN_PROGRESS, COMPLETED, VERIFIED
    Recalculates overall_progress % automatically.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    skill_id = data.get("skill_id")
    new_status = data.get("status")
    plan_id = data.get("plan_id")

    if not skill_id or not new_status:
        return jsonify({"error": "Missing required fields 'skill_id' and 'status'."}), 400

    valid_statuses = {"NOT_STARTED", "IN_PROGRESS", "COMPLETED", "VERIFIED", "NEEDS_IMPROVEMENT"}
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status '{new_status}'. Allowed: {', '.join(valid_statuses)}"}), 400

    def db_update_progress():
        # Query active plan
        if plan_id:
            doc_ref = db.collection("career_learning_plans").document(plan_id)
            doc_snap = doc_ref.get()
            if not doc_snap.exists:
                return None, "Plan not found."
            plan = doc_snap.to_dict()
        else:
            docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("status", "==", "active").stream()
            records = [d.to_dict() for d in docs]
            if not records:
                return None, "No active learning plan found."
            records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            plan = records[0]
            doc_ref = db.collection("career_learning_plans").document(plan["id"])

        # Check ownership
        if plan.get("user_id") != uid:
            return None, "Unauthorized access to learning plan."

        # Mutate the skill status
        found = False
        total_skills = 0
        completed_skills = 0

        for phase in plan.get("phases", []):
            for sk in phase.get("skills", []):
                total_skills += 1
                if sk.get("skill_id") == skill_id or sk.get("name", "").lower() == skill_id.lower():
                    sk["status"] = new_status
                    found = True
                if sk.get("status") in ["COMPLETED", "VERIFIED"]:
                    completed_skills += 1

        if not found:
            return None, f"Skill '{skill_id}' not found in learning plan."

        overall_prog = int((completed_skills / total_skills) * 100) if total_skills > 0 else 0
        plan["overall_progress"] = overall_prog
        plan["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        doc_ref.set(plan)
        return plan, None

    def mock_update_progress():
        target_plan = None
        if plan_id:
            target_plan = MOCK_LEARNING_PLANS_DB.get(plan_id)
        else:
            active_plans = [p for p in MOCK_LEARNING_PLANS_DB.values() if p.get("user_id") == uid and p.get("status") == "active"]
            if active_plans:
                active_plans.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                target_plan = active_plans[0]

        if not target_plan:
            return None, "No active learning plan found."

        if target_plan.get("user_id") != uid:
            return None, "Unauthorized access to learning plan."

        found = False
        total_skills = 0
        completed_skills = 0

        for phase in target_plan.get("phases", []):
            for sk in phase.get("skills", []):
                total_skills += 1
                if sk.get("skill_id") == skill_id or sk.get("name", "").lower() == skill_id.lower():
                    sk["status"] = new_status
                    found = True
                if sk.get("status") in ["COMPLETED", "VERIFIED"]:
                    completed_skills += 1

        if not found:
            return None, f"Skill '{skill_id}' not found in learning plan."

        overall_prog = int((completed_skills / total_skills) * 100) if total_skills > 0 else 0
        target_plan["overall_progress"] = overall_prog
        target_plan["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return target_plan, None

    try:
        updated_plan, error_msg = handle_db_op(db_update_progress, mock_update_progress)
        if error_msg:
            return jsonify({"error": error_msg}), 400 if "not found" in error_msg else 403

        return jsonify({
            "success": True,
            "overall_progress": updated_plan.get("overall_progress"),
            "learning_plan": updated_plan
        }), 200
    except Exception as e:
        logger.error(f"Error updating learning progress: {e}")
        return jsonify({"error": "Failed to update learning progress."}), 500
