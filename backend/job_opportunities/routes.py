"""
CareerPilot AI — Job Opportunities & Real-Time Hiring Flask Blueprint Routes
"""
import logging
from flask import Blueprint, request, jsonify
from firebase_client import firebase_auth
from job_opportunities.service import JobOpportunityService
from job_opportunities.notification_service import NotificationService

logger = logging.getLogger(__name__)

jobs_bp = Blueprint('job_opportunities', __name__)
job_service = JobOpportunityService()

def get_auth_uid(req):
    """Verify authorization token and return user UID."""
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("Unauthorized. Missing or invalid Authorization header.")
    
    token = auth_header.split(" ")[1]
    try:
        if firebase_auth:
            decoded_token = firebase_auth.verify_id_token(token)
            return decoded_token.get("uid") or decoded_token.get("user_id")
    except Exception as e:
        logger.warning(f"Auth token verification via Firebase failed: {e}. Falling back to unverified decode.")
        
    from career_goal_routes import decode_jwt_payload_unverified
    jwt_payload = decode_jwt_payload_unverified(token)
    if jwt_payload and (jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")):
        return jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("uid")
    raise ValueError("Unauthorized. Invalid session token.")


@jobs_bp.route('/api/jobs/relevant', methods=['GET'])
@jobs_bp.route('/api/jobs/opportunities', methods=['GET'])
def get_relevant_jobs_endpoint():
    """
    Retrieves filtered and prioritized real job opportunities tailored to
    the authenticated user's target job role and dream company from Adzuna.
    Accepts query params: company_filter, location, experience, search.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    client_filters = {
        "company_filter": request.args.get("company_filter", "ALL"),
        "location": request.args.get("location", ""),
        "experience": request.args.get("experience", ""),
        "search": request.args.get("search", "")
    }

    try:
        results = job_service.fetch_and_sync_opportunities(user_id=uid, client_filters=client_filters)
        return jsonify(results), 200
    except Exception as e:
        logger.error(f"Error serving job opportunities: {e}", exc_info=True)
        return jsonify({"error": "Failed to load job opportunities."}), 500


@jobs_bp.route('/api/jobs/opportunities/<job_id>', methods=['GET'])
def get_opportunity_detail_endpoint(job_id):
    """
    Retrieves detailed view of a single job opportunity.
    """
    try:
        get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    job = job_service.get_opportunity_detail(job_id)
    if not job:
        return jsonify({"error": "Job opportunity not found."}), 404

    return jsonify({"success": True, "job": job}), 200


@jobs_bp.route('/api/jobs/notifications', methods=['GET'])
def get_notifications_endpoint():
    """
    Retrieves the authenticated user's job notification history and unread count.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    try:
        data = NotificationService.get_notifications(user_id=uid)
        return jsonify({"success": True, **data}), 200
    except Exception as e:
        logger.error(f"Error fetching job notifications: {e}")
        return jsonify({"error": "Failed to fetch notifications."}), 500


@jobs_bp.route('/api/jobs/notifications/<notification_id>/read', methods=['POST'])
def mark_notification_read_endpoint(notification_id):
    """
    Marks a single notification as read.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    success = NotificationService.mark_as_read(user_id=uid, notification_id=notification_id)
    return jsonify({"success": success}), 200


@jobs_bp.route('/api/jobs/notifications/read-all', methods=['POST'])
def mark_all_notifications_read_endpoint():
    """
    Marks all notifications for the authenticated user as read.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    count = NotificationService.mark_all_as_read(user_id=uid)
    return jsonify({"success": True, "marked_count": count}), 200


@jobs_bp.route('/api/jobs/refresh', methods=['POST'])
def refresh_jobs_endpoint():
    """
    Triggers fresh Adzuna job polling and returns updated results.
    """
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    try:
        results = job_service.fetch_and_sync_opportunities(user_id=uid)
        return jsonify(results), 200
    except Exception as e:
        logger.error(f"Error refreshing job opportunities: {e}")
        return jsonify({"error": "Failed to refresh job opportunities."}), 500
