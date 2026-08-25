import os
import json
import logging
import uuid
import datetime
from flask import Blueprint, request, jsonify
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op
from services.job_matching_service import analyze_job_match, is_gemini_configured

logger = logging.getLogger(__name__)

jobmatch_bp = Blueprint('jobmatch', __name__)

MOCK_JOBMATCH_DB = {}


def _run_analyze_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    job_description = data.get("job_description")
    job_title = data.get("job_title", "").strip()

    if not resume_id or not job_description or not job_description.strip():
        return jsonify({"error": "Missing required fields: resume_id and job_description."}), 400

    # Fetch resume text and verify ownership
    def db_select_resume():
        doc = db.collection("resumes").document(resume_id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == uid:
                return d
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
        return jsonify({"error": "Selected resume does not contain any readable text. Please upload a readable PDF or DOCX file."}), 422

    # Check Firestore cache for identical request
    def db_select_cache():
        docs = db.collection("job_matches").where("user_id", "==", uid).where("resume_id", "==", resume_id).stream()
        for doc in docs:
            d = doc.to_dict()
            if d.get("job_title") == (job_title or "Target Role") and d.get("job_description") == job_description:
                return d
        return None

    def mock_select_cache():
        for r in MOCK_JOBMATCH_DB.values():
            if r.get("user_id") == uid and r.get("resume_id") == resume_id and r.get("job_description") == job_description:
                return r
        return None

    try:
        cached_record = handle_db_op(db_select_cache, mock_select_cache)
        if cached_record:
            logger.info(f"Returning cached job match analysis for resume_id {resume_id}")
            return jsonify({
                "success": True,
                "match_id": cached_record.get("id"),
                "analysis": cached_record,
                "job_match": cached_record.get("analysis_result", cached_record),
                "match_percentage": cached_record.get("match_score"),
                "matching_skills": cached_record.get("matching_skills"),
                "missing_skills": cached_record.get("missing_skills"),
                "recommendations": cached_record.get("recommendations")
            }), 200
    except Exception as cache_err:
        logger.warning(f"Job match cache lookup failed: {cache_err}")

    # Execute dynamic AI Job Matching analysis using Gemini
    try:
        analysis_result = analyze_job_match(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title
        )
    except ValueError as val_err:
        logger.error(f"AI Job Match validation error: {val_err}")
        return jsonify({"error": str(val_err)}), 422
    except RuntimeError as run_err:
        logger.error(f"AI Job Match runtime error: {run_err}")
        return jsonify({"error": f"AI service temporarily unavailable: {run_err}"}), 503
    except Exception as exc:
        logger.error(f"Unexpected error during job match: {exc}")
        return jsonify({"error": f"AI job matching failed: {exc}"}), 500

    match_id = str(uuid.uuid4())
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    record = {
        "id": match_id,
        "user_id": uid,
        "resume_id": resume_id,
        "resume_filename": resume_filename,
        "job_title": analysis_result.get("job_title") or job_title or "Target Role",
        "job_description": job_description,
        "match_score": analysis_result.get("match_score", 0),
        "match_level": analysis_result.get("qualification_level") or analysis_result.get("match_level", "Good Match"),
        "qualification_level": analysis_result.get("qualification_level", "Good Match"),
        "matching_skills": analysis_result.get("matched_skills", []),
        "matched_skills": analysis_result.get("matched_skills", []),
        "partial_skills": analysis_result.get("partial_skills", []),
        "missing_skills": analysis_result.get("missing_skills", []),
        "recommended_skills": analysis_result.get("recommended_skills", []),
        "skill_gap_analysis": analysis_result.get("skill_gap_analysis", []),
        "skill_gaps": analysis_result.get("skill_gap_analysis", []),
        "certifications": analysis_result.get("certifications", []),
        "programming_languages": analysis_result.get("programming_languages", []),
        "technologies_to_learn": analysis_result.get("technologies_to_learn", []),
        "experience_gaps": analysis_result.get("experience_gaps", []),
        "project_recommendations": analysis_result.get("project_recommendations", []),
        "improvement_plan": analysis_result.get("improvement_plan", []),
        "recommendations": analysis_result.get("recommendations", []),
        "summary": analysis_result.get("summary", ""),
        "final_recommendation": analysis_result.get("final_recommendation", ""),
        "analysis_result": analysis_result,
        "created_at": now_iso
    }

    def db_insert():
        db.collection("job_matches").document(match_id).set(record)
        return record

    def mock_insert():
        MOCK_JOBMATCH_DB[match_id] = record
        return record

    try:
        saved_record = handle_db_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "match_id": saved_record.get("id"),
            "analysis": saved_record,
            "job_match": analysis_result,
            # Backward compatibility fields
            "match_percentage": saved_record.get("match_score"),
            "matching_skills": saved_record.get("matching_skills"),
            "missing_skills": saved_record.get("missing_skills"),
            "recommendations": saved_record.get("recommendations")
        }), 201
    except Exception as save_err:
        logger.error(f"Failed to save job match results: {save_err}")
        return jsonify({"error": "Failed to save job match results."}), 500


@jobmatch_bp.route('/api/job-matching/analyze', methods=['POST'])
def analyze_job_matching():
    return _run_analyze_handler()

@jobmatch_bp.route('/api/jobmatch/match', methods=['POST'])
def match_jobmatch_alias():
    return _run_analyze_handler()

@jobmatch_bp.route('/api/jobmatch/analyze', methods=['POST'])
def analyze_jobmatch_alias():
    return _run_analyze_handler()


def _run_history_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_history():
        docs = db.collection("job_matches").where("user_id", "==", uid).stream()
        history = []
        for doc in docs:
            d = doc.to_dict()
            history.append(d)
        return sorted(history, key=lambda x: x.get("created_at", ""), reverse=True)

    def mock_select_history():
        user_matches = [m for m in MOCK_JOBMATCH_DB.values() if m.get("user_id") == uid]
        return sorted(user_matches, key=lambda x: x.get("created_at", ""), reverse=True)

    try:
        history_data = handle_db_op(db_select_history, mock_select_history)
        return jsonify(history_data), 200
    except Exception as e:
        logger.error(f"Failed to fetch job match history: {e}")
        return jsonify({"error": "Failed to fetch job match history."}), 500

@jobmatch_bp.route('/api/job-matching/history', methods=['GET'])
def history_job_matching():
    return _run_history_handler()

@jobmatch_bp.route('/api/jobmatch/history', methods=['GET'])
def history_jobmatch_alias():
    return _run_history_handler()


def _run_get_one_handler(analysis_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("job_matches").document(analysis_id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == uid:
                return d
        return None

    def mock_select_one():
        m = MOCK_JOBMATCH_DB.get(analysis_id)
        if m and m.get("user_id") == uid:
            return m
        return None

    try:
        record = handle_db_op(db_select_one, mock_select_one)
        if not record:
            return jsonify({"error": "Job match analysis not found or unauthorized."}), 404
        return jsonify(record), 200
    except Exception as e:
        logger.error(f"Failed to fetch job match record {analysis_id}: {e}")
        return jsonify({"error": "Failed to fetch job match record."}), 500

@jobmatch_bp.route('/api/job-matching/<analysis_id>', methods=['GET'])
def get_job_matching(analysis_id):
    return _run_get_one_handler(analysis_id)

@jobmatch_bp.route('/api/jobmatch/<analysis_id>', methods=['GET'])
def get_jobmatch_alias(analysis_id):
    return _run_get_one_handler(analysis_id)


def _run_delete_handler(analysis_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("job_matches").document(analysis_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        m = MOCK_JOBMATCH_DB.get(analysis_id)
        if m and m.get("user_id") == uid:
            return m
        return None

    try:
        record = handle_db_op(db_select_one, mock_select_one)
        if not record:
            return jsonify({"error": "Job match record not found or unauthorized."}), 404

        def db_delete():
            db.collection("job_matches").document(analysis_id).delete()
            return True

        def mock_delete():
            if analysis_id in MOCK_JOBMATCH_DB:
                del MOCK_JOBMATCH_DB[analysis_id]
            return True

        handle_db_op(db_delete, mock_delete)
        return jsonify({"message": "Job match analysis successfully deleted.", "id": analysis_id}), 200
    except Exception as e:
        logger.error(f"Failed to delete job match analysis {analysis_id}: {e}")
        return jsonify({"error": "Failed to delete job match analysis."}), 500

@jobmatch_bp.route('/api/job-matching/<analysis_id>', methods=['DELETE'])
def delete_job_matching(analysis_id):
    return _run_delete_handler(analysis_id)

@jobmatch_bp.route('/api/jobmatch/<analysis_id>', methods=['DELETE'])
def delete_jobmatch_alias(analysis_id):
    return _run_delete_handler(analysis_id)
