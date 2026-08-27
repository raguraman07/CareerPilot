import os
import json
import re
import logging
try:
    from backend.services.career_context_service import fetch_user_career_data
except ImportError:
    from services.career_context_service import fetch_user_career_data

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

# Ensure environment variables are loaded from backend/.env or root .env
_backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)
else:
    load_dotenv()

from services.resume_intelligence import call_gemini_with_retry, clean_json_text

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
        logger.info("Career Roadmap Service: Official google.genai client initialized.")
    except Exception as client_err:
        logger.warning(f"Career Roadmap Service: google.genai client initialization failed: {client_err}")
elif not is_gemini_configured:
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
    based on the candidate's actual CareerPilot profile data (Career Goal, Profile, Resumes, ATS, Job Matches, Skill Gaps, Interview Feedback).
    """
    if not is_gemini_configured or not genai_client:
        raise ValueError("Gemini API key is not configured.")

    # 1. Retrieve all user career context
    user_data = fetch_user_career_data(uid)

    goal_obj = user_data.get("career_goal") or {}
    profile_obj = user_data.get("profile") or {}
    resumes = user_data.get("resumes") or []
    job_matches = user_data.get("job_matches") or []
    analyses = user_data.get("analyses") or []
    ats_scores = user_data.get("ats_scores") or []
    interviews = user_data.get("interviews") or []

    # Target company and role determination
    target_company = (goal_obj.get("company_name") or "").strip()
    target_role = (goal_obj.get("job_role") or "").strip()

    if not target_role:
        if career_goal and career_goal.strip():
            target_role = career_goal.strip()
        elif job_matches:
            target_role = job_matches[0].get("job_title") or "Software Engineer"
        else:
            target_role = "Software Engineer"

    if not target_company:
        target_company = "Target Tech Company"

    # Profile & Education Details
    edu = profile_obj.get("education") or {}
    edu_text = f"Education: {edu.get('highest_education', '')} in {edu.get('specialization', '')} from {edu.get('institution', '')}" if edu else "Education: Not specified"

    skills_dict = profile_obj.get("skills") or {}
    curr_prog_langs = skills_dict.get("programming_languages") or []
    curr_tech_skills = skills_dict.get("technical_skills") or []
    curr_tools = skills_dict.get("tools_and_technologies") or []
    curr_soft_skills = skills_dict.get("soft_skills") or []
    
    # Existing Certifications & Projects
    curr_certs = [c.get("name") for c in (profile_obj.get("certifications") or []) if isinstance(c, dict) and c.get("name")]
    curr_projects = [p.get("title") for p in (profile_obj.get("projects") or []) if isinstance(p, dict) and p.get("title")]

    # Resume & Analysis Data
    resume_text = resumes[0].get("extracted_text", "") if resumes else "No uploaded resume."
    
    analysis_skills = []
    missing_analysis_skills = []
    if analyses:
        analysis_skills = analyses[0].get("technical_skills") or []
        missing_analysis_skills = analyses[0].get("missing_skills") or []

    # Job Match & Skill Gaps
    jm_summary = ""
    jm_missing_skills = []
    if job_matches:
        jm = job_matches[0]
        jm_missing_skills = jm.get("missing_skills") or []
        gaps_list = [f"{g.get('skill')}: {g.get('reason')}" for g in (jm.get("skill_gaps") or []) if isinstance(g, dict)]
        jm_summary = f"Job Match Role: {jm.get('job_title')}\nMatching: {', '.join(jm.get('matching_skills') or [])}\nMissing: {', '.join(jm_missing_skills)}\nSkill Gaps: {'; '.join(gaps_list)}"

    ats_summary = ""
    if ats_scores:
        ats = ats_scores[0]
        ats_summary = f"ATS Score: {ats.get('ats_score')}/100\nMissing Keywords: {', '.join(ats.get('missing_keywords') or [])}"

    interview_summary = ""
    if interviews:
        inv = interviews[0]
        interview_summary = f"Interview Prep Target: {inv.get('job_title')}\nIdentified Weaknesses: {', '.join(inv.get('potential_weaknesses') or [])}"

    prompt = f"""You are an expert career development and technical recruitment advisor for CareerPilot AI.

Create a realistic, personalized, and actionable career preparation roadmap for this specific user.
The objective is to help the user become genuinely prepared for the selected job role and company.

Do not provide generic career advice.
Analyze the user's current skills against the expected requirements of the target role and company.
Identify the most important missing skills and skill gaps.
Prioritize skills based on job relevance.
Recommend only technologies, subjects, certifications, and projects that meaningfully improve the user's readiness.

Do not invent certifications, companies, technologies, requirements or URLs.
If reliable certification information cannot be established, return an empty string for the certification URL rather than fabricating one.
The roadmap must be practical and achievable for the user's current level.

USER CAREER PROFILE:
- Target Company: {target_company}
- Target Job Role: {target_role}
- {edu_text}
- Current Verified Skills & Programming Languages: {', '.join(curr_prog_langs + curr_tech_skills) if (curr_prog_langs or curr_tech_skills) else 'None listed'}
- Current Tools & Platforms: {', '.join(curr_tools) if curr_tools else 'None listed'}
- Current Soft Skills: {', '.join(curr_soft_skills) if curr_soft_skills else 'None listed'}
- Existing Portfolio Projects: {', '.join(curr_projects) if curr_projects else 'None recorded'}
- Existing Certifications: {', '.join(curr_certs) if curr_certs else 'None recorded'}
- Identified Skill Gaps from Resume & Match Analysis: {', '.join(missing_analysis_skills + jm_missing_skills) if (missing_analysis_skills or jm_missing_skills) else 'Analyze gaps based on role requirements'}

--- RESUME TEXT CONTEXT ---
{resume_text[:2500]}

--- MATCH & ATS CONTEXT ---
{jm_summary if jm_summary else "No prior job match data recorded."}
{ats_summary if ats_summary else "No prior ATS analysis recorded."}
{interview_summary if interview_summary else "No prior interview session recorded."}

CRITICAL RULES FOR ROADMAP GENERATION:
1. Personalized Skill Gaps: Directly identify what this specific candidate lacks for {target_company} {target_role}. Provide a detailed 'skill_gaps' array with skill name, importance (High/Medium/Low), why needed, current level, and target level.
2. Logical Sequence: Follow a clear dependency progression:
   FOUNDATION -> CORE SKILLS -> ROLE-SPECIFIC TECHNOLOGIES -> ADVANCED SKILLS -> PROJECTS -> CERTIFICATION -> INTERVIEW READINESS.
3. Skill Prioritization: Categorize every skill into "High", "Medium", or "Low" priority:
   - High: Essential for {target_role} at {target_company} and candidate currently lacks it.
   - Medium: Highly recommended for proficiency.
   - Low: Good to have / future improvement.
   Provide a concrete 'reason' and 'what_to_learn' for each.
4. Clean Categorization: Provide distinct lists for programming languages, technologies, developer tools, and core academic subjects.
5. Certifications: Recommend ONLY 1 to 3 legitimate, highly relevant certifications for {target_company} + {target_role}. Provide provider, priority, rationale, and official certification website URL (or leave url empty if unavailable).
6. Portfolio Projects: Recommend 2 to 3 progressive projects (Beginner -> Intermediate -> Advanced Portfolio) specifically designed to demonstrate the missing skills. Include project title, difficulty, skills demonstrated, what to build, and why it helps.
7. Return ONLY a single raw valid JSON object matching this exact schema:

{{
  "career_goal": {{
    "company": "{target_company}",
    "role": "{target_role}"
  }},
  "current_readiness": {{
    "score": 65,
    "summary": "Concise summary of candidate's current capabilities, key skill gaps, and strategic focus for {target_company} {target_role}."
  }},
  "roadmap_duration": "10–12 weeks",
  "skill_gaps": [
    {{
      "skill": "Skill Name",
      "importance": "High",
      "reason": "Detailed explanation of why this skill is needed for {target_company} {target_role}.",
      "current_level": "Beginner / None",
      "target_level": "Intermediate / Production Ready"
    }}
  ],
  "phases": [
    {{
      "phase_number": 1,
      "title": "Phase Title (e.g. Core Foundations & System Mastery)",
      "duration": "2 weeks",
      "objective": "Clear milestone objective",
      "skills": [
        {{
          "name": "Skill Name",
          "priority": "High",
          "reason": "Why this skill is needed",
          "what_to_learn": "Key concepts and topics to master"
        }}
      ],
      "languages": ["Language 1"],
      "technologies": ["Tech 1"],
      "tools": ["Tool 1"],
      "core_subjects": ["Subject 1"],
      "certifications": [],
      "projects": [],
      "milestone": "Measurable milestone to complete this phase"
    }}
  ],
  "final_readiness": {{
    "technical_skills": ["Skill 1", "Skill 2"],
    "certifications_completed": ["Relevant Cert"],
    "projects_completed": ["Portfolio Project"],
    "interview_ready": false
  }}
}}

Constraints:
- Include between 3 and 5 well-structured sequential phases.
- Do NOT return markdown codeblocks or placeholder text. Return pure JSON.
"""

    raw_text = ""
    try:
        raw_text = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
    except Exception as api_err:
        logger.error(f"Gemini API call failed during career roadmap generation: {api_err}")
        raise RuntimeError("Career roadmap generation is temporarily unavailable. Please try again.")

    if not raw_text or not raw_text.strip():
        raise RuntimeError("Empty response from Gemini AI.")

    cleaned = clean_json_text(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse Gemini JSON output for career roadmap: {json_err}. Cleaned text: {cleaned[:300]}")
        raise ValueError("Invalid JSON response from Gemini AI.")

    return sanitize_and_validate_roadmap(parsed, target_company, target_role)


def sanitize_and_validate_roadmap(parsed, default_company="Target Company", default_role="Software Engineer"):
    """
    Validates and standardizes the AI roadmap schema, adding defaults where needed.
    """
    from backend.services.resume_intelligence import deduplicate_list

    if not isinstance(parsed, dict):
        parsed = {}

    # 1. Career Goal
    cg = parsed.get("career_goal")
    if not isinstance(cg, dict):
        cg = {}
    company = str(cg.get("company") or default_company).strip()
    role = str(cg.get("role") or default_role).strip()
    parsed["career_goal"] = {"company": company, "role": role}

    # 2. Current Readiness
    cr = parsed.get("current_readiness")
    if not isinstance(cr, dict):
        cr = {}
    try:
        score = max(0, min(100, int(cr.get("score", parsed.get("readiness_score", 60)))))
    except (ValueError, TypeError):
        score = 60
    summary = str(cr.get("summary") or parsed.get("current_profile_summary") or f"Roadmap for {role} at {company}.").strip()
    parsed["current_readiness"] = {
        "score": score,
        "summary": summary
    }

    # Backward compatibility root scores
    parsed["readiness_score"] = score
    parsed["readiness_label"] = get_readiness_label(score)
    parsed["roadmap_duration"] = str(parsed.get("roadmap_duration") or parsed.get("estimated_timeline") or "8–12 weeks").strip()

    # 3. Dynamic Skill Gaps Validation
    raw_gaps = parsed.get("skill_gaps") or []
    sanitized_gaps = []
    if isinstance(raw_gaps, list):
        for g in raw_gaps:
            if isinstance(g, dict) and g.get("skill"):
                imp = str(g.get("importance") or "High").capitalize()
                if imp not in ["High", "Medium", "Low"]:
                    imp = "High"
                sanitized_gaps.append({
                    "skill": str(g.get("skill")).strip(),
                    "importance": imp,
                    "reason": str(g.get("reason") or f"Required for {company} {role} competency.").strip(),
                    "current_level": str(g.get("current_level") or "Beginner").strip(),
                    "target_level": str(g.get("target_level") or "Production Ready").strip()
                })
            elif isinstance(g, str) and g.strip():
                sanitized_gaps.append({
                    "skill": g.strip(),
                    "importance": "High",
                    "reason": f"Required competency for {role}.",
                    "current_level": "Needs Improvement",
                    "target_level": "Intermediate / Job Ready"
                })
    parsed["skill_gaps"] = sanitized_gaps

    # 4. Phases validation
    raw_phases = parsed.get("phases") or parsed.get("roadmap") or []
    if not isinstance(raw_phases, list):
        raw_phases = []

    sanitized_phases = []
    for idx, p in enumerate(raw_phases):
        if not isinstance(p, dict):
            continue

        p_num = p.get("phase_number") or p.get("phase") or (idx + 1)
        p_title = str(p.get("title") or f"Phase {p_num}").strip()
        p_duration = str(p.get("duration") or p.get("estimated_duration") or "2 weeks").strip()
        p_obj = str(p.get("objective") or p.get("description") or "").strip()
        p_milestone = str(p.get("milestone") or (p.get("success_criteria")[0] if p.get("success_criteria") else "")).strip()

        # Skills with priorities
        raw_skills = p.get("skills") or []
        sanitized_skills = []
        if isinstance(raw_skills, list):
            for s in raw_skills:
                if isinstance(s, dict):
                    priority = str(s.get("priority") or "High").capitalize()
                    if priority not in ["High", "Medium", "Low"]:
                        priority = "High"
                    sanitized_skills.append({
                        "name": str(s.get("name") or "Skill").strip(),
                        "priority": priority,
                        "reason": str(s.get("reason") or "").strip(),
                        "what_to_learn": str(s.get("what_to_learn") or "").strip(),
                        "status": str(s.get("status") or "not_started").strip()
                    })
                elif isinstance(s, str) and s.strip():
                    sanitized_skills.append({
                        "name": s.strip(),
                        "priority": "High",
                        "reason": "Core competency for this phase.",
                        "what_to_learn": f"Master {s.strip()} fundamentals and hands-on usage.",
                        "status": "not_started"
                    })

        # If no skills in skills list, check skills_to_develop
        if not sanitized_skills and p.get("skills_to_develop"):
            for s_str in p.get("skills_to_develop", []):
                if isinstance(s_str, str) and s_str.strip():
                    sanitized_skills.append({
                        "name": s_str.strip(),
                        "priority": "High",
                        "reason": "Required phase skill.",
                        "what_to_learn": f"Learn practical {s_str.strip()}.",
                        "status": "not_started"
                    })

        # Certifications inside phase
        raw_certs = p.get("certifications") or []
        sanitized_certs = []
        if isinstance(raw_certs, list):
            for c in raw_certs:
                if isinstance(c, dict):
                    sanitized_certs.append({
                        "name": str(c.get("name") or "Certification").strip(),
                        "provider": str(c.get("provider") or "").strip(),
                        "priority": str(c.get("priority") or "High").strip(),
                        "reason": str(c.get("reason") or "").strip(),
                        "url": str(c.get("url") or c.get("official_url") or "").strip(),
                        "status": str(c.get("status") or "not_started").strip()
                    })
                elif isinstance(c, str) and c.strip():
                    sanitized_certs.append({
                        "name": c.strip(),
                        "provider": company,
                        "priority": "High",
                        "reason": "Directly relevant certification.",
                        "url": "",
                        "status": "not_started"
                    })

        # Projects inside phase
        raw_projects = p.get("projects") or []
        sanitized_projects = []
        if isinstance(raw_projects, list):
            for pr in raw_projects:
                if isinstance(pr, dict):
                    sanitized_projects.append({
                        "title": str(pr.get("title") or pr.get("name") or "Portfolio Project").strip(),
                        "difficulty": str(pr.get("difficulty") or "Intermediate").strip(),
                        "skills": deduplicate_list(pr.get("skills") or []),
                        "what_to_build": str(pr.get("what_to_build") or pr.get("description") or "").strip(),
                        "expected_outcome": str(pr.get("expected_outcome") or "").strip(),
                        "status": str(pr.get("status") or "not_started").strip()
                    })
                elif isinstance(pr, str) and pr.strip():
                    sanitized_projects.append({
                        "title": pr.strip(),
                        "difficulty": "Intermediate",
                        "skills": [],
                        "what_to_build": f"Implement a working solution for {pr.strip()}.",
                        "expected_outcome": "Working repository deployed to portfolio.",
                        "status": "not_started"
                    })

        sanitized_phases.append({
            "phase_number": p_num,
            "title": p_title,
            "duration": p_duration,
            "objective": p_obj,
            "skills": sanitized_skills,
            "languages": deduplicate_list(p.get("languages") or []),
            "technologies": deduplicate_list(p.get("technologies") or []),
            "tools": deduplicate_list(p.get("tools") or []),
            "core_subjects": deduplicate_list(p.get("core_subjects") or []),
            "certifications": sanitized_certs,
            "projects": sanitized_projects,
            "milestone": p_milestone,
            "status": str(p.get("status") or "not_started").strip()
        })

    parsed["phases"] = sanitized_phases
    # Maintain backward compatibility 'roadmap' key
    parsed["roadmap"] = sanitized_phases

    # 4. Final Readiness
    fr = parsed.get("final_readiness")
    if not isinstance(fr, dict):
        fr = {}
    parsed["final_readiness"] = {
        "technical_skills": deduplicate_list(fr.get("technical_skills") or []),
        "certifications_completed": deduplicate_list(fr.get("certifications_completed") or []),
        "projects_completed": deduplicate_list(fr.get("projects_completed") or []),
        "interview_ready": bool(fr.get("interview_ready", False))
    }

    # Consolidated project list & certifications
    all_projects = []
    for ph in sanitized_phases:
        for pr in ph.get("projects", []):
            all_projects.append(pr)
    parsed["recommended_projects"] = all_projects if all_projects else deduplicate_list(parsed.get("recommended_projects") or [])

    parsed["progress"] = parsed.get("progress", 0)

    return parsed

