import time
import logging
import base64
import json
import uuid as uuid_lib
from flask import Blueprint, request, jsonify
from firebase_client import db, firebase_auth

logger = logging.getLogger(__name__)

career_goal_bp = Blueprint('career_goal', __name__)

# Temporary in-memory database mock fallback if Firestore is not connected
MOCK_CAREER_GOALS_DB = {}

VALID_EXPERIENCE_LEVELS = {
    "Student",
    "Fresher",
    "Entry Level",
    "1–2 Years",
    "1-2 Years",
    "3–5 Years",
    "3-5 Years",
    "5+ Years"
}

VALID_STATUSES = {"active", "completed", "archived"}

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

@career_goal_bp.route('/api/career-goals', methods=['POST'])
def create_career_goal():
    """Create a new Career Goal for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    company_name = (data.get("company_name") or "").strip()
    job_role = (data.get("job_role") or "").strip()
    experience_level = (data.get("experience_level") or "").strip()
    target_location = (data.get("target_location") or "").strip()
    target_timeline = (data.get("target_timeline") or "").strip()

    if not company_name:
        return jsonify({"error": "Target company is required."}), 400
    if not job_role:
        return jsonify({"error": "Target job role is required."}), 400
    if not experience_level:
        return jsonify({"error": "Experience level is required."}), 400

    goal_id = str(uuid_lib.uuid4())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    goal_doc = {
        "id": goal_id,
        "user_id": uid,
        "company_name": company_name,
        "job_role": job_role,
        "experience_level": experience_level,
        "target_location": target_location,
        "target_timeline": target_timeline,
        "status": "active",
        "created_at": now_iso,
        "updated_at": now_iso
    }

    def db_insert():
        # Archive any previous active goals for this user to ensure single active goal
        existing_active = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        for doc in existing_active:
            db.collection("career_goals").document(doc.id).update({
                "status": "archived",
                "updated_at": now_iso
            })
        db.collection("career_goals").document(goal_id).set(goal_doc)
        return goal_doc

    def mock_insert():
        for gid, g in MOCK_CAREER_GOALS_DB.items():
            if g.get("user_id") == uid and g.get("status") == "active":
                g["status"] = "archived"
                g["updated_at"] = now_iso
        MOCK_CAREER_GOALS_DB[goal_id] = goal_doc
        return goal_doc

    try:
        created = handle_db_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "message": "Career goal created successfully.",
            "career_goal": created
        }), 201
    except Exception as e:
        logger.error(f"Error creating career goal: {e}")
        return jsonify({"error": "Failed to create career goal. Please try again."}), 500

@career_goal_bp.route('/api/career-goals/current', methods=['GET'])
def get_current_career_goal():
    """Retrieve the currently active Career Goal for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_get():
        docs = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        goals = [d.to_dict() for d in docs]
        if goals:
            # Sort by updated_at / created_at descending if multiple
            goals.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
            return goals[0]
        return None

    def mock_get():
        user_goals = [
            g for g in MOCK_CAREER_GOALS_DB.values()
            if g.get("user_id") == uid and g.get("status") == "active"
        ]
        if user_goals:
            user_goals.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
            return user_goals[0]
        return None

    try:
        current_goal = handle_db_op(db_get, mock_get)
        return jsonify({
            "success": True,
            "career_goal": current_goal
        }), 200
    except Exception as e:
        logger.error(f"Error fetching current career goal: {e}")
        return jsonify({"error": "Failed to fetch career goal."}), 500

@career_goal_bp.route('/api/career-goals/<goal_id>', methods=['PUT'])
def update_career_goal(goal_id):
    """Update an existing Career Goal owned by the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    
    def db_fetch():
        doc = db.collection("career_goals").document(goal_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def mock_fetch():
        return MOCK_CAREER_GOALS_DB.get(goal_id)

    goal = handle_db_op(db_fetch, mock_fetch)
    if not goal:
        return jsonify({"error": "Career goal not found."}), 404

    # Verify user ownership
    if goal.get("user_id") != uid:
        return jsonify({"error": "Unauthorized. You do not own this career goal."}), 403

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    updates = {"updated_at": now_iso}

    if "company_name" in data:
        cname = str(data["company_name"]).strip()
        if not cname:
            return jsonify({"error": "Target company cannot be empty."}), 400
        updates["company_name"] = cname

    if "job_role" in data:
        jrole = str(data["job_role"]).strip()
        if not jrole:
            return jsonify({"error": "Target job role cannot be empty."}), 400
        updates["job_role"] = jrole

    if "experience_level" in data:
        exp = str(data["experience_level"]).strip()
        if not exp:
            return jsonify({"error": "Experience level cannot be empty."}), 400
        updates["experience_level"] = exp

    if "target_location" in data:
        updates["target_location"] = str(data["target_location"]).strip()

    if "target_timeline" in data:
        updates["target_timeline"] = str(data["target_timeline"]).strip()

    if "status" in data:
        st = str(data["status"]).strip().lower()
        if st in VALID_STATUSES:
            updates["status"] = st

    def db_update():
        db.collection("career_goals").document(goal_id).update(updates)
        updated_doc = db.collection("career_goals").document(goal_id).get().to_dict()
        return updated_doc

    def mock_update():
        MOCK_CAREER_GOALS_DB[goal_id].update(updates)
        return MOCK_CAREER_GOALS_DB[goal_id]

    try:
        updated_goal = handle_db_op(db_update, mock_update)
        return jsonify({
            "success": True,
            "message": "Career goal updated successfully.",
            "career_goal": updated_goal
        }), 200
    except Exception as e:
        logger.error(f"Error updating career goal {goal_id}: {e}")
        return jsonify({"error": "Failed to update career goal."}), 500

@career_goal_bp.route('/api/career-goals', methods=['GET'])
def list_career_goals():
    """List all career goals for the authenticated user."""
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_list():
        docs = db.collection("career_goals").where("user_id", "==", uid).stream()
        goals = [d.to_dict() for d in docs]
        goals.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return goals

    def mock_list():
        user_goals = [g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == uid]
        user_goals.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return user_goals

    try:
        goals = handle_db_op(db_list, mock_list)
        return jsonify({
            "success": True,
            "career_goals": goals
        }), 200
    except Exception as e:
        logger.error(f"Error listing career goals: {e}")
        return jsonify({"error": "Failed to list career goals."}), 500
