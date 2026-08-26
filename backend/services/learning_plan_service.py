"""
CareerPilot AI — Personalized Learning Path & Skill Development Service (Phase 4)

Transforms skill gaps identified in Phase 3 into a clear, personalized, actionable
learning and development plan tailored to the candidate's target company and job role.

Grounding rules:
1. Primary Source is Phase 3 Assessment (skill_gaps, partial_matches, strong_matches).
2. Distinguish: Already Know (improve if needed) vs. Needs Improvement vs. Must Learn from Scratch.
3. Organize into dynamic, logical phases and dependencies.
4. Concrete practical tasks connected to candidate's existing projects where available.
5. Provide topics, why needed, current vs. target levels, estimated effort, and expected outcomes.
"""

import json
import logging
import hashlib
import uuid as uuid_lib
from services.resume_intelligence import (
    genai_client,
    is_gemini_configured,
    call_gemini_with_retry,
    clean_json_text,
    deduplicate_list,
    deduplicate_dict_list
)

logger = logging.getLogger(__name__)

REQUIRED_LEARNING_PLAN_KEYS = {
    "plan_summary",
    "overall_learning_priority",
    "phases"
}

REQUIRED_PHASE_KEYS = {
    "name",
    "description",
    "order",
    "skills"
}

REQUIRED_SKILL_KEYS = {
    "name",
    "category",
    "priority",
    "current_level",
    "target_level",
    "why_needed",
    "topics",
    "practice_tasks",
    "expected_outcome",
    "estimated_effort"
}

def generate_learning_plan_cache_hash(goal, profile, assessment, timeline=None):
    """
    Creates a deterministic MD5 hash of input data to enable caching of learning plans.
    """
    t_line = timeline or goal.get("target_timeline", "Flexible")
    raw_str = (
        f"{goal.get('id')}_{goal.get('company_name')}_{goal.get('job_role')}_{goal.get('experience_level')}_{t_line}_"
        f"{profile.get('updated_at')}_{profile.get('completeness')}_"
        f"{assessment.get('id')}_{assessment.get('created_at')}_{assessment.get('career_readiness_score')}"
    )
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def validate_learning_plan_json(data):
    """
    Validates that Gemini returned a complete JSON object matching the expected schema.
    """
    if not isinstance(data, dict):
        return False
    if not REQUIRED_LEARNING_PLAN_KEYS.issubset(data.keys()):
        missing = REQUIRED_LEARNING_PLAN_KEYS - set(data.keys())
        logger.warning(f"Learning Plan JSON missing required root keys: {missing}")
        return False
    
    phases = data.get("phases")
    if not isinstance(phases, list) or len(phases) == 0:
        logger.warning("Learning Plan JSON contains empty or non-list phases.")
        return False
    
    seen_skills = set()
    for phase in phases:
        if not isinstance(phase, dict) or not REQUIRED_PHASE_KEYS.issubset(phase.keys()):
            return False
        skills = phase.get("skills")
        if not isinstance(skills, list):
            return False
        for sk in skills:
            if not isinstance(sk, dict) or not REQUIRED_SKILL_KEYS.issubset(sk.keys()):
                return False
            # Normalize skill name and prevent duplicate items
            sk_name = sk.get("name", "").strip().lower()
            if sk_name in seen_skills:
                continue
            seen_skills.add(sk_name)
            
    return True

def clean_and_normalize_learning_plan(data):
    """
    Ensures all IDs, order indices, default statuses, and deduplication are in place.
    """
    cleaned_phases = []
    seen_skills = set()
    total_skills = 0
    completed_skills = 0

    for p_idx, phase in enumerate(data.get("phases", [])):
        phase_id = phase.get("phase_id") or f"phase-{p_idx + 1}"
        phase_name = phase.get("name") or f"Phase {p_idx + 1}"
        phase_desc = phase.get("description") or ""
        phase_order = phase.get("order") or (p_idx + 1)
        
        normalized_skills = []
        for s_idx, sk in enumerate(phase.get("skills", [])):
            sk_name = (sk.get("name") or "Skill").strip()
            sk_lower = sk_name.lower()
            if sk_lower in seen_skills:
                continue
            seen_skills.add(sk_lower)
            
            skill_id = sk.get("skill_id") or f"skill-{p_idx + 1}-{s_idx + 1}-{uuid_lib.uuid4().hex[:6]}"
            status = sk.get("status", "NOT_STARTED")
            if status not in ["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "VERIFIED"]:
                status = "NOT_STARTED"
                
            priority = str(sk.get("priority", "MEDIUM")).upper()
            if priority not in ["HIGH", "MEDIUM", "LOW"]:
                priority = "MEDIUM"

            topics = sk.get("topics") or []
            if isinstance(topics, str):
                topics = [t.strip() for t in topics.split(",") if t.strip()]
            topics = deduplicate_list(topics)

            practice_tasks = sk.get("practice_tasks") or []
            if isinstance(practice_tasks, str):
                practice_tasks = [pt.strip() for pt in practice_tasks.split("\n") if pt.strip()]
            practice_tasks = deduplicate_list(practice_tasks)

            total_skills += 1
            if status in ["COMPLETED", "VERIFIED"]:
                completed_skills += 1

            normalized_skills.append({
                "skill_id": skill_id,
                "name": sk_name,
                "category": sk.get("category") or "Technical Skills",
                "priority": priority,
                "current_level": sk.get("current_level") or "NOT_STARTED",
                "target_level": sk.get("target_level") or "INTERMEDIATE",
                "status": status,
                "why_needed": sk.get("why_needed") or f"Essential for target role readiness.",
                "topics": topics,
                "practice_tasks": practice_tasks,
                "expected_outcome": sk.get("expected_outcome") or "Demonstrable proficiency in practical scenarios.",
                "estimated_effort": sk.get("estimated_effort") or "1-2 Weeks"
            })
            
        if normalized_skills:
            cleaned_phases.append({
                "phase_id": phase_id,
                "name": phase_name,
                "description": phase_desc,
                "order": phase_order,
                "skills": normalized_skills
            })

    overall_prog = int((completed_skills / total_skills) * 100) if total_skills > 0 else 0

    return {
        "plan_summary": data.get("plan_summary", "Custom tailored learning path."),
        "overall_learning_priority": data.get("overall_learning_priority", "HIGH"),
        "overall_progress": overall_prog,
        "phases": cleaned_phases
    }

def generate_rule_based_fallback_learning_plan(goal, profile, assessment, resume=None):
    """
    Robust, role-grounded fallback learning plan generator if Gemini is unconfigured or unavailable.
    """
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Software Engineer")
    timeline = goal.get("target_timeline", "6 Months")

    # Extract user projects for practical linking
    projects = profile.get("projects") or []
    sample_proj_title = projects[0].get("title") if projects else "CareerPilot AI"

    # Extract Phase 3 findings
    assess_res = assessment.get("assessment_result") or assessment
    strong_matches = assess_res.get("strong_matches") or []
    partial_matches = assess_res.get("partial_matches") or []
    skill_gaps = assess_res.get("skill_gaps") or []
    prog_gaps = assess_res.get("programming_language_gaps") or []
    knowledge_gaps = assess_res.get("knowledge_gaps") or []

    phases = []
    
    # Phase 1: Foundations & Systems
    foundations_skills = []
    for kg in knowledge_gaps[:2]:
        topic = kg.get("topic") or "Core Systems"
        foundations_skills.append({
            "skill_id": f"skill-fnd-{uuid_lib.uuid4().hex[:6]}",
            "name": topic,
            "category": "Knowledge Areas",
            "priority": kg.get("priority", "HIGH"),
            "current_level": "BEGINNER",
            "target_level": "INTERMEDIATE",
            "status": "NOT_STARTED",
            "why_needed": kg.get("relevance") or f"Foundational understanding required for {company} {role}.",
            "topics": ["Architecture Principles", "Troubleshooting & Analysis", "System Design Patterns"],
            "practice_tasks": [f"Design a system diagram incorporating {topic} principles for {sample_proj_title}."],
            "expected_outcome": f"Solid conceptual mastery of {topic}.",
            "estimated_effort": "2 Weeks"
        })
    
    # Check partial matches for improvement in Phase 1 or 2
    for pm in partial_matches[:2]:
        foundations_skills.append({
            "skill_id": f"skill-pm-{uuid_lib.uuid4().hex[:6]}",
            "name": f"Advanced {pm}",
            "category": "Technical Skills",
            "priority": "HIGH",
            "current_level": "BEGINNER",
            "target_level": "INTERMEDIATE",
            "status": "NOT_STARTED",
            "why_needed": f"Your profile shows basic knowledge of {pm}. Strengthen to production-grade proficiency for {role}.",
            "topics": ["Production Best Practices", "Performance Optimization", "Security Patterns"],
            "practice_tasks": [f"Refactor parts of {sample_proj_title} utilizing optimized {pm} techniques."],
            "expected_outcome": f"Confidently apply {pm} in production environments.",
            "estimated_effort": "2 Weeks"
        })

    if not foundations_skills:
        foundations_skills.append({
            "skill_id": f"skill-fnd-1",
            "name": "System Architecture & Foundations",
            "category": "Knowledge Areas",
            "priority": "HIGH",
            "current_level": "BEGINNER",
            "target_level": "INTERMEDIATE",
            "status": "NOT_STARTED",
            "why_needed": f"Understanding baseline architecture patterns expected at {company}.",
            "topics": ["Client-Server Models", "Data Flow", "API Protocols"],
            "practice_tasks": ["Build and test API interfaces between local services."],
            "expected_outcome": "Understand full architecture lifecycle.",
            "estimated_effort": "2 Weeks"
        })

    phases.append({
        "phase_id": "phase-1",
        "name": "Phase 1 — Core Foundations & System Mastery",
        "description": "Establish key system and architecture fundamentals required before tackling advanced tooling.",
        "order": 1,
        "skills": foundations_skills
    })

    # Phase 2: Core Missing Technologies (from Phase 3 Skill Gaps)
    core_tech_skills = []
    for gap in skill_gaps:
        if gap.get("priority") == "HIGH":
            core_tech_skills.append({
                "skill_id": f"skill-gap-{uuid_lib.uuid4().hex[:6]}",
                "name": gap.get("skill", "Core Tool"),
                "category": gap.get("category", "Technical Skills"),
                "priority": "HIGH",
                "current_level": "NOT_STARTED",
                "target_level": "INTERMEDIATE",
                "status": "NOT_STARTED",
                "why_needed": gap.get("why") or f"Core requirement identified for {company} {role}.",
                "topics": gap.get("what_to_learn") or ["Fundamentals", "Configuration", "Deployment"],
                "practice_tasks": [gap.get("practice_task") or f"Integrate {gap.get('skill')} into {sample_proj_title}."],
                "expected_outcome": f"Hands-on ability to build, configure, and maintain {gap.get('skill')}.",
                "estimated_effort": "2-3 Weeks"
            })
            
    if not core_tech_skills and skill_gaps:
        gap = skill_gaps[0]
        core_tech_skills.append({
            "skill_id": f"skill-gap-0",
            "name": gap.get("skill", "Technology"),
            "category": gap.get("category", "Technical Skills"),
            "priority": gap.get("priority", "HIGH"),
            "current_level": "NOT_STARTED",
            "target_level": "INTERMEDIATE",
            "status": "NOT_STARTED",
            "why_needed": gap.get("why", "Key requirement."),
            "topics": gap.get("what_to_learn", ["Core concepts"]),
            "practice_tasks": [gap.get("practice_task", "Hands-on task")],
            "expected_outcome": "Demonstrated technical capability.",
            "estimated_effort": "2 Weeks"
        })

    phases.append({
        "phase_id": "phase-2",
        "name": "Phase 2 — Core Technical & Tooling Gaps",
        "description": "Learn the primary missing technologies and tools identified during your Phase 3 Career Assessment.",
        "order": 2,
        "skills": core_tech_skills or [{
            "skill_id": "skill-tech-1",
            "name": "Role Tooling & Automation",
            "category": "Tools",
            "priority": "HIGH",
            "current_level": "NOT_STARTED",
            "target_level": "INTERMEDIATE",
            "status": "NOT_STARTED",
            "why_needed": f"Essential operational tooling for {role}.",
            "topics": ["CLI Tools", "Scripting", "Version Control Workflows"],
            "practice_tasks": [f"Automate deployment workflows for {sample_proj_title}."],
            "expected_outcome": "Operational confidence in role tools.",
            "estimated_effort": "2 Weeks"
        }]
    })

    # Phase 3: Role-Specific & Advanced Integration
    adv_skills = []
    for gap in skill_gaps:
        if gap.get("priority") in ["MEDIUM", "LOW"]:
            adv_skills.append({
                "skill_id": f"skill-gap-{uuid_lib.uuid4().hex[:6]}",
                "name": gap.get("skill", "Advanced Technology"),
                "category": gap.get("category", "Role-Specific Technologies"),
                "priority": gap.get("priority", "MEDIUM"),
                "current_level": "NOT_STARTED",
                "target_level": "INTERMEDIATE",
                "status": "NOT_STARTED",
                "why_needed": gap.get("why") or f"Supports high-quality delivery in {role} projects at {company}.",
                "topics": gap.get("what_to_learn") or ["Advanced Features", "Monitoring", "Scale"],
                "practice_tasks": [gap.get("practice_task") or f"Extend {sample_proj_title} with {gap.get('skill')}."],
                "expected_outcome": f"End-to-end integration proficiency in {gap.get('skill')}.",
                "estimated_effort": "2-3 Weeks"
            })

    if not adv_skills:
        adv_skills.append({
            "skill_id": "skill-adv-1",
            "name": f"End-to-End {role} Pipeline & Integration",
            "category": "Role-Specific Technologies",
            "priority": "MEDIUM",
            "current_level": "NOT_STARTED",
            "target_level": "INTERMEDIATE",
            "status": "NOT_STARTED",
            "why_needed": f"Connect all learned technologies into a cohesive, deployable project.",
            "topics": ["Automated Testing", "CI/CD Integration", "Cloud Deployment"],
            "practice_tasks": [f"Deploy {sample_proj_title} with automated test and build steps."],
            "expected_outcome": "A complete, production-ready portfolio project.",
            "estimated_effort": "3 Weeks"
        })

    phases.append({
        "phase_id": "phase-3",
        "name": "Phase 3 — Advanced Integration & Project Execution",
        "description": "Combine newly acquired skills into production-ready project workflows.",
        "order": 3,
        "skills": adv_skills
    })

    raw_plan = {
        "plan_summary": f"Personalized learning plan structured for {role} at {company} based on your {timeline} timeline and Phase 3 assessment gaps.",
        "overall_learning_priority": "HIGH",
        "phases": phases
    }

    return clean_and_normalize_learning_plan(raw_plan)

def generate_personalized_learning_plan(goal, profile, assessment, resume=None, timeline=None):
    """
    Main entry point for generating the Personalized Learning Path & Skill Development Plan.
    """
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Target Role")
    exp_level = goal.get("experience_level", "Fresher")
    plan_timeline = timeline or goal.get("target_timeline", "6 Months")

    # Extract user profile context
    full_name = profile.get("full_name", "Candidate")
    skills = profile.get("skills") or {}
    prog_skills = skills.get("programming_languages") or []
    tech_skills = skills.get("technical_skills") or []
    tools_skills = skills.get("tools_and_technologies") or []
    all_candidate_skills = prog_skills + tech_skills + tools_skills

    projects = profile.get("projects") or []
    projects_str = "\n".join([f"- {p.get('title')}: {p.get('description')} (Tech: {', '.join(p.get('technologies') or [])})" for p in projects]) if projects else "None recorded."

    # Extract Phase 3 assessment findings
    assess_res = assessment.get("assessment_result") or assessment
    strong_matches = assess_res.get("strong_matches") or []
    partial_matches = assess_res.get("partial_matches") or []
    skill_gaps = assess_res.get("skill_gaps") or []
    prog_lang_gaps = assess_res.get("programming_language_gaps") or []
    knowledge_gaps = assess_res.get("knowledge_gaps") or []
    priority_actions = assess_res.get("priority_actions") or []
    readiness_score = assess_res.get("career_readiness_score", 50)

    if not is_gemini_configured or not genai_client:
        logger.info("Learning Plan Service: Using rule-based fallback (Gemini not configured).")
        return generate_rule_based_fallback_learning_plan(goal, profile, assessment, resume)

    prompt = f"""
SYSTEM INSTRUCTION:
You are the Chief Learning Architect and Career Mentor for CareerPilot AI.
Your goal is to build a structured, realistic, and highly actionable PERSONALIZED LEARNING PATH for this candidate.

TARGET CAREER GOAL:
- Target Company: {company}
- Target Job Role: {role}
- Experience Level: {exp_level}
- Preparation Timeline: {plan_timeline}

CANDIDATE STARTING POINT & PROFILE:
- Name: {full_name}
- Current Verified / Stated Skills: {', '.join(all_candidate_skills) if all_candidate_skills else 'None entered'}
- Existing Projects:
{projects_str}

PHASE 3 CAREER ASSESSMENT SOURCE DATA:
- Career Readiness Score: {readiness_score}%
- Skills User Already Has (Strong Matches): {', '.join(strong_matches) if strong_matches else 'None'}
- Partial Knowledge / Needs Improvement: {', '.join(partial_matches) if partial_matches else 'None'}
- Missing Skill Gaps Identified in Phase 3:
{json.dumps(skill_gaps, indent=2)}
- Programming Language Gaps:
{json.dumps(prog_lang_gaps, indent=2)}
- Knowledge & Core Subject Gaps:
{json.dumps(knowledge_gaps, indent=2)}
- Recommended Priority Actions:
{json.dumps(priority_actions, indent=2)}

CRITICAL AI GENERATION & GROUNDING RULES:
1. USE PHASE 3 AS THE PRIMARY SOURCE: Do not invent unrelated gaps. Base the learning path on the gaps identified above.
2. RESPECT EXISTING KNOWLEDGE:
   - If the candidate ALREADY knows a skill (e.g. Python, SQL, Linux), DO NOT put that skill into "Learn from scratch".
   - Instead, if needed for {role}, create an advanced/production improvement item (e.g. "Advanced Python for Cloud Automation") or skip it.
   - Missing skills should have clear learning roadmaps.
3. LOGICAL LEARNING PHASES:
   - Structure the plan into 3 to 4 sequential, progressive phases (e.g., Phase 1: Core Foundations, Phase 2: Role Technologies, Phase 3: Advanced Tooling & Orchestration).
   - Order skills by dependencies (foundations before advanced tooling).
4. PRACTICAL & PROJECT CONNECTION:
   - For every major skill, provide a concrete practical task.
   - Whenever possible, connect practical tasks to the candidate's existing projects (e.g., "Containerize {projects[0].get('title') if projects else 'CareerPilot AI'}").
5. REALISTIC TIMELINES:
   - Calibrate the phases and estimated effort to fit the "{plan_timeline}" target timeline.
6. EXPLAIN WHY IT IS NEEDED:
   - Provide clear, simple explanations of why {company} and the {role} position require each skill.
7. NO DUPLICATE SKILLS: Ensure each skill appears only once across the entire plan.

Return ONLY a valid JSON object matching this exact schema:
{{
  "plan_summary": "Concise 2-3 sentence overview of this personalized learning roadmap for {role} at {company}.",
  "overall_learning_priority": "HIGH",
  "phases": [
    {{
      "phase_id": "phase-1",
      "name": "Phase 1 — Foundations & Core Principles",
      "description": "Establish necessary system fundamentals before diving into cloud tooling.",
      "order": 1,
      "skills": [
        {{
          "skill_id": "skill-1",
          "name": "Skill Name",
          "category": "Technical Skills / Programming Languages / Tools / Knowledge Areas / Role-Specific Technologies",
          "priority": "HIGH",
          "current_level": "NOT_STARTED",
          "target_level": "INTERMEDIATE",
          "why_needed": "Explanation of why this skill is needed for {company} {role}.",
          "topics": ["Topic 1", "Topic 2", "Topic 3", "Topic 4"],
          "practice_tasks": ["Concrete task connected to project."],
          "expected_outcome": "Outcome after completing this skill.",
          "estimated_effort": "1-2 Weeks",
          "status": "NOT_STARTED"
        }}
      ]
    }}
  ]
}}
"""

    def parse_gemini_learning_plan_response(text):
        cleaned = clean_json_text(text)
        data = json.loads(cleaned)
        if validate_learning_plan_json(data):
            return clean_and_normalize_learning_plan(data)
        logger.warning("Gemini returned JSON that failed Learning Plan schema validation.")
        return None

    try:
        raw_response = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        if raw_response:
            parsed = parse_gemini_learning_plan_response(raw_response)
            if parsed:
                return parsed
        logger.warning("Gemini failed or returned invalid schema. Falling back to rule-based Learning Plan.")
        return generate_rule_based_fallback_learning_plan(goal, profile, assessment, resume)
    except Exception as e:
        logger.error(f"Error in generate_personalized_learning_plan AI generation: {e}")
        return generate_rule_based_fallback_learning_plan(goal, profile, assessment, resume)
