import os
import json
import logging
import uuid
import datetime
import io
from flask import Blueprint, request, jsonify, send_file
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op
from services.career_roadmap_service import (
    generate_career_roadmap,
    get_readiness_label,
    is_gemini_configured
)
from services.roadmap_pdf_service import generate_roadmap_pdf_bytes

logger = logging.getLogger(__name__)

roadmap_bp = Blueprint('roadmap', __name__)

MOCK_ROADMAP_DB = {}


def _run_generate_roadmap_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    career_goal = (data.get("career_goal") or data.get("goal") or data.get("target_role") or "").strip()

    try:
        roadmap_data = generate_career_roadmap(uid=uid, career_goal=career_goal)
    except (ValueError, RuntimeError) as ai_err:
        logger.error(f"Career roadmap generation failed: {ai_err}")
        return jsonify({"error": "Career roadmap generation is temporarily unavailable. Please try again."}), 502
    except Exception as exc:
        logger.error(f"Unexpected error during career roadmap generation: {exc}")
        return jsonify({"error": "Career roadmap generation is temporarily unavailable. Please try again."}), 502

    roadmap_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    record = {
        "id": roadmap_id,
        "user_id": uid,
        "career_goal": roadmap_data.get("career_goal") or {"company": "Target Company", "role": "Software Engineer"},
        "current_readiness": roadmap_data.get("current_readiness") or {"score": 60, "summary": ""},
        "readiness_score": roadmap_data.get("readiness_score", 60),
        "readiness_label": roadmap_data.get("readiness_label", "Developing"),
        "roadmap_duration": roadmap_data.get("roadmap_duration", "8–12 weeks"),
        "phases": roadmap_data.get("phases", []),
        "roadmap": roadmap_data.get("phases", []),  # backward compatibility
        "recommended_projects": roadmap_data.get("recommended_projects", []),
        "final_readiness": roadmap_data.get("final_readiness", {}),
        "progress": 0,
        "version": 2,
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
            "roadmap_data": saved_record,
            # Backward compatibility fields
            "goal": saved_record.get("career_goal"),
            "roadmap_json": {"milestones": saved_record.get("phases")}
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


def _run_get_latest_handler():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_latest():
        docs = db.collection("career_roadmaps").where("user_id", "==", uid).stream()
        history = [doc.to_dict() for doc in docs]
        if not history:
            return None
        history.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
        return history[0]

    def mock_select_latest():
        user_roadmaps = [r for r in MOCK_ROADMAP_DB.values() if r.get("user_id") == uid]
        if not user_roadmaps:
            return None
        user_roadmaps.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
        return user_roadmaps[0]

    try:
        latest = handle_db_op(db_select_latest, mock_select_latest)
        if not latest:
            return jsonify({"success": True, "roadmap": None, "message": "No career roadmap found."}), 200
        return jsonify({
            "success": True,
            "roadmap_id": latest.get("id"),
            "roadmap": latest,
            "roadmap_data": latest
        }), 200
    except Exception as e:
        logger.error(f"Failed to fetch latest roadmap: {e}")
        return jsonify({"error": "Failed to fetch latest career roadmap."}), 500


@roadmap_bp.route('/api/career-roadmap/latest', methods=['GET'])
def get_latest_career_roadmap():
    return _run_get_latest_handler()

@roadmap_bp.route('/api/roadmap/latest', methods=['GET'])
def get_latest_roadmap_alias():
    return _run_get_latest_handler()


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
    item_type = data.get("item_type")  # 'phase', 'skill', 'cert', 'project'
    item_index = data.get("item_index")
    status = data.get("status", "completed")

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
    except Exception:
        return jsonify({"error": "Failed to fetch career roadmap."}), 500

    if not record:
        return jsonify({"error": "Career roadmap not found or unauthorized."}), 404

    phases = record.get("phases") or record.get("roadmap") or []

    # Update item or phase
    if phase_index is not None:
        try:
            p_idx = int(phase_index)
            if 0 <= p_idx < len(phases):
                target_phase = phases[p_idx]
                if item_type == "skill" and item_index is not None:
                    s_idx = int(item_index)
                    if 0 <= s_idx < len(target_phase.get("skills", [])):
                        target_phase["skills"][s_idx]["status"] = status
                elif item_type == "cert" and item_index is not None:
                    c_idx = int(item_index)
                    if 0 <= c_idx < len(target_phase.get("certifications", [])):
                        target_phase["certifications"][c_idx]["status"] = status
                elif item_type == "project" and item_index is not None:
                    pr_idx = int(item_index)
                    if 0 <= pr_idx < len(target_phase.get("projects", [])):
                        target_phase["projects"][pr_idx]["status"] = status
                else:
                    target_phase["status"] = status
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid index parameter."}), 400

    # Recalculate progress percentage
    total_items = 0
    completed_items = 0

    for ph in phases:
        total_items += 1
        if ph.get("status") == "completed":
            completed_items += 1
        for sk in ph.get("skills", []):
            total_items += 1
            if sk.get("status") == "completed":
                completed_items += 1
        for c in ph.get("certifications", []):
            total_items += 1
            if c.get("status") == "completed":
                completed_items += 1
        for pr in ph.get("projects", []):
            total_items += 1
            if pr.get("status") == "completed":
                completed_items += 1

    progress_pct = round((completed_items / total_items) * 100) if total_items > 0 else 0

    # Dynamic readiness score update based on base score + progress
    base_readiness = record.get("current_readiness", {}).get("score", 60)
    adjusted_score = min(100, round(base_readiness + (100 - base_readiness) * (progress_pct / 100)))

    record["phases"] = phases
    record["roadmap"] = phases
    record["progress"] = progress_pct
    record["current_readiness"]["score"] = adjusted_score
    record["readiness_score"] = adjusted_score
    record["readiness_label"] = get_readiness_label(adjusted_score)
    record["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def db_update():
        db.collection("career_roadmaps").document(roadmap_id).update({
            "phases": phases,
            "roadmap": phases,
            "progress": progress_pct,
            "current_readiness": record["current_readiness"],
            "readiness_score": adjusted_score,
            "readiness_label": record["readiness_label"],
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
            "readiness_score": adjusted_score,
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


def _run_export_pdf_handler(roadmap_id=None):
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select():
        if roadmap_id:
            doc = db.collection("career_roadmaps").document(roadmap_id).get()
            if doc.exists and doc.to_dict().get("user_id") == uid:
                return doc.to_dict()
        else:
            docs = db.collection("career_roadmaps").where("user_id", "==", uid).stream()
            history = [doc.to_dict() for doc in docs]
            if history:
                history.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
                return history[0]
        return None

    def mock_select():
        if roadmap_id:
            r = MOCK_ROADMAP_DB.get(roadmap_id)
            if r and r.get("user_id") == uid:
                return r
        else:
            user_roadmaps = [r for r in MOCK_ROADMAP_DB.values() if r.get("user_id") == uid]
            if user_roadmaps:
                user_roadmaps.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
                return user_roadmaps[0]
        return None

    try:
        record = handle_db_op(db_select, mock_select)
        if not record:
            return jsonify({"error": "Roadmap not found."}), 404

        pdf_bytes = generate_roadmap_pdf_bytes(record)
        if not pdf_bytes:
            return jsonify({"error": "Failed to generate roadmap PDF."}), 500

        cg = record.get("career_goal") or {}
        comp = (cg.get("company") if isinstance(cg, dict) else "Company").replace(" ", "_")
        role = (cg.get("role") if isinstance(cg, dict) else "Role").replace(" ", "_")
        filename = f"CareerPilot_Roadmap_{comp}_{role}.pdf"

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error during roadmap PDF export: {e}")
        return jsonify({"error": "Server error exporting roadmap PDF."}), 500


@roadmap_bp.route('/api/career-roadmap/<roadmap_id>/export-pdf', methods=['POST', 'GET'])
def export_roadmap_pdf(roadmap_id):
    return _run_export_pdf_handler(roadmap_id)

@roadmap_bp.route('/api/career-roadmap/export-pdf', methods=['POST', 'GET'])
def export_latest_career_roadmap_pdf():
    return _run_export_pdf_handler(None)

@roadmap_bp.route('/api/roadmap/export-pdf', methods=['POST', 'GET'])
def export_latest_roadmap_pdf_alias():
    return _run_export_pdf_handler(None)


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
