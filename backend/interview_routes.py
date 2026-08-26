import os
import json
import logging
import uuid as uuid_lib
import datetime
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth
from services.interview_service import (
    generate_personalized_interview_questions,
    evaluate_interview_answer_ai,
    finalize_interview_session_evaluation
)

logger = logging.getLogger(__name__)

interview_bp = Blueprint('interview', __name__)

# Mock fallback DB if Firestore is offline
MOCK_INTERVIEW_SESSIONS_DB = {}

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


@interview_bp.route('/api/interview/generate', methods=['POST'])
def create_interview_training_session():
    """
    Generates a personalized interview training or mock interview session grounded in:
    Goal + Candidate Profile + Resume + Assessment + Learning Plan + Phase 5 Verified Skills.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    session_type = data.get("session_type", "MOCK_INTERVIEW")  # MOCK_INTERVIEW, DAILY_PRACTICE, CATEGORY_DRILL
    focus_category = data.get("focus_category")
    difficulty = data.get("difficulty", "MEDIUM")
    num_questions = int(data.get("num_questions", 10 if session_type == "MOCK_INTERVIEW" else 5))

    # 1. Fetch full candidate context
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
            latest_resume = resumes[0]

        # Assessment
        assess_docs = db.collection("career_assessments").where("user_id", "==", uid).stream()
        assessments = [d.to_dict() for d in assess_docs]
        latest_assessment = assessments[0] if assessments else None

        # Learning Plan
        plan_docs = db.collection("career_learning_plans").where("user_id", "==", uid).where("status", "==", "active").stream()
        plans = [d.to_dict() for d in plan_docs]
        active_plan = plans[0] if plans else None

        return active_goal, profile, latest_resume, latest_assessment, active_plan

    def mock_fetch_context():
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

    active_goal, profile, resume, assessment, learning_plan = handle_db_op(db_fetch_context, mock_fetch_context)

    if not active_goal:
        # Fallback dummy goal if not created yet
        active_goal = {
            "company_name": "Target Company",
            "job_role": "Software Engineer",
            "experience_level": "Fresher"
        }

    # 2. Generate questions via AI service
    try:
        generated = generate_personalized_interview_questions(
            goal=active_goal,
            profile=profile,
            resume=resume or {"available": False, "extracted_text": ""},
            assessment=assessment or {},
            learning_plan=learning_plan or {},
            session_type=session_type,
            num_questions=num_questions,
            focus_category=focus_category
        )
    except Exception as e:
        logger.error(f"Failed to generate interview questions: {e}")
        return jsonify({"error": "Failed to initialize interview session."}), 500

    session_id = str(uuid_lib.uuid4())
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    session_doc = {
        "id": session_id,
        "user_id": uid,
        "goal_id": active_goal.get("id"),
        "target_company": active_goal.get("company_name"),
        "target_role": active_goal.get("job_role"),
        "experience_level": active_goal.get("experience_level", "Fresher"),
        "session_type": session_type,
        "difficulty": difficulty,
        "total_questions": len(generated.get("questions", [])),
        "questions": generated.get("questions", []),
        "answers": {},
        "status": "in_progress",
        "overall_score": None,
        "readiness_level": None,
        "performance_breakdown": None,
        "strengths": None,
        "weaknesses": None,
        "personalized_improvement_plan": None,
        "started_at": now_iso,
        "completed_at": None,
        "created_at": now_iso
    }

    def db_save():
        db.collection("interview_sessions").document(session_id).set(session_doc)
        return session_doc

    def mock_save():
        MOCK_INTERVIEW_SESSIONS_DB[session_id] = session_doc
        return session_doc

    try:
        saved = handle_db_op(db_save, mock_save)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "interview_title": generated.get("interview_title"),
            "target_company": active_goal.get("company_name"),
            "target_role": active_goal.get("job_role"),
            "session_type": session_type,
            "total_questions": len(saved.get("questions", [])),
            "questions": saved.get("questions", [])
        }), 201
    except Exception as err:
        logger.error(f"Error persisting interview session: {err}")
        return jsonify({"error": "Failed to persist interview session."}), 500


@interview_bp.route('/api/interview/<session_id>/answer', methods=['POST'])
def submit_single_answer(session_id):
    """
    Submits a candidate's answer for a single interview question, evaluates it via AI against the rubric,
    and updates session answer progress in real time.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    question_id = data.get("question_id")
    user_answer = (data.get("answer") or "").strip()

    if not question_id:
        return jsonify({"error": "Missing required field: question_id."}), 400

    def db_get():
        doc = db.collection("interview_sessions").document(session_id).get()
        return doc.to_dict() if doc.exists else None

    def mock_get():
        return MOCK_INTERVIEW_SESSIONS_DB.get(session_id)

    session_doc = handle_db_op(db_get, mock_get)
    if not session_doc:
        return jsonify({"error": "Interview session not found."}), 404

    if session_doc.get("user_id") != uid:
        return jsonify({"error": "Unauthorized access to interview session."}), 403

    # Find the target question
    target_q = next((q for q in session_doc.get("questions", []) if q.get("question_id") == question_id), None)
    if not target_q:
        return jsonify({"error": f"Question '{question_id}' not found in this session."}), 404

    # Evaluate answer via AI
    evaluation = evaluate_interview_answer_ai(
        question_data=target_q,
        user_answer=user_answer,
        role=session_doc.get("target_role", "Software Engineer"),
        company=session_doc.get("target_company", "Target Company")
    )

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    answer_record = {
        "user_answer": user_answer,
        "score": evaluation.get("score", 0),
        "technical_accuracy": evaluation.get("technical_accuracy", 0),
        "completeness": evaluation.get("completeness", 0),
        "clarity": evaluation.get("clarity", 0),
        "relevance": evaluation.get("relevance", 0),
        "feedback": evaluation.get("feedback", ""),
        "strengths": evaluation.get("strengths", []),
        "missing_points": evaluation.get("missing_points", []),
        "improvement": evaluation.get("improvement", ""),
        "better_answer_structure": evaluation.get("better_answer_structure", []),
        "submitted_at": now_iso
    }

    if "answers" not in session_doc or not isinstance(session_doc["answers"], dict):
        session_doc["answers"] = {}
    session_doc["answers"][question_id] = answer_record

    def db_update():
        db.collection("interview_sessions").document(session_id).update({
            f"answers.{question_id}": answer_record
        })
        return session_doc

    def mock_update():
        MOCK_INTERVIEW_SESSIONS_DB[session_id] = session_doc
        return session_doc

    try:
        handle_db_op(db_update, mock_update)
        return jsonify({
            "success": True,
            "question_id": question_id,
            "evaluation": answer_record
        }), 200
    except Exception as e:
        logger.error(f"Failed to record answer evaluation: {e}")
        return jsonify({"error": "Failed to save answer evaluation."}), 500


@interview_bp.route('/api/interview/<session_id>/complete', methods=['POST'])
def finalize_interview_session(session_id):
    """
    Finalizes the interview session, calculates category performance breakdown,
    determines interview readiness level, and generates personalized next improvement steps.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        doc = db.collection("interview_sessions").document(session_id).get()
        return doc.to_dict() if doc.exists else None

    def mock_get():
        return MOCK_INTERVIEW_SESSIONS_DB.get(session_id)

    session_doc = handle_db_op(db_get, mock_get)
    if not session_doc:
        return jsonify({"error": "Interview session not found."}), 404

    if session_doc.get("user_id") != uid:
        return jsonify({"error": "Unauthorized access to interview session."}), 403

    # Calculate overall analysis
    analysis = finalize_interview_session_evaluation(session_doc)
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    session_doc["status"] = "completed"
    session_doc["completed_at"] = now_iso
    session_doc["overall_score"] = analysis["overall_score"]
    session_doc["readiness_level"] = analysis["readiness_level"]
    session_doc["performance_breakdown"] = analysis["performance_breakdown"]
    session_doc["strengths"] = analysis["strengths"]
    session_doc["weaknesses"] = analysis["weaknesses"]
    session_doc["personalized_improvement_plan"] = analysis["personalized_improvement_plan"]

    def db_save():
        db.collection("interview_sessions").document(session_id).set(session_doc)
        return session_doc

    def mock_save():
        MOCK_INTERVIEW_SESSIONS_DB[session_id] = session_doc
        return session_doc

    try:
        saved = handle_db_op(db_save, mock_save)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "overall_score": saved["overall_score"],
            "readiness_level": saved["readiness_level"],
            "performance_breakdown": saved["performance_breakdown"],
            "strengths": saved["strengths"],
            "weaknesses": saved["weaknesses"],
            "personalized_improvement_plan": saved["personalized_improvement_plan"],
            "session": saved
        }), 200
    except Exception as e:
        logger.error(f"Failed to finalize interview session: {e}")
        return jsonify({"error": "Failed to finalize interview session."}), 500


@interview_bp.route('/api/interview/<session_id>', methods=['GET'])
def get_interview_session(session_id):
    """Retrieve an interview session with questions and answers."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        doc = db.collection("interview_sessions").document(session_id).get()
        return doc.to_dict() if doc.exists else None

    def mock_get():
        return MOCK_INTERVIEW_SESSIONS_DB.get(session_id)

    session_doc = handle_db_op(db_get, mock_get)
    if not session_doc:
        return jsonify({"error": "Interview session not found."}), 404

    if session_doc.get("user_id") != uid:
        return jsonify({"error": "Unauthorized access to interview session."}), 403

    return jsonify({
        "success": True,
        "session": session_doc
    }), 200


@interview_bp.route('/api/interview/history', methods=['GET'])
def get_user_interview_history():
    """Retrieve interview session attempt history for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get_all():
        docs = db.collection("interview_sessions").where("user_id", "==", uid).stream()
        return [d.to_dict() for d in docs]

    def mock_get_all():
        return [s for s in MOCK_INTERVIEW_SESSIONS_DB.values() if s.get("user_id") == uid]

    sessions = handle_db_op(db_get_all, mock_get_all)
    sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    summary_list = []
    for s in sessions:
        summary_list.append({
            "session_id": s.get("id"),
            "target_company": s.get("target_company"),
            "target_role": s.get("target_role"),
            "session_type": s.get("session_type"),
            "status": s.get("status"),
            "overall_score": s.get("overall_score"),
            "readiness_level": s.get("readiness_level"),
            "total_questions": s.get("total_questions", 0),
            "answered_count": len(s.get("answers", {})),
            "created_at": s.get("created_at"),
            "completed_at": s.get("completed_at")
        })

    return jsonify(summary_list), 200


@interview_bp.route('/api/interview/readiness', methods=['GET'])
def get_interview_readiness_summary():
    """
    Computes explainable overall interview readiness score based on completed sessions and categories.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get_completed():
        docs = db.collection("interview_sessions").where("user_id", "==", uid).where("status", "==", "completed").stream()
        return [d.to_dict() for d in docs]

    def mock_get_completed():
        return [s for s in MOCK_INTERVIEW_SESSIONS_DB.values() if s.get("user_id") == uid and s.get("status") == "completed"]

    completed = handle_db_op(db_get_completed, mock_get_completed)

    if not completed:
        return jsonify({
            "readiness_score": 60,
            "readiness_level": "NEEDS_MORE_PRACTICE",
            "readiness_label": "Needs Initial Training",
            "total_sessions": 0,
            "questions_practiced": 0,
            "category_averages": {
                "technical": 60,
                "role_specific": 60,
                "project": 60,
                "behavioral": 60
            }
        }), 200

    scores = [s.get("overall_score", 0) for s in completed if s.get("overall_score") is not None]
    avg_score = int(round(sum(scores) / len(scores))) if scores else 60
    total_q = sum(len(s.get("answers", {})) for s in completed)

    return jsonify({
        "readiness_score": avg_score,
        "readiness_level": "READY" if avg_score >= 80 else ("ALMOST_READY" if avg_score >= 70 else "NEEDS_MORE_PRACTICE"),
        "readiness_label": "Interview Ready" if avg_score >= 80 else ("Almost Ready" if avg_score >= 70 else "Needs More Practice"),
        "total_sessions": len(completed),
        "questions_practiced": total_q,
        "latest_score": scores[0] if scores else None
    }), 200
