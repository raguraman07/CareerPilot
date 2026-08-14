import os
import json
import logging
import re

logger = logging.getLogger(__name__)

# Safely import official Google GenAI SDK (google.genai) and legacy SDK (google.generativeai)
genai_module = None
genai_legacy_module = None

try:
    from google import genai
    from google.genai import types
    genai_module = genai
except ImportError:
    logger.warning("google.genai package not found in Python environment.")

try:
    import google.generativeai as genai_legacy
    genai_legacy_module = genai_legacy
except ImportError:
    logger.warning("google.generativeai package not found in Python environment.")


# Retrieve API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_mock = not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-") or GEMINI_API_KEY.startswith("dummy") or GEMINI_API_KEY == "your_api_key"

genai_client = None
genai_legacy_model = None

if not is_gemini_mock:
    if genai_module is not None:
        try:
            genai_client = genai_module.Client(api_key=GEMINI_API_KEY)
            logger.info("Google GenAI official SDK (google.genai) client initialized successfully.")
        except Exception as client_err:
            logger.warning(f"google.genai client initialization failed: {client_err}.")
    
    if genai_client is None and genai_legacy_module is not None:
        try:
            genai_legacy_module.configure(api_key=GEMINI_API_KEY)
            genai_legacy_model = genai_legacy_module.GenerativeModel("gemini-1.5-flash")
            logger.info("Google GenerativeAI legacy SDK model initialized successfully.")
        except Exception as legacy_err:
            logger.error(f"Failed to configure Google Gemini legacy SDK: {legacy_err}")
            is_gemini_mock = True

    if genai_client is None and genai_legacy_model is None:
        logger.warning("No Google GenAI SDK could be configured with the provided GEMINI_API_KEY. Running in Mock AI Mode.")
        is_gemini_mock = True
else:
    logger.warning("GEMINI_API_KEY is not configured or is placeholder. Resume analysis will run in Mock AI Mode.")


REQUIRED_KEYS = [
    "resume_summary",
    "technical_skills",
    "soft_skills",
    "strengths",
    "weaknesses",
    "missing_skills",
    "improvements",
    "recommended_roles",
    "career_recommendations"
]

MOCK_ANALYSIS_RESULTS = {
    "resume_summary": "Highly motivated and results-oriented Software Engineer with experience building modern web applications. Proficient in Python, Flask, JavaScript, and SQL, with a strong focus on clean architecture, performance optimization, and scalable backend design.",
    "technical_skills": ["Python", "Flask", "JavaScript", "HTML5", "CSS3", "SQL", "Git", "RESTful APIs"],
    "soft_skills": ["Problem-solving", "Collaboration", "Technical Communication", "Adaptability", "Teamwork"],
    "strengths": [
        "Strong foundation in web application development using Python and Flask.",
        "Demonstrated experience with database management and API design.",
        "Clean project organization and structured implementation."
    ],
    "weaknesses": [
        "Lacks representation of automated testing frameworks (e.g. pytest, Jest).",
        "Limited exposure to containerization technologies (e.g. Docker, Kubernetes).",
        "No mention of CI/CD pipeline automation or cloud deployment models (AWS, GCP)."
    ],
    "missing_skills": ["TypeScript", "Docker", "pytest", "Jest", "CI/CD Pipelines", "AWS/GCP Cloud Deployments"],
    "improvements": [
        "Incorporate a dedicated 'Testing' subsection in technical skills and list unit testing libraries like pytest or Jest.",
        "Include cloud deployment tools (e.g., Docker, AWS) in your technical stack to demonstrate modern DevOps readiness.",
        "Rephrase project bullet points using the STAR methodology, focusing on quantifiable metrics (e.g., 'improved query performance by 25%')."
    ],
    "recommended_roles": ["Full-Stack Software Engineer", "Backend Developer", "Junior DevOps Specialist", "Application Developer"],
    "career_recommendations": [
        "Gain hands-on experience with Docker containerization and deploy a project to AWS or GCP to build cloud competency.",
        "Learn TypeScript to complement JavaScript skills and increase eligibility for senior Full-Stack roles.",
        "Contribute to open-source projects or build a portfolio project that implements a full CI/CD deployment pipeline."
    ]
}


def validate_analysis_json(data):
    """Validates if the dictionary contains all 9 required keys and correct types."""
    if not isinstance(data, dict):
        logger.warning("Validation failed: Root data is not a dictionary.")
        return False
    for key in REQUIRED_KEYS:
        if key not in data:
            logger.warning(f"Validation failed: missing required key '{key}'")
            return False
    # Validate resume_summary string
    if not isinstance(data["resume_summary"], str):
        logger.warning("Validation failed: 'resume_summary' is not a string.")
        return False
    # Validate array fields
    for k in REQUIRED_KEYS[1:]:
        if not isinstance(data[k], list):
            logger.warning(f"Validation failed: '{k}' is not a list/array.")
            return False
        # Ensure all elements in lists are strings
        if not all(isinstance(item, str) for item in data[k]):
            logger.warning(f"Validation failed: an element in list '{k}' is not a string.")
            return False
    return True


def clean_json_response(raw_text):
    """Strips markdown formatting, ```json blocks, and leading/trailing whitespace."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    # Remove codeblock wrappers if present
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def analyze_resume_text(resume_text):
    """
    Sends resume text to Google Gemini and returns a validated 9-key JSON dictionary.
    Retries once if response parsing or JSON validation fails.
    """
    global is_gemini_mock
    if is_gemini_mock or (not genai_client and not genai_legacy_model):
        logger.info("Gemini Service: Running in Mock Mode. Returning validated mock analysis results.")
        return MOCK_ANALYSIS_RESULTS

    prompt = f"""
You are an expert professional resume reviewer and career advisor.
Analyze the following resume text carefully.

Evaluate:
- Professional summary
- Education
- Technical skills
- Soft skills
- Projects
- Work experience
- Certifications
- Achievements
- Resume structure
- Resume clarity
- Career relevance
- Missing information
- Potential ATS issues

Do NOT invent information that does not exist in the resume. If information is missing or unavailable, return empty arrays or appropriate descriptions instead of hallucinating.

You MUST return ONLY a raw valid JSON object.
Do NOT return Markdown.
Do NOT return ```json formatting.
Do NOT include explanations outside the JSON.

REQUIRED JSON STRUCTURE:
{{
  "resume_summary": "Short professional summary paragraph",
  "technical_skills": ["Skill 1", "Skill 2"],
  "soft_skills": ["Soft Skill 1", "Soft Skill 2"],
  "strengths": ["Strength 1", "Strength 2"],
  "weaknesses": ["Weakness 1", "Weakness 2"],
  "missing_skills": ["Missing Skill 1", "Missing Skill 2"],
  "improvements": ["Improvement suggestion 1", "Improvement suggestion 2"],
  "recommended_roles": ["Recommended Role 1", "Recommended Role 2"],
  "career_recommendations": ["Career Recommendation 1", "Career Recommendation 2"]
}}

Resume Text:
{resume_text}
"""

    for attempt in range(1, 3):
        logger.info(f"Gemini Service: Requesting analysis from Gemini API (Attempt {attempt}/2)...")
        try:
            raw_response_text = ""
            if genai_client:
                # Official new SDK call
                response = genai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json'
                    }
                )
                raw_response_text = response.text or ""
            elif genai_legacy_model:
                # Legacy SDK call
                response = genai_legacy_model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                raw_response_text = response.text or ""

            cleaned_text = clean_json_response(raw_response_text)
            logger.info("Gemini Service: Received raw response from Gemini API.")

            try:
                parsed_data = json.loads(cleaned_text)
                if validate_analysis_json(parsed_data):
                    logger.info("Gemini Service: Successfully validated Gemini response JSON schema.")
                    return parsed_data
                else:
                    logger.warning(f"Gemini Service: Response validation failed on attempt {attempt}.")
            except json.JSONDecodeError as jde:
                logger.error(f"Gemini Service: JSON decode error on attempt {attempt}: {jde}. Text: {cleaned_text}")

        except Exception as api_err:
            err_str = str(api_err).lower()
            logger.error(f"Gemini Service: API call error on attempt {attempt}: {api_err}")
            if "invalid authentication credentials" in err_str or "401" in err_str or "api_key" in err_str:
                logger.warning("Gemini Service: Invalid API key/credentials detected. Falling back to Mock AI Mode.")
                is_gemini_mock = True
                return MOCK_ANALYSIS_RESULTS

        if attempt == 1:
            logger.info("Gemini Service: Retrying Gemini request (attempt 2 of 2)...")

    # If attempts failed, fall back safely to mock response to ensure app reliability
    logger.warning("Gemini Service: All Gemini API attempts failed validation. Falling back to Mock AI Mode.")
    is_gemini_mock = True
    return MOCK_ANALYSIS_RESULTS
