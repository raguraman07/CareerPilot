import os
import json
import logging
import uuid
import time
import re
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op

# Configure logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

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
            logger.info("analysis_routes: Official google.genai client initialized.")
        except Exception as e:
            logger.warning(f"analysis_routes: official genai client init failed: {e}")

    if genai_client is None and genai_legacy_module is not None:
        try:
            genai_legacy_module.configure(api_key=GEMINI_API_KEY)
            genai_legacy_model = genai_legacy_module.GenerativeModel("gemini-3.6-flash")
            logger.info("analysis_routes: Legacy google.generativeai model initialized.")
        except Exception as e:
            logger.error(f"analysis_routes: Legacy model init failed: {e}")
            is_gemini_configured = False
else:
    logger.warning("analysis_routes: GEMINI_API_KEY is missing or placeholder.")

# In-memory fallback DB for local development/offline database operations
MOCK_ANALYSES_DB = {}


def clean_json(text):
    """Strips markdown codeblock markers."""
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()


@analysis_bp.route('/api/analysis/analyze', methods=['POST'])
def analyze_resume():
    """
    POST /api/analysis/analyze
    Generates 100% dynamic resume feedback using Google Gemini based strictly on actual resume content.
    Returns 502 Error if Gemini API is unavailable or fails.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    resume_text = data.get("resume_text")

    if not resume_id or not resume_text or not resume_text.strip():
        return jsonify({"error": "Missing resume_id or resume_text in request body."}), 400

    if not is_gemini_configured or (not genai_client and not genai_legacy_model):
        logger.error("Gemini API key is unconfigured or invalid. Returning AI service error.")
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    prompt = f"""
You are an expert resume evaluator, recruiter, career advisor, and ATS specialist.

Analyze the provided resume independently.

Identify information that is actually present in the resume.

Infer strengths, weaknesses, technical skills, soft skills, experience quality, career relevance, missing competencies, and improvement opportunities based on the resume content.

Do not assume that a particular technology, programming language, framework, certification, or job role is relevant.

Do not use a predefined list of technologies or skills.

Do not invent information.

Only make recommendations that are reasonably supported by the candidate's resume and career context.

If a skill or technology is not present in the resume, do not claim that the candidate has it.

You MUST return ONLY a raw valid JSON object matching the exact structure below.
Do NOT wrap the JSON inside markdown formatting or ```json blocks.

JSON Schema:
{{
    "professional_summary": {{
        "quality": "Assessment of professional summary quality",
        "suggestions": "Suggestions to improve professional summary"
    }},
    "skills": {{
        "technical_skills_found": ["Detected Skill 1", "Detected Skill 2"],
        "soft_skills_found": ["Detected Soft Skill 1"],
        "missing_skills": ["Inferred missing competency 1"],
        "suggested_skills": ["Suggested skill recommendation 1"]
    }},
    "education": {{
        "present_or_missing": "Present or Missing status",
        "suggestions": "Education section feedback"
    }},
    "projects": {{
        "number_of_projects": 0,
        "project_quality": "Assessment of project details and technical depth",
        "missing_details": "Missing details in projects",
        "improvement_suggestions": "Suggestions to improve project section"
    }},
    "experience": {{
        "present_or_missing": "Present or Missing status",
        "suggestions": "Experience bullet points feedback"
    }},
    "certifications": {{
        "existing_certifications": ["Existing Cert 1"],
        "recommended_certifications": ["Recommended Cert 1"]
    }},
    "resume_formatting": {{
        "readability": "Readability assessment",
        "structure": "Structural layout assessment",
        "grammar": "Grammar feedback",
        "spelling": "Spelling feedback",
        "professionalism": "Overall professionalism rating"
    }},
    "strengths": ["Strength 1", "Strength 2"],
    "weaknesses": ["Weakness 1", "Weakness 2"],
    "actionable_recommendations": [
        "Actionable recommendation 1", "Actionable recommendation 2"
    ]
}}

Resume Text to Analyze:
{resume_text}
"""

    analysis_results = None

    try:
        logger.info(f"Analyzing resume {resume_id} using dynamic Gemini API...")
        raw_text = ""
        if genai_client:
            response = genai_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            raw_text = response.text or ""
        elif genai_legacy_model:
            response = genai_legacy_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            raw_text = response.text or ""

        cleaned = clean_json(raw_text)
        analysis_results = json.loads(cleaned)
        
        if not isinstance(analysis_results, dict):
            raise ValueError("Gemini returned non-dictionary JSON.")
    except Exception as gemini_err:
        logger.error(f"Gemini API invocation or JSON parsing failed: {gemini_err}")
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    # Persist the dynamic analysis in DB
    analysis_id = str(uuid.uuid4())
    
    def db_insert():
        logger.info(f"Calling transactional save_resume_analysis RPC for resume_id {resume_id}")
        try:
            res = supabase_admin.rpc("save_resume_analysis", {
                "p_resume_id": resume_id,
                "p_user_id": uid,
                "p_status": "completed",
                "p_analysis_results": analysis_results
            }).execute()
            if res.data:
                return res.data[0] if isinstance(res.data, list) else res.data
        except Exception as rpc_err:
            logger.warning(f"RPC save_resume_analysis failed ({rpc_err}). Falling back to direct table insert.")

        ins = supabase_admin.table("resume_analyses").insert({
            "id": analysis_id,
            "resume_id": resume_id,
            "user_id": uid,
            "status": "completed",
            "analysis_results": analysis_results
        }).execute()
        
        supabase_admin.table("resumes").update({"status": "analyzed"}).eq("id", resume_id).execute()
        return ins.data[0] if ins.data else {"id": analysis_id}

    def mock_insert():
        mock_rec = {
            "id": analysis_id,
            "resume_id": resume_id,
            "user_id": uid,
            "status": "completed",
            "analysis_results": analysis_results,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        MOCK_ANALYSES_DB[analysis_id] = mock_rec
        return mock_rec

    try:
        saved_record = handle_supabase_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "analysis_id": saved_record.get("id") if isinstance(saved_record, dict) else analysis_id,
            "resume_id": resume_id,
            "status": "completed",
            "analysis_results": analysis_results
        }), 201
    except Exception as db_err:
        logger.error(f"Failed to save dynamic analysis to database: {db_err}")
        return jsonify({"error": "Failed to save analysis to database."}), 500


@analysis_bp.route('/api/analysis/latest', methods=['GET'])
def get_latest_analysis():
    """
    GET /api/analysis/latest
    Retrieves the most recent resume analysis for the authenticated user.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_latest():
        res = supabase_admin.table("resume_analyses") \
            .select("*, resumes(filename)") \
            .eq("user_id", uid) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None

    def mock_select_latest():
        user_records = [r for r in MOCK_ANALYSES_DB.values() if r.get("user_id") == uid]
        if not user_records:
            return None
        sorted_records = sorted(user_records, key=lambda x: x.get("created_at", ""), reverse=True)
        return sorted_records[0]

    try:
        latest = handle_supabase_op(db_select_latest, mock_select_latest)
        if not latest:
            return jsonify({"message": "No resume analysis records found."}), 404
        return jsonify(latest), 200
    except Exception as e:
        logger.error(f"Failed to retrieve latest analysis: {e}")
        return jsonify({"error": "Failed to retrieve analysis."}), 500
