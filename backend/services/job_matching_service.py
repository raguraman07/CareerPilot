"""
CareerPilot AI — Job Matching & Skill Gap Analysis Service
Performs personalized, evidence-grounded comparison between candidate resume text and target job descriptions.
Intelligently handles short job descriptions by inferring industry expectations while strictly distinguishing
user-provided requirements from AI-inferred recommendations.
"""

import os
import json
import re
import logging
from backend.services.resume_intelligence import call_gemini_with_retry, clean_json_text, deduplicate_list, deduplicate_dict_list

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
    """Returns the qualification match level string based on match_score."""
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
    
    Returns structured JSON matching the comprehensive Career Pilot Job Match schema.
    """
    if not is_gemini_configured or not genai_client:
        raise ValueError("Gemini API key is not configured.")

    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is empty or unreadable.")

    if not job_description or not job_description.strip():
        raise ValueError("Job description or target role details are required.")

    clean_title = job_title.strip() if job_title else "Target Role"
    clean_desc = job_description.strip()
    is_short_desc = len(clean_desc.split()) < 25

    prompt = f"""You are an expert career advisor, technical recruiter, resume evaluator, and skills-gap analyst.

Analyze ONLY the information provided in the candidate's resume and target job information.

CRITICAL INSTRUCTIONS & GROUNDING RULES:
1. Do NOT invent candidate resume experience, projects, or credentials.
2. Separate explicit employer requirements from AI-inferred industry recommendations for the role '{clean_title}'.
3. For short job descriptions (e.g. user interest statements), infer standard industry role expectations for '{clean_title}', but mark them as "recommended_skills" rather than "required by employer".
4. Give practical, evidence-based recommendations suitable for a student or fresh graduate.
5. Recommend certifications ONLY when relevant to the target role level. Clearly label whether required vs recommended.
6. Recommend programming languages, cloud tools, databases, and frameworks ONLY if relevant to the selected role.
7. Return clean structured JSON only.

Target Job Title / Role: {clean_title}
Input Job Description / Goal:
\"\"\"
{clean_desc}
\"\"\"

Candidate Resume Text:
\"\"\"
{resume_text.strip()[:6000]}
\"\"\"

Return ONLY a single valid raw JSON object matching this exact schema:

{{
  "job_title": "{clean_title}",
  "match_score": 72,
  "qualification_level": "Good Match",
  "summary": "2-3 sentence executive summary of candidate readiness for this role.",
  "strengths": ["Candidate strength 1 based on resume", "Candidate strength 2"],
  "matched_skills": ["Skill 1", "Skill 2"],
  "partial_skills": [
    {{
      "skill": "Skill Name",
      "user_has": "What user currently has in resume",
      "gap_explanation": "Why this is a partial match for target role"
    }}
  ],
  "missing_skills": ["Missing Skill 1", "Missing Skill 2"],
  "recommended_skills": ["Inferred Industry Recommended Skill 1"],
  "skill_gap_analysis": [
    {{
      "skill": "Skill Name",
      "category": "Cloud / DevOps / Database / Backend",
      "status": "Missing",
      "priority": "High",
      "why_needed": "Clear explanation of why this skill is needed for this role",
      "what_to_learn": ["Concept 1", "Concept 2"],
      "practice_project": "Hands-on task to build and demonstrate this skill",
      "certification": "Relevant certification name if applicable, or 'Not necessary; practical project preferred'"
    }}
  ],
  "certifications": [
    {{
      "name": "Certification Title",
      "provider": "AWS / Microsoft / GCP / CompTIA",
      "level": "Beginner / Intermediate",
      "priority": "Recommended",
      "reason": "Why useful for candidate level and target role"
    }}
  ],
  "programming_languages": [
    {{
      "name": "Language Name",
      "status": "Strong / Moderate / Missing"
    }}
  ],
  "technologies_to_learn": ["Tech 1", "Tech 2"],
  "experience_gaps": ["Experience gap 1"],
  "project_recommendations": [
    {{
      "title": "Project Title",
      "technologies": ["Tech 1", "Tech 2"],
      "difficulty": "Intermediate",
      "what_to_build": "Specific project build instructions",
      "skills_gained": "Target skills demonstrated",
      "why_improves_employability": "Why this project impresses recruiters"
    }}
  ],
  "improvement_plan": [
    {{
      "priority": 1,
      "action": "Actionable step to take",
      "reason": "Justification for priority"
    }}
  ],
  "final_recommendation": "Encouraging, realistic final advice sentence for candidate."
}}

Constraints:
1. "match_score" MUST be an integer between 0 and 100.
2. "qualification_level" MUST be "Excellent Match", "Good Match", "Moderate Match", or "Needs Improvement".
3. Return ONLY raw valid JSON with no markdown syntax.
"""

    try:
        raw_text = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        cleaned = clean_json_text(raw_text)
        parsed = json.loads(cleaned)
    except Exception as err:
        logger.error(f"Gemini API call failed during job matching analysis: {err}")
        raise RuntimeError(f"AI job matching analysis failed: {err}")

    try:
        raw_score = int(parsed.get("match_score", 0))
        match_score = max(0, min(100, raw_score))
    except (ValueError, TypeError):
        match_score = 70

    parsed["match_score"] = match_score
    parsed["qualification_level"] = str(parsed.get("qualification_level") or get_match_level(match_score)).strip()
    parsed["match_level"] = parsed["qualification_level"]  # Backward compatibility
    parsed["job_title"] = str(parsed.get("job_title") or clean_title).strip()

    # Deduplicate arrays and normalize fields
    parsed["strengths"] = deduplicate_list(parsed.get("strengths") or [])
    parsed["matched_skills"] = deduplicate_list(parsed.get("matched_skills") or parsed.get("matching_skills") or [])
    parsed["matching_skills"] = parsed["matched_skills"]
    
    parsed["partial_skills"] = deduplicate_dict_list(parsed.get("partial_skills") or [], key="skill")
    
    raw_missing = parsed.get("missing_skills") or []
    if raw_missing and isinstance(raw_missing[0], dict):
        parsed["missing_skills"] = deduplicate_dict_list(raw_missing, key="skill")
    else:
        parsed["missing_skills"] = deduplicate_list(raw_missing)

    parsed["recommended_skills"] = deduplicate_list(parsed.get("recommended_skills") or [])
    parsed["skill_gap_analysis"] = deduplicate_dict_list(parsed.get("skill_gap_analysis") or parsed.get("skill_gaps") or [], key="skill")
    parsed["skill_gaps"] = parsed["skill_gap_analysis"]

    parsed["certifications"] = deduplicate_dict_list(parsed.get("certifications") or parsed.get("certification_requirements") or [], key="name")
    parsed["programming_languages"] = deduplicate_dict_list(parsed.get("programming_languages") or [], key="name")
    parsed["technologies_to_learn"] = deduplicate_list(parsed.get("technologies_to_learn") or parsed.get("technology_gaps") or [])
    parsed["experience_gaps"] = deduplicate_list(parsed.get("experience_gaps") or [])
    parsed["project_recommendations"] = deduplicate_dict_list(parsed.get("project_recommendations") or parsed.get("projects_to_build") or [], key="title")
    parsed["improvement_plan"] = deduplicate_dict_list(parsed.get("improvement_plan") or parsed.get("top_5_improvements") or [], key="action")
    parsed["recommendations"] = deduplicate_list(parsed.get("recommendations") or [p.get("action") for p in parsed["improvement_plan"] if isinstance(p, dict)])
    parsed["summary"] = str(parsed.get("summary") or "").strip()
    parsed["final_recommendation"] = str(parsed.get("final_recommendation") or "").strip()

    return parsed
