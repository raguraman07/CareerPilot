import os
import re
import logging
try:
    from backend.services.career_context_service import fetch_user_career_data
except ImportError:
    from services.career_context_service import fetch_user_career_data

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
        logger.info("RAG Service: Official google.genai client initialized.")
    except Exception as client_err:
        logger.warning(f"RAG Service: google.genai client initialization failed: {client_err}")
elif not is_gemini_configured:
    logger.warning("RAG Service: GEMINI_API_KEY is not configured or is placeholder.")


def build_rag_context(user_data, question):
    """
    Selects relevant career context sections based on question intent
    and formats a structured USER CAREER CONTEXT string for Gemini.
    Returns (context_string, sources_used_list).
    """
    q_lower = question.lower()
    sources_used = []
    context_blocks = []

    # Detect user intent
    is_resume_query = any(k in q_lower for k in ["resume", "summary", "experience", "education", "format", "profile", "projects", "bullet"])
    is_ats_query = any(k in q_lower for k in ["ats", "score", "keyword", "parser", "compatibility", "warning"])
    is_jobmatch_query = any(k in q_lower for k in ["job", "match", "skill gap", "missing skill", "requirement", "target", "role", "position"])
    is_interview_query = any(k in q_lower for k in ["interview", "question", "answer", "behavioral", "technical", "prep", "practice", "mock"])

    # If general question, default to retrieving resume, job matches, and skill gaps
    if not (is_resume_query or is_ats_query or is_jobmatch_query or is_interview_query):
        is_resume_query = True
        is_jobmatch_query = True

    # 1. Resume Context
    resumes = user_data.get("resumes") or []
    if resumes and (is_resume_query or is_jobmatch_query or is_interview_query):
        latest_res = resumes[0]
        context_blocks.append(f"--- RESUME (Filename: {latest_res.get('filename')}) ---\n{latest_res.get('extracted_text')}")
        sources_used.append("Resume Content")

    # 2. Resume Analysis Context
    analyses = user_data.get("analyses") or []
    if analyses and is_resume_query:
        latest_ana = analyses[0]
        ana_text = f"--- RESUME ANALYSIS ---\nSummary: {latest_ana.get('summary')}\nTechnical Skills Found: {', '.join(latest_ana.get('technical_skills') or [])}\nStrengths: {', '.join(latest_ana.get('strengths') or [])}\nWeaknesses: {', '.join(latest_ana.get('weaknesses') or [])}\nRecommendations: {', '.join(latest_ana.get('recommendations') or [])}"
        context_blocks.append(ana_text)
        sources_used.append("AI Resume Analysis")

    # 3. ATS Analysis Context
    ats_scores = user_data.get("ats_scores") or []
    if ats_scores and (is_ats_query or is_resume_query):
        latest_ats = ats_scores[0]
        ats_text = f"--- ATS SCORE ANALYSIS ---\nOverall ATS Score: {latest_ats.get('ats_score')}/100\nFound Keywords: {', '.join(latest_ats.get('found_keywords') or [])}\nMissing Keywords: {', '.join(latest_ats.get('missing_keywords') or [])}\nATS Warnings: {', '.join(latest_ats.get('warnings') or [])}\nRecommendations: {', '.join(latest_ats.get('recommendations') or [])}"
        context_blocks.append(ats_text)
        sources_used.append("ATS Score Analysis")

    # 4. Job Match & Skill Gap Context
    job_matches = user_data.get("job_matches") or []
    if job_matches and (is_jobmatch_query or is_interview_query or is_resume_query):
        latest_jm = job_matches[0]
        gaps_summary = [f"{g.get('skill')}: {g.get('reason')}" for g in (latest_jm.get('skill_gaps') or []) if isinstance(g, dict)]
        jm_text = f"--- LATEST JOB MATCH ANALYSIS ---\nJob Title: {latest_jm.get('job_title')}\nMatch Score: {latest_jm.get('match_score')}% ({latest_jm.get('match_level')})\nMatching Skills: {', '.join(latest_jm.get('matching_skills') or [])}\nMissing Skills: {', '.join(latest_jm.get('missing_skills') or [])}\nIdentified Skill Gaps: {'; '.join(gaps_summary)}\nRecommendations: {', '.join(latest_jm.get('recommendations') or [])}"
        context_blocks.append(jm_text)
        sources_used.append("Job Match & Skill Gaps")

    # 5. Interview Session & Feedback Context
    interviews = user_data.get("interviews") or []
    if interviews and (is_interview_query or is_jobmatch_query):
        latest_int = interviews[0]
        int_text = f"--- LATEST INTERVIEW PREPARATION SESSION ---\nTarget Job: {latest_int.get('job_title')}\nInterview Type: {latest_int.get('interview_type')} ({latest_int.get('difficulty')})\nPreparation Tips: {', '.join(latest_int.get('preparation_tips') or [])}\nPotential Weaknesses: {', '.join(latest_int.get('potential_weaknesses') or [])}"
        context_blocks.append(int_text)
        sources_used.append("Interview Preparation")

    if not context_blocks:
        context_str = "No specific career data or uploaded resume found for this user in CareerPilot yet."
    else:
        context_str = "\n\n".join(context_blocks)

    return context_str, sources_used


def generate_rag_answer(uid, user_message, chat_history=None):
    """
    RAG Pipeline:
    1. Fetches authenticated user's Firestore career data.
    2. Builds intent-filtered context string and tracks sources.
    3. Prompts Gemini AI with System Prompt + Retrieved Context + Conversation History + User Message.
    4. Returns (ai_response_text, sources_used_list).
    """
    if not is_gemini_configured or not genai_client:
        raise ValueError("Gemini API key is not configured.")

    if not user_message or not user_message.strip():
        raise ValueError("Message cannot be empty.")

    # 1. Fetch user career data
    user_data = fetch_user_career_data(uid)

    # 2. Build RAG context & sources used
    context_str, sources_used = build_rag_context(user_data, user_message)

    # Format recent chat history if provided
    history_str = ""
    if chat_history and isinstance(chat_history, list):
        recent_msgs = chat_history[-6:]  # Limit to last 6 messages for token efficiency
        hist_lines = [f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in recent_msgs]
        history_str = "RECENT CHAT HISTORY:\n" + "\n".join(hist_lines) + "\n\n"

    system_prompt = f"""You are CareerPilot AI, a personalized career advisor and AI Assistant for students and job seekers.

Your mission is to provide helpful, personalized, and honest career advice to the user based STRICTLY on their actual CareerPilot data.

RETRIEVED USER CAREER CONTEXT:
\"\"\"
{context_str}
\"\"\"

{history_str}USER QUESTION:
\"{user_message.strip()}\"

Instructions:
1. Primary Source: Use the retrieved user career context above as your primary reference for personalized answers.
2. Source Attribution: When referencing user data, state clearly where it comes from (e.g. "Based on your uploaded resume...", "According to your recent job match for Backend Engineer...", "From your ATS analysis...").
3. Anti-Hallucination: Do NOT invent user experience, skills, projects, certifications, ATS scores, job applications, or interview feedback if they are not in the context.
4. Data Gap Handling: If the retrieved context does not contain enough information to answer a personalized question (e.g. user asks about ATS score but hasn't run ATS analysis), explicitly inform the user that the data is not yet in their profile, and then offer clear general advice.
5. Formatting & Tone: Provide concise, encouraging, professional, and structured answers using clean Markdown.
"""

    bot_reply = ""
    try:
        response = genai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=system_prompt
        )
        bot_reply = (response.text or "").strip()
    except Exception as api_err:
        logger.error(f"Gemini API call failed during RAG career assistant chat: {api_err}")
        raise RuntimeError("AI Career Assistant is temporarily unavailable. Please try again.")

    if not bot_reply:
        raise RuntimeError("Empty response from Gemini AI.")

    return bot_reply, sources_used
