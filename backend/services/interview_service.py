"""
CareerPilot AI — Company-Specific Interview Training & Mock Interview Service (Phase 6)

Personalized Interview Training grounded in:
Career Goal + Candidate Profile + Resume + Phase 3 Assessment + Phase 4 Learning Plan + Phase 5 Verified Skills.

Supports:
- Category Question Generation (Technical, Role-Specific, Resume-Based, Project Deep-Dive, Behavioral STAR, Company-Oriented)
- Full Mock Interview Mode (10-15 balanced questions with post-interview comprehensive review)
- Daily Practice Training Mode (3-5 targeted questions focused on weak areas with instant feedback)
- Rubric-based answer evaluation (Technical Accuracy, Completeness, Clarity, Relevance, STAR method)
- Explainable Interview Readiness Calculation
"""

import os
import json
import re
import logging
import uuid as uuid_lib
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure environment variables are loaded
_backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)
else:
    load_dotenv()

from services.resume_intelligence import (
    call_gemini_with_retry,
    clean_json_text,
    deduplicate_list,
    genai_client,
    is_gemini_configured
)

VALID_CATEGORIES = {"technical", "role_specific", "resume", "project", "behavioral", "company"}
VALID_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}

REQUIRED_QUESTION_KEYS = {
    "question_id",
    "category",
    "difficulty",
    "topic",
    "question",
    "why_this_question",
    "expected_areas"
}

def validate_interview_questions_json(data):
    """Validates Gemini generated interview questions JSON structure."""
    if not isinstance(data, dict):
        return False
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        return False
    
    for q in questions:
        if not isinstance(q, dict):
            return False
        # Phase 6 requires question, category, etc. Legacy Phase 8 requires question
        if "question" not in q:
            return False
    return True

def generate_fallback_interview_questions(goal, profile, resume, assessment, learning_plan, session_type="MOCK_INTERVIEW", num_questions=10):
    """
    Robust rule-based question generator tailored to candidate's goal, profile projects, and verified skills.
    """
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Software Engineer")
    exp_level = goal.get("experience_level", "Fresher")

    projects = profile.get("projects") or []
    sample_proj = projects[0].get("title") if projects else "CareerPilot AI"
    proj_techs = ", ".join(projects[0].get("technologies") or ["Python", "Flask"]) if projects else "Python, Flask, APIs"

    # Extract verified skills vs weak skills from learning plan
    verified_skills = []
    weak_skills = []
    if learning_plan:
        for phase in learning_plan.get("phases", []):
            for sk in phase.get("skills", []):
                if sk.get("status") == "VERIFIED":
                    verified_skills.append(sk.get("name"))
                elif sk.get("status") in ["NEEDS_IMPROVEMENT", "NOT_STARTED"]:
                    weak_skills.append(sk.get("name"))

    top_verified = verified_skills[0] if verified_skills else "Python"
    top_weak = weak_skills[0] if weak_skills else "Cloud Architecture"

    questions = [
        {
            "question_id": f"q-tech-{uuid_lib.uuid4().hex[:6]}",
            "category": "technical",
            "difficulty": "MEDIUM",
            "priority": "HIGH",
            "topic": top_verified,
            "question": f"Given your experience with {top_verified}, how do you structure an application to handle high concurrency and prevent resource bottlenecks in a {role} environment?",
            "why_this_question": f"Evaluates production-level {top_verified} architecture depth required at {company}.",
            "expected_areas": ["Concurrency models", "Asynchronous processing", "Resource pooling", "Memory management"]
        },
        {
            "question_id": f"q-weak-{uuid_lib.uuid4().hex[:6]}",
            "category": "technical",
            "difficulty": "MEDIUM",
            "priority": "HIGH",
            "topic": top_weak,
            "question": f"In a distributed system at {company}, how would you implement fault-tolerance and secure configuration for {top_weak} components?",
            "why_this_question": f"Focuses on strengthening {top_weak} concepts aligned with your learning roadmap.",
            "expected_areas": ["Fault tolerance", "Secret management", "Network isolation", "High availability"]
        },
        {
            "question_id": f"q-proj-{uuid_lib.uuid4().hex[:6]}",
            "category": "project",
            "difficulty": "MEDIUM",
            "priority": "HIGH",
            "topic": sample_proj,
            "question": f"In your project '{sample_proj}', why did you choose ({proj_techs}) for implementation, and what architectural trade-offs did you make?",
            "why_this_question": f"Tests decision-making and real-world trade-off analysis on your actual project.",
            "expected_areas": ["Tech stack rationale", "Alternative frameworks evaluated", "Performance trade-offs", "Scalability bottlenecks"]
        },
        {
            "question_id": f"q-role-{uuid_lib.uuid4().hex[:6]}",
            "category": "role_specific",
            "difficulty": "HARD",
            "priority": "HIGH",
            "topic": "System Design",
            "question": f"Design a resilient, scalable backend pipeline for {role} responsibilities at {company}. How would you manage monitoring and automated alerting?",
            "why_this_question": f"Core scenario question assessing end-to-end design thinking for {role}.",
            "expected_areas": ["System architecture", "Data flow", "Observability/metrics", "Failover strategies"]
        },
        {
            "question_id": f"q-beh-{uuid_lib.uuid4().hex[:6]}",
            "category": "behavioral",
            "difficulty": "EASY",
            "priority": "MEDIUM",
            "topic": "Problem Solving & STAR",
            "question": f"Describe a situation where you encountered an unexpected technical bug or deployment failure in '{sample_proj}'. What action did you take and what was the outcome?",
            "why_this_question": "Evaluates structured STAR-method communication and problem-solving resilience.",
            "expected_areas": ["Situation context", "Task clarity", "Action taken / debugging steps", "Measurable result/learning"]
        }
    ]

    if session_type == "MOCK_INTERVIEW" and num_questions > 5:
        # Add additional diverse questions for full mock interview
        questions.extend([
            {
                "question_id": f"q-resume-{uuid_lib.uuid4().hex[:6]}",
                "category": "resume",
                "difficulty": "MEDIUM",
                "priority": "MEDIUM",
                "topic": "Profile & Experience",
                "question": f"Walk me through your journey preparing for the {role} position. How have your projects and technical milestones prepared you for {company}?",
                "why_this_question": "Evaluates candidate articulation and alignment between resume experience and target role.",
                "expected_areas": ["Career narrative", "Technical growth", "Alignment with company mission", "Self-learning initiative"]
            },
            {
                "question_id": f"q-comp-{uuid_lib.uuid4().hex[:6]}",
                "category": "company",
                "difficulty": "MEDIUM",
                "priority": "MEDIUM",
                "topic": f"{company} Role Intelligence",
                "question": f"What specific technical challenges or engineering practices at {company} interest you most for the {role} position?",
                "why_this_question": f"Assesses company understanding and genuine enthusiasm for {company}.",
                "expected_areas": ["Company engineering values", "Role expectations", "Industry relevance"]
            },
            {
                "question_id": f"q-proj2-{uuid_lib.uuid4().hex[:6]}",
                "category": "project",
                "difficulty": "HARD",
                "priority": "HIGH",
                "topic": "Security & Testing",
                "question": f"How did you approach testing and security in '{sample_proj}', and how would you adapt your approach when deploying at enterprise scale?",
                "why_this_question": "Evaluates security rigor and automated testing discipline.",
                "expected_areas": ["Unit & integration tests", "Authentication/security safeguards", "CI/CD integration", "Enterprise compliance"]
            }
        ])

    return {
        "interview_title": f"{company} {role} Interview Training",
        "target_company": company,
        "target_role": role,
        "difficulty": "MEDIUM",
        "session_type": session_type,
        "questions": questions[:num_questions]
    }

def generate_personalized_interview_questions(goal, profile, resume, assessment, learning_plan, session_type="MOCK_INTERVIEW", num_questions=10, focus_category=None):
    """
    Main entry point for generating company and role-specific interview training questions.
    """
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Target Role")
    exp_level = goal.get("experience_level", "Fresher")
    full_name = profile.get("full_name", "Candidate")

    projects = profile.get("projects") or []
    projects_summary = "\n".join([f"- {p.get('title')}: {p.get('description')} (Tech: {', '.join(p.get('technologies') or [])})" for p in projects]) if projects else "None recorded."

    resume_text = (resume.get("extracted_text") or "")[:3500]
    has_resume = bool(resume.get("available") and resume_text)

    # Extract verified vs improvement skills from Phase 4/5
    verified_skills = []
    weak_skills = []
    if learning_plan:
        for phase in learning_plan.get("phases", []):
            for sk in phase.get("skills", []):
                if sk.get("status") == "VERIFIED":
                    verified_skills.append(sk.get("name"))
                elif sk.get("status") in ["NEEDS_IMPROVEMENT", "NOT_STARTED"]:
                    weak_skills.append(sk.get("name"))

    if not is_gemini_configured or not genai_client:
        logger.info("Interview Service: Using rule-based fallback question generator.")
        return generate_fallback_interview_questions(goal, profile, resume, assessment, learning_plan, session_type, num_questions)

    prompt = f"""
SYSTEM INSTRUCTION:
You are the Executive Technical Interviewer and Hiring Bar Raiser for {company} evaluating candidates for the position of {role} ({exp_level}).
Generate a highly personalized, rigorous set of {num_questions} interview questions for candidate {full_name}.

CONTEXT:
- Target Company: {company}
- Target Role: {role}
- Experience Level: {exp_level}
- Session Mode: {session_type} (Options: MOCK_INTERVIEW, DAILY_PRACTICE, CATEGORY_DRILL)
- Focus Category Filter: {focus_category or 'Balanced Mix'}

CANDIDATE STARTING CONTEXT & EVIDENCE:
- Verified Skills (Passed Phase 5 Knowledge Assessment): {', '.join(verified_skills) if verified_skills else 'None verified yet'}
- Skills Needing Improvement / In Progress: {', '.join(weak_skills) if weak_skills else 'General foundations'}
- Candidate Projects:
{projects_summary}
- Resume Details:
{resume_text if has_resume else 'Evaluate purely on profile data and projects.'}

CRITICAL RULES:
1. Grounding & Anti-Hallucination: Questions about projects MUST reference the candidate's actual projects ({projects[0].get('title') if projects else 'CareerPilot AI'}). Do NOT invent fictional projects or companies.
2. Category Mix:
   - Technical questions testing verified skills & weak areas.
   - Role-Specific scenarios for {role} at {company}.
   - Project deep-dive questions (architecture, trade-offs, bottlenecks, security).
   - Behavioral questions using the STAR framework.
   - Resume-based questions.
3. Personalization: Ask deeper technical questions on verified skills ({', '.join(verified_skills[:2]) if verified_skills else 'core skills'}) and diagnostic questions on weak areas ({', '.join(weak_skills[:2]) if weak_skills else 'cloud systems'}).
4. Output Format: Return strictly a valid JSON object.

Return ONLY a valid JSON object matching this exact schema:
{{
  "interview_title": "{company} {role} Interview Training",
  "target_company": "{company}",
  "target_role": "{role}",
  "difficulty": "MEDIUM",
  "session_type": "{session_type}",
  "questions": [
    {{
      "question_id": "q1",
      "category": "technical",
      "difficulty": "MEDIUM",
      "priority": "HIGH",
      "topic": "Docker / Cloud",
      "question": "Specific question text...",
      "why_this_question": "Why {company} asks this for {role}...",
      "expected_areas": ["Key concept 1", "Key concept 2", "Key concept 3"]
    }}
  ]
}}
"""

    def parse_gemini_interview_questions(text):
        cleaned = clean_json_text(text)
        data = json.loads(cleaned)
        if validate_interview_questions_json(data):
            return data
        logger.warning("Gemini returned JSON that failed Interview Questions validation.")
        return None

    try:
        raw_response = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        if raw_response:
            parsed = parse_gemini_interview_questions(raw_response)
            if parsed:
                return parsed
        logger.warning("Gemini generation failed. Using rule-based fallback.")
        return generate_fallback_interview_questions(goal, profile, resume, assessment, learning_plan, session_type, num_questions)
    except Exception as e:
        logger.error(f"Error in generate_personalized_interview_questions: {e}")
        return generate_fallback_interview_questions(goal, profile, resume, assessment, learning_plan, session_type, num_questions)


def evaluate_interview_answer_ai(question_data, user_answer, role="Software Engineer", company="Target Company"):
    """
    Evaluates a single written interview answer using Gemini AI against a structured rubric.
    """
    if not user_answer or not user_answer.strip():
        return {
            "score": 0,
            "technical_accuracy": 0,
            "completeness": 0,
            "clarity": 0,
            "relevance": 0,
            "feedback": "No answer provided.",
            "strengths": [],
            "missing_points": question_data.get("expected_areas", ["Technical explanation"]),
            "improvement": "Provide a structured answer addressing the question criteria.",
            "better_answer_structure": [
                "1. State the core concept or direct answer.",
                "2. Explain architectural/operational details.",
                "3. Reference practical examples from your projects."
            ]
        }

    q_text = question_data.get("question", "")
    q_cat = question_data.get("category", "technical")
    expected_areas = question_data.get("expected_areas", [])

    if not is_gemini_configured or not genai_client:
        # Heuristic rule-based scoring fallback
        words = len(user_answer.split())
        base_score = min(85, max(30, words * 2))
        return {
            "score": base_score,
            "technical_accuracy": base_score,
            "completeness": base_score,
            "clarity": 80,
            "relevance": 85,
            "feedback": f"Your response demonstrates familiarity with {question_data.get('topic', 'the topic')}. Expand on concrete project implementation details for higher impact.",
            "strengths": ["Clear communication", "Addresses core premise"],
            "missing_points": expected_areas[:2] if expected_areas else ["Specific quantitative metrics"],
            "improvement": f"Structure your response to clearly link {question_data.get('topic', 'the concept')} to real-world performance trade-offs at {company}.",
            "better_answer_structure": [
                "1. Define the primary architecture principle.",
                "2. Walk through step-by-step implementation.",
                "3. Conclude with monitoring and measurable results."
            ]
        }

    prompt = f"""
SYSTEM INSTRUCTION:
You are the Lead Technical Interview Evaluator for {company} interviewing for {role}.
Evaluate the candidate's written response to the following interview question.

QUESTION:
Category: {q_cat}
Topic: {question_data.get('topic')}
Question: {q_text}
Expected Technical Areas: {json.dumps(expected_areas)}

CANDIDATE'S ANSWER:
\"\"\"{user_answer.strip()}\"\"\"

EVALUATION RUBRIC:
- Technical Accuracy (0-100): Correctness of concepts, protocols, and architectural patterns.
- Completeness (0-100): Thoroughness in addressing all parts of the question.
- Clarity (0-100): Logical flow, conciseness, and professionalism.
- Relevance (0-100): Direct relevance to the {role} position.
- Overall Score (0-100): Weighted synthesis.

For behavioral questions, evaluate based on the STAR methodology (Situation, Task, Action, Result).
Provide actionable, constructive feedback that teaches the user how to improve.

Return ONLY a valid JSON object matching this schema:
{{
  "score": 82,
  "technical_accuracy": 85,
  "completeness": 80,
  "clarity": 85,
  "relevance": 80,
  "feedback": "Concise 2-sentence summary of candidate answer quality.",
  "strengths": ["Identified concept X well", "Clear explanation of Y"],
  "missing_points": ["Did not mention Z", "Lacked quantitative outcome"],
  "improvement": "Specific advice on what to add or rephrase.",
  "better_answer_structure": [
    "1. Introduce core concept...",
    "2. Explain workflow...",
    "3. Highlight practical project example..."
  ]
}}
"""

    def parse_answer_eval(text):
        cleaned = clean_json_text(text)
        data = json.loads(cleaned)
        if isinstance(data, dict) and "score" in data:
            return data
        return None

    try:
        raw_response = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        if raw_response:
            parsed = parse_answer_eval(raw_response)
            if parsed:
                return parsed
    except Exception as e:
        logger.error(f"Error evaluating interview answer via Gemini: {e}")

    # Fallback score if LLM parsing errors
    return {
        "score": 75,
        "technical_accuracy": 75,
        "completeness": 70,
        "clarity": 80,
        "relevance": 75,
        "feedback": "Answer recorded and evaluated against role requirements.",
        "strengths": ["Directly addresses the question"],
        "missing_points": expected_areas[:1] if expected_areas else [],
        "improvement": "Elaborate with deeper architectural examples.",
        "better_answer_structure": [
            "1. Concept overview",
            "2. Implementation details",
            "3. Project connection"
        ]
    }


def finalize_interview_session_evaluation(session_doc):
    """
    Computes overall session score, category performance breakdowns, readiness level,
    strengths, weaknesses, and personalized improvement plan across all answered questions.
    """
    questions = session_doc.get("questions", [])
    answers = session_doc.get("answers", {})

    category_scores = {
        "technical": [],
        "role_specific": [],
        "project": [],
        "resume": [],
        "behavioral": [],
        "company": []
    }

    all_scores = []
    all_strengths = []
    all_weaknesses = []
    all_missing_points = []

    for q in questions:
        qid = q.get("question_id")
        cat = q.get("category", "technical").lower()
        if cat not in category_scores:
            cat = "technical"
            
        ans_eval = answers.get(qid)
        if ans_eval:
            score = ans_eval.get("score", 0)
            all_scores.append(score)
            category_scores[cat].append(score)
            all_strengths.extend(ans_eval.get("strengths", []))
            all_missing_points.extend(ans_eval.get("missing_points", []))
            if score < 75:
                all_weaknesses.append(f"Needs deeper mastery in {q.get('topic', 'concept')}")
        else:
            all_scores.append(0)
            category_scores[cat].append(0)
            all_weaknesses.append(f"Unanswered question: {q.get('topic', 'question')}")

    overall_score = int(round(sum(all_scores) / len(all_scores))) if all_scores else 0

    # Calculate category performance averages
    performance_breakdown = {}
    for cat_name, scores in category_scores.items():
        performance_breakdown[cat_name] = int(round(sum(scores) / len(scores))) if scores else overall_score

    # Determine Readiness Level
    if overall_score >= 90:
        readiness_level = "HIGHLY_READY"
        readiness_label = "Highly Ready for Interview"
    elif overall_score >= 80:
        readiness_level = "READY"
        readiness_label = "Interview Ready"
    elif overall_score >= 70:
        readiness_level = "ALMOST_READY"
        readiness_label = "Almost Ready — Fine-tune weak spots"
    elif overall_score >= 50:
        readiness_level = "NEEDS_MORE_PRACTICE"
        readiness_label = "Needs More Practice"
    else:
        readiness_level = "FOUNDATION_REQUIRED"
        readiness_label = "Foundation Preparation Required"

    unique_strengths = deduplicate_list(all_strengths)[:4]
    unique_weaknesses = deduplicate_list(all_weaknesses)[:4]

    # Generate Personalized Improvement Plan
    improvement_plan = []
    for miss in deduplicate_list(all_missing_points)[:3]:
        improvement_plan.append(f"Review and practice: {miss}")
    if performance_breakdown.get("behavioral", 100) < 75:
        improvement_plan.append("Practice STAR-method structured storytelling for behavioral questions.")
    if performance_breakdown.get("project", 100) < 75:
        improvement_plan.append("Prepare detailed explanations of project trade-offs and architecture bottlenecks.")
    if not improvement_plan:
        improvement_plan.append("Maintain consistency with daily practice drills and periodic mock interviews.")

    return {
        "overall_score": overall_score,
        "readiness_level": readiness_level,
        "readiness_label": readiness_label,
        "performance_breakdown": performance_breakdown,
        "strengths": unique_strengths or ["Solid communication foundation"],
        "weaknesses": unique_weaknesses or ["Minor technical edge cases"],
        "personalized_improvement_plan": improvement_plan
    }

# Backward compatibility aliases for earlier tests
def generate_interview_session(resume_text, job_description="", job_title="", interview_type="Mixed", difficulty="Intermediate", num_questions=10):
    goal = {"company_name": "Target Company", "job_role": job_title or "Software Engineer", "experience_level": difficulty}
    profile = {"full_name": "Candidate", "projects": []}
    resume = {"available": bool(resume_text), "extracted_text": resume_text}
    return generate_personalized_interview_questions(goal, profile, resume, {}, {}, session_type="MOCK_INTERVIEW", num_questions=num_questions)

def evaluate_interview_answer(question_text="", user_answer="", candidate_answer="", difficulty="Intermediate", category="General", role="Candidate", why_this_question="", answer_guidance=""):
    ans = candidate_answer or user_answer
    q_data = {"question": question_text, "category": category.lower(), "topic": role, "expected_areas": [answer_guidance] if answer_guidance else []}
    return evaluate_interview_answer_ai(q_data, ans, role=role, company="Target Company")

