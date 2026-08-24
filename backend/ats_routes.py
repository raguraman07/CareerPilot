import os
import time
import json
import uuid
import logging
from flask import Blueprint, request, jsonify
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op
from services.ats_service import (
    run_gemini_ats_analysis,
    calculate_deterministic_ats_scores
)

logger = logging.getLogger(__name__)

ats_bp = Blueprint('ats', __name__)

# Local in-memory fallback database for local offline testing
MOCK_ATS_DB = {}


def get_cached_ats_result(resume_id, user_id):
    """Checks if a completed ATS analysis record already exists for (resume_id, user_id)."""
    def db_select():
        docs = db.collection("resume_ats_scores").where("resume_id", "==", resume_id).where("user_id", "==", user_id).stream()
        records = [d.to_dict() for d in docs]
        if records:
            sorted_records = sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)
            return sorted_records[0]
        return None

    def mock_select():
        user_records = [r for r in MOCK_ATS_DB.values() if r.get("resume_id") == resume_id and r.get("user_id") == user_id]
        if user_records:
            sorted_records = sorted(user_records, key=lambda x: x.get("created_at", ""), reverse=True)
            return sorted_records[0]
        return None

    try:
        return handle_db_op(db_select, mock_select)
    except Exception as e:
        logger.warning(f"Error checking ATS cache: {e}")
        return None


def fetch_and_verify_resume(resume_id, user_id):
    """
    Retrieves resume from database and verifies ownership.
    Ensures user_id matches authenticated Firebase UID.
    """
    def db_select():
        doc = db.collection("resumes").document(resume_id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == user_id:
                return d
        return None

    def mock_select():
        from resume_routes import MOCK_RESUMES_DB
        r = MOCK_RESUMES_DB.get(resume_id)
        if r and r.get("user_id") == user_id:
            return r
        return None

    return handle_db_op(db_select, mock_select)


def save_ats_record(resume_id, user_id, scores, ats_results):
    """Saves calculated ATS score and structured Gemini analysis to Firestore DB."""
    rec_id = str(uuid.uuid4())
    curr_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    record = {
        "id": rec_id,
        "resume_id": resume_id,
        "user_id": user_id,
        "overall_score": scores["overall_score"],
        "keyword_score": scores["keyword_score"],
        "skills_score": scores["skills_score"],
        "experience_score": scores["experience_score"],
        "structure_score": scores["structure_score"],
        "formatting_score": scores["formatting_score"],
        "education_score": scores["education_score"],
        "achievements_score": scores["achievements_score"],
        "score_level": scores["score_level"],
        "ats_results": ats_results,
        "created_at": curr_time,
        "updated_at": curr_time
    }

    def db_insert():
        db.collection("resume_ats_scores").document(rec_id).set(record)
        return record

    def mock_insert():
        MOCK_ATS_DB[rec_id] = record
        return record

    return handle_db_op(db_insert, mock_insert)


@ats_bp.route('/api/ats/analyze/<resume_id>', methods=['POST'])
@ats_bp.route('/api/ats/score', methods=['POST'])
def analyze_ats(resume_id=None):
    """
    POST /api/ats/analyze/<resume_id> or POST /api/ats/score
    Analyzes resume text against modern ATS criteria using deterministic backend scoring + Gemini semantic analysis.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        logger.error(f"Authentication failure: {val_err}")
        return jsonify({"success": False, "error": str(val_err)}), 401

    data = request.get_json(silent=True) or {}
    if not resume_id:
        resume_id = data.get("resume_id")

    if not resume_id:
        return jsonify({"success": False, "error": "Missing resume_id parameter."}), 400

    force_reanalyze = request.args.get("force", "false").lower() == "true" or data.get("force") is True

    try:
        resume_record = fetch_and_verify_resume(resume_id, uid)
    except Exception as db_err:
        logger.error(f"Database error checking resume {resume_id}: {db_err}")
        return jsonify({"success": False, "error": "Database error while fetching resume details."}), 500

    if not resume_record:
        logger.error(f"Resume {resume_id} not found or unauthorized for user {uid}")
        return jsonify({"success": False, "error": "Resume not found or access denied."}), 404

    if not force_reanalyze:
        cached = get_cached_ats_result(resume_id, uid)
        if cached:
            logger.info(f"Returning cached ATS analysis for resume_id {resume_id}")
            return jsonify({
                "success": True,
                "cached": True,
                "ats_result": cached,
                "id": cached.get("id"),
                "overall_score": cached.get("overall_score"),
                "keyword_score": cached.get("keyword_score"),
                "skills_score": cached.get("skills_score", cached.get("keyword_score", 0)),
                "experience_score": cached.get("experience_score"),
                "structure_score": cached.get("structure_score", cached.get("grammar_score", 0)),
                "formatting_score": cached.get("formatting_score", cached.get("format_score", 0)),
                "education_score": cached.get("education_score", 8),
                "achievements_score": cached.get("achievements_score", 4),
                "score_level": cached.get("score_level", "Strong ATS Compatibility"),
                "ats_results": cached.get("ats_results", {})
            }), 200

    extracted_text = (resume_record.get("extracted_text") or "").strip()
    if not extracted_text:
        logger.warning(f"Resume {resume_id} contains no extracted text content.")
        return jsonify({
            "success": False,
            "error": "Resume text is unavailable for ATS analysis."
        }), 400

    try:
        ats_results = run_gemini_ats_analysis(extracted_text)
    except Exception as gemini_err:
        logger.error(f"Gemini API invocation failed for resume {resume_id}: {gemini_err}")
        return jsonify({"success": False, "error": "AI analysis is temporarily unavailable. Please try again."}), 502

    scores = calculate_deterministic_ats_scores(ats_results, extracted_text)

    try:
        saved_record = save_ats_record(resume_id, uid, scores, ats_results)
    except Exception as save_err:
        logger.error(f"Failed to save ATS result: {save_err}")
        return jsonify({"success": False, "error": "Failed to save ATS analysis to database."}), 500

    return jsonify({
        "success": True,
        "cached": False,
        "ats_result": saved_record,
        "id": saved_record.get("id"),
        "overall_score": scores["overall_score"],
        "keyword_score": scores["keyword_score"],
        "skills_score": scores["skills_score"],
        "experience_score": scores["experience_score"],
        "structure_score": scores["structure_score"],
        "formatting_score": scores["formatting_score"],
        "education_score": scores["education_score"],
        "achievements_score": scores["achievements_score"],
        "score_level": scores["score_level"],
        "ats_results": ats_results
    }), 201


@ats_bp.route('/api/ats/result/<resume_id>', methods=['GET'])
def get_ats_result(resume_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 401

    if not resume_id:
        return jsonify({"success": False, "error": "Missing resume_id."}), 400

    cached = get_cached_ats_result(resume_id, uid)
    if not cached:
        return jsonify({"success": False, "error": "No ATS score result found for this resume."}), 404

    return jsonify({
        "success": True,
        "ats_result": cached
    }), 200


@ats_bp.route('/api/ats/history', methods=['GET'])
def get_ats_history():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 401

    def db_select_history():
        docs = db.collection("resume_ats_scores").where("user_id", "==", uid).stream()
        records = []
        for doc in docs:
            d = doc.to_dict()
            try:
                res_doc = db.collection("resumes").document(d.get("resume_id")).get()
                if res_doc.exists:
                    d["resumes"] = {"filename": res_doc.to_dict().get("filename")}
            except Exception:
                pass
            records.append(d)
        return sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)

    def mock_select_history():
        user_records = [r for r in MOCK_ATS_DB.values() if r.get("user_id") == uid]
        return sorted(user_records, key=lambda x: x.get("created_at", ""), reverse=True)

    try:
        history = handle_db_op(db_select_history, mock_select_history)
        return jsonify({
            "success": True,
            "history": history
        }), 200
    except Exception as e:
        logger.error(f"Failed to retrieve ATS history: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve ATS history."}), 500


@ats_bp.route('/api/ats/latest', methods=['GET'])
def get_latest_ats_score():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 401

    def db_select_latest():
        docs = db.collection("resume_ats_scores").where("user_id", "==", uid).stream()
        records = [doc.to_dict() for doc in docs]
        if not records:
            return None
        sorted_records = sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)
        return sorted_records[0]

    def mock_select_latest():
        user_scores = [s for s in MOCK_ATS_DB.values() if s.get("user_id") == uid]
        if not user_scores:
            return None
        sorted_scores = sorted(user_scores, key=lambda x: x.get("created_at", ""), reverse=True)
        return sorted_scores[0]

    try:
        latest = handle_db_op(db_select_latest, mock_select_latest)
        if not latest:
            return jsonify({"success": True, "data": None, "message": "No ATS score logs found."}), 200
        return jsonify(latest), 200
    except Exception as e:
        logger.error(f"Failed to retrieve latest ATS score: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve ATS score."}), 500
