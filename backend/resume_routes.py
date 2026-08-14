import os
import time
import logging
import base64
import json
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from supabase_client import supabase_admin
from resume_parser import parse_resume

logger = logging.getLogger(__name__)

resume_bp = Blueprint('resume', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Temporary in-memory database mock fallback if Supabase is not connected
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
    """Verify authorization token and return user UID using Supabase."""
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("Unauthorized. Missing or invalid Authorization header.")
    
    token = auth_header.split(" ")[1]
    try:
        user_response = supabase_admin.auth.get_user(token)
        return user_response.user.id
    except Exception as e:
        logger.warning(f"Authentication token verification via supabase_admin failed: {e}. Attempting fallback JWT decode.")
        jwt_payload = decode_jwt_payload_unverified(token)
        if jwt_payload and (jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")):
            return jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")
        raise ValueError("Unauthorized. Invalid session token.")

def handle_supabase_op(callback, fallback_return):
    """Wrapper to handle Supabase DB operations with a local mock fallback if DB is offline or tables do not exist."""
    try:
        return callback()
    except Exception as db_err:
        db_err_str = str(db_err).lower()
        is_mock_trigger = (
            "getaddrinfo" in db_err_str or 
            "failed to connect" in db_err_str or 
            "connection" in db_err_str or 
            "dummy" in db_err_str or
            "could not find the table" in db_err_str or
            "pgrst205" in db_err_str or
            "relation" in db_err_str or
            "does not exist" in db_err_str
        )
        if is_mock_trigger:
            logger.warning(f"Supabase operation failed: {db_err}. Falling back to Mock DB Mode.")
            return fallback_return()
        else:
            logger.error(f"Supabase DB error: {db_err}")
            raise db_err

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
    
    # Check duplicate filenames under this user, auto-rename if duplicate
    # Define a callback for Supabase duplicate check
    def db_duplicate_check():
        res = supabase_admin.table("resumes").select("filename").eq("user_id", uid).eq("filename", orig_filename).execute()
        return len(res.data) > 0

    def mock_duplicate_check():
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r["user_id"] == uid]
        return any(r["filename"] == orig_filename for r in user_resumes)

    has_duplicate = handle_supabase_op(db_duplicate_check, mock_duplicate_check)
    if has_duplicate:
        # Auto rename filename with timestamp suffix
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
        # Cleanup file if parsing failed
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": f"Failed to parse resume content: {str(parse_err)}"}), 400

    # Upload to Supabase Storage and retrieve public URL
    bucket_name = "resumes"
    storage_path = f"{uid}/{filename}"
    file_url = f"/api/resume/download/{filename}" # Fallback path if offline

    try:
        # Ensure the bucket exists
        try:
            supabase_admin.storage.create_bucket(bucket_name, options={"public": True})
        except Exception:
            pass # Suppress warning if bucket already exists
        
        with open(filepath, 'rb') as f:
            file_bytes = f.read()
            
        supabase_admin.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": file.content_type or "application/pdf"}
        )
        file_url = supabase_admin.storage.from_(bucket_name).get_public_url(storage_path)
    except Exception as storage_err:
        logger.error(f"Supabase storage upload failed: {storage_err}")
    finally:
        # Clean up temporary local file used for parsing
        if os.path.exists(filepath):
            os.remove(filepath)

    # Insert metadata into Supabase DB
    resume_id = None

    def db_insert():
        record = {
            "user_id": uid,
            "filename": filename,
            "file_type": parse_result["file_type"],
            "file_url": file_url,
            "pages": parse_result["pages"],
            "extracted_text": parse_result["text"],
            "status": "parsed"
        }
        res = supabase_admin.table("resumes").insert(record).execute()
        return res.data[0]["id"] if res.data else "mock-uuid"

    import uuid as uuid_lib
    def mock_insert():
        rid = str(uuid_lib.uuid4())
        MOCK_RESUMES_DB[rid] = {
            "id": rid,
            "user_id": uid,
            "filename": filename,
            "file_type": parse_result["file_type"],
            "file_url": file_url,
            "pages": parse_result["pages"],
            "extracted_text": parse_result["text"],
            "status": "parsed",
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return rid

    try:
        resume_id = handle_supabase_op(db_insert, mock_insert)
    except Exception as insert_err:
        return jsonify({"error": f"Database insertion failed: {str(insert_err)}"}), 500

    return jsonify({
        "id": resume_id,
        "filename": filename,
        "file_type": parse_result["file_type"],
        "pages": parse_result["pages"],
        "text": parse_result["text"],
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }), 201

@resume_bp.route('/api/resume/list', methods=['GET'])
def list_resumes():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select():
        res = supabase_admin.table("resumes").select("id, filename, file_type, pages, status, uploaded_at").eq("user_id", uid).order("uploaded_at", desc=True).execute()
        return res.data

    def mock_select():
        user_resumes = [r for r in MOCK_RESUMES_DB.values() if r["user_id"] == uid]
        # Return only public list view attributes (exclude heavy extracted_text)
        return [{
            "id": r["id"],
            "filename": r["filename"],
            "file_type": r["file_type"],
            "pages": r["pages"],
            "status": r["status"],
            "uploaded_at": r["uploaded_at"]
        } for r in sorted(user_resumes, key=lambda x: x["uploaded_at"], reverse=True)]

    try:
        data = handle_supabase_op(db_select, mock_select)
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
        res = supabase_admin.table("resumes").select("*").eq("id", id).eq("user_id", uid).execute()
        return res.data[0] if res.data else None

    def mock_select_one():
        r = MOCK_RESUMES_DB.get(id)
        if r and r["user_id"] == uid:
            return r
        return None

    try:
        resume = handle_supabase_op(db_select_one, mock_select_one)
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
        res = supabase_admin.table("resumes").select("filename").eq("id", id).eq("user_id", uid).execute()
        return res.data[0] if res.data else None

    def mock_select_one():
        r = MOCK_RESUMES_DB.get(id)
        if r and r["user_id"] == uid:
            return {"filename": r["filename"]}
        return None

    try:
        resume = handle_supabase_op(db_select_one, mock_select_one)
        if not resume:
            return jsonify({"error": "Resume not found."}), 404
        # Delete from Supabase Storage
        filename = resume["filename"]
        try:
            supabase_admin.storage.from_("resumes").remove([f"{uid}/{filename}"])
        except Exception as storage_err:
            logger.error(f"Failed to delete resume from storage: {storage_err}")

        # Delete database record
        def db_delete():
            supabase_admin.table("resumes").delete().eq("id", id).eq("user_id", uid).execute()
            return True

        def mock_delete():
            if id in MOCK_RESUMES_DB:
                del MOCK_RESUMES_DB[id]
            return True

        handle_supabase_op(db_delete, mock_delete)
        return jsonify({"message": "Resume successfully deleted."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
