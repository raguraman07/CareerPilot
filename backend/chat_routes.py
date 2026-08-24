import os
import time
import logging
import uuid
from flask import Blueprint, request, jsonify
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

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
        except Exception:
            pass
    if genai_client is None and genai_legacy_module is not None:
        try:
            genai_legacy_module.configure(api_key=GEMINI_API_KEY)
            genai_legacy_model = genai_legacy_module.GenerativeModel("gemini-3.6-flash")
        except Exception:
            is_gemini_configured = False

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
        docs = db.collection("resumes").where("user_id", "==", uid).stream()
        records = [d.to_dict() for d in docs]
        if records:
            sorted_records = sorted(records, key=lambda x: x.get("uploaded_at", ""), reverse=True)
            return sorted_records[0].get("extracted_text") or ""
        return ""

    def mock_select_resume():
        from resume_routes import MOCK_RESUMES_DB
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r["user_id"] == uid]
        if user_resumes:
            sorted_res = sorted(user_resumes, key=lambda x: x.get("uploaded_at", ""), reverse=True)
            return sorted_res[0].get("extracted_text") or ""
        return ""

    try:
        extracted_text = handle_db_op(db_select_resume, mock_select_resume)
        if extracted_text:
            resume_context = f"\nCandidate Resume Context:\n{extracted_text}\n"
    except Exception as db_err:
        logger.warning(f"Could not load user resume context for chat: {db_err}")

    if not is_gemini_configured or (not genai_client and not genai_legacy_model):
        return jsonify({"error": "AI Career Coach service is temporarily unavailable. Please try again."}), 502

    try:
        prompt = f"""
        You are a helpful and professional AI Career Coach. 
        Answer the user's career, resume, or job search query. Use their resume details to provide personalized, concrete advice.
        Keep your response conversational, concise, and professional.
        
        {resume_context}
        
        User's Query:
        {user_message}
        """
        bot_reply = ""
        if genai_client:
            resp = genai_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            bot_reply = (resp.text or "").strip()
        elif genai_legacy_model:
            resp = genai_legacy_model.generate_content(prompt)
            bot_reply = (resp.text or "").strip()
    except Exception as e:
        logger.error(f"Gemini Career Coach invocation failed: {e}")
        return jsonify({"error": "AI Career Coach service is temporarily unavailable. Please try again."}), 502

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    u_id = str(uuid.uuid4())
    b_id = str(uuid.uuid4())
    user_record = {"id": u_id, "user_id": uid, "message": user_message, "sender": "user", "timestamp": now_iso}
    bot_record = {"id": b_id, "user_id": uid, "message": bot_reply, "sender": "bot", "timestamp": now_iso}

    def db_insert():
        db.collection("chat_history").document(u_id).set(user_record)
        db.collection("chat_history").document(b_id).set(bot_record)
        return True

    def mock_insert():
        MOCK_CHAT_DB.append(user_record)
        MOCK_CHAT_DB.append(bot_record)
        return True

    try:
        handle_db_op(db_insert, mock_insert)
    except Exception as db_save_err:
        logger.warning(f"Failed to persist chat message: {db_save_err}")

    return jsonify({
        "success": True,
        "reply": bot_reply
    }), 200
