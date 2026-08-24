import logging
import time
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op
from app.blueprints.ai.gemini_service import analyze_resume_text
import app.blueprints.ai.db_service as db_service

logger = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/api/ai/analyze-resume', methods=['POST'])
def analyze_resume():
    """
    POST /api/ai/analyze-resume
    Input: { "resume_id": "<uuid>" }
    Output: { "success": true, "analysis": { ... }, "analysis_results": { ... } }
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        logger.error(f"Authentication failure: {val_err}")
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")

    if not resume_id:
        logger.error("Missing resume_id in request body.")
        return jsonify({"error": "Missing resume_id in request body."}), 400

    logger.info(f"Analysis requested for resume_id {resume_id} by user {uid}")

    # 1. Verify resume ownership & Retrieve extracted text
    def db_select_resume():
        res = supabase_admin.table("resumes").select("extracted_text, filename, user_id").eq("id", resume_id).eq("user_id", uid).execute()
        return res.data[0] if res.data else None

    def mock_select_resume():
        try:
            from resume_routes import MOCK_RESUMES_DB
            r = MOCK_RESUMES_DB.get(resume_id)
            if r and r["user_id"] == uid:
                return {
                    "extracted_text": r.get("extracted_text") or "",
                    "filename": r.get("filename") or "uploaded_resume.pdf",
                    "user_id": uid
                }
        except Exception:
            pass
        return None

    try:
        resume_record = handle_supabase_op(db_select_resume, mock_select_resume)
    except Exception as db_err:
        logger.error(f"Database error while querying resume {resume_id}: {db_err}")
        return jsonify({"error": "Database error while fetching resume details."}), 500

    if not resume_record:
        logger.error(f"Resume {resume_id} not found or unauthorized for user {uid}")
        return jsonify({"error": "Resume not found or access denied."}), 404

    # 2. Check cached analysis
    cached_record = db_service.get_cached_analysis(resume_id, uid)
    if cached_record:
        logger.info(f"Performance: Returning cached analysis results for resume {resume_id}")
        analysis_results = cached_record.get("analysis_results") if isinstance(cached_record, dict) else cached_record
        analysis_payload = {
            "id": cached_record.get("id") if isinstance(cached_record, dict) else "cached-id",
            "resume_id": resume_id,
            "user_id": uid,
            "status": "completed",
            "analysis_results": analysis_results,
            "created_at": cached_record.get("created_at") if isinstance(cached_record, dict) else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return jsonify({
            "success": True,
            "analysis": analysis_payload,
            "analysis_results": analysis_results,
            "resume_id": resume_id,
            "status": "completed",
            "cached": True
        }), 200

    resume_text = resume_record.get("extracted_text") or ""
    if not resume_text.strip():
        logger.error(f"Resume {resume_id} contains no extracted text.")
        return jsonify({"error": "Resume has no extracted text content. Please parse or re-upload your resume."}), 400

    # 3. Call Gemini to perform structured analysis
    try:
        logger.info(f"Gemini API request started for resume_id {resume_id}")
        analysis_results = analyze_resume_text(resume_text)
        logger.info(f"Gemini response received and validated for resume_id {resume_id}")
    except Exception as gemini_err:
        logger.error(f"Gemini API Analysis failed for resume {resume_id}: {gemini_err}")
        return jsonify({
            "success": False,
            "error": "AI resume analysis is temporarily unavailable. Please try again."
        }), 502

    # 4. Save results in database
    try:
        logger.info(f"Database save started for resume_id {resume_id}")
        saved_record = db_service.save_analysis(resume_id, uid, analysis_results)
        logger.info(f"Database save completed successfully for resume_id {resume_id}")
    except Exception as db_save_err:
        logger.error(f"Failed to persist analysis results for resume {resume_id}: {db_save_err}")
        return jsonify({"error": "Failed to save analysis results to database."}), 500

    analysis_payload = {
        "id": saved_record.get("id") if isinstance(saved_record, dict) else str(saved_record),
        "resume_id": resume_id,
        "user_id": uid,
        "status": "completed",
        "analysis_results": analysis_results,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    return jsonify({
        "success": True,
        "analysis": analysis_payload,
        "analysis_results": analysis_results,
        "resume_id": resume_id,
        "status": "completed",
        "cached": False
    }), 201


@ai_bp.route('/api/ai/analysis/<resume_id>', methods=['GET'])
def get_analysis_by_resume(resume_id):
    """
    GET /api/ai/analysis/<resume_id>
    Returns existing analysis for the authenticated user for the specified resume_id.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        logger.error(f"Authentication failure: {val_err}")
        return jsonify({"error": str(val_err)}), 401

    if not resume_id:
        return jsonify({"error": "Missing resume_id path parameter."}), 400

    try:
        analysis_record = db_service.get_analysis_by_resume_id(resume_id, uid)
        if not analysis_record:
            return jsonify({"error": "Analysis not found for this resume."}), 404

        analysis_results = analysis_record.get("analysis_results") if isinstance(analysis_record, dict) else analysis_record
        analysis_payload = {
            "id": analysis_record.get("id") if isinstance(analysis_record, dict) else "id",
            "resume_id": resume_id,
            "user_id": uid,
            "status": "completed",
            "analysis_results": analysis_results,
            "created_at": analysis_record.get("created_at") if isinstance(analysis_record, dict) else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return jsonify({
            "success": True,
            "analysis": analysis_payload,
            "analysis_results": analysis_results
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving analysis for resume {resume_id}: {e}")
        return jsonify({"error": "Failed to retrieve analysis."}), 500


@ai_bp.route('/api/ai/history', methods=['GET'])
def get_analysis_history():
    """
    GET /api/ai/history
    Returns: List of all previous resume analyses for the logged-in user.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        logger.error(f"Authentication failure: {val_err}")
        return jsonify({"error": str(val_err)}), 401

    try:
        history = db_service.get_user_analysis_history(uid)
        return jsonify(history), 200
    except Exception as e:
        logger.error(f"Error fetching analysis history for user {uid}: {e}")
        return jsonify({"error": "Failed to fetch resume analysis history."}), 500
