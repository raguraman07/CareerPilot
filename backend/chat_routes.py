import os
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op
import google.generativeai as genai

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_mock = not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-") or GEMINI_API_KEY.startswith("dummy")

if not is_gemini_mock:
    genai.configure(api_key=GEMINI_API_KEY)

# In-memory database fallback for local testing
MOCK_CHAT_DB = []

@chat_bp.route('/api/chat/send', methods=['POST'])
def send_chat_message():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    user_message = data.get("message")

    if not user_message:
        return jsonify({"error": "Missing message in request."}), 400

    # Fetch latest user resume for context-aware coaching
    resume_context = ""
    def db_select_resume():
        res = supabase_admin.table("resumes").select("extracted_text").eq("user_id", uid).order("uploaded_at", desc=True).limit(1).execute()
        return res.data[0].get("extracted_text") or "" if res.data else ""

    def mock_select_resume():
        from resume_routes import MOCK_RESUMES_DB
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r["user_id"] == uid]
        if user_resumes:
            sorted_res = sorted(user_resumes, key=lambda x: x.get("uploaded_at", ""), reverse=True)
            return sorted_res[0].get("extracted_text") or ""
        return ""

    try:
        extracted_text = handle_supabase_op(db_select_resume, mock_select_resume)
        if extracted_text:
            resume_context = f"\nCandidate Resume Context:\n{extracted_text}\n"
    except Exception as db_err:
        logger.warning(f"Could not load user resume context for chat: {db_err}")

    # Generate chatbot response
    bot_reply = ""
    if is_gemini_mock:
        bot_reply = f"Hi! I am your AI Career Coach. I've reviewed your resume details and I recommend focusing on software engineering metrics. Let me know if you have specific questions about career progression!"
    else:
        try:
            prompt = f"""
            You are a helpful and professional AI Career Coach. 
            Answer the user's career, resume, or job search query. Use their resume details to provide personalized, concrete advice.
            Keep your response conversational, concise, and professional.
            
            {resume_context}
            
            User's Query:
            {user_message}
            """
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            bot_reply = response.text.strip()
        except Exception as e:
            logger.error(f"Gemini Career Coach invocation failed: {e}")
            bot_reply = "I'm having trouble connecting to my brain right now. Let me know if there's anything else you'd like to discuss!"

    # Save to chat_history table in Supabase
    user_record = {"user_id": uid, "message": user_message, "sender": "user"}
    bot_record = {"user_id": uid, "message": bot_reply, "sender": "bot"}

    def db_insert():
        supabase_admin.table("chat_history").insert([user_record, bot_record]).execute()
        return True

    import time
    def mock_insert():
        curr_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        ur = dict(user_record)
        ur["created_at"] = curr_time
        br = dict(bot_record)
        br["created_at"] = curr_time
        MOCK_CHAT_DB.extend([ur, br])
        return True

    try:
        handle_supabase_op(db_insert, mock_insert)
    except Exception as db_err:
        logger.error(f"Failed to log chat messages in database: {db_err}")

    return jsonify({"reply": bot_reply}), 200

@chat_bp.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_history():
        res = supabase_admin.table("chat_history").select("message", "sender", "created_at").eq("user_id", uid).order("created_at", desc=False).execute()
        return res.data or []

    def mock_select_history():
        user_chat = [c for c in MOCK_CHAT_DB if c["user_id"] == uid]
        return sorted(user_chat, key=lambda x: x.get("created_at", ""), reverse=False)

    try:
        history = handle_supabase_op(db_select_history, mock_select_history)
        return jsonify(history), 200
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}")
        return jsonify({"error": "Failed to retrieve chat history."}), 500
