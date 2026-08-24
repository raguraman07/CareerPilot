import os
import json
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op

logger = logging.getLogger(__name__)

interview_bp = Blueprint('interview', __name__)

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

MOCK_INTERVIEW_DB = {}

@interview_bp.route('/api/interview/generate', methods=['POST'])
def generate_questions():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    category = data.get("category", "technical")
    difficulty = data.get("difficulty", "medium")

    if not resume_id:
        return jsonify({"error": "Missing resume_id in request."}), 400

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
        return "Developer resume sample text."

    try:
        resume_text = handle_supabase_op(db_select, mock_select)
    except Exception as db_err:
        logger.error(f"Failed to fetch resume details: {db_err}")
        return jsonify({"error": "Failed to fetch resume details."}), 500

    if not is_gemini_configured or (not genai_client and not genai_legacy_model) or not resume_text:
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    try:
        prompt = f"""
        You are a senior technical interviewer.
        Generate a list of 5 customized interview questions matching difficulty '{difficulty}' and category '{category}' based strictly on the candidate's resume.
        Do not use hardcoded or generic questions. Customize questions dynamically for this resume.
        
        You must return a raw JSON object matching the exact structure below:
        {{
            "questions": [
                {{
                    "id": 1,
                    "question": "Question text here?",
                    "hint": "Hint to guide the candidate",
                    "answer_guideline": "Short description of what key concepts should be mentioned in the answer"
                }}
            ]
        }}
        
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
        interview_data = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Gemini Interview generation failed: {e}")
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    record = {
        "user_id": uid,
        "resume_id": resume_id,
        "category": category,
        "difficulty": difficulty,
        "questions": interview_data.get("questions", [])
    }

    def db_insert():
        res = supabase_admin.table("interview_questions").insert(record).execute()
        return res.data[0] if res.data else record

    def mock_insert():
        q_id = f"interview-{len(MOCK_INTERVIEW_DB) + 1}"
        record["id"] = q_id
        MOCK_INTERVIEW_DB[q_id] = record
        return record

    try:
        saved_record = handle_supabase_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "interview_id": saved_record.get("id"),
            "category": category,
            "difficulty": difficulty,
            "questions": saved_record.get("questions")
        }), 201
    except Exception as save_err:
        logger.error(f"Failed to save interview questions: {save_err}")
        return jsonify({"error": "Failed to save interview questions."}), 500
