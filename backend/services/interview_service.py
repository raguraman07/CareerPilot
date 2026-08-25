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
        logger.info("Interview Service: Official google.genai client initialized.")
    except Exception as client_err:
        logger.warning(f"Interview Service: google.genai client initialization failed: {client_err}")
elif not is_gemini_configured:
    logger.warning("Interview Service: GEMINI_API_KEY is not configured or is placeholder.")


def generate_interview_session(resume_text, job_description="", job_title="", interview_type="Mixed", difficulty="Intermediate", num_questions=10):
    """
    Generates dynamic personalized interview questions, preparation tips, and weaknesses 
    using Gemini AI based on the candidate's resume and job requirements.
    """
    if not is_gemini_configured or not genai_client:
        raise ValueError("Gemini API key is not configured.")

    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is empty.")

    try:
        num_q = max(3, min(20, int(num_questions)))
    except (ValueError, TypeError):
        num_q = 10

    prompt = f"""You are an expert technical interviewer, recruiter, HR interviewer, and career coach.

Generate a personalized interview preparation session for the candidate.

Use the candidate's actual resume and the supplied job description.

Questions must be relevant to the candidate's actual background and the target position.

Do not use a predefined question bank.
Do not assume technologies, skills, or projects that are not present in the resume or job description.
Prioritize important skills and responsibilities from the job description.
Ask questions that allow the interviewer to evaluate the candidate's actual experience, projects, skills, problem-solving ability, communication, and suitability for the role.

For resume-based questions, reference only information actually present in the resume. Do not invent candidate experience or projects.

Provide helpful answer guidance, but do not fabricate candidate-specific answers (e.g. advise candidate to reference their real project decisions).

Target Position / Title: {job_title if job_title else "Target Role"}
Interview Category Focus: {interview_type} (Options: Mixed, Technical, Behavioral, HR)
Difficulty Level: {difficulty} (Options: Beginner, Intermediate, Advanced)
Total Questions Requested: {num_q}

Candidate Resume Text:
\"\"\"
{resume_text.strip()}
\"\"\"

Target Job Description:
\"\"\"
{job_description.strip() if job_description else "General industry role aligned with candidate profile"}
\"\"\"

Return ONLY a single valid JSON object matching this exact structure:

{{
  "interview_title": "Custom Title for Interview Session",
  "difficulty": "{difficulty}",
  "interview_type": "{interview_type}",
  "questions": [
    {{
      "id": 1,
      "category": "Technical",
      "question": "Question text customized for candidate and job?",
      "why_this_question": "Why the interviewer asks this question",
      "what_interviewer_is_evaluating": "What skills or traits are being assessed",
      "answer_guidance": "Clear advice on how to structure the response",
      "follow_up_questions": ["Follow-up question 1", "Follow-up question 2"]
    }}
  ],
  "overall_preparation_tips": ["Tip 1", "Tip 2"],
  "areas_to_prepare": ["Area 1", "Area 2"],
  "potential_weaknesses": ["Weakness 1", "Weakness 2"],
  "summary": "2-3 sentence overview of this interview preparation session."
}}

Constraints:
1. "questions" array MUST contain exactly {num_q} customized questions.
2. Categories should correspond to the requested focus: {interview_type}. If "Mixed", mix Technical, Behavioral, HR, and Resume-Based.
3. Return ONLY raw valid JSON with no markdown syntax.
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
        logger.error(f"Gemini API call failed during interview generation: {api_err}")
        raise RuntimeError("AI interview preparation is temporarily unavailable. Please try again.")

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
        logger.error(f"Failed to parse Gemini JSON output for interview generation: {json_err}")
        raise ValueError("Invalid JSON response from Gemini AI.")

    # Sanitize and validate questions
    questions = parsed.get("questions") or []
    if not isinstance(questions, list) or len(questions) == 0:
        raise ValueError("No questions generated by Gemini AI.")

    sanitized_q = []
    for idx, q in enumerate(questions):
        if isinstance(q, dict):
            sanitized_q.append({
                "id": q.get("id") or (idx + 1),
                "category": str(q.get("category") or "Technical").strip(),
                "question": str(q.get("question") or "").strip(),
                "why_this_question": str(q.get("why_this_question") or "").strip(),
                "what_interviewer_is_evaluating": str(q.get("what_interviewer_is_evaluating") or "").strip(),
                "answer_guidance": str(q.get("answer_guidance") or "").strip(),
                "follow_up_questions": list(q.get("follow_up_questions") or [])
            })

    from backend.services.resume_intelligence import deduplicate_list

    parsed["questions"] = sanitized_q
    parsed["interview_title"] = str(parsed.get("interview_title") or f"{interview_type} Interview ({difficulty})").strip()
    parsed["overall_preparation_tips"] = deduplicate_list(parsed.get("overall_preparation_tips") or [])
    parsed["areas_to_prepare"] = deduplicate_list(parsed.get("areas_to_prepare") or [])
    parsed["potential_weaknesses"] = deduplicate_list(parsed.get("potential_weaknesses") or [])
    parsed["summary"] = str(parsed.get("summary") or "").strip()

    return parsed


def evaluate_interview_answer(question_text, candidate_answer, why_this_question="", answer_guidance="", resume_text="", job_description=""):
    """
    Evaluates candidate's typed practice answer semantically using Gemini AI.
    Returns structured feedback with numerical score (0-100), strengths, weaknesses, and improvement guidance.
    """
    if not is_gemini_configured or not genai_client:
        raise ValueError("Gemini API key is not configured.")

    if not candidate_answer or not candidate_answer.strip():
        raise ValueError("Candidate answer is empty.")

    prompt = f"""You are an expert technical interviewer, recruiter, and candidate coach.

Evaluate the candidate's practice interview answer semantically based on relevance, clarity, completeness, technical accuracy, communication, and structure.

Question Asked:
\"{question_text}\"

Question Intent / Evaluation Criteria:
\"{why_this_question}\"

Expected Answer Guidance:
\"{answer_guidance}\"

Candidate's Answer:
\"\"\"
{candidate_answer.strip()}
\"\"\"

Evaluate the answer objectively.
Do not use fixed keyword matching. Evaluate semantic depth and accuracy.

Return ONLY a single valid JSON object matching this exact schema:

{{
  "score": 82,
  "strengths": ["Clear explanation of concept", "Good structure"],
  "weaknesses": ["Missed discussion on edge cases"],
  "feedback": "Detailed 2-3 sentence evaluation feedback on performance.",
  "improved_answer_guidance": "Actionable advice on how candidate can improve this answer.",
  "follow_up_question": "Logical follow-up question the interviewer might ask."
}}

Constraints:
1. "score" MUST be an integer between 0 and 100 representing answer quality.
2. Return ONLY raw valid JSON with no markdown formatting.
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
        logger.error(f"Gemini API call failed during answer evaluation: {api_err}")
        raise RuntimeError("AI answer evaluation is temporarily unavailable. Please try again.")

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
        logger.error(f"Failed to parse Gemini JSON output for answer evaluation: {json_err}")
        raise ValueError("Invalid JSON response from Gemini AI.")

    try:
        raw_score = int(parsed.get("score", 0))
        score = max(0, min(100, raw_score))
    except (ValueError, TypeError):
        score = 60

    parsed["score"] = score
    parsed["strengths"] = list(parsed.get("strengths") or [])
    parsed["weaknesses"] = list(parsed.get("weaknesses") or [])
    parsed["feedback"] = str(parsed.get("feedback") or "").strip()
    parsed["improved_answer_guidance"] = str(parsed.get("improved_answer_guidance") or "").strip()
    parsed["follow_up_question"] = str(parsed.get("follow_up_question") or "").strip()

    return parsed
