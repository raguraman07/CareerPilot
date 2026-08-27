"""
CareerPilot AI — Job Opportunities Firestore Persistence & Isolation Service
"""
import logging
from firebase_client import db

logger = logging.getLogger(__name__)

# In-memory mock databases for testing and offline resilience
MOCK_JOB_OPPORTUNITIES_DB = {}
MOCK_JOB_NOTIFICATIONS_DB = {}

def save_job_opportunity(job: dict) -> dict:
    """
    Saves a normalized job opportunity to Firestore collection 'job_opportunities'.
    """
    job_id = job.get("id")
    if not job_id:
        return job

    if db is not None:
        try:
            db.collection("job_opportunities").document(job_id).set(job, merge=True)
            return job
        except Exception as e:
            logger.warning(f"Firestore save_job_opportunity failed: {e}. Falling back to in-memory store.")

    MOCK_JOB_OPPORTUNITIES_DB[job_id] = job
    return job


def get_job_by_id(job_id: str) -> dict:
    """
    Retrieves a single job opportunity by ID.
    """
    if db is not None:
        try:
            doc = db.collection("job_opportunities").document(job_id).get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logger.warning(f"Firestore get_job_by_id failed: {e}.")

    return MOCK_JOB_OPPORTUNITIES_DB.get(job_id)


def get_all_active_jobs() -> list:
    """
    Retrieves all active job opportunities from Firestore.
    """
    if db is not None:
        try:
            docs = db.collection("job_opportunities").where("status", "==", "active").stream()
            return [d.to_dict() for d in docs]
        except Exception as e:
            logger.warning(f"Firestore get_all_active_jobs failed: {e}.")

    return list(MOCK_JOB_OPPORTUNITIES_DB.values())


def save_user_notification(user_id: str, notification: dict) -> dict:
    """
    Saves a notification to the user's isolated subcollection: users/{user_id}/job_notifications.
    """
    notif_id = notification.get("id")
    if not notif_id or not user_id:
        return notification

    if db is not None:
        try:
            db.collection("users").document(user_id).collection("job_notifications").document(notif_id).set(notification, merge=True)
            return notification
        except Exception as e:
            logger.warning(f"Firestore save_user_notification failed: {e}.")

    if user_id not in MOCK_JOB_NOTIFICATIONS_DB:
        MOCK_JOB_NOTIFICATIONS_DB[user_id] = {}
    MOCK_JOB_NOTIFICATIONS_DB[user_id][notif_id] = notification
    return notification


def get_user_notifications(user_id: str) -> list:
    """
    Retrieves all notifications for a specific user, sorted newest first.
    """
    if not user_id:
        return []

    if db is not None:
        try:
            docs = db.collection("users").document(user_id).collection("job_notifications").stream()
            notifs = [d.to_dict() for d in docs]
            notifs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return notifs
        except Exception as e:
            logger.warning(f"Firestore get_user_notifications failed: {e}.")

    user_dict = MOCK_JOB_NOTIFICATIONS_DB.get(user_id, {})
    notifs = list(user_dict.values())
    notifs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return notifs


def mark_notification_read(user_id: str, notification_id: str) -> bool:
    """
    Marks a single user notification as read.
    """
    if not user_id or not notification_id:
        return False

    if db is not None:
        try:
            ref = db.collection("users").document(user_id).collection("job_notifications").document(notification_id)
            ref.update({"read": True})
            return True
        except Exception as e:
            logger.warning(f"Firestore mark_notification_read failed: {e}.")

    if user_id in MOCK_JOB_NOTIFICATIONS_DB and notification_id in MOCK_JOB_NOTIFICATIONS_DB[user_id]:
        MOCK_JOB_NOTIFICATIONS_DB[user_id][notification_id]["read"] = True
        return True
    return False


def mark_all_user_notifications_read(user_id: str) -> int:
    """
    Marks all notifications for a given user as read.
    """
    if not user_id:
        return 0

    count = 0
    if db is not None:
        try:
            docs = db.collection("users").document(user_id).collection("job_notifications").where("read", "==", False).stream()
            for d in docs:
                d.reference.update({"read": True})
                count += 1
            return count
        except Exception as e:
            logger.warning(f"Firestore mark_all_user_notifications_read failed: {e}.")

    if user_id in MOCK_JOB_NOTIFICATIONS_DB:
        for notif in MOCK_JOB_NOTIFICATIONS_DB[user_id].values():
            if not notif.get("read"):
                notif["read"] = True
                count += 1
    return count
