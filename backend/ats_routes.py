import os
import time
import json
import uuid
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op
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
        try:
            res = supabase_admin.table("resume_ats_scores") \
                .select("*") \
                .eq("resume_id", resume_id) \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            if res.data:
                return res.data[0]
        except Exception:
            pass

        # Fallback query to legacy ats_scores table
        res_legacy = supabase_admin.table("ats_scores") \
            .select("*") \
            .eq("resume_id", resume_id) \
            .eq("user_id", str(user_id)) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        return res_legacy.data[0] if res_legacy.data else None

    def mock_select():
        user_records = [r for r in MOCK_ATS_DB.values() if r.get("resume_id") == resume_id and r.get("user_id") == user_id]
        if user_records:
            sorted_records = sorted(user_records, key=lambda x: x.get("created_at", ""), reverse=True)
            return sorted_records[0]
        return None

    try:
        return handle_supabase_op(db_select, mock_select)
    except Exception as e:
        logger.warning(f"Error checking ATS cache: {e}")
        return None


def fetch_and_verify_resume(resume_id, user_id):
    """
    Retrieves resume from database and verifies ownership.
    Ensures user_id matches authenticated Firebase UID.
    """
    def db_select():
        res = supabase_admin.table("resumes").select("*").eq("id", resume_id).eq("user_id", user_id).execute()
        return res.data[0] if res.data else None

    def mock_select():
        from resume_routes import MOCK_RESUMES_DB
        r = MOCK_RESUMES_DB.get(resume_id)
        if r and r.get("user_id") == user_id:
            return r
        return None

    return handle_supabase_op(db_select, mock_select)


def save_ats_record(resume_id, user_id, scores, ats_results):
    """Saves calculated ATS score and structured Gemini analysis to Supabase DB."""
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
        try:
            ins = supabase_admin.table("resume_ats_scores").insert(record).execute()
            return ins.data[0] if ins.data else record
        except Exception as err:
            err_str = str(err).lower()
            if "relation" in err_str or "does not exist" in err_str or "pgrst205" in err_str:
                logger.warning("resume_ats_scores table not found. Inserting into legacy ats_scores table.")
                legacy_record = {
                    "id": rec_id,
                    "user_id": user_id,
                    "resume_id": resume_id,
                    "overall_score": scores["overall_score"],
                    "keyword_score": scores["keyword_score"],
                    "format_score": scores["formatting_score"],
                    "grammar_score": scores["structure_score"],
                    "experience_score": scores["experience_score"],
                    "recommendations": ats_results.get("overall_recommendations", [])
                }
                legacy_ins = supabase_admin.table("ats_scores").insert(legacy_record).execute()
                return record
            raise err

    def mock_insert():
        MOCK_ATS_DB[rec_id] = record
        return record

    return handle_supabase_op(db_insert, mock_insert)


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

    # Support resume_id from URL path or request body
    data = request.get_json(silent=True) or {}
    if not resume_id:
        resume_id = data.get("resume_id")

    if not resume_id:
        return jsonify({"success": False, "error": "Missing resume_id parameter."}), 400

    # Force re-analysis query parameter check
    force_reanalyze = request.args.get("force", "false").lower() == "true" or data.get("force") is True

    # 1. Verify resume ownership
    try:
        resume_record = fetch_and_verify_resume(resume_id, uid)
    except Exception as db_err:
        logger.error(f"Database error checking resume {resume_id}: {db_err}")
        return jsonify({"success": False, "error": "Database error while fetching resume details."}), 500

    if not resume_record:
        logger.error(f"Resume {resume_id} not found or unauthorized for user {uid}")
        return jsonify({"success": False, "error": "Resume not found or access denied."}), 404

    # 2. Check cached analysis unless force=true
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

    # 3. Retrieve and verify extracted text
    extracted_text = (resume_record.get("extracted_text") or "").strip()
    if not extracted_text:
        logger.warning(f"Resume {resume_id} contains no extracted text content.")
        return jsonify({
            "success": False,
            "error": "Resume text is unavailable for ATS analysis."
        }), 400

    # 4. Run Gemini semantic evaluation
    try:
        ats_results = run_gemini_ats_analysis(extracted_text)
    except Exception as gemini_err:
        logger.error(f"Gemini API invocation failed for resume {resume_id}: {gemini_err}")
        return jsonify({"success": False, "error": "AI analysis is temporarily unavailable. Please try again."}), 502

    # 5. Calculate backend deterministic scores
    scores = calculate_deterministic_ats_scores(ats_results, extracted_text)

    # 6. Save ATS evaluation to Supabase DB
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
    """GET /api/ats/result/<resume_id> — Retrieves ATS analysis for a specific resume."""
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
    """GET /api/ats/history — Retrieves all past ATS evaluations for the logged-in user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 401

    def db_select_history():
        try:
            res = supabase_admin.table("resume_ats_scores") \
                .select("*, resumes(filename)") \
                .eq("user_id", uid) \
                .order("created_at", desc=True) \
                .execute()
            if res.data:
                return res.data
        except Exception:
            pass

        res_legacy = supabase_admin.table("ats_scores") \
            .select("*, resumes(filename)") \
            .eq("user_id", uid) \
            .order("created_at", desc=True) \
            .execute()
        return res_legacy.data or []

    def mock_select_history():
        user_records = [r for r in MOCK_ATS_DB.values() if r.get("user_id") == uid]
        return sorted(user_records, key=lambda x: x.get("created_at", ""), reverse=True)

    try:
        history = handle_supabase_op(db_select_history, mock_select_history)
        return jsonify({
            "success": True,
            "history": history
        }), 200
    except Exception as e:
        logger.error(f"Failed to retrieve ATS history: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve ATS history."}), 500


@ats_bp.route('/api/ats/latest', methods=['GET'])
def get_latest_ats_score():
    """GET /api/ats/latest — Retained for dashboard integration."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 401

    def db_select_latest():
        try:
            res = supabase_admin.table("resume_ats_scores") \
                .select("*") \
                .eq("user_id", uid) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            if res.data:
                return res.data[0]
        except Exception:
            pass

        res_legacy = supabase_admin.table("ats_scores") \
            .select("*") \
            .eq("user_id", uid) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        return res_legacy.data[0] if res_legacy.data else None

    def mock_select_latest():
        user_scores = [s for s in MOCK_ATS_DB.values() if s.get("user_id") == uid]
        if not user_scores:
            return None
        sorted_scores = sorted(user_scores, key=lambda x: x.get("created_at", ""), reverse=True)
        return sorted_scores[0]

    try:
        latest = handle_supabase_op(db_select_latest, mock_select_latest)
        if not latest:
            return jsonify({"success": False, "message": "No ATS score logs found."}), 404
        return jsonify(latest), 200
    except Exception as e:
        logger.error(f"Failed to retrieve latest ATS score: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve ATS score."}), 500
