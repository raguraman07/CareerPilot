import os
import json
import logging
import uuid
import datetime
from flask import Blueprint, request, jsonify
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op
from services.rag_service import generate_rag_answer, is_gemini_configured

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

MOCK_CHATS_DB = {}


def _run_chat_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    user_message = (data.get("message") or "").strip()
    chat_id = data.get("chat_id")

    if not user_message:
        return jsonify({"error": "Missing message in request."}), 400

    if not chat_id:
        chat_id = str(uuid.uuid4())

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    # Retrieve existing chat to fetch message history for context
    def db_select_chat():
        doc = db.collection("career_assistant_chats").document(chat_id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == uid:
                return d
        return None

    def mock_select_chat():
        c = MOCK_CHATS_DB.get(chat_id)
        if c and c.get("user_id") == uid:
            return c
        return None

    try:
        chat_doc = handle_db_op(db_select_chat, mock_select_chat)
    except Exception as err:
        logger.warning(f"Could not load chat session {chat_id}: {err}")
        chat_doc = None

    existing_messages = chat_doc.get("messages", []) if chat_doc else []

    # Execute RAG Pipeline via Gemini AI
    try:
        bot_reply, sources_used = generate_rag_answer(
            uid=uid,
            user_message=user_message,
            chat_history=existing_messages
        )
    except (ValueError, RuntimeError) as ai_err:
        logger.error(f"RAG Career Assistant invocation failed: {ai_err}")
        return jsonify({"error": "AI Career Assistant is temporarily unavailable. Please try again."}), 502
    except Exception as exc:
        logger.error(f"Unexpected error during RAG chat: {exc}")
        return jsonify({"error": "AI Career Assistant is temporarily unavailable. Please try again."}), 502

    # Append new messages
    user_msg_obj = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": user_message,
        "created_at": now_iso
    }
    bot_msg_obj = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": bot_reply,
        "sources_used": sources_used,
        "created_at": now_iso
    }

    new_messages = existing_messages + [user_msg_obj, bot_msg_obj]
    chat_title = chat_doc.get("title") if chat_doc else (user_message[:35] + "..." if len(user_message) > 35 else user_message)

    chat_record = {
        "id": chat_id,
        "user_id": uid,
        "title": chat_title,
        "messages": new_messages,
        "created_at": chat_doc.get("created_at") if chat_doc else now_iso,
        "updated_at": now_iso
    }

    def db_save_chat():
        db.collection("career_assistant_chats").document(chat_id).set(chat_record)
        return chat_record

    def mock_save_chat():
        MOCK_CHATS_DB[chat_id] = chat_record
        return chat_record

    try:
        handle_db_op(db_save_chat, mock_save_chat)
    except Exception as db_save_err:
        logger.warning(f"Failed to persist chat session {chat_id}: {db_save_err}")

    return jsonify({
        "success": True,
        "chat_id": chat_id,
        "reply": bot_reply,
        "response": bot_reply,
        "sources_used": sources_used,
        "messages": new_messages
    }), 200


@chat_bp.route('/api/career-assistant/chat', methods=['POST'])
def career_assistant_chat():
    return _run_chat_handler()

@chat_bp.route('/api/chat/send', methods=['POST'])
def send_chat_alias():
    return _run_chat_handler()


def _run_list_chats_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_chats():
        docs = db.collection("career_assistant_chats").where("user_id", "==", uid).stream()
        chats = [d.to_dict() for d in docs]
        return sorted(chats, key=lambda x: x.get("updated_at", ""), reverse=True)

    def mock_select_chats():
        user_chats = [c for c in MOCK_CHATS_DB.values() if c.get("user_id") == uid]
        return sorted(user_chats, key=lambda x: x.get("updated_at", ""), reverse=True)

    try:
        chats = handle_db_op(db_select_chats, mock_select_chats)
        return jsonify(chats), 200
    except Exception as e:
        logger.error(f"Failed to fetch chats: {e}")
        return jsonify({"error": "Failed to fetch chat history."}), 500

@chat_bp.route('/api/career-assistant/chats', methods=['GET'])
def list_chats():
    return _run_list_chats_handler()

@chat_bp.route('/api/chat/history', methods=['GET'])
def list_chats_alias():
    return _run_list_chats_handler()


def _run_get_chat_handler(chat_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("career_assistant_chats").document(chat_id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == uid:
                return d
        return None

    def mock_select_one():
        c = MOCK_CHATS_DB.get(chat_id)
        if c and c.get("user_id") == uid:
            return c
        return None

    try:
        chat = handle_db_op(db_select_one, mock_select_one)
        if not chat:
            return jsonify({"error": "Chat session not found or unauthorized."}), 404
        return jsonify(chat), 200
    except Exception as e:
        logger.error(f"Failed to fetch chat {chat_id}: {e}")
        return jsonify({"error": "Failed to fetch chat session."}), 500

@chat_bp.route('/api/career-assistant/chats/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    return _run_get_chat_handler(chat_id)


def _run_delete_chat_handler(chat_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("career_assistant_chats").document(chat_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        c = MOCK_CHATS_DB.get(chat_id)
        if c and c.get("user_id") == uid:
            return c
        return None

    try:
        chat = handle_db_op(db_select_one, mock_select_one)
        if not chat:
            return jsonify({"error": "Chat session not found or unauthorized."}), 404

        def db_delete():
            db.collection("career_assistant_chats").document(chat_id).delete()
            return True

        def mock_delete():
            if chat_id in MOCK_CHATS_DB:
                del MOCK_CHATS_DB[chat_id]
            return True

        handle_db_op(db_delete, mock_delete)
        return jsonify({"message": "Chat session successfully deleted.", "id": chat_id}), 200
    except Exception as e:
        logger.error(f"Failed to delete chat {chat_id}: {e}")
        return jsonify({"error": "Failed to delete chat session."}), 500

@chat_bp.route('/api/career-assistant/chats/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    return _run_delete_chat_handler(chat_id)


@chat_bp.route('/api/career-assistant/chats/<chat_id>/clear', methods=['DELETE'])
def clear_chat_messages(chat_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("career_assistant_chats").document(chat_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        c = MOCK_CHATS_DB.get(chat_id)
        if c and c.get("user_id") == uid:
            return c
        return None

    try:
        chat = handle_db_op(db_select_one, mock_select_one)
        if not chat:
            return jsonify({"error": "Chat session not found or unauthorized."}), 404

        chat["messages"] = []
        chat["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"

        def db_update():
            db.collection("career_assistant_chats").document(chat_id).set(chat)
            return chat

        def mock_update():
            MOCK_CHATS_DB[chat_id] = chat
            return chat

        handle_db_op(db_update, mock_update)
        return jsonify({"message": "Chat history cleared.", "chat": chat}), 200
    except Exception as e:
        logger.error(f"Failed to clear chat {chat_id}: {e}")
        return jsonify({"error": "Failed to clear chat history."}), 500
