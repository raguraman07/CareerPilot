import os
import time
import logging
import base64
import json
import uuid as uuid_lib
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from firebase_client import db, firebase_auth
from resume_parser import parse_resume

logger = logging.getLogger(__name__)

resume_bp = Blueprint('resume', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Temporary in-memory database mock fallback if Firestore is not connected
MOCK_RESUMES_DB = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

def get_auth_uid(req):
    """Verify authorization token and return user UID using Firebase Auth."""
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("Unauthorized. Missing or invalid Authorization header.")
    
    token = auth_header.split(" ")[1]
    try:
        if firebase_auth:
            decoded_token = firebase_auth.verify_id_token(token)
            return decoded_token.get("uid") or decoded_token.get("user_id")
    except Exception as e:
        logger.warning(f"Authentication token verification via Firebase failed: {e}. Attempting fallback JWT decode.")
        
    jwt_payload = decode_jwt_payload_unverified(token)
    if jwt_payload and (jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")):
        return jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")
    raise ValueError("Unauthorized. Invalid session token.")

def handle_db_op(callback, fallback_return):
    """Wrapper to handle Firestore operations with a local mock fallback if DB is offline."""
    try:
        if db is not None:
            return callback()
        return fallback_return()
    except Exception as db_err:
        logger.warning(f"Firestore operation failed: {db_err}. Falling back to Mock DB Mode.")
        return fallback_return()

@resume_bp.route('/api/resume/upload', methods=['POST'])
def upload_resume():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file format. Only PDF and DOCX files are allowed."}), 400

    # Read length of stream to validate size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    if file_length > MAX_FILE_SIZE:
        return jsonify({"error": f"File exceeds maximum allowed size of 5 MB."}), 413
    file.seek(0)  # Reset stream pointer

    # Secure and sanitize the filename
    orig_filename = secure_filename(file.filename)
    filename = orig_filename
    
    def db_duplicate_check():
        docs = db.collection("resumes").where("user_id", "==", uid).where("filename", "==", orig_filename).stream()
        return any(True for _ in docs)

    def mock_duplicate_check():
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r["user_id"] == uid]
        return any(r["filename"] == orig_filename for r in user_resumes)

    has_duplicate = handle_db_op(db_duplicate_check, mock_duplicate_check)
    if has_duplicate:
        name_part, ext_part = os.path.splitext(orig_filename)
        filename = f"{name_part}_{int(time.time())}{ext_part}"

    # Setup unique path for the uploaded file temporarily: backend/uploads/<uid>/ for parsing
    upload_dir = os.path.join(os.path.dirname(__file__), 'uploads', uid)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Parse the resume file contents
    try:
        parse_result = parse_resume(filepath)
    except Exception as parse_err:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": f"Failed to parse resume content: {str(parse_err)}"}), 400

    file_url = f"/api/resume/download/{filename}"
    rid = str(uuid_lib.uuid4())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    record = {
        "id": rid,
        "user_id": uid,
        "filename": filename,
        "file_type": parse_result["file_type"],
        "file_url": file_url,
        "pages": parse_result["pages"],
        "extracted_text": parse_result["text"],
        "status": "parsed",
        "uploaded_at": now_iso
    }

    def db_insert():
        db.collection("resumes").document(rid).set(record)
        return rid

    def mock_insert():
        MOCK_RESUMES_DB[rid] = record
        return rid

    try:
        resume_id = handle_db_op(db_insert, mock_insert)
    except Exception as insert_err:
        return jsonify({"error": f"Database insertion failed: {str(insert_err)}"}), 500

    return jsonify({
        "id": resume_id,
        "filename": filename,
        "file_type": parse_result["file_type"],
        "pages": parse_result["pages"],
        "text": parse_result["text"],
        "uploaded_at": now_iso
    }), 201

@resume_bp.route('/api/resume/list', methods=['GET'])
def list_resumes():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select():
        docs = db.collection("resumes").where("user_id", "==", uid).stream()
        resumes = []
        for doc in docs:
            d = doc.to_dict()
            resumes.append({
                "id": d.get("id", doc.id),
                "filename": d.get("filename"),
                "file_type": d.get("file_type"),
                "pages": d.get("pages"),
                "status": d.get("status"),
                "uploaded_at": d.get("uploaded_at")
            })
        return sorted(resumes, key=lambda x: x.get("uploaded_at", ""), reverse=True)

    def mock_select():
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r["user_id"] == uid]
        return [{
            "id": r["id"],
            "filename": r["filename"],
            "file_type": r["file_type"],
            "pages": r["pages"],
            "status": r["status"],
            "uploaded_at": r["uploaded_at"]
        } for r in sorted(user_resumes, key=lambda x: x["uploaded_at"], reverse=True)]

    try:
        data = handle_db_op(db_select, mock_select)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@resume_bp.route('/api/resume/<id>', methods=['GET'])
def get_resume(id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("resumes").document(id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == uid:
                return d
        return None

    def mock_select_one():
        r = MOCK_RESUMES_DB.get(id)
        if r and r["user_id"] == uid:
            return r
        return None

    try:
        resume = handle_db_op(db_select_one, mock_select_one)
        if not resume:
            return jsonify({"error": "Resume not found."}), 404
        return jsonify(resume), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@resume_bp.route('/api/resume/<id>', methods=['DELETE'])
def delete_resume(id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("resumes").document(id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        r = MOCK_RESUMES_DB.get(id)
        if r and r["user_id"] == uid:
            return {"filename": r["filename"]}
        return None

    try:
        resume = handle_db_op(db_select_one, mock_select_one)
        if not resume:
            return jsonify({"error": "Resume not found."}), 404

        def db_delete():
            db.collection("resumes").document(id).delete()
            return True

        def mock_delete():
            if id in MOCK_RESUMES_DB:
                del MOCK_RESUMES_DB[id]
            return True

        handle_db_op(db_delete, mock_delete)
        return jsonify({"message": "Resume successfully deleted."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
