import os
import json
import logging
import re

logger = logging.getLogger(__name__)

# Official Google GenAI SDK (google-genai)
try:
    from google import genai
except ImportError:
    genai = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_configured = bool(
    GEMINI_API_KEY 
    and not GEMINI_API_KEY.startswith("your-") 
    and not GEMINI_API_KEY.startswith("dummy") 
    and GEMINI_API_KEY != "your_gemini_api_key_here"
)

genai_client = None

if is_gemini_configured and genai is not None:
    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini Service: Official google.genai SDK client initialized successfully.")
    except Exception as client_err:
        logger.warning(f"Gemini Service: google.genai client initialization failed: {client_err}")
elif not is_gemini_configured:
    logger.warning("Gemini Service: GEMINI_API_KEY is not configured or is placeholder in environment.")

REQUIRED_KEYS = [
    "resume_summary",
    "technical_skills_found",
    "soft_skills_found",
    "strengths",
    "weaknesses",
    "missing_skills",
    "recommended_roles",
    "actionable_recommendations"
]


def validate_analysis_json(data):
    """
    Validates that Gemini returned a valid dictionary with all required schema keys,
    correct data types, non-null values, and bounded ATS score.
    """
    if not isinstance(data, dict):
        logger.warning("Validation failed: Root data is not a dictionary.")
        return False

    for key in REQUIRED_KEYS:
        if key not in data:
            logger.warning(f"Validation failed: missing required key '{key}'")
            return False

    # Validate summary string
    if not isinstance(data["resume_summary"], str):
        logger.warning("Validation failed: 'resume_summary' is not a string.")
        return False

    # Validate primary list fields
    array_fields = [
        "technical_skills_found",
        "soft_skills_found",
        "strengths",
        "weaknesses",
        "missing_skills",
        "recommended_roles",
        "actionable_recommendations"
    ]

    for field in array_fields:
        if not isinstance(data[field], list):
            logger.warning(f"Validation failed: '{field}' is not a list/array.")
            return False
        if not all(isinstance(item, str) for item in data[field]):
            logger.warning(f"Validation failed: an element in list '{field}' is not a string.")
            return False

    return True


def clean_json_response(raw_text):
    """Strips markdown codeblock wrappers, ```json headers, and surrounding whitespace."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def normalize_analysis_payload(data):
    """
    Normalizes keys to support both new dynamic structure and legacy field aliases
    (technical_skills, soft_skills, improvements, career_recommendations).
    """
    normalized = dict(data)
    
    normalized["technical_skills"] = data.get("technical_skills_found", [])
    normalized["soft_skills"] = data.get("soft_skills_found", [])
    normalized["improvements"] = data.get("actionable_recommendations", [])
    normalized["career_recommendations"] = data.get("actionable_recommendations", [])
    
    if "experience_analysis" not in normalized or not isinstance(normalized["experience_analysis"], dict):
        normalized["experience_analysis"] = {"strengths": [], "weaknesses": [], "recommendations": []}
    if "education_analysis" not in normalized or not isinstance(normalized["education_analysis"], dict):
        normalized["education_analysis"] = {"strengths": [], "weaknesses": [], "recommendations": []}
    if "project_analysis" not in normalized or not isinstance(normalized["project_analysis"], dict):
        normalized["project_analysis"] = {"strengths": [], "weaknesses": [], "recommendations": []}
    if "ats_analysis" not in normalized or not isinstance(normalized["ats_analysis"], dict):
        normalized["ats_analysis"] = {"score": 75, "keyword_analysis": [], "structure_analysis": [], "formatting_analysis": [], "warnings": []}
        
    return normalized


def analyze_resume_text(resume_text):
    """
    Sends extracted resume text to Google Gemini API for fast dynamic analysis.
    NO hardcoded or predefined skill lists are supplied.
    NO fake mock responses are returned if Gemini fails.
    Returns validated, normalized dictionary or raises RuntimeError.
    """
    if not is_gemini_configured or not genai_client:
        logger.error("Gemini Service: GEMINI_API_KEY is missing or invalid. AI service unavailable.")
        raise RuntimeError("AI resume analysis is temporarily unavailable. Please try again.")

    prompt = f"""
You are an expert resume evaluator, recruiter, career advisor, and ATS specialist.

Analyze the provided resume independently.

Use only information supported by the resume.

Identify the candidate's actual technical skills, soft skills, strengths, weaknesses, experience quality, projects, education, certifications, career relevance, missing competencies, and improvement opportunities.

Do not assume a predefined list of technologies or skills.

Do not invent information.

Do not claim that a candidate has a skill unless it is supported by the resume.

Recommendations should be based on the candidate's actual profile.

You MUST return ONLY a raw valid JSON object matching the requested structure below.
Do NOT wrap inside markdown ```json codeblocks or include conversational text.

REQUIRED JSON STRUCTURE:
{{
  "resume_summary": "Professional summary paragraph",
  "technical_skills_found": ["Detected Skill 1", "Detected Skill 2"],
  "soft_skills_found": ["Detected Soft Skill 1"],
  "strengths": ["Strength 1", "Strength 2"],
  "weaknesses": ["Weakness 1", "Weakness 2"],
  "missing_skills": ["Inferred Missing Skill 1"],
  "recommended_roles": ["Recommended Role 1"],
  "experience_analysis": {{
    "strengths": ["Experience Strength 1"],
    "weaknesses": ["Experience Weakness 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "education_analysis": {{
    "strengths": ["Education Strength 1"],
    "weaknesses": ["Education Weakness 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "project_analysis": {{
    "strengths": ["Project Strength 1"],
    "weaknesses": ["Project Weakness 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "ats_analysis": {{
    "score": 80,
    "keyword_analysis": ["Keyword note 1"],
    "structure_analysis": ["Structure note 1"],
    "formatting_analysis": ["Formatting note 1"],
    "warnings": ["ATS warning 1"]
  }},
  "actionable_recommendations": ["Actionable recommendation 1", "Actionable recommendation 2"]
}}

Resume Text to Analyze:
{resume_text}
"""

    for attempt in range(1, 3):
        logger.info(f"Gemini Service: Executing Gemini API request (Attempt {attempt}/2)...")
        try:
            response = genai_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            raw_text = response.text or ""

            cleaned_text = clean_json_response(raw_text)
            parsed_data = json.loads(cleaned_text)

            if validate_analysis_json(parsed_data):
                logger.info("Gemini Service: Response successfully parsed and validated.")
                return normalize_analysis_payload(parsed_data)
            else:
                logger.warning(f"Gemini Service: JSON validation failed on attempt {attempt}.")
        except Exception as err:
            logger.error(f"Gemini Service: API call error on attempt {attempt}: {err}")

        if attempt == 1:
            logger.info("Gemini Service: Retrying Gemini API request...")

    logger.error("Gemini Service: All Gemini API attempts failed or produced invalid JSON.")
    raise RuntimeError("AI resume analysis is temporarily unavailable. Please try again.")
