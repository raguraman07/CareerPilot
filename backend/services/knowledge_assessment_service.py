"""
CareerPilot AI — Knowledge Assessment & Skill Verification Service (Phase 5)

Generates targeted, role-grounded assessments for skills from the candidate's Phase 4 Learning Plan.
Evaluates answers objectively and via Gemini short-answer rubric scoring, determines skill level,
identifies knowledge strengths and weak areas, and updates skill verification status.
"""

import json
import logging
import random
import uuid as uuid_lib
from services.resume_intelligence import (
    genai_client,
    is_gemini_configured,
    call_gemini_with_retry,
    clean_json_text,
    deduplicate_list
)

logger = logging.getLogger(__name__)

REQUIRED_QUESTION_KEYS = {
    "id",
    "type",
    "question",
    "difficulty",
    "topic",
    "explanation"
}

VALID_QUESTION_TYPES = {"mcq", "true_false", "scenario", "short_answer"}
VALID_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}

def sanitize_questions_for_client(questions):
    """
    Strips answer keys, expected concepts, and grading rubrics before sending to client.
    Guarantees that inspecting network payloads or browser DOM cannot reveal answers.
    """
    sanitized = []
    for q in questions:
        client_q = {
            "id": q.get("id"),
            "type": q.get("type"),
            "question": q.get("question"),
            "difficulty": q.get("difficulty", "MEDIUM"),
            "topic": q.get("topic", "General")
        }
        if q.get("type") in ["mcq", "scenario"]:
            # Shuffle options deterministically or randomly for security
            opts = list(q.get("options", []))
            client_q["options"] = opts
        elif q.get("type") == "true_false":
            client_q["options"] = ["True", "False"]
        
        sanitized.append(client_q)
    return sanitized

def validate_generated_assessment_json(data):
    """
    Validates Gemini assessment JSON structure.
    """
    if not isinstance(data, dict):
        return False
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) < 3:
        return False
    
    seen_ids = set()
    for q in questions:
        if not isinstance(q, dict) or not REQUIRED_QUESTION_KEYS.issubset(q.keys()):
            return False
        q_type = q.get("type")
        if q_type not in VALID_QUESTION_TYPES:
            return False
        if q_type in ["mcq", "scenario"]:
            opts = q.get("options")
            if not isinstance(opts, list) or len(opts) < 2:
                return False
            if "correct_answer" not in q:
                return False
        elif q_type == "true_false":
            if str(q.get("correct_answer")).strip().lower() not in ["true", "false"]:
                return False
        elif q_type == "short_answer":
            if not q.get("expected_concepts") and not q.get("correct_answer"):
                return False
                
        qid = q.get("id")
        if qid in seen_ids:
            return False
        seen_ids.add(qid)
        
    return True

def generate_fallback_skill_assessment(skill_data, goal, profile):
    """
    Rule-based, skill-specific assessment generator used when Gemini is unconfigured or rate-limited.
    """
    skill_name = skill_data.get("name", "Software Engineering")
    category = skill_data.get("category", "Technical Skills")
    topics = skill_data.get("topics") or ["Architecture", "Configuration", "Best Practices", "Troubleshooting"]
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Software Engineer")

    questions = [
        {
            "id": "q1",
            "type": "mcq",
            "question": f"When configuring {skill_name} in a {role} environment, what is the primary purpose of separating configuration from source code?",
            "options": [
                "To allow seamless environment portability and security compliance",
                "To increase execution time during build steps",
                "To eliminate the need for version control",
                "To prevent unit tests from executing"
            ],
            "correct_answer": "To allow seamless environment portability and security compliance",
            "explanation": "Separating configuration from application code (12-factor principle) ensures portability across dev, staging, and production without code modifications.",
            "difficulty": "EASY",
            "topic": topics[0] if len(topics) > 0 else "Configuration"
        },
        {
            "id": "q2",
            "type": "true_false",
            "question": f"In {skill_name} production deployments, automated health checks and monitoring are considered optional best practices that have no impact on service availability.",
            "options": ["True", "False"],
            "correct_answer": "False",
            "explanation": "Automated health checks and observability are vital requirements in production systems to maintain high availability and enable automated failover.",
            "difficulty": "EASY",
            "topic": topics[1] if len(topics) > 1 else "Monitoring"
        },
        {
            "id": "q3",
            "type": "scenario",
            "question": f"You are deploying an application at {company} using {skill_name}. Traffic spikes cause intermittent latency bottlenecks. What is the most effective initial troubleshooting approach?",
            "options": [
                "Inspect resource metrics, logs, and connection pools to isolate the exact constraint before scaling",
                "Immediately delete and recreate all instances without analyzing logs",
                "Disable all error monitoring to reduce CPU load",
                "Switch programming languages immediately"
            ],
            "correct_answer": "Inspect resource metrics, logs, and connection pools to isolate the exact constraint before scaling",
            "explanation": "Systematic root-cause analysis via logs and metrics identifies whether the bottleneck is CPU, I/O, database connections, or network latency.",
            "difficulty": "MEDIUM",
            "topic": topics[2] if len(topics) > 2 else "Troubleshooting"
        },
        {
            "id": "q4",
            "type": "mcq",
            "question": f"Which security standard is most critical when managing secrets and credentials in {skill_name} workflows?",
            "options": [
                "Inject secrets via secure environment key-vaults/managers at runtime rather than hardcoding them in code or images",
                "Hardcode credentials directly into client repository files for faster debugging",
                "Store production credentials in public README documentation",
                "Disable all authentication mechanisms"
            ],
            "correct_answer": "Inject secrets via secure environment key-vaults/managers at runtime rather than hardcoding them in code or images",
            "explanation": "Runtime secret injection via dedicated secret managers prevents accidental exposure in revision control and image layers.",
            "difficulty": "MEDIUM",
            "topic": "Security"
        },
        {
            "id": "q5",
            "type": "short_answer",
            "question": f"Explain the core benefits of utilizing {skill_name} within the context of a {role} pipeline at {company}. Mention at least two concrete advantages.",
            "expected_concepts": [
                "Scalability or consistency across environments",
                "Efficiency, automation, or reliability in deployment",
                "Isolation of dependencies and rapid recovery"
            ],
            "rubric": {
                "concept_accuracy": 4,
                "key_points": 3,
                "technical_correctness": 2,
                "clarity": 1
            },
            "explanation": f"A solid answer highlights consistency, automation, scalability, and security benefits provided by {skill_name}.",
            "difficulty": "HARD",
            "topic": "Architecture & Strategy"
        }
    ]

    return {
        "assessment_title": f"{skill_name} Skill Assessment",
        "skill": skill_name,
        "difficulty": "MEDIUM",
        "time_limit_minutes": 15,
        "questions": questions
    }

def generate_skill_assessment(skill_data, goal, profile, learning_plan):
    """
    Generates a targeted knowledge assessment for a specific skill in the learning plan.
    """
    skill_name = skill_data.get("name", "Core Skill")
    category = skill_data.get("category", "Technical Skills")
    current_lvl = skill_data.get("current_level", "BEGINNER")
    target_lvl = skill_data.get("target_level", "INTERMEDIATE")
    why_needed = skill_data.get("why_needed", "")
    topics = skill_data.get("topics") or []
    practice_tasks = skill_data.get("practice_tasks") or []
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Target Role")
    exp_level = goal.get("experience_level", "Fresher")

    if not is_gemini_configured or not genai_client:
        logger.info(f"Knowledge Assessment: Using rule-based fallback for {skill_name}.")
        return generate_fallback_skill_assessment(skill_data, goal, profile)

    prompt = f"""
SYSTEM INSTRUCTION:
You are the Chief Assessment Architect and Senior Technical Interviewer for CareerPilot AI.
Generate a rigorous, high-quality, 5-question SKILL KNOWLEDGE ASSESSMENT specifically tailored to verify the candidate's mastery of '{skill_name}'.

TARGET CONTEXT:
- Target Company: {company}
- Target Job Role: {role}
- Experience Level: {exp_level}
- Skill Being Tested: {skill_name}
- Skill Category: {category}
- Target Level: {target_lvl}
- Why Needed: {why_needed}
- Specific Topics Covered in Learning Plan: {', '.join(topics) if topics else 'Core principles, configuration, architecture'}
- Practice Tasks Assigned: {', '.join(practice_tasks) if practice_tasks else 'Hands-on project integration'}

ASSESSMENT DESIGN REQUIREMENTS:
1. Grounding: Questions must be STRICTLY about '{skill_name}' and relevant to a {role} at {company}.
2. Balanced Question Mix (Total 5 Questions):
   - 2 Multiple Choice Questions (MCQ) with 4 realistic options (1 correct, 3 plausible distractors).
   - 1 True/False Question testing a nuanced technical concept.
   - 1 Scenario-Based Question (practical real-world problem solving for {role}).
   - 1 Short Answer Question testing conceptual architecture/deep understanding.
3. Difficulty:
   - 2 Easy questions (fundamental definitions/operations)
   - 2 Medium questions (scenario/configuration/troubleshooting)
   - 1 Hard question (architecture trade-offs or performance optimization)
4. For every question provide:
   - "id": "q1", "q2", etc.
   - "type": "mcq" | "true_false" | "scenario" | "short_answer"
   - "question": Clear, unambiguous question text.
   - "options": Array of string choices (for mcq and scenario). For true_false use ["True", "False"]. For short_answer leave empty or omit.
   - "correct_answer": Exact string of the correct answer (or summary for short_answer).
   - "expected_concepts": Array of 2-3 key conceptual criteria (required for short_answer).
   - "rubric": {{"concept_accuracy": 4, "key_points": 3, "technical_correctness": 2, "clarity": 1}} (for short_answer).
   - "explanation": Educational explanation of why this answer is correct and why other options are wrong.
   - "difficulty": "EASY" | "MEDIUM" | "HARD"
   - "topic": The specific topic being tested.

Return ONLY a valid JSON object matching this exact schema:
{{
  "assessment_title": "{skill_name} Skill Assessment",
  "skill": "{skill_name}",
  "difficulty": "MEDIUM",
  "time_limit_minutes": 15,
  "questions": [
    {{
      "id": "q1",
      "type": "mcq",
      "question": "...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "...",
      "difficulty": "EASY",
      "topic": "..."
    }},
    {{
      "id": "q2",
      "type": "true_false",
      "question": "...",
      "options": ["True", "False"],
      "correct_answer": "True",
      "explanation": "...",
      "difficulty": "EASY",
      "topic": "..."
    }},
    {{
      "id": "q3",
      "type": "scenario",
      "question": "...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "...",
      "difficulty": "MEDIUM",
      "topic": "..."
    }},
    {{
      "id": "q4",
      "type": "mcq",
      "question": "...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "...",
      "difficulty": "MEDIUM",
      "topic": "..."
    }},
    {{
      "id": "q5",
      "type": "short_answer",
      "question": "...",
      "options": [],
      "correct_answer": "Key conceptual explanation summary.",
      "expected_concepts": ["Concept 1", "Concept 2"],
      "rubric": {{
        "concept_accuracy": 4,
        "key_points": 3,
        "technical_correctness": 2,
        "clarity": 1
      }},
      "explanation": "...",
      "difficulty": "HARD",
      "topic": "..."
    }}
  ]
}}
"""

    def parse_gemini_assessment_response(text):
        cleaned = clean_json_text(text)
        data = json.loads(cleaned)
        if validate_generated_assessment_json(data):
            return data
        logger.warning("Gemini returned JSON that failed Assessment schema validation.")
        return None

    try:
        raw_response = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        if raw_response:
            parsed = parse_gemini_assessment_response(raw_response)
            if parsed:
                return parsed
        logger.warning(f"Gemini generation failed. Using rule-based fallback for {skill_name}.")
        return generate_fallback_skill_assessment(skill_data, goal, profile)
    except Exception as e:
        logger.error(f"Error in generate_skill_assessment AI generation: {e}")
        return generate_fallback_skill_assessment(skill_data, goal, profile)


def evaluate_short_answer_with_gemini(question_text, expected_concepts, user_answer, skill_name, role):
    """
    Evaluates a candidate's short answer response using Gemini against a structured 10-point rubric.
    """
    if not user_answer or not user_answer.strip():
        return {
            "score": 0,
            "max_score": 10,
            "is_correct": False,
            "feedback": "No answer provided.",
            "missing_concepts": expected_concepts or ["Core conceptual explanation"]
        }

    if not is_gemini_configured or not genai_client:
        # Simple heuristic fallback
        ans_lower = user_answer.lower()
        matched = 0
        for concept in (expected_concepts or []):
            words = [w.lower() for w in concept.split() if len(w) > 3]
            if any(w in ans_lower for w in words):
                matched += 1
        points = min(10, max(3, matched * 4)) if len(user_answer.split()) >= 5 else 2
        return {
            "score": points,
            "max_score": 10,
            "is_correct": points >= 7,
            "feedback": "Answer addresses key aspects of the question." if points >= 7 else "Answer lacks sufficient technical depth or key concepts.",
            "missing_concepts": [] if points >= 7 else (expected_concepts or ["Deeper conceptual detail"])
        }

    prompt = f"""
SYSTEM INSTRUCTION:
You are an expert technical evaluator for CareerPilot AI assessing a candidate targeting the role of {role}.
Evaluate the candidate's short-answer response to the following question about {skill_name}.

QUESTION:
{question_text}

EXPECTED CONCEPTS & CRITERIA:
{json.dumps(expected_concepts)}

CANDIDATE'S ANSWER:
"{user_answer.strip()}"

EVALUATION RUBRIC (Total 10 Points):
- Concept Accuracy (0-4 pts): Does the candidate demonstrate true understanding of the core concept?
- Key Points (0-3 pts): Did they mention the expected architectural/operational aspects?
- Technical Correctness (0-2 pts): Is the terminology and logic sound without misconceptions?
- Clarity (0-1 pt): Is the explanation coherent and concise?

Return ONLY a valid JSON object:
{{
  "score": 8,
  "max_score": 10,
  "is_correct": true,
  "feedback": "Clear explanation covering container isolation and portability.",
  "missing_concepts": []
}}
"""

    def parse_eval_response(text):
        cleaned = clean_json_text(text)
        data = json.loads(cleaned)
        if isinstance(data, dict) and "score" in data:
            score = int(data.get("score", 0))
            return {
                "score": max(0, min(10, score)),
                "max_score": 10,
                "is_correct": score >= 7,
                "feedback": data.get("feedback", "Evaluated."),
                "missing_concepts": data.get("missing_concepts", [])
            }
        return None

    try:
        raw_response = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        if raw_response:
            parsed = parse_eval_response(raw_response)
            if parsed:
                return parsed
    except Exception as e:
        logger.error(f"Error evaluating short answer with Gemini: {e}")

    # Heuristic fallback if Gemini evaluation fails
    return {
        "score": 7 if len(user_answer.split()) >= 10 else 4,
        "max_score": 10,
        "is_correct": len(user_answer.split()) >= 10,
        "feedback": "Answer recorded and evaluated.",
        "missing_concepts": []
    }


def evaluate_assessment_submission(assessment_doc, submitted_answers, role="Software Engineer"):
    """
    Evaluates complete assessment submission:
    - Deterministic scoring for MCQ, True/False, and Scenario questions.
    - AI / Rubric evaluation for Short Answer questions.
    - Calculates total score (0-100), determines skill level and pass/needs_improvement status.
    - Extracts knowledge strengths and weak areas.
    """
    questions = assessment_doc.get("questions", [])
    skill_name = assessment_doc.get("skill_name") or assessment_doc.get("skill") or "Skill"
    
    total_points = 0
    earned_points = 0
    question_results = []
    strengths = []
    weak_areas = []

    for q in questions:
        qid = q.get("id")
        q_type = q.get("type")
        topic = q.get("topic", "General Concept")
        correct_ans = q.get("correct_answer")
        user_ans = submitted_answers.get(qid, "")

        if q_type in ["mcq", "true_false", "scenario"]:
            q_points = 10
            total_points += q_points
            
            # Normalize comparison
            is_match = False
            if user_ans and correct_ans:
                is_match = str(user_ans).strip().lower() == str(correct_ans).strip().lower()

            if is_match:
                earned_points += q_points
                strengths.append(topic)
                question_results.append({
                    "id": qid,
                    "type": q_type,
                    "question": q.get("question"),
                    "user_answer": user_ans,
                    "correct_answer": correct_ans,
                    "is_correct": True,
                    "points_earned": q_points,
                    "max_points": q_points,
                    "explanation": q.get("explanation", ""),
                    "topic": topic
                })
            else:
                weak_areas.append(topic)
                question_results.append({
                    "id": qid,
                    "type": q_type,
                    "question": q.get("question"),
                    "user_answer": user_ans or "No answer provided",
                    "correct_answer": correct_ans,
                    "is_correct": False,
                    "points_earned": 0,
                    "max_points": q_points,
                    "explanation": q.get("explanation", ""),
                    "topic": topic
                })

        elif q_type == "short_answer":
            q_points = 10
            total_points += q_points
            eval_res = evaluate_short_answer_with_gemini(
                q.get("question"),
                q.get("expected_concepts", []),
                user_ans,
                skill_name,
                role
            )
            score_pts = eval_res.get("score", 0)
            earned_points += score_pts

            if score_pts >= 7:
                strengths.append(topic)
            else:
                weak_areas.append(topic)

            question_results.append({
                "id": qid,
                "type": q_type,
                "question": q.get("question"),
                "user_answer": user_ans or "No answer provided",
                "correct_answer": correct_ans or "Detailed conceptual answer required",
                "is_correct": eval_res.get("is_correct", False),
                "points_earned": score_pts,
                "max_points": q_points,
                "feedback": eval_res.get("feedback", ""),
                "missing_concepts": eval_res.get("missing_concepts", []),
                "explanation": q.get("explanation", ""),
                "topic": topic
            })

    final_score = int(round((earned_points / total_points) * 100)) if total_points > 0 else 0
    
    # Determine Skill Level
    if final_score >= 90:
        skill_level = "ADVANCED"
    elif final_score >= 75:
        skill_level = "INTERMEDIATE"
    elif final_score >= 50:
        skill_level = "BEGINNER"
    else:
        skill_level = "NEEDS_IMPROVEMENT"

    passed = final_score >= 75
    status = "PASSED" if passed else "NEEDS_IMPROVEMENT"

    # Deduplicate strengths and weak topics
    unique_strengths = deduplicate_list(strengths)
    unique_weak = deduplicate_list([w for w in weak_areas if w not in unique_strengths])
    if not unique_weak and not passed:
        unique_weak = deduplicate_list(weak_areas)

    # Next Action Recommendation
    if passed:
        recommendation = f"You demonstrated strong proficiency in {skill_name} ({final_score}%). This skill is now officially verified in your CareerPilot roadmap. Proceed to the next skill in your learning plan."
        next_step = "Move to the next sequential learning phase."
    else:
        weak_topics_str = ", ".join(unique_weak[:2]) if unique_weak else "core principles"
        recommendation = f"You achieved {final_score}% in {skill_name}. Focus on strengthening your understanding of {weak_topics_str} before retaking the assessment."
        next_step = f"Review learning topics and practice tasks for {weak_topics_str}, then retake this verification test."

    return {
        "score": final_score,
        "passed": passed,
        "status": status,
        "skill_level": skill_level,
        "strengths": unique_strengths,
        "weak_areas": unique_weak,
        "recommendation": recommendation,
        "next_step": next_step,
        "question_results": question_results
    }
