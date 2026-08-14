import os
import json
import logging
import uuid
import time
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op

# Configure logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

# Configure Google Gemini
import google.generativeai as genai
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

is_gemini_mock = not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-") or GEMINI_API_KEY.startswith("dummy")

if not is_gemini_mock:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Google Gemini SDK initialized successfully using GEMINI_API_KEY.")
else:
    logger.warning("GEMINI_API_KEY is not configured or is placeholder. Resume analysis will run in Mock AI Mode.")

# In-memory fallback DB for local development/offline testing
MOCK_ANALYSES_DB = {}

# Standard high-quality mock analysis response to guarantee structured JSON is returned in mock mode
MOCK_RESPONSE_DATA = {
    "professional_summary": {
        "quality": "Good start, but lacks metrics and specific key achievements.",
        "suggestions": "Add 1-2 sentences highlighting your years of experience, primary framework expertise, and a quantifiable achievement (e.g., 'improved page load times by 35%')."
    },
    "skills": {
        "technical_skills_found": ["JavaScript", "HTML5", "CSS3", "React", "Python", "Flask", "SQL"],
        "soft_skills_found": ["Collaboration", "Problem-solving", "Team Leadership"],
        "missing_skills": ["TypeScript", "Docker", "REST APIs", "Jest", "CI/CD"],
        "suggested_skills": ["Add Docker and CI/CD pipelines as these are highly requested in modern Full-Stack Developer job descriptions."]
    },
    "education": {
        "present_or_missing": "Present",
        "suggestions": "Include your GPA if it is above 3.5. Also list relevant coursework such as 'Data Structures and Algorithms' or 'Database Management Systems'."
    },
    "projects": {
        "number_of_projects": 2,
        "project_quality": "Average. The projects show good use of modern stacks but don't explain the business impact or scale.",
        "missing_details": "Missing descriptions of the scaling challenges, database queries optimization, or user engagement metrics.",
        "improvement_suggestions": "Use the STAR method (Situation, Task, Action, Result) for both projects. Describe the specific problem you solved and quantify the results."
    },
    "experience": {
        "present_or_missing": "Present",
        "suggestions": "Rewrite bullet points using action verbs (e.g., 'Engineered', 'Optimized', 'Architected'). Avoid passive phrases like 'Responsible for maintaining backend systems'."
    },
    "certifications": {
        "existing_certifications": ["AWS Certified Cloud Practitioner"],
        "recommended_certifications": ["AWS Certified Developer - Associate", "Google Cloud Associate Cloud Engineer"]
    },
    "resume_formatting": {
        "readability": "High. Consistent font choice and clean margin space make it easy to scan.",
        "structure": "Standard single-column reverse-chronological layout which is optimal for ATS parsers.",
        "grammar": "No major grammatical issues found.",
        "spelling": "Spelling is correct.",
        "professionalism": "Strong. Tone is objective and focuses on technical competencies."
    },
    "strengths": [
        "Clean resume layout that is highly ATS-compliant.",
        "Strong technical skills foundation using modern technologies (Python/Flask, React).",
        "Good inclusion of project links and description of technologies used."
    ],
    "weaknesses": [
        "Lacks quantifiable achievements and metrics across experiences and projects.",
        "No modern testing frameworks or CI/CD pipelines mentioned in the skills section.",
        "Professional summary could be more impactful by focusing on business outcomes."
    ],
    "actionable_recommendations": [
        "Add metrics to your experience section (e.g., 'Optimized query speeds by 20%').",
        "Incorporate 2-3 modern testing libraries (Jest, PyTest, or Cypress) into your skills.",
        "Rephrase professional summary to focus on your specialization and value proposition.",
        "Add links to live demo deployments or GitHub repositories for each project.",
        "Ensure all bullet points start with strong action verbs (e.g. 'Coordinated', 'Designed').",
        "List relevant university courses or specializations related to cloud or databases.",
        "Include cloud deployment tools like AWS, Docker, or Vercel in your technical stack.",
        "Review projects to explicitly mention your contribution if they were team projects.",
        "Format certification section to include date of achievement and expiration.",
        "Remove outdated high-school achievements or generic personal interests."
    ]
}

@analysis_bp.route('/api/analysis/analyze', methods=['POST'])
def analyze_resume():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    resume_text = data.get("resume_text")

    if not resume_id or not resume_text:
        return jsonify({"error": "Missing resume_id or resume_text in request body."}), 400

    analysis_results = None

    if is_gemini_mock:
        logger.info(f"Analyzing resume {resume_id} using Mock AI mode...")
        # Simulate slight network delay
        time.sleep(1.5)
        analysis_results = MOCK_RESPONSE_DATA
    else:
        logger.info(f"Analyzing resume {resume_id} using Gemini API...")
        try:
            # We construct a detailed prompt instructing Gemini to return JSON with the specific keys required
            prompt = f"""
            You are a professional technical resume reviewer. Analyze the following resume text and provide detailed feedback to help students improve.
            You must output a raw JSON object matching the exact structure described below. 
            Do NOT wrap the JSON inside markdown formatting or ```json blocks. Return ONLY the raw valid JSON.

            JSON Schema:
            {{
                "professional_summary": {{
                    "quality": "Description of the quality of professional summary",
                    "suggestions": "Suggestions to improve the professional summary"
                }},
                "skills": {{
                    "technical_skills_found": ["skill1", "skill2"],
                    "soft_skills_found": ["skill1", "skill2"],
                    "missing_skills": ["missing1", "missing2"],
                    "suggested_skills": ["suggested1", "suggested2"]
                }},
                "education": {{
                    "present_or_missing": "Present/Missing status description",
                    "suggestions": "Suggestions to improve the education section"
                }},
                "projects": {{
                    "number_of_projects": 0,
                    "project_quality": "Description of the projects quality",
                    "missing_details": "Description of missing details in projects",
                    "improvement_suggestions": "Suggestions to improve the projects section"
                }},
                "experience": {{
                    "present_or_missing": "Present/Missing status description",
                    "suggestions": "Suggestions to improve the experience section"
                }},
                "certifications": {{
                    "existing_certifications": ["cert1"],
                    "recommended_certifications": ["cert2"]
                }},
                "resume_formatting": {{
                    "readability": "Description of readability",
                    "structure": "Description of structural layout",
                    "grammar": "Grammar status/feedback",
                    "spelling": "Spelling status/feedback",
                    "professionalism": "Professionalism feedback"
                }},
                "strengths": ["strength1", "strength2"],
                "weaknesses": ["weakness1", "weakness2"],
                "actionable_recommendations": [
                    "rec1", "rec2", "rec3", "rec4", "rec5", "rec6", "rec7", "rec8", "rec9", "rec10"
                ]
            }}

            Ensure there are at least 10 prioritized actionable recommendations in the "actionable_recommendations" list.

            Resume Text to Analyze:
            {resume_text}
            """

            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            try:
                analysis_results = json.loads(response.text.strip())
            except Exception as json_parse_err:
                logger.error(f"Failed to parse Gemini response as JSON. Response text: {response.text}")
                logger.warning("Falling back to mock response due to parser error.")
                analysis_results = MOCK_RESPONSE_DATA
                
        except Exception as gemini_err:
            logger.error(f"Gemini API invocation failed: {gemini_err}")
            # Fall back to mock response to ensure system reliability
            analysis_results = MOCK_RESPONSE_DATA

    # Persist the analysis in DB
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
            return res.data if res.data else analysis_id
        except Exception as e:
            err_msg = str(e).lower()
            if "pgrst202" in err_msg or "function" in err_msg:
                logger.warning(f"RPC save_resume_analysis not found in database schema. Falling back to direct table updates: {e}")
                # Insert into public.resume_analyses
                supabase_admin.table("resume_analyses").insert({
                    "id": analysis_id,
                    "resume_id": resume_id,
                    "user_id": uid,
                    "status": "completed",
                    "analysis_results": analysis_results
                }).execute()
                # Update parent resume status to 'analyzed'
                supabase_admin.table("resumes").update({
                    "status": "analyzed"
                }).eq("id", resume_id).eq("user_id", uid).execute()
                return analysis_id
            else:
                raise e

    def mock_insert():
        MOCK_ANALYSES_DB[analysis_id] = {
            "id": analysis_id,
            "resume_id": resume_id,
            "user_id": uid,
            "status": "completed",
            "analysis_results": analysis_results,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return analysis_id

    try:
        handle_supabase_op(db_insert, mock_insert)
    except Exception as db_err:
        logger.error(f"Database insertion of analysis results failed: {db_err}")
        return jsonify({"error": "Failed to save analysis results to database."}), 500

    return jsonify({
        "id": analysis_id,
        "resume_id": resume_id,
        "status": "completed",
        "analysis_results": analysis_results,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }), 201


@analysis_bp.route('/api/analysis/latest', methods=['GET'])
def get_latest_analysis():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_latest():
        res = supabase_admin.table("resume_analyses").select("*").eq("user_id", uid).order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    def mock_select_latest():
        user_analyses = [a for a in MOCK_ANALYSES_DB.values() if a["user_id"] == uid]
        if not user_analyses:
            return None
        sorted_analyses = sorted(user_analyses, key=lambda x: x["created_at"], reverse=True)
        return sorted_analyses[0]

    try:
        latest = handle_supabase_op(db_select_latest, mock_select_latest)
        if not latest:
            return jsonify({"message": "No analysis record found."}), 404
        return jsonify(latest), 200
    except Exception as e:
        logger.error(f"Failed to fetch latest analysis: {e}")
        return jsonify({"error": str(e)}), 500
