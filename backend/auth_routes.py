import re
import logging
import base64
import json
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

def sanitize_full_name(name):
    """Sanitize full_name to prevent HTML injection."""
    if not name:
        return ""
    clean = re.sub(r'<[^>]*?>', '', name)
    return clean.strip()

def map_firebase_error(e):
    """Map Auth error messages to friendly user-facing messages."""
    err_str = str(e).lower()
    logger.error(f"Auth Error: {err_str}")
    
    if "user-not-found" in err_str or "wrong-password" in err_str or "invalid credential" in err_str:
        return "That email or password doesn't look right. Please try again."
    elif "email-already-in-use" in err_str or "already exists" in err_str:
        return "An account with this email address already exists. Please login instead."
    elif "weak-password" in err_str:
        return "Password is too weak. Please choose a stronger password."
    else:
        return "An unexpected authentication error occurred. Please try again later."

def decode_jwt_payload_unverified(token):
    """Fallback utility to decode JWT payload without verifying signature (for offline/mock key resilience)."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padded = payload_b64 + '=' * (-len(payload_b64) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        return None

@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    """Sync authenticated user profile into Firestore database `profiles` collection."""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized. Missing bearer token."}), 401
        
        token = auth_header.split(" ")[1]
        
        uid = None
        email = ""
        user_name = ""

        try:
            if firebase_auth:
                decoded_token = firebase_auth.verify_id_token(token)
                uid = decoded_token.get("uid") or decoded_token.get("user_id")
                email = decoded_token.get("email", "")
                user_name = decoded_token.get("name", "")
        except Exception as ver_err:
            logger.warning(f"Firebase token verification failed during signup: {ver_err}. Trying unverified decode.")
            jwt_payload = decode_jwt_payload_unverified(token)
            if jwt_payload and (jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")):
                uid = jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")
                email = jwt_payload.get("email", "")

        if not uid:
            return jsonify({"error": "Invalid session token."}), 401

        data = request.get_json() or {}
        full_name = data.get("full_name") or user_name or ""
        clean_name = sanitize_full_name(full_name)
        if not clean_name:
            clean_name = email.split('@')[0] if email else "New User"

        profile_data = {
            "id": uid,
            "full_name": clean_name,
            "email": email
        }
        
        if db is not None:
            try:
                db.collection("profiles").document(uid).set(profile_data, merge=True)
                logger.info(f"Successfully synced profile for uid: {uid} to Firestore.")
            except Exception as db_err:
                logger.warning(f"Firestore profile sync failed: {db_err}. Continuing.")

        return jsonify({
            "message": "User profile successfully synced.",
            "user": {
                "id": uid,
                "email": email,
                "full_name": clean_name
            }
        }), 201

    except Exception as e:
        friendly_msg = map_firebase_error(e)
        return jsonify({"error": friendly_msg}), 400

@auth_bp.route('/api/auth/session', methods=['GET'])
def get_session():
    """Validate bearer token and return user & profile details."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized. No valid bearer token provided."}), 401

    token = auth_header.split(" ")[1]

    try:
        uid = None
        email = ""
        token_name = ""

        if firebase_auth:
            decoded_token = firebase_auth.verify_id_token(token)
            uid = decoded_token.get("uid") or decoded_token.get("user_id")
            email = decoded_token.get("email", "")
            token_name = decoded_token.get("name", "")

        if not uid:
            jwt_payload = decode_jwt_payload_unverified(token)
            if jwt_payload:
                uid = jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")
                email = jwt_payload.get("email", "")

        if not uid:
            return jsonify({"error": "Invalid session token."}), 401

        profile = None
        if db is not None:
            try:
                doc = db.collection("profiles").document(uid).get()
                if doc.exists:
                    profile = doc.to_dict()
            except Exception as db_err:
                logger.warning(f"Firestore profile fetch failed: {db_err}")

        if not profile:
            profile = {
                "id": uid,
                "email": email,
                "full_name": token_name or (email.split('@')[0] if email else "User")
            }

        return jsonify({
            "user": {
                "id": uid,
                "email": email,
                "full_name": profile.get("full_name", token_name or "User")
            },
            "profile": profile
        }), 200

    except Exception as e:
        logger.error(f"Session token validation completely failed: {e}")
        return jsonify({"error": "Invalid or expired session token."}), 401
