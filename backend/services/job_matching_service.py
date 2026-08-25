"""
CareerPilot AI — Job Matching & Skill Gap Analysis Service
Performs personalized, evidence-grounded comparison between candidate resume text and target job descriptions.
Produces structured career gap report, technology gaps, certification recommendations, project ideas,
prioritized top 5 improvements, and an ordered learning plan.
"""

import os
import json
import re
import logging
from backend.services.resume_intelligence import deduplicate_list, deduplicate_dict_list

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
    against target job description using Google Gemini API.
    
    Returns structured JSON matching the detailed Career Gap Report schema.
    """
    if not is_gemini_configured or not genai_client:
        raise ValueError("Gemini API key is not configured.")

    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is empty.")

    if not job_description or not job_description.strip():
        raise ValueError("Job description is required for job matching & skill gap analysis.")

    prompt = f"""You are an expert technical recruiter, career advisor, resume evaluator, and job-matching specialist.

Analyze the candidate's resume against the supplied target job description.

CRITICAL GROUNDING & HALLUCINATION RULES:
1. Compare ONLY the supplied resume text against the supplied job description.
2. Identify skills, technologies, experience, and tools present in the resume vs required by the job.
3. Do NOT invent candidate skills, projects, experience, or certifications not in the resume.
4. Do NOT mark a certification as "required_by_job: true" unless explicitly required by the job text.
5. Explain skill gaps in clear, simple language (What is missing, Why it matters, What to learn, How to practice).
6. Prioritize gaps using HIGH (explicit job requirement), MEDIUM (strongly useful), LOW (nice-to-have).

Target Job Title: {job_title if job_title else "Target Role"}

Target Job Description:
\"\"\"
{job_description.strip()}
\"\"\"

Candidate Resume Text:
\"\"\"
{resume_text.strip()}
\"\"\"

Return ONLY a single valid JSON object matching this exact schema:

{{
  "job_title": "{job_title if job_title else "Target Role"}",
  "match_score": 78,
  "match_level": "Strong Match",
  "matched_skills": ["Skill 1", "Skill 2"],
  "partial_matches": [
    {{
      "skill": "Skill Name",
      "user_has": "What candidate currently has in resume",
      "gap_explanation": "Why this is a partial fit vs job requirement"
    }}
  ],
  "missing_skills": [
    {{
      "skill": "Missing Skill Name",
      "priority": "HIGH",
      "reason": "Detailed explanation why this skill is missing and why it matters for the target job.",
      "what_to_learn": ["Concept 1", "Concept 2"],
      "practical_task": "Actionable task or project to practice this skill",
      "certification": null
    }}
  ],
  "experience_gaps": ["Experience gap detail 1"],
  "education_gaps": ["Education gap detail 1 or 'None'"],
  "certification_requirements": [
    {{
      "name": "Certification Name",
      "provider": "Provider Name (e.g. AWS, Microsoft)",
      "relevance": "Why relevant",
      "priority": "HIGH",
      "reason": "Clear justification",
      "required_by_job": false
    }}
  ],
  "technology_gaps": ["Tech 1", "Tech 2"],
  "projects_to_build": [
    {{
      "title": "Project Title",
      "description": "How building this project solves a skill gap",
      "target_skill": "Target Skill"
    }}
  ],
  "top_5_improvements": [
    {{
      "rank": 1,
      "item": "Improvement Item",
      "priority": "HIGH",
      "reason": "Why this is top priority"
    }}
  ],
  "recommended_learning_order": [
    {{
      "step": 1,
      "title": "Prerequisite / Core",
      "focus": "Topic to master first"
    }}
  ],
  "recommendations": ["Actionable tip 1", "Actionable tip 2"],
  "summary": "2-3 sentence overview of candidate match and career gap findings."
}}

Constraints:
1. "match_score" MUST be an integer between 0 and 100.
2. "match_level" MUST correspond to score thresholds.
3. Return ONLY raw valid JSON with no markdown block wrappers.
"""

    from backend.services.resume_intelligence import call_gemini_with_retry, clean_json_text

    raw_text = ""
    try:
        raw_text = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
    except Exception as api_err:
        logger.error(f"Gemini API call failed during job matching analysis: {api_err}")
        raise RuntimeError("AI analysis is temporarily unavailable. Please try again.")

    if not raw_text or not raw_text.strip():
        raise RuntimeError("Empty response from Gemini AI.")

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse Gemini JSON output for job matching: {json_err}")
        raise ValueError("Invalid JSON response from Gemini AI.")

    try:
        raw_score = int(parsed.get("match_score", 0))
        match_score = max(0, min(100, raw_score))
    except (ValueError, TypeError):
        match_score = 50

    parsed["match_score"] = match_score
    parsed["match_level"] = get_match_level(match_score)
    parsed["job_title"] = str(parsed.get("job_title") or job_title or "Target Role").strip()

    # Deduplicate and format arrays (support both string elements and dict elements)
    raw_matched = parsed.get("matched_skills") or parsed.get("matching_skills") or []
    if raw_matched and isinstance(raw_matched[0], dict):
        parsed["matched_skills"] = deduplicate_dict_list(raw_matched, key="skill")
    else:
        parsed["matched_skills"] = deduplicate_list(raw_matched)
    parsed["matching_skills"] = parsed["matched_skills"]  # Alias for backward compatibility
    
    parsed["partial_matches"] = deduplicate_dict_list(parsed.get("partial_matches") or [], key="skill")
    
    raw_missing = parsed.get("missing_skills") or parsed.get("skill_gaps") or []
    if raw_missing and isinstance(raw_missing[0], dict):
        parsed["missing_skills"] = deduplicate_dict_list(raw_missing, key="skill")
    else:
        parsed["missing_skills"] = deduplicate_list(raw_missing)
    parsed["skill_gaps"] = parsed["missing_skills"]  # Alias for backward compatibility

    parsed["experience_gaps"] = deduplicate_list(parsed.get("experience_gaps") or [])
    parsed["education_gaps"] = deduplicate_list(parsed.get("education_gaps") or [])
    parsed["certification_requirements"] = deduplicate_dict_list(parsed.get("certification_requirements") or [], key="name")
    parsed["technology_gaps"] = deduplicate_list(parsed.get("technology_gaps") or [])
    parsed["projects_to_build"] = deduplicate_dict_list(parsed.get("projects_to_build") or [], key="title")
    parsed["top_5_improvements"] = deduplicate_dict_list(parsed.get("top_5_improvements") or [], key="item")
    parsed["recommended_learning_order"] = deduplicate_dict_list(parsed.get("recommended_learning_order") or [], key="title")
    parsed["recommendations"] = deduplicate_list(parsed.get("recommendations") or [])
    parsed["summary"] = str(parsed.get("summary") or "").strip()

    return parsed
