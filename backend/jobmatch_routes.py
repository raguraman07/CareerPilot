import os
import json
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op
import google.generativeai as genai

logger = logging.getLogger(__name__)

jobmatch_bp = Blueprint('jobmatch', __name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_mock = not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-") or GEMINI_API_KEY.startswith("dummy")

if not is_gemini_mock:
    genai.configure(api_key=GEMINI_API_KEY)

# Mock fallback data for Job Match
MOCK_JOBMATCH_DATA = {
    "match_percentage": 78,
    "missing_skills": ["Docker", "Kubernetes", "CI/CD Pipelines"],
    "matching_skills": ["Python", "Flask", "PostgreSQL", "JavaScript"],
    "recommendations": [
        "Mention containerization experience (Docker) explicitly to align with the infrastructure requirements.",
        "Add a brief description of backend test suites to demonstrate CI/CD familiarity."
    ]
}

# In-memory database fallback for local testing
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
        return jsonify({"error": "Failed to fetch resume details."}), 500

    match_data = None

    if is_gemini_mock or not resume_text:
        match_data = MOCK_JOBMATCH_DATA
    else:
        try:
            prompt = f"""
            You are a technical recruiter and resume matching specialist.
            Compare the candidate's resume text against the target job description.
            Evaluate matching skills, identify missing keywords/skills, compute a match percentage (0-100), and provide helpful tips.
            
            You must return a raw JSON object matching the exact structure below:
            {{
                "match_percentage": 78,
                "missing_skills": ["skill1", "skill2"],
                "matching_skills": ["skill3", "skill4"],
                "recommendations": [
                    "rec1", "rec2"
                ]
            }}
            
            Job Description:
            {job_description}
            
            Resume Text:
            {resume_text}
            """
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            match_data = json.loads(response.text.strip())
        except Exception as e:
            logger.error(f"Gemini Job Match failed: {e}")
            match_data = MOCK_JOBMATCH_DATA

    # Insert into public.job_matches
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

    import uuid as uuid_lib
    import time
    def mock_insert():
        mock_record = dict(record)
        mock_record["id"] = str(uuid_lib.uuid4())
        mock_record["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        MOCK_JOBMATCH_DB[mock_record["id"]] = mock_record
        return mock_record

    try:
        saved_record = handle_supabase_op(db_insert, mock_insert)
        return jsonify(saved_record), 200
    except Exception as db_err:
        logger.error(f"Failed to save job match details: {db_err}")
        return jsonify({"error": "Failed to save job match details to database."}), 500


@jobmatch_bp.route('/api/jobmatch/history', methods=['GET'])
def get_jobmatch_history():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_history():
        res = supabase_admin.table("job_matches").select("*").eq("user_id", uid).order("created_at", desc=True).execute()
        return res.data or []

    def mock_select_history():
        user_matches = [m for m in MOCK_JOBMATCH_DB.values() if m["user_id"] == uid]
        return sorted(user_matches, key=lambda x: x.get("created_at", ""), reverse=True)

    try:
        history = handle_supabase_op(db_select_history, mock_select_history)
        return jsonify(history), 200
    except Exception as e:
        logger.error(f"Failed to retrieve job match history: {e}")
        return jsonify({"error": "Failed to retrieve history."}), 500
