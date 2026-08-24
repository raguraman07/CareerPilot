import os
import json
import logging
import uuid
import datetime
from flask import Blueprint, request, jsonify
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op
from services.career_roadmap_service import (
    generate_career_roadmap,
    get_readiness_label,
    is_gemini_configured
)

logger = logging.getLogger(__name__)

roadmap_bp = Blueprint('roadmap', __name__)

MOCK_ROADMAP_DB = {}


def _run_generate_roadmap_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    career_goal = (data.get("career_goal") or data.get("goal") or "").strip()

    try:
        roadmap_data = generate_career_roadmap(uid=uid, career_goal=career_goal)
    except (ValueError, RuntimeError) as ai_err:
        logger.error(f"Career roadmap generation failed: {ai_err}")
        return jsonify({"error": "Career roadmap generation is temporarily unavailable. Please try again."}), 502
    except Exception as exc:
        logger.error(f"Unexpected error during career roadmap generation: {exc}")
        return jsonify({"error": "Career roadmap generation is temporarily unavailable. Please try again."}), 502

    roadmap_id = str(uuid.uuid4())
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    record = {
        "id": roadmap_id,
        "user_id": uid,
        "career_goal": roadmap_data.get("career_goal") or "Target Career",
        "readiness_score": roadmap_data.get("readiness_score", 60),
        "readiness_label": roadmap_data.get("readiness_label", "Developing"),
        "current_profile_summary": roadmap_data.get("current_profile_summary", ""),
        "current_strengths": roadmap_data.get("current_strengths", []),
        "priority_gaps": roadmap_data.get("priority_gaps", []),
        "roadmap": roadmap_data.get("roadmap", []),
        "recommended_projects": roadmap_data.get("recommended_projects", []),
        "interview_preparation": roadmap_data.get("interview_preparation", []),
        "job_readiness_checklist": roadmap_data.get("job_readiness_checklist", []),
        "estimated_timeline": roadmap_data.get("estimated_timeline", "4–8 weeks"),
        "final_recommendations": roadmap_data.get("final_recommendations", []),
        "progress": 0,
        "version": 1,
        "created_at": now_iso,
        "updated_at": now_iso
    }

    def db_insert():
        db.collection("career_roadmaps").document(roadmap_id).set(record)
        return record

    def mock_insert():
        MOCK_ROADMAP_DB[roadmap_id] = record
        return record

    try:
        saved_record = handle_db_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "roadmap_id": saved_record.get("id"),
            "roadmap": saved_record,
            # Backward compatibility fields
            "goal": saved_record.get("career_goal"),
            "roadmap_json": {"milestones": saved_record.get("roadmap")}
        }), 201
    except Exception as save_err:
        logger.error(f"Failed to save career roadmap: {save_err}")
        return jsonify({"error": "Failed to save career roadmap."}), 500


@roadmap_bp.route('/api/career-roadmap/generate', methods=['POST'])
def create_career_roadmap():
    return _run_generate_roadmap_handler()

@roadmap_bp.route('/api/roadmap/generate', methods=['POST'])
def generate_roadmap_alias():
    return _run_generate_roadmap_handler()


def _run_get_history_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_history():
        docs = db.collection("career_roadmaps").where("user_id", "==", uid).stream()
        history = [doc.to_dict() for doc in docs]
        return sorted(history, key=lambda x: x.get("created_at", ""), reverse=True)

    def mock_select_history():
        user_roadmaps = [r for r in MOCK_ROADMAP_DB.values() if r.get("user_id") == uid]
        return sorted(user_roadmaps, key=lambda x: x.get("created_at", ""), reverse=True)

    try:
        history_data = handle_db_op(db_select_history, mock_select_history)
        return jsonify(history_data), 200
    except Exception as e:
        logger.error(f"Failed to fetch career roadmaps: {e}")
        return jsonify({"error": "Failed to fetch career roadmaps."}), 500

@roadmap_bp.route('/api/career-roadmap', methods=['GET'])
def get_career_roadmaps():
    return _run_get_history_handler()

@roadmap_bp.route('/api/roadmap/history', methods=['GET'])
def get_roadmap_history_alias():
    return _run_get_history_handler()


def _run_get_one_handler(roadmap_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("career_roadmaps").document(roadmap_id).get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == uid:
                return d
        return None

    def mock_select_one():
        r = MOCK_ROADMAP_DB.get(roadmap_id)
        if r and r.get("user_id") == uid:
            return r
        return None

    try:
        record = handle_db_op(db_select_one, mock_select_one)
        if not record:
            return jsonify({"error": "Career roadmap not found or unauthorized."}), 404
        return jsonify(record), 200
    except Exception as e:
        logger.error(f"Failed to fetch roadmap {roadmap_id}: {e}")
        return jsonify({"error": "Failed to fetch career roadmap."}), 500

@roadmap_bp.route('/api/career-roadmap/<roadmap_id>', methods=['GET'])
def get_career_roadmap(roadmap_id):
    return _run_get_one_handler(roadmap_id)

@roadmap_bp.route('/api/roadmap/<roadmap_id>', methods=['GET'])
def get_roadmap_alias(roadmap_id):
    return _run_get_one_handler(roadmap_id)


def _run_patch_progress_handler(roadmap_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    phase_index = data.get("phase_index")
    status = data.get("status", "completed")

    if phase_index is None:
        return jsonify({"error": "Missing required field: phase_index."}), 400

    def db_select_one():
        doc = db.collection("career_roadmaps").document(roadmap_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        r = MOCK_ROADMAP_DB.get(roadmap_id)
        if r and r.get("user_id") == uid:
            return r
        return None

    try:
        record = handle_db_op(db_select_one, mock_select_one)
    except Exception as db_err:
        return jsonify({"error": "Failed to fetch career roadmap."}), 500

    if not record:
        return jsonify({"error": "Career roadmap not found or unauthorized."}), 404

    phases = record.get("roadmap") or []
    try:
        idx = int(phase_index)
        if 0 <= idx < len(phases):
            phases[idx]["status"] = status
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid phase_index."}), 400

    # Recalculate progress percentage
    total_phases = len(phases)
    completed_phases = sum(1 for p in phases if p.get("status") == "completed")
    progress_pct = round((completed_phases / total_phases) * 100) if total_phases > 0 else 0

    record["roadmap"] = phases
    record["progress"] = progress_pct
    record["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    def db_update():
        db.collection("career_roadmaps").document(roadmap_id).update({
            "roadmap": phases,
            "progress": progress_pct,
            "updated_at": record["updated_at"]
        })
        return record

    def mock_update():
        MOCK_ROADMAP_DB[roadmap_id] = record
        return record

    try:
        updated = handle_db_op(db_update, mock_update)
        return jsonify({
            "success": True,
            "roadmap_id": roadmap_id,
            "progress": progress_pct,
            "roadmap": updated
        }), 200
    except Exception as err:
        logger.error(f"Failed to update roadmap progress: {err}")
        return jsonify({"error": "Failed to update roadmap progress."}), 500

@roadmap_bp.route('/api/career-roadmap/<roadmap_id>/progress', methods=['PATCH'])
def update_roadmap_progress(roadmap_id):
    return _run_patch_progress_handler(roadmap_id)

@roadmap_bp.route('/api/roadmap/<roadmap_id>/progress', methods=['PATCH'])
def update_roadmap_progress_alias(roadmap_id):
    return _run_patch_progress_handler(roadmap_id)


def _run_delete_roadmap_handler(roadmap_id):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_one():
        doc = db.collection("career_roadmaps").document(roadmap_id).get()
        if doc.exists and doc.to_dict().get("user_id") == uid:
            return doc.to_dict()
        return None

    def mock_select_one():
        r = MOCK_ROADMAP_DB.get(roadmap_id)
        if r and r.get("user_id") == uid:
            return r
        return None

    try:
        record = handle_db_op(db_select_one, mock_select_one)
        if not record:
            return jsonify({"error": "Career roadmap not found or unauthorized."}), 404

        def db_delete():
            db.collection("career_roadmaps").document(roadmap_id).delete()
            return True

        def mock_delete():
            if roadmap_id in MOCK_ROADMAP_DB:
                del MOCK_ROADMAP_DB[roadmap_id]
            return True

        handle_db_op(db_delete, mock_delete)
        return jsonify({"message": "Career roadmap successfully deleted.", "id": roadmap_id}), 200
    except Exception as e:
        logger.error(f"Failed to delete roadmap {roadmap_id}: {e}")
        return jsonify({"error": "Failed to delete career roadmap."}), 500

@roadmap_bp.route('/api/career-roadmap/<roadmap_id>', methods=['DELETE'])
def delete_career_roadmap(roadmap_id):
    return _run_delete_roadmap_handler(roadmap_id)

@roadmap_bp.route('/api/roadmap/<roadmap_id>', methods=['DELETE'])
def delete_roadmap_alias(roadmap_id):
    return _run_delete_roadmap_handler(roadmap_id)
