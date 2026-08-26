"""
CareerPilot AI — Career Assessment & Target Company Intelligence Service (Phase 3)
Analyzes:
  Career Goal + Candidate Profile + Resume + Target Company/Job Requirements
Generates:
  Explainable Career Readiness Score, Target-Specific ATS Match, Prioritized Skill Gap Matrix,
  Programming Language Assessment, Knowledge Gaps, Certification & Project Recommendations,
  and Top Priority Next Actions with strict anti-hallucination grounding.
"""

import json
import logging
import re
import hashlib
from services.resume_intelligence import (
    genai_client,
    is_gemini_configured,
    call_gemini_with_retry,
    clean_json_text,
    deduplicate_list,
    deduplicate_dict_list
)

logger = logging.getLogger(__name__)

REQUIRED_ASSESSMENT_KEYS = {
    "career_readiness_score",
    "ats_score",
    "summary",
    "strong_matches",
    "partial_matches",
    "skill_gaps",
    "programming_language_gaps",
    "knowledge_gaps",
    "resume_gaps",
    "certification_relevance",
    "project_gaps",
    "priority_actions"
}

def generate_context_cache_hash(goal, profile, resume, job_description=""):
    """Creates a deterministic MD5 hash of input data to enable caching."""
    raw_str = (
        f"{goal.get('id')}_{goal.get('company_name')}_{goal.get('job_role')}_{goal.get('experience_level')}_"
        f"{profile.get('updated_at')}_{profile.get('completeness')}_"
        f"{resume.get('resume_id')}_{resume.get('uploaded_at')}_"
        f"{job_description.strip()}"
    )
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def validate_assessment_json(data):
    """Validates that Gemini returned complete JSON matching the expected schema."""
    if not isinstance(data, dict):
        return False
    if not REQUIRED_ASSESSMENT_KEYS.issubset(data.keys()):
        missing = REQUIRED_ASSESSMENT_KEYS - set(data.keys())
        logger.warning(f"Assessment JSON missing required keys: {missing}")
        return False
    
    if not isinstance(data.get("skill_gaps"), list):
        return False
    if not isinstance(data.get("priority_actions"), list):
        return False
    return True

def assess_career_readiness(goal, profile, resume, job_description=""):
    """
    Main entry point for Phase 3 Career Assessment generation.
    """
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Target Role")
    exp_level = goal.get("experience_level", "Fresher")
    location = goal.get("target_location", "Any")
    timeline = goal.get("target_timeline", "Flexible")

    # Extract candidate data
    full_name = profile.get("full_name", "Candidate")
    status = (profile.get("career_information") or {}).get("current_status", "Fresher")
    edu = profile.get("education") or {}
    edu_str = f"{edu.get('highest_education', '')} in {edu.get('specialization', '')} from {edu.get('institution', '')} ({edu.get('graduation_year', '')})".strip()
    
    skills = profile.get("skills") or {}
    prog_skills = skills.get("programming_languages") or []
    tech_skills = skills.get("technical_skills") or []
    tools_skills = skills.get("tools_and_technologies") or []
    soft_skills = skills.get("soft_skills") or []
    all_candidate_skills = prog_skills + tech_skills + tools_skills + soft_skills

    projects = profile.get("projects") or []
    projects_str = "\n".join([f"- {p.get('title')}: {p.get('description')} (Tech: {', '.join(p.get('technologies') or [])})" for p in projects]) if projects else "None recorded in profile."
    
    certs = profile.get("certifications") or []
    certs_str = "\n".join([f"- {c.get('name')} issued by {c.get('issuing_organization')}" for c in certs]) if certs else "None recorded in profile."

    resume_text = (resume.get("extracted_text") or "")[:4000]
    has_resume = bool(resume.get("available") and resume_text)

    if not is_gemini_configured or not genai_client:
        logger.info("Career Assessment: Using rule-based fallback assessment (Gemini not configured).")
        return generate_rule_based_fallback_assessment(goal, profile, resume, job_description)

    prompt = f"""
SYSTEM INSTRUCTION:
You are the Lead Career Architect and Company Intelligence Engine for CareerPilot AI.
You must perform an in-depth, realistic, and highly specific Career Readiness & Target Company Gap Assessment for this candidate.

CANDIDATE PROFILE:
- Name: {full_name}
- Career Stage: {status}
- Education: {edu_str or 'Not provided'}
- Skills Provided by Candidate: {', '.join(all_candidate_skills) if all_candidate_skills else 'None entered yet'}
- Projects:
{projects_str}
- Certifications:
{certs_str}

RESUME:
{f"Extracted Resume Content:\n{resume_text}" if has_resume else "Candidate has not uploaded a resume yet. Evaluate purely on profile data."}

TARGET CAREER GOAL:
- Target Company: {company}
- Target Job Role: {role}
- Experience Level: {exp_level}
- Target Location: {location}
- Target Preparation Timeline: {timeline}
- Specific Job Description Provided by User: {job_description.strip() if job_description.strip() else 'None provided (Use company and job role requirements intelligence)'}

CRITICAL RULES:
1. Grounding & Zero Generic Text: Provide recommendations strictly specific to {company} and the {role} position.
2. Verified vs. Inferred Requirements: Do not state that {company} mandates a skill or certification unless it is standard industry knowledge for this role. Label skills transparently.
3. Classify Skills:
   - "strong_matches": Skills the candidate clearly has.
   - "partial_matches": Skills where the candidate has basic/related foundation but needs deeper role-specific practice.
   - "skill_gaps": Missing core skills required for {role}. For each, provide priority (HIGH/MEDIUM/LOW), "why", "what_to_learn", and a concrete "practice_task".
4. Programming Languages: Classify into "Already know", "Need improvement", or "Need to learn" relevant to {role}.
5. Knowledge Gaps: Identify core CS / domain areas (e.g. Cloud Networking, OS, Distributed Systems) essential for {role}.
6. Certification Relevance: Classify certifications into "Required", "Recommended", or "Not necessary".
7. Project Recommendations: Identify existing project strengths and recommend 1-2 high-impact practical projects tailored to {company}.
8. ATS Match Score: Explainable score (0-100) reflecting resume/profile keyword and skill alignment with {company} {role}.
9. Career Readiness Score: Comprehensive percentage (0-100) derived from skills, projects, experience, and education.

Return ONLY a valid JSON object matching this exact structure:
{{
  "career_readiness_score": 65,
  "ats_score": 70,
  "readiness_breakdown": {{
    "skills_match": 65,
    "project_alignment": 60,
    "education_alignment": 80,
    "experience_alignment": 60,
    "certification_alignment": 50,
    "resume_quality": 75
  }},
  "summary": "Specific, encouraging, and actionable assessment summary for {full_name} targeting {company} {role}.",
  "target_company": "{company}",
  "target_job_role": "{role}",
  "strong_matches": ["Skill 1", "Skill 2"],
  "partial_matches": ["Skill 3"],
  "skill_gaps": [
    {{
      "skill": "Target Skill Name",
      "category": "technical / tools / conceptual",
      "priority": "HIGH / MEDIUM / LOW",
      "why": "Why this specific skill matters for {role} at {company}",
      "what_to_learn": ["Key topic 1", "Key topic 2"],
      "practice_task": "Concrete hands-on project or task to master this skill"
    }}
  ],
  "programming_language_gaps": [
    {{
      "language": "Language Name",
      "status": "Already know / Need improvement / Need to learn",
      "recommendation": "Brief reason and focus area"
    }}
  ],
  "knowledge_gaps": [
    {{
      "topic": "Knowledge Area / Subject",
      "priority": "HIGH / MEDIUM / LOW",
      "relevance": "Why it is critical for {role}"
    }}
  ],
  "resume_gaps": [
    "Specific improvement 1 for resume/profile",
    "Specific improvement 2"
  ],
  "certification_relevance": [
    {{
      "name": "Certification Name",
      "type": "Required / Recommended / Not necessary",
      "reason": "Why this cert helps or why it is not required"
    }}
  ],
  "project_gaps": {{
    "existing_strengths": ["Strong aspect of existing projects"],
    "recommended_projects": [
      {{
        "title": "Specific Project Name",
        "description": "Clear project scope using target technologies",
        "why": "Why this strengthens candidate profile for {company}"
      }}
    ]
  }},
  "priority_actions": [
    "1. Immediate action step",
    "2. Second action step",
    "3. Third action step",
    "4. Fourth action step",
    "5. Fifth action step"
  ]
}}
"""

    try:
        raw_text = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        cleaned = clean_json_text(raw_text)
        assessment = json.loads(cleaned)

        if validate_assessment_json(assessment):
            # Clean and deduplicate lists
            assessment["strong_matches"] = deduplicate_list(assessment.get("strong_matches", []))
            assessment["partial_matches"] = deduplicate_list(assessment.get("partial_matches", []))
            assessment["skill_gaps"] = deduplicate_dict_list(assessment.get("skill_gaps", []), key="skill")
            assessment["priority_actions"] = deduplicate_list(assessment.get("priority_actions", []))
            logger.info("Career Assessment generated successfully with Gemini.")
            return assessment
        else:
            logger.warning("Assessment response failed schema validation. Using rule fallback.")
            return generate_rule_based_fallback_assessment(goal, profile, resume, job_description)

    except Exception as err:
        logger.error(f"Error during Gemini career assessment generation: {err}")
        return generate_rule_based_fallback_assessment(goal, profile, resume, job_description)


def generate_rule_based_fallback_assessment(goal, profile, resume, job_description=""):
    """
    Robust deterministic rule-based assessment fallback if Gemini is offline or fails validation.
    """
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Cloud Engineer")
    skills = profile.get("skills") or {}
    cand_skills = (skills.get("programming_languages") or []) + (skills.get("technical_skills") or []) + (skills.get("tools_and_technologies") or [])
    cand_skills_lower = {s.lower() for s in cand_skills}

    # Role standard skill sets
    role_lower = role.lower()
    target_benchmark_skills = []
    if "cloud" in role_lower or "devops" in role_lower:
        target_benchmark_skills = ["AWS/Azure", "Linux", "Docker", "Kubernetes", "Python", "Networking", "Terraform", "CI/CD"]
    elif "data" in role_lower or "ai" in role_lower or "ml" in role_lower:
        target_benchmark_skills = ["Python", "SQL", "Pandas", "Machine Learning", "Data Structures", "Tableau/PowerBI", "Cloud Basics"]
    else:
        target_benchmark_skills = ["Data Structures", "Algorithms", "System Design", "SQL", "REST APIs", "Git", "Clean Code"]

    strong = []
    missing = []
    for skill in target_benchmark_skills:
        if any(w in cand_skills_lower for w in skill.lower().split('/')):
            strong.append(skill)
        else:
            missing.append(skill)

    if not strong:
        strong = cand_skills[:3] if cand_skills else ["Problem Solving"]

    # Calculate baseline scores
    match_ratio = len(strong) / max(len(target_benchmark_skills), 1)
    readiness_score = int(min(max(match_ratio * 70 + (20 if profile.get("projects") else 5), 45), 92))
    ats_score = int(min(max(match_ratio * 75 + (15 if resume.get('available') else 0), 50), 90))

    skill_gaps = []
    for m in missing[:4]:
        skill_gaps.append({
            "skill": m,
            "category": "technical",
            "priority": "HIGH",
            "why": f"Fundamental requirement for {role} at {company}.",
            "what_to_learn": [f"Core {m} principles", f"Practical {m} implementations"],
            "practice_task": f"Build a practical mini-project applying {m} concepts."
        })

    return {
        "career_readiness_score": readiness_score,
        "ats_score": ats_score,
        "readiness_breakdown": {
            "skills_match": int(match_ratio * 100),
            "project_alignment": 65 if profile.get("projects") else 40,
            "education_alignment": 80,
            "experience_alignment": 60,
            "certification_alignment": 50 if profile.get("certifications") else 30,
            "resume_quality": 75 if resume.get("available") else 50
        },
        "summary": f"Your profile demonstrates a solid starting foundation for a {role} position. Targeting {company} requires closing gaps in {', '.join(missing[:2])}.",
        "target_company": company,
        "target_job_role": role,
        "strong_matches": strong,
        "partial_matches": ["System Architecture Fundamentals", "Scripting Automation"],
        "skill_gaps": skill_gaps,
        "programming_language_gaps": [
            {"language": "Python", "status": "Already know" if "python" in cand_skills_lower else "Need to learn", "recommendation": f"Core language for {role} automation."},
            {"language": "Bash / Shell", "status": "Need improvement", "recommendation": "Essential for server configuration."}
        ],
        "knowledge_gaps": [
            {"topic": "Operating Systems & Networking", "priority": "HIGH", "relevance": f"Crucial for {role} infrastructure."},
            {"topic": "Distributed System Architecture", "priority": "MEDIUM", "relevance": f"Required for scale at {company}."}
        ],
        "resume_gaps": [
            f"Add clear bullet points featuring {company} relevant technologies.",
            "Quantify project achievements with measurable performance outcomes."
        ],
        "certification_relevance": [
            {"name": f"Foundational {role} Certification", "type": "Recommended", "reason": f"Validates baseline competencies for {company}."}
        ],
        "project_gaps": {
            "existing_strengths": ["Practical hands-on programming experience"],
            "recommended_projects": [
                {
                    "title": f"End-to-End {role} Solution",
                    "description": f"Design and deploy a project highlighting {', '.join(missing[:2])}.",
                    "why": f"Directly proves capability for {company} {role} responsibilities."
                }
            ]
        },
        "priority_actions": [
            f"1. Close your top skill gap in {missing[0] if missing else 'Cloud Computing'}.",
            f"2. Build a project demonstrating {company} relevant infrastructure.",
            "3. Update your resume with measurable achievements.",
            "4. Practice system design and architecture concepts.",
            "5. Review standard technical interview questions for this role."
        ]
    }
