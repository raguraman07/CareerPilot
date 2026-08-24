import os
import json
import logging
import uuid
import datetime
from flask import Blueprint, request, jsonify
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op
from services.interview_service import (
    generate_interview_session,
    evaluate_interview_answer,
    is_gemini_configured
)

logger = logging.getLogger(__name__)

interview_bp = Blueprint('interview', __name__)

MOCK_INTERVIEW_DB = {}


@interview_bp.route('/api/interview/generate', methods=['POST'])
def create_interview_session():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    job_match_id = data.get("job_match_id")
    job_title = (data.get("job_title") or "").strip()
    job_description = (data.get("job_description") or "").strip()
    interview_type = data.get("interview_type", "Mixed")
    difficulty = data.get("difficulty", "Intermediate")
    num_questions = data.get("num_questions", 10)

    if not resume_id:
        return jsonify({"error": "Missing required field: resume_id."}), 400

    # Fetch resume text and verify ownership
    def db_select_resume():
        doc = db.collection("resumes").document(resume_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_resume():
        from resume_routes import MOCK_RESUMES_DB
        r = MOCK_RESUMES_DB.get(resume_id)
        if r and r.get("user_id") == uid:
            return r
        return None

    try:
        resume_doc = handle_db_op(db_select_resume, mock_select_resume)
    except Exception as db_err:
        logger.error(f"Failed to fetch resume details: {db_err}")
        return jsonify({"error": "Failed to fetch resume details."}), 500

    if not resume_doc:
        return jsonify({"error": "Resume not found or unauthorized access."}), 404

    resume_text = resume_doc.get("extracted_text") or resume_doc.get("text") or ""
    resume_filename = resume_doc.get("filename") or "Resume.pdf"

    if not resume_text.strip():
        return jsonify({"error": "Selected resume does not contain readable text."}), 400

    # If job_match_id is specified, fetch job description from Firestore job_matches collection
    if job_match_id:
        def db_select_jobmatch():
            doc = db.collection("job_matches").document(job_match_id).get()
            if doc.exists and doc.to_dict().get("user_id") == uid:
                return doc.to_dict()
            return None

        def mock_select_jobmatch():
            from jobmatch_routes import MOCK_JOBMATCH_DB
            m = MOCK_JOBMATCH_DB.get(job_match_id)
            if m and m.get("user_id") == uid:
                return m
            return None

        try:
            match_doc = handle_db_op(db_select_jobmatch, mock_select_jobmatch)
            if match_doc:
                if not job_description:
                    job_description = match_doc.get("job_description") or ""
                if not job_title:
                    job_title = match_doc.get("job_title") or ""
        except Exception as jm_err:
            logger.warning(f"Failed to fetch job match data for interview generation: {jm_err}")

    # Generate dynamic AI interview session via Gemini
    try:
        session_data = generate_interview_session(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title,
            interview_type=interview_type,
            difficulty=difficulty,
            num_questions=num_questions
        )
    except (ValueError, RuntimeError) as ai_err:
        logger.error(f"AI interview generation failed: {ai_err}")
        return jsonify({"error": "AI interview preparation is temporarily unavailable. Please try again."}), 502
    except Exception as exc:
        logger.error(f"Unexpected error during interview generation: {exc}")
        return jsonify({"error": "AI interview preparation is temporarily unavailable. Please try again."}), 502

    session_id = str(uuid.uuid4())
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    record = {
        "id": session_id,
        "user_id": uid,
        "resume_id": resume_id,
        "resume_filename": resume_filename,
        "job_match_id": job_match_id or None,
        "job_title": job_title or session_data.get("interview_title") or "Target Role",
        "job_description": job_description,
        "interview_type": interview_type,
        "difficulty": difficulty,
        "num_questions": len(session_data.get("questions") or []),
        "questions": session_data.get("questions", []),
        "overall_preparation_tips": session_data.get("overall_preparation_tips", []),
        "areas_to_prepare": session_data.get("areas_to_prepare", []),
        "potential_weaknesses": session_data.get("potential_weaknesses", []),
        "summary": session_data.get("summary", ""),
        "answers": [],
        "overall_score": None,
        "status": "in_progress",
        "created_at": now_iso
    }

    def db_insert():
        db.collection("interview_sessions").document(session_id).set(record)
        return record

    def mock_insert():
        MOCK_INTERVIEW_DB[session_id] = record
        return record

    try:
        saved_record = handle_db_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "session_id": saved_record.get("id"),
            "session": saved_record,
            # Backward compatibility fields
            "interview_id": saved_record.get("id"),
            "questions": saved_record.get("questions")
        }), 201
    except Exception as save_err:
        logger.error(f"Failed to save interview session: {save_err}")
        return jsonify({"error": "Failed to save interview session."}), 500


@interview_bp.route('/api/interview/history', methods=['GET'])
def get_interview_history():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_history():
        docs = db.collection("interview_sessions").where("user_id", "==", uid).stream()
        history = []
        for doc in docs:
            d = doc.to_dict()
            history.append(d)
        return sorted(history, key=lambda x: x.get("created_at", ""), reverse=True)

    def mock_select_history():
        user_sessions = [s for s in MOCK_INTERVIEW_DB.values() if s.get("user_id") == uid]
        return sorted(user_sessions, key=lambda x: x.get("created_at", ""), reverse=True)

    try:
        history_data = handle_db_op(db_select_history, mock_select_history)
        return jsonify(history_data), 200
    except Exception as e:
        logger.error(f"Failed to fetch interview history: {e}")
        return jsonify({"error": "Failed to fetch interview history."}), 500


@interview_bp.route('/api/interview/<session_id>', methods=['GET'])
def get_interview_session(session_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("interview_sessions").document(session_id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == uid:
                return d
        return None

    def mock_select_one():
        s = MOCK_INTERVIEW_DB.get(session_id)
        if s and s.get("user_id") == uid:
            return s
        return None

    try:
        record = handle_db_op(db_select_one, mock_select_one)
        if not record:
            return jsonify({"error": "Interview session not found or unauthorized."}), 404
        return jsonify(record), 200
    except Exception as e:
        logger.error(f"Failed to fetch interview session {session_id}: {e}")
        return jsonify({"error": "Failed to fetch interview session."}), 500


@interview_bp.route('/api/interview/<session_id>/answer', methods=['POST'])
def submit_answer(session_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    question_id = data.get("question_id")
    candidate_answer = (data.get("answer") or "").strip()

    if question_id is None or not candidate_answer:
        return jsonify({"error": "Missing required fields: question_id and answer."}), 400

    def db_select_one():
        doc = db.collection("interview_sessions").document(session_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        s = MOCK_INTERVIEW_DB.get(session_id)
        if s and s.get("user_id") == uid:
            return s
        return None

    try:
        session_record = handle_db_op(db_select_one, mock_select_one)
    except Exception as db_err:
        logger.error(f"Failed to fetch interview session for answer evaluation: {db_err}")
        return jsonify({"error": "Failed to fetch interview session."}), 500

    if not session_record:
        return jsonify({"error": "Interview session not found or unauthorized."}), 404

    # Locate the target question
    questions = session_record.get("questions") or []
    target_q = next((q for q in questions if str(q.get("id")) == str(question_id)), None)

    if not target_q:
        return jsonify({"error": f"Question with ID {question_id} not found in this interview session."}), 404

    # Evaluate answer using Gemini
    try:
        evaluation = evaluate_interview_answer(
            question_text=target_q.get("question", ""),
            candidate_answer=candidate_answer,
            why_this_question=target_q.get("why_this_question", ""),
            answer_guidance=target_q.get("answer_guidance", "")
        )
    except (ValueError, RuntimeError) as ai_err:
        logger.error(f"AI answer evaluation failed: {ai_err}")
        return jsonify({"error": "AI evaluation is temporarily unavailable. Please try again."}), 502

    # Append answer evaluation to session answers list
    answers = session_record.get("answers") or []
    # Replace existing answer evaluation if candidate retakes same question
    answers = [a for a in answers if str(a.get("question_id")) != str(question_id)]
    answer_entry = {
        "question_id": question_id,
        "answer": candidate_answer,
        "evaluation": evaluation,
        "answered_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    answers.append(answer_entry)
    session_record["answers"] = answers

    # Compute overall score across evaluated answers
    scores = [a.get("evaluation", {}).get("score", 0) for a in answers if a.get("evaluation")]
    if scores:
        session_record["overall_score"] = round(sum(scores) / len(scores))

    def db_update():
        db.collection("interview_sessions").document(session_id).update({
            "answers": answers,
            "overall_score": session_record.get("overall_score")
        })
        return session_record

    def mock_update():
        MOCK_INTERVIEW_DB[session_id] = session_record
        return session_record

    try:
        handle_db_op(db_update, mock_update)
        return jsonify({
            "success": True,
            "question_id": question_id,
            "evaluation": evaluation,
            "overall_score": session_record.get("overall_score")
        }), 200
    except Exception as save_err:
        logger.error(f"Failed to save answer evaluation: {save_err}")
        return jsonify({"error": "Failed to save answer evaluation."}), 500


@interview_bp.route('/api/interview/<session_id>/complete', methods=['POST'])
def complete_interview_session(session_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("interview_sessions").document(session_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        s = MOCK_INTERVIEW_DB.get(session_id)
        if s and s.get("user_id") == uid:
            return s
        return None

    try:
        session_record = handle_db_op(db_select_one, mock_select_one)
    except Exception as e:
        return jsonify({"error": "Failed to fetch session."}), 500

    if not session_record:
        return jsonify({"error": "Session not found."}), 404

    answers = session_record.get("answers") or []
    scores = [a.get("evaluation", {}).get("score", 0) for a in answers if a.get("evaluation")]
    overall_score = round(sum(scores) / len(scores)) if scores else 0

    session_record["status"] = "completed"
    session_record["overall_score"] = overall_score

    def db_update():
        db.collection("interview_sessions").document(session_id).update({
            "status": "completed",
            "overall_score": overall_score
        })
        return session_record

    def mock_update():
        MOCK_INTERVIEW_DB[session_id] = session_record
        return session_record

    try:
        updated = handle_db_op(db_update, mock_update)
        return jsonify({
            "success": True,
            "status": "completed",
            "overall_score": overall_score,
            "session": updated
        }), 200
    except Exception as err:
        return jsonify({"error": "Failed to complete interview session."}), 500


@interview_bp.route('/api/interview/<session_id>', methods=['DELETE'])
def delete_interview_session(session_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("interview_sessions").document(session_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        s = MOCK_INTERVIEW_DB.get(session_id)
        if s and s.get("user_id") == uid:
            return s
        return None

    try:
        record = handle_db_op(db_select_one, mock_select_one)
        if not record:
            return jsonify({"error": "Interview session not found or unauthorized."}), 404

        def db_delete():
            db.collection("interview_sessions").document(session_id).delete()
            return True

        def mock_delete():
            if session_id in MOCK_INTERVIEW_DB:
                del MOCK_INTERVIEW_DB[session_id]
            return True

        handle_db_op(db_delete, mock_delete)
        return jsonify({"message": "Interview session successfully deleted.", "id": session_id}), 200
    except Exception as e:
        logger.error(f"Failed to delete interview session {session_id}: {e}")
        return jsonify({"error": "Failed to delete interview session."}), 500
