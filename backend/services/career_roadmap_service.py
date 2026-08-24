import os
import json
import re
import logging
from services.career_context_service import fetch_user_career_data

logger = logging.getLogger(__name__)

# Safely import Google GenAI SDKs (official google.genai and legacy google.generativeai)
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
            logger.info("Career Roadmap Service: Official google.genai client initialized.")
        except Exception as client_err:
            logger.warning(f"Career Roadmap Service: google.genai client initialization failed: {client_err}")
    
    if genai_client is None and genai_legacy_module is not None:
        try:
            genai_legacy_module.configure(api_key=GEMINI_API_KEY)
            genai_legacy_model = genai_legacy_module.GenerativeModel("gemini-3.6-flash")
            logger.info("Career Roadmap Service: Legacy google.generativeai SDK configured.")
        except Exception as legacy_err:
            logger.error(f"Career Roadmap Service: Failed to configure Google Gemini legacy SDK: {legacy_err}")
            is_gemini_configured = False
else:
    logger.warning("Career Roadmap Service: GEMINI_API_KEY is not configured or is placeholder.")


def get_readiness_label(score):
    """Computes readiness label based on numerical score (0-100)."""
    if score >= 90:
        return "Highly Ready"
    elif score >= 75:
        return "Strongly Prepared"
    elif score >= 60:
        return "Developing"
    elif score >= 40:
        return "Needs Improvement"
    else:
        return "Early Stage"


def generate_career_roadmap(uid, career_goal=""):
    """
    Generates a dynamic personalized career roadmap and learning plan
    based on the candidate's actual CareerPilot profile data (resumes, ATS, job matches, skill gaps, interview feedback).
    """
    if not is_gemini_configured or (not genai_client and not genai_legacy_model):
        raise ValueError("Gemini API key is not configured.")

    # 1. Retrieve all user career context
    user_data = fetch_user_career_data(uid)

    resumes = user_data.get("resumes") or []
    job_matches = user_data.get("job_matches") or []
    analyses = user_data.get("analyses") or []
    ats_scores = user_data.get("ats_scores") or []
    interviews = user_data.get("interviews") or []

    # If no goal supplied, attempt to infer target from job matches or resume
    inferred_goal = career_goal.strip()
    if not inferred_goal:
        if job_matches:
            inferred_goal = job_matches[0].get("job_title") or "Software Career"
        else:
            inferred_goal = "Target Professional Role"

    # Construct context blocks
    resume_text = resumes[0].get("extracted_text", "") if resumes else "No uploaded resume."
    
    jm_summary = ""
    if job_matches:
        jm = job_matches[0]
        gaps_list = [f"{g.get('skill')}: {g.get('reason')}" for g in (jm.get("skill_gaps") or []) if isinstance(g, dict)]
        jm_summary = f"Job Match Target: {jm.get('job_title')}\nMatch Score: {jm.get('match_score')}%\nMatching Skills: {', '.join(jm.get('matching_skills') or [])}\nMissing Skills: {', '.join(jm.get('missing_skills') or [])}\nSkill Gaps: {'; '.join(gaps_list)}"

    ats_summary = ""
    if ats_scores:
        ats = ats_scores[0]
        ats_summary = f"ATS Score: {ats.get('ats_score')}/100\nMissing Keywords: {', '.join(ats.get('missing_keywords') or [])}\nWarnings: {', '.join(ats.get('warnings') or [])}"

    interview_summary = ""
    if interviews:
        inv = interviews[0]
        interview_summary = f"Interview Prep Target: {inv.get('job_title')}\nIdentified Weaknesses: {', '.join(inv.get('potential_weaknesses') or [])}"

    prompt = f"""You are an expert career strategist, technical mentor, learning advisor, and hiring specialist.

Create a personalized career roadmap and learning plan for the candidate using the supplied career profile context.

Analyze the candidate's current capabilities, target career direction, job requirements, missing skills, resume weaknesses, ATS feedback, and interview weaknesses.

Prioritize the most important improvements first based on dependencies and impact.

Target Career Goal: {inferred_goal}

CANDIDATE CAREER CONTEXT:

--- RESUME TEXT ---
{resume_text}

--- JOB MATCH & SKILL GAP ANALYSIS ---
{jm_summary if jm_summary else "No job match data recorded."}

--- ATS SCORE ANALYSIS ---
{ats_summary if ats_summary else "No ATS score recorded."}

--- INTERVIEW FEEDBACK ---
{interview_summary if interview_summary else "No interview session recorded."}


Instructions:
1. Do not assume technologies or skills that are not supported by the candidate's target role or job requirements.
2. Recommendations must be justified by the gap between candidate's current profile and target career goal.
3. For learning resources, recommend resource TYPES (e.g. "Official documentation", "Interactive hands-on course", "Practice platform"). Do NOT invent fake URLs or course names.
4. "readiness_score" MUST be an integer between 0 and 100 evaluating candidate's overall readiness for the target role.

Return ONLY a single valid JSON object matching this exact schema:

{{
  "career_goal": "{inferred_goal}",
  "current_profile_summary": "Concise summary of candidate's current state relative to goal.",
  "readiness_score": 75,
  "readiness_label": "Strongly Prepared",
  "current_strengths": ["Strength 1", "Strength 2"],
  "priority_gaps": ["Priority Gap 1", "Priority Gap 2"],
  "roadmap": [
    {{
      "phase": 1,
      "title": "Phase Title",
      "objective": "Clear learning objective",
      "reason": "Why this comes first in the learning sequence",
      "skills_to_develop": ["Skill 1", "Skill 2"],
      "activities": ["Practical activity 1", "Practical activity 2"],
      "project_ideas": ["Specific project idea to build"],
      "success_criteria": ["Measurable success criterion"],
      "status": "not_started"
    }}
  ],
  "recommended_projects": ["Project 1", "Project 2"],
  "interview_preparation": ["Interview focus area 1"],
  "job_readiness_checklist": ["Checklist item 1", "Checklist item 2"],
  "estimated_timeline": "4–6 weeks",
  "final_recommendations": ["Final actionable tip 1"]
}}

Constraints:
1. "roadmap" array MUST contain 3 to 5 logically sequenced phases.
2. Return ONLY raw valid JSON with no markdown syntax.
"""

    raw_text = ""
    try:
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
    except Exception as api_err:
        logger.error(f"Gemini API call failed during career roadmap generation: {api_err}")
        raise RuntimeError("Career roadmap generation is temporarily unavailable. Please try again.")

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
        logger.error(f"Failed to parse Gemini JSON output for career roadmap: {json_err}")
        raise ValueError("Invalid JSON response from Gemini AI.")

    # Validate readiness score and label
    try:
        score = max(0, min(100, int(parsed.get("readiness_score", 60))))
    except (ValueError, TypeError):
        score = 60

    parsed["readiness_score"] = score
    parsed["readiness_label"] = get_readiness_label(score)
    parsed["career_goal"] = str(parsed.get("career_goal") or inferred_goal).strip()
    parsed["current_profile_summary"] = str(parsed.get("current_profile_summary") or "").strip()
    parsed["current_strengths"] = list(parsed.get("current_strengths") or [])
    parsed["priority_gaps"] = list(parsed.get("priority_gaps") or [])
    parsed["recommended_projects"] = list(parsed.get("recommended_projects") or [])
    parsed["interview_preparation"] = list(parsed.get("interview_preparation") or [])
    parsed["job_readiness_checklist"] = list(parsed.get("job_readiness_checklist") or [])
    parsed["estimated_timeline"] = str(parsed.get("estimated_timeline") or "4–8 weeks").strip()
    parsed["final_recommendations"] = list(parsed.get("final_recommendations") or [])

    # Validate roadmap phases
    phases = parsed.get("roadmap") or []
    sanitized_phases = []
    for idx, p in enumerate(phases):
        if isinstance(p, dict):
            sanitized_phases.append({
                "phase": p.get("phase") or (idx + 1),
                "title": str(p.get("title") or f"Phase {idx + 1}").strip(),
                "objective": str(p.get("objective") or "").strip(),
                "reason": str(p.get("reason") or "").strip(),
                "skills_to_develop": list(p.get("skills_to_develop") or []),
                "activities": list(p.get("activities") or []),
                "project_ideas": list(p.get("project_ideas") or []),
                "success_criteria": list(p.get("success_criteria") or []),
                "status": str(p.get("status") or "not_started").strip()
            })

    parsed["roadmap"] = sanitized_phases
    parsed["progress"] = 0

    return parsed
