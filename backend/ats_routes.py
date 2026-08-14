import os
import json
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op
import google.generativeai as genai

logger = logging.getLogger(__name__)

ats_bp = Blueprint('ats', __name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_mock = not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-") or GEMINI_API_KEY.startswith("dummy")

if not is_gemini_mock:
    genai.configure(api_key=GEMINI_API_KEY)

# Mock fallback data for ATS Score
MOCK_ATS_DATA = {
    "overall_score": 85,
    "keyword_score": 80,
    "format_score": 90,
    "grammar_score": 95,
    "experience_score": 75,
    "recommendations": [
        "Include more action verbs in your experience bullet points.",
        "Add key industry keywords matching target descriptions to improve ATS relevance.",
        "Ensure layout uses standard fonts and single column spacing."
    ]
}

# In-memory database fallback for local testing
MOCK_ATS_DB = {}

@ats_bp.route('/api/ats/score', methods=['POST'])
def calculate_ats_score():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")

    if not resume_id:
        return jsonify({"error": "Missing resume_id in request."}), 400

    # Fetch resume text
    def db_select():
        res = supabase_admin.table("resumes").select("extracted_text").eq("id", resume_id).eq("user_id", uid).execute()
        return res.data[0].get("extracted_text") or "" if res.data else ""

    def mock_select():
        from resume_routes import MOCK_RESUMES_DB
        r = MOCK_RESUMES_DB.get(resume_id)
        if r and r["user_id"] == uid:
            return r.get("extracted_text") or ""
        return "Mock Developer Resume details"

    try:
        resume_text = handle_supabase_op(db_select, mock_select)
    except Exception as db_err:
        logger.error(f"Failed to fetch resume details: {db_err}")
        return jsonify({"error": "Failed to fetch resume details from database."}), 500

    ats_data = None

    if is_gemini_mock or not resume_text:
        ats_data = MOCK_ATS_DATA
    else:
        try:
            prompt = f"""
            You are an advanced Application Tracking System (ATS) parser and compliance grader.
            Analyze the following resume text and score it against modern ATS readability benchmarks.
            
            You must return a raw JSON object matching the exact structure below:
            {{
                "overall_score": 85,
                "keyword_score": 80,
                "format_score": 90,
                "grammar_score": 95,
                "experience_score": 75,
                "recommendations": [
                    "rec1", "rec2", "rec3"
                ]
            }}
            Provide at least 3 high-impact recommendations.
            
            Resume Text:
            {resume_text}
            """
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            ats_data = json.loads(response.text.strip())
        except Exception as e:
            logger.error(f"Gemini ATS evaluation failed: {e}")
            ats_data = MOCK_ATS_DATA

    # Insert into public.ats_scores
    record = {
        "user_id": uid,
        "resume_id": resume_id,
        "overall_score": int(ats_data.get("overall_score", 0)),
        "keyword_score": int(ats_data.get("keyword_score", 0)),
        "format_score": int(ats_data.get("format_score", 0)),
        "grammar_score": int(ats_data.get("grammar_score", 0)),
        "experience_score": int(ats_data.get("experience_score", 0)),
        "recommendations": ats_data.get("recommendations", [])
    }

    def db_insert():
        res = supabase_admin.table("ats_scores").insert(record).execute()
        return res.data[0] if res.data else record

    import uuid as uuid_lib
    import time
    def mock_insert():
        mock_record = dict(record)
        mock_record["id"] = str(uuid_lib.uuid4())
        mock_record["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        MOCK_ATS_DB[mock_record["id"]] = mock_record
        return mock_record

    try:
        saved_record = handle_supabase_op(db_insert, mock_insert)
        return jsonify(saved_record), 200
    except Exception as db_err:
        logger.error(f"Failed to save ATS scores: {db_err}")
        return jsonify({"error": "Failed to save ATS scores to database."}), 500


@ats_bp.route('/api/ats/latest', methods=['GET'])
def get_latest_ats_score():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_latest():
        res = supabase_admin.table("ats_scores").select("*").eq("user_id", uid).order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    def mock_select_latest():
        user_scores = [s for s in MOCK_ATS_DB.values() if s["user_id"] == uid]
        if not user_scores:
            return None
        sorted_scores = sorted(user_scores, key=lambda x: x.get("created_at", ""), reverse=True)
        return sorted_scores[0]

    try:
        latest = handle_supabase_op(db_select_latest, mock_select_latest)
        if not latest:
            return jsonify({"message": "No ATS score logs found."}), 404
        return jsonify(latest), 200
    except Exception as e:
        logger.error(f"Failed to retrieve latest ATS score: {e}")
        return jsonify({"error": "Failed to retrieve ATS score."}), 500
