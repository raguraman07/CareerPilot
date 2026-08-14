import os
import json
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op
import google.generativeai as genai

logger = logging.getLogger(__name__)

interview_bp = Blueprint('interview', __name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_mock = not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-") or GEMINI_API_KEY.startswith("dummy")

if not is_gemini_mock:
    genai.configure(api_key=GEMINI_API_KEY)

# Mock fallback data for Interview Questions
MOCK_INTERVIEW_DATA = {
    "questions": [
        {
            "id": 1,
            "question": "Can you describe a challenging backend bug you resolved in Flask?",
            "hint": "Focus on your debugging process, use of logging, and the actual fix.",
            "answer_guideline": "STAR method: Situation (bug description), Task (fixing it), Action (tools used like pdb/logging), Result (performance restore)."
        },
        {
            "id": 2,
            "question": "How do you ensure secure token handling in API endpoints?",
            "hint": "Mention Bearer tokens, HTTP headers, and signature verification.",
            "answer_guideline": "Explain why service role keys are kept secret and how public keys or JWT claims verify user identity on the server side."
        }
    ]
}

# In-memory database fallback for local testing
MOCK_INTERVIEW_DB = {}

@interview_bp.route('/api/interview/generate', methods=['POST'])
def generate_interview_questions():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    difficulty = data.get("difficulty") or "Medium"
    category = data.get("category") or "Technical"

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
        return jsonify({"error": "Failed to fetch resume details."}), 500

    interview_data = None

    if is_gemini_mock or not resume_text:
        interview_data = MOCK_INTERVIEW_DATA
    else:
        try:
            prompt = f"""
            You are a senior technical interviewer.
            Generate a list of 5 customized interview questions matching difficulty '{difficulty}' and category '{category}' based on the candidate's resume.
            
            You must return a raw JSON object matching the exact structure below:
            {{
                "questions": [
                    {{
                        "id": 1,
                        "question": "Question text here?",
                        "hint": "Hint to guide the developer",
                        "answer_guideline": "Short description of what key concepts should be mentioned in the answer"
                    }}
                ]
            }}
            
            Resume Text:
            {resume_text}
            """
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            interview_data = json.loads(response.text.strip())
        except Exception as e:
            logger.error(f"Gemini Interview generation failed: {e}")
            interview_data = MOCK_INTERVIEW_DATA

    # Insert into public.interview_questions
    record = {
        "user_id": uid,
        "resume_id": resume_id,
        "difficulty": difficulty,
        "category": category,
        "questions": interview_data.get("questions", [])
    }

    def db_insert():
        res = supabase_admin.table("interview_questions").insert(record).execute()
        return res.data[0] if res.data else record

    import uuid as uuid_lib
    import time
    def mock_insert():
        mock_record = dict(record)
        mock_record["id"] = str(uuid_lib.uuid4())
        mock_record["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        MOCK_INTERVIEW_DB[mock_record["id"]] = mock_record
        return mock_record

    try:
        saved_record = handle_supabase_op(db_insert, mock_insert)
        return jsonify(saved_record), 200
    except Exception as db_err:
        logger.error(f"Failed to save interview questions: {db_err}")
        return jsonify({"error": "Failed to save interview questions to database."}), 500


@interview_bp.route('/api/interview/history', methods=['GET'])
def get_interview_history():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_history():
        res = supabase_admin.table("interview_questions").select("*").eq("user_id", uid).order("created_at", desc=True).execute()
        return res.data or []

    def mock_select_history():
        user_interviews = [i for i in MOCK_INTERVIEW_DB.values() if i["user_id"] == uid]
        return sorted(user_interviews, key=lambda x: x.get("created_at", ""), reverse=True)

    try:
        history = handle_supabase_op(db_select_history, mock_select_history)
        return jsonify(history), 200
    except Exception as e:
        logger.error(f"Failed to retrieve interview questions history: {e}")
        return jsonify({"error": "Failed to retrieve history."}), 500
