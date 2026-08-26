import time
import logging
import uuid as uuid_lib
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth
from services.knowledge_assessment_service import (
    generate_skill_assessment,
    sanitize_questions_for_client,
    evaluate_assessment_submission
)

logger = logging.getLogger(__name__)

knowledge_assessment_bp = Blueprint('knowledge_assessment', __name__)

# In-memory mock fallback if Firestore is offline
MOCK_SKILL_ASSESSMENTS_DB = {}

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


@knowledge_assessment_bp.route('/api/skill-assessment/generate', methods=['POST'])
def generate_assessment_session():
    """
    Generates a targeted Knowledge Assessment session for a specific skill in the active learning plan.
    Returns sanitized questions WITHOUT correct answers to protect test integrity.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    skill_id = data.get("skill_id")
    skill_name = data.get("skill_name")

    if not skill_id and not skill_name:
        return jsonify({"error": "Missing required field 'skill_id' or 'skill_name'."}), 400

    # 1. Fetch prerequisite context (Active Goal, Profile, Active Learning Plan)
    def db_fetch_context():
        # Active Goal
        goal_docs = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        goals = [d.to_dict() for d in goal_docs]
        active_goal = goals[0] if goals else None

        # Profile
        prof_doc = db.collection("profiles").document(uid).get()
        profile = prof_doc.to_dict() if prof_doc.exists else {}

        # Active Learning Plan
        plan_docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("status", "==", "active").stream()
        plans = [d.to_dict() for d in plan_docs]
        active_plan = plans[0] if plans else None

        return active_goal, profile, active_plan

    def mock_fetch_context():
        from career_goal_routes import MOCK_CAREER_GOALS_DB
        from profile_routes import MOCK_PROFILES_DB
        from learning_plan_routes import MOCK_LEARNING_PLANS_DB

        active_goal = next((g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == uid and g.get("status") == "active"), None)
        profile = MOCK_PROFILES_DB.get(uid, {})
        
        user_plans = [p for p in MOCK_LEARNING_PLANS_DB.values() if p.get("user_id") == uid and p.get("status") == "active"]
        active_plan = user_plans[0] if user_plans else None

        return active_goal, profile, active_plan

    active_goal, profile, learning_plan = handle_db_op(db_fetch_context, mock_fetch_context)

    if not active_goal:
        return jsonify({"error": "No active career goal found. Set your Career Goal before taking an assessment."}), 400

    if not learning_plan:
        return jsonify({"error": "No active learning plan found. Please create your Learning Plan (Phase 4) first."}), 400

    # Find the skill in the user's learning plan
    matched_skill = None
    for phase in learning_plan.get("phases", []):
        for sk in phase.get("skills", []):
            if (skill_id and sk.get("skill_id") == skill_id) or (skill_name and sk.get("name", "").lower() == skill_name.lower()):
                matched_skill = sk
                break
        if matched_skill:
            break

    if not matched_skill:
        return jsonify({"error": f"Skill '{skill_name or skill_id}' was not found in your active learning plan."}), 404

    # 2. Check previous attempts to determine attempt number
    def db_count_attempts():
        docs = db.collection("skill_assessments").where("user_id", "==", uid).where("skill_id", "==", matched_skill.get("skill_id")).stream()
        return len(list(docs))

    def mock_count_attempts():
        return len([a for a in MOCK_SKILL_ASSESSMENTS_DB.values() if a.get("user_id") == uid and a.get("skill_id") == matched_skill.get("skill_id")])

    previous_attempts_count = handle_db_op(db_count_attempts, mock_count_attempts)
    attempt_num = previous_attempts_count + 1

    # 3. Generate Knowledge Assessment
    try:
        raw_assessment = generate_skill_assessment(matched_skill, active_goal, profile, learning_plan)
    except Exception as ai_err:
        logger.error(f"Failed to generate skill assessment: {ai_err}")
        return jsonify({"error": "Failed to generate assessment. Please try again."}), 500

    assessment_id = str(uuid_lib.uuid4())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Full document stored on server with answer keys
    assessment_doc = {
        "id": assessment_id,
        "user_id": uid,
        "goal_id": active_goal.get("id"),
        "learning_plan_id": learning_plan.get("id"),
        "skill_id": matched_skill.get("skill_id"),
        "skill_name": matched_skill.get("name"),
        "category": matched_skill.get("category"),
        "target_company": active_goal.get("company_name"),
        "target_role": active_goal.get("job_role"),
        "difficulty": raw_assessment.get("difficulty", "MEDIUM"),
        "time_limit_minutes": raw_assessment.get("time_limit_minutes", 15),
        "questions": raw_assessment.get("questions", []),
        "attempt_number": attempt_num,
        "status": "in_progress",
        "score": None,
        "result": None,
        "skill_level": None,
        "evaluation": None,
        "started_at": now_iso,
        "submitted_at": None,
        "created_at": now_iso,
        "updated_at": now_iso
    }

    def db_save_assessment():
        db.collection("skill_assessments").document(assessment_id).set(assessment_doc)
        return assessment_doc

    def mock_save_assessment():
        MOCK_SKILL_ASSESSMENTS_DB[assessment_id] = assessment_doc
        return assessment_doc

    try:
        handle_db_op(db_save_assessment, mock_save_assessment)
    except Exception as save_err:
        logger.error(f"Error persisting skill assessment: {save_err}")
        return jsonify({"error": "Failed to initialize assessment session."}), 500

    # 4. Return sanitized payload to client (answers stripped)
    client_questions = sanitize_questions_for_client(assessment_doc["questions"])

    return jsonify({
        "success": True,
        "assessment_id": assessment_id,
        "skill_name": matched_skill.get("name"),
        "target_company": active_goal.get("company_name"),
        "target_role": active_goal.get("job_role"),
        "difficulty": assessment_doc["difficulty"],
        "time_limit_minutes": assessment_doc["time_limit_minutes"],
        "attempt_number": attempt_num,
        "total_questions": len(client_questions),
        "questions": client_questions
    }), 201


@knowledge_assessment_bp.route('/api/skill-assessment/<assessment_id>', methods=['GET'])
def get_assessment_session(assessment_id):
    """Retrieve an assessment session. Returns sanitized questions."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        doc = db.collection("skill_assessments").document(assessment_id).get()
        return doc.to_dict() if doc.exists else None

    def mock_get():
        return MOCK_SKILL_ASSESSMENTS_DB.get(assessment_id)

    assessment = handle_db_op(db_get, mock_get)
    if not assessment:
        return jsonify({"error": "Assessment not found."}), 404

    if assessment.get("user_id") != uid:
        return jsonify({"error": "Unauthorized access to this assessment."}), 403

    client_questions = sanitize_questions_for_client(assessment.get("questions", []))
    
    return jsonify({
        "success": True,
        "assessment_id": assessment.get("id"),
        "skill_name": assessment.get("skill_name"),
        "target_company": assessment.get("target_company"),
        "target_role": assessment.get("target_role"),
        "difficulty": assessment.get("difficulty"),
        "time_limit_minutes": assessment.get("time_limit_minutes", 15),
        "status": assessment.get("status"),
        "total_questions": len(client_questions),
        "questions": client_questions
    }), 200


@knowledge_assessment_bp.route('/api/skill-assessment/<assessment_id>/submit', methods=['POST'])
def submit_assessment_session(assessment_id):
    """
    Submits answers for evaluation:
    1. Verifies user ownership.
    2. Deterministically scores MCQs and evaluates Short Answers.
    3. Calculates final score (0-100), skill level, and pass/fail.
    4. Updates Phase 4 Learning Plan skill status to VERIFIED (if >=75%) or NEEDS_IMPROVEMENT (if <75%).
    5. Saves and returns detailed results.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    submitted_answers = data.get("answers") or {}

    def db_fetch():
        doc = db.collection("skill_assessments").document(assessment_id).get()
        return doc.to_dict() if doc.exists else None

    def mock_fetch():
        return MOCK_SKILL_ASSESSMENTS_DB.get(assessment_id)

    assessment = handle_db_op(db_fetch, mock_fetch)
    if not assessment:
        return jsonify({"error": "Assessment session not found."}), 404

    if assessment.get("user_id") != uid:
        return jsonify({"error": "Unauthorized access to assessment."}), 403

    # Evaluate submission
    eval_result = evaluate_assessment_submission(
        assessment,
        submitted_answers,
        role=assessment.get("target_role", "Software Engineer")
    )

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    assessment["status"] = "completed"
    assessment["submitted_at"] = now_iso
    assessment["updated_at"] = now_iso
    assessment["score"] = eval_result["score"]
    assessment["result"] = eval_result["status"]
    assessment["skill_level"] = eval_result["skill_level"]
    assessment["evaluation"] = eval_result

    # 4. Update Phase 4 Learning Plan skill status
    new_skill_status = "VERIFIED" if eval_result["passed"] else "NEEDS_IMPROVEMENT"
    plan_id = assessment.get("learning_plan_id")
    target_skill_id = assessment.get("skill_id")
    target_skill_name = assessment.get("skill_name", "")

    def db_update_learning_plan():
        if plan_id:
            plan_ref = db.collection("career_learning_plans").document(plan_id)
            plan_snap = plan_ref.get()
            if plan_snap.exists:
                plan = plan_snap.to_dict()
                total_skills = 0
                completed_skills = 0
                for phase in plan.get("phases", []):
                    for sk in phase.get("skills", []):
                        total_skills += 1
                        if sk.get("skill_id") == target_skill_id or sk.get("name", "").lower() == target_skill_name.lower():
                            sk["status"] = new_skill_status
                        if sk.get("status") in ["COMPLETED", "VERIFIED"]:
                            completed_skills += 1
                plan["overall_progress"] = int((completed_skills / total_skills) * 100) if total_skills > 0 else 0
                plan["updated_at"] = now_iso
                plan_ref.set(plan)

    def mock_update_learning_plan():
        from learning_plan_routes import MOCK_LEARNING_PLANS_DB
        plan = MOCK_LEARNING_PLANS_DB.get(plan_id)
        if plan:
            total_skills = 0
            completed_skills = 0
            for phase in plan.get("phases", []):
                for sk in phase.get("skills", []):
                    total_skills += 1
                    if sk.get("skill_id") == target_skill_id or sk.get("name", "").lower() == target_skill_name.lower():
                        sk["status"] = new_skill_status
                    if sk.get("status") in ["COMPLETED", "VERIFIED"]:
                        completed_skills += 1
            plan["overall_progress"] = int((completed_skills / total_skills) * 100) if total_skills > 0 else 0
            plan["updated_at"] = now_iso

    def db_save_evaluation():
        db.collection("skill_assessments").document(assessment_id).set(assessment)
        db_update_learning_plan()
        return assessment

    def mock_save_evaluation():
        MOCK_SKILL_ASSESSMENTS_DB[assessment_id] = assessment
        mock_update_learning_plan()
        return assessment

    try:
        saved = handle_db_op(db_save_evaluation, mock_save_evaluation)
        return jsonify({
            "success": True,
            "assessment_id": assessment_id,
            "score": eval_result["score"],
            "passed": eval_result["passed"],
            "status": eval_result["status"],
            "skill_level": eval_result["skill_level"],
            "skill_status_updated": new_skill_status,
            "strengths": eval_result["strengths"],
            "weak_areas": eval_result["weak_areas"],
            "recommendation": eval_result["recommendation"],
            "next_step": eval_result["next_step"],
            "question_results": eval_result["question_results"]
        }), 200
    except Exception as e:
        logger.error(f"Error persisting assessment evaluation: {e}")
        return jsonify({"error": "Failed to record assessment evaluation."}), 500


@knowledge_assessment_bp.route('/api/skill-assessment/<assessment_id>/result', methods=['GET'])
def get_assessment_result(assessment_id):
    """Fetch complete evaluation details & question review for a submitted assessment."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        doc = db.collection("skill_assessments").document(assessment_id).get()
        return doc.to_dict() if doc.exists else None

    def mock_get():
        return MOCK_SKILL_ASSESSMENTS_DB.get(assessment_id)

    assessment = handle_db_op(db_get, mock_get)
    if not assessment:
        return jsonify({"error": "Assessment not found."}), 404

    if assessment.get("user_id") != uid:
        return jsonify({"error": "Unauthorized access to assessment result."}), 403

    if assessment.get("status") != "completed" or not assessment.get("evaluation"):
        return jsonify({"error": "Assessment has not been submitted or evaluated yet."}), 400

    eval_data = assessment.get("evaluation")

    return jsonify({
        "success": True,
        "assessment_id": assessment.get("id"),
        "skill_name": assessment.get("skill_name"),
        "target_company": assessment.get("target_company"),
        "target_role": assessment.get("target_role"),
        "score": assessment.get("score"),
        "passed": eval_data.get("passed", False),
        "status": assessment.get("result"),
        "skill_level": assessment.get("skill_level"),
        "attempt_number": assessment.get("attempt_number", 1),
        "strengths": eval_data.get("strengths", []),
        "weak_areas": eval_data.get("weak_areas", []),
        "recommendation": eval_data.get("recommendation", ""),
        "next_step": eval_data.get("next_step", ""),
        "question_results": eval_data.get("question_results", []),
        "submitted_at": assessment.get("submitted_at")
    }), 200


@knowledge_assessment_bp.route('/api/skill-assessment/history', methods=['GET'])
def get_assessment_history():
    """Retrieve all assessment attempts for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    skill_filter = request.args.get("skill_name")

    def db_get_history():
        query = db.collection("skill_assessments").where("user_id", "==", uid)
        docs = query.stream()
        records = [d.to_dict() for d in docs]
        return records

    def mock_get_history():
        return [a for a in MOCK_SKILL_ASSESSMENTS_DB.values() if a.get("user_id") == uid]

    records = handle_db_op(db_get_history, mock_get_history)
    
    if skill_filter:
        records = [r for r in records if r.get("skill_name", "").lower() == skill_filter.lower()]

    records.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Sanitize history summary items
    history_summary = []
    for r in records:
        history_summary.append({
            "assessment_id": r.get("id"),
            "skill_name": r.get("skill_name"),
            "target_company": r.get("target_company"),
            "target_role": r.get("target_role"),
            "difficulty": r.get("difficulty"),
            "status": r.get("status"),
            "score": r.get("score"),
            "result": r.get("result"),
            "skill_level": r.get("skill_level"),
            "attempt_number": r.get("attempt_number", 1),
            "submitted_at": r.get("submitted_at"),
            "created_at": r.get("created_at")
        })

    return jsonify({
        "success": True,
        "history": history_summary
    }), 200
