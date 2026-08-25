import os
import json
import re
import logging

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
        logger.info("Job Matching Service: Official google.genai client initialized.")
    except Exception as client_err:
        logger.warning(f"Job Matching Service: google.genai client initialization failed: {client_err}")
elif not is_gemini_configured:
    logger.warning("Job Matching Service: GEMINI_API_KEY is not configured or is placeholder.")


def get_match_level(score):
    """Returns the score interpretation level string based on match_score."""
    if score >= 90:
        return "Excellent Match"
    elif score >= 75:
        return "Strong Match"
    elif score >= 60:
        return "Moderate Match"
    elif score >= 40:
        return "Low Match"
    else:
        return "Poor Match"


def analyze_job_match(resume_text, job_description, job_title=""):
    """
    Performs dynamic AI job matching & skill gap analysis comparing candidate resume text
    against the target job description using Google Gemini API.
    
    Returns structured JSON matching the specified schema or raises an exception.
    """
    if not is_gemini_configured or (not genai_client and not genai_legacy_model):
        raise ValueError("Gemini API key is not configured.")

    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is empty.")

    if not job_description or not job_description.strip():
        raise ValueError("Job description is empty.")

    prompt = f"""You are an expert technical recruiter, career advisor, resume evaluator, and job-matching specialist.

Analyze the candidate's resume against the supplied job description.

Use ONLY the information contained in the resume and job description.

Identify the skills, technologies, qualifications, experience, projects, and competencies that are actually present or explicitly required.

Do not use a predefined list of technologies.
Do not assume that any particular programming language, framework, tool, certification, or technology is required unless stated in the job description.
Do not invent candidate experience.
Do not claim that the candidate has a skill unless supported by the resume.

Target Job Title: {job_title if job_title else "Not specified"}

Target Job Description:
\"\"\"
{job_description.strip()}
\"\"\"

Candidate Resume Text:
\"\"\"
{resume_text.strip()}
\"\"\"

Determine the job match based on the actual relationship between the resume and the job description.

Return ONLY a single valid JSON object matching this exact schema:

{{
  "job_title": "{job_title if job_title else ""}",
  "match_score": 82,
  "match_level": "Strong Match",
  "matching_skills": ["Skill1", "Skill2"],
  "missing_skills": ["Skill3", "Skill4"],
  "experience_match": {{
    "score": 80,
    "strengths": ["Relevant experience detail 1"],
    "gaps": ["Missing experience detail 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "education_match": {{
    "score": 85,
    "strengths": ["Education strength 1"],
    "gaps": ["Education gap 1"]
  }},
  "qualification_match": {{
    "score": 80,
    "strengths": ["Qualification strength 1"],
    "gaps": ["Qualification gap 1"]
  }},
  "candidate_strengths": ["Candidate strength 1", "Candidate strength 2"],
  "candidate_weaknesses": ["Candidate weakness 1"],
  "skill_gaps": [
    {{
      "skill": "Name of missing or weak skill",
      "importance": "High",
      "reason": "Why this skill is critical for the job",
      "recommendation": "Actionable step to acquire or highlight this skill"
    }}
  ],
  "recommendations": ["Personalized recommendation 1", "Personalized recommendation 2"],
  "summary": "Comprehensive 2-3 sentence summary of candidate fit."
}}

Constraints:
1. "match_score" MUST be an integer between 0 and 100.
2. "match_level" MUST correspond to:
   - 90-100: "Excellent Match"
   - 75-89: "Strong Match"
   - 60-74: "Moderate Match"
   - 40-59: "Low Match"
   - 0-39: "Poor Match"
3. Extract all skills dynamically from the provided text. Do not invent skills.
4. Return ONLY valid raw JSON with no markdown block wrappers if possible.
"""

    raw_text = ""
    try:
        response = genai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        raw_text = response.text or ""
    except Exception as api_err:
        logger.error(f"Gemini API call failed during job matching analysis: {api_err}")
        raise RuntimeError("AI analysis is temporarily unavailable. Please try again.")

    if not raw_text or not raw_text.strip():
        raise RuntimeError("Empty response from Gemini AI.")

    # Clean markdown formatting if present
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse Gemini JSON output for job matching: {json_err}. Raw output:\n{cleaned}")
        raise ValueError("Invalid JSON response from Gemini AI.")

    # Validate and sanitize match_score
    try:
        raw_score = int(parsed.get("match_score", 0))
        match_score = max(0, min(100, raw_score))
    except (ValueError, TypeError):
        match_score = 50

    parsed["match_score"] = match_score
    parsed["match_level"] = get_match_level(match_score)

    # Ensure required arrays and objects exist
    parsed["job_title"] = str(parsed.get("job_title") or job_title or "").strip()
    parsed["matching_skills"] = list(parsed.get("matching_skills") or [])
    parsed["missing_skills"] = list(parsed.get("missing_skills") or [])

    if not isinstance(parsed.get("experience_match"), dict):
        parsed["experience_match"] = {"score": match_score, "strengths": [], "gaps": [], "recommendations": []}
    else:
        exp = parsed["experience_match"]
        exp["score"] = max(0, min(100, int(exp.get("score", match_score))))
        exp["strengths"] = list(exp.get("strengths") or [])
        exp["gaps"] = list(exp.get("gaps") or [])
        exp["recommendations"] = list(exp.get("recommendations") or [])

    if not isinstance(parsed.get("education_match"), dict):
        parsed["education_match"] = {"score": match_score, "strengths": [], "gaps": []}
    else:
        edu = parsed["education_match"]
        edu["score"] = max(0, min(100, int(edu.get("score", match_score))))
        edu["strengths"] = list(edu.get("strengths") or [])
        edu["gaps"] = list(edu.get("gaps") or [])

    if not isinstance(parsed.get("qualification_match"), dict):
        parsed["qualification_match"] = {"score": match_score, "strengths": [], "gaps": []}
    else:
        qual = parsed["qualification_match"]
        qual["score"] = max(0, min(100, int(qual.get("score", match_score))))
        qual["strengths"] = list(qual.get("strengths") or [])
        qual["gaps"] = list(qual.get("gaps") or [])

    parsed["candidate_strengths"] = list(parsed.get("candidate_strengths") or [])
    parsed["candidate_weaknesses"] = list(parsed.get("candidate_weaknesses") or [])
    parsed["skill_gaps"] = list(parsed.get("skill_gaps") or [])
    parsed["recommendations"] = list(parsed.get("recommendations") or [])
    parsed["summary"] = str(parsed.get("summary") or "").strip()

    return parsed
