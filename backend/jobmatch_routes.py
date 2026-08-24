import os
import json
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op

logger = logging.getLogger(__name__)

jobmatch_bp = Blueprint('jobmatch', __name__)

# Safely import Google GenAI SDKs
genai_module = None
genai_legacy_module = None

try:
    from google import genai
    genai_module = genai
except ImportError:
    pass

try:
    import google.generativeai as genai_legacy
    genai_legacy_module = genai_legacy
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_configured = bool(
    GEMINI_API_KEY 
    and not GEMINI_API_KEY.startswith("your-") 
    and not GEMINI_API_KEY.startswith("dummy") 
    and GEMINI_API_KEY != "your_gemini_api_key_here"
)

genai_client = None
genai_legacy_model = None

if is_gemini_configured:
    if genai_module is not None:
        try:
            genai_client = genai_module.Client(api_key=GEMINI_API_KEY)
        except Exception:
            pass
    if genai_client is None and genai_legacy_module is not None:
        try:
            genai_legacy_module.configure(api_key=GEMINI_API_KEY)
            genai_legacy_model = genai_legacy_module.GenerativeModel("gemini-3.6-flash")
        except Exception:
            is_gemini_configured = False

MOCK_JOBMATCH_DB = {}

@jobmatch_bp.route('/api/jobmatch/match', methods=['POST'])
def run_job_match():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    job_description = data.get("job_description")

    if not resume_id or not job_description:
        return jsonify({"error": "Missing resume_id or job_description in request."}), 400

    def db_select():
        res = supabase_admin.table("resumes").select("extracted_text").eq("id", resume_id).eq("user_id", uid).execute()
        if res.data:
            return res.data[0].get("extracted_text") or ""
        return ""

    def mock_select():
        from resume_routes import MOCK_RESUMES_DB
        r = MOCK_RESUMES_DB.get(resume_id)
        if r and r["user_id"] == uid:
            return r.get("extracted_text") or ""
        return "Developer Resume text sample."

    try:
        resume_text = handle_supabase_op(db_select, mock_select)
    except Exception as db_err:
        logger.error(f"Failed to fetch resume details: {db_err}")
        return jsonify({"error": "Failed to fetch resume details."}), 500

    if not is_gemini_configured or (not genai_client and not genai_legacy_model) or not resume_text:
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    try:
        prompt = f"""
        You are a technical recruiter and resume matching specialist.
        Compare the candidate's resume text against the target job description.
        Evaluate matching skills, identify missing keywords/skills, compute a match percentage (0-100), and provide helpful tips.
        
        Do not use predefined lists of skills. Extract skills dynamically from the provided text.
        
        You must return a raw JSON object matching the exact structure below:
        {{
            "match_percentage": 78,
            "missing_skills": ["missing1", "missing2"],
            "matching_skills": ["matching1", "matching2"],
            "recommendations": [
                "rec1", "rec2"
            ]
        }}
        
        Job Description:
        {job_description}
        
        Resume Text:
        {resume_text}
        """
        raw_text = ""
        if genai_client:
            resp = genai_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            raw_text = resp.text or ""
        elif genai_legacy_model:
            resp = genai_legacy_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            raw_text = resp.text or ""

        cleaned = raw_text.strip().replace("```json", "").replace("```", "").strip()
        match_data = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Gemini Job Match failed: {e}")
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    record = {
        "user_id": uid,
        "resume_id": resume_id,
        "job_description": job_description,
        "match_percentage": int(match_data.get("match_percentage", 0)),
        "missing_skills": match_data.get("missing_skills", []),
        "matching_skills": match_data.get("matching_skills", []),
        "recommendations": match_data.get("recommendations", [])
    }

    def db_insert():
        res = supabase_admin.table("job_matches").insert(record).execute()
        return res.data[0] if res.data else record

    def mock_insert():
        match_id = f"match-{len(MOCK_JOBMATCH_DB) + 1}"
        record["id"] = match_id
        MOCK_JOBMATCH_DB[match_id] = record
        return record

    try:
        saved_record = handle_supabase_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "match_id": saved_record.get("id"),
            "match_percentage": saved_record.get("match_percentage"),
            "missing_skills": saved_record.get("missing_skills"),
            "matching_skills": saved_record.get("matching_skills"),
            "recommendations": saved_record.get("recommendations")
        }), 201
    except Exception as save_err:
        logger.error(f"Failed to save job match results: {save_err}")
        return jsonify({"error": "Failed to save job match results."}), 500
