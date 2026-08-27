"""
CareerPilot AI — In-App Job Notification Management Service
"""
import logging
from job_opportunities.models import create_job_notification_dict
from job_opportunities.firestore_service import (
    save_user_notification,
    get_user_notifications,
    mark_notification_read,
    mark_all_user_notifications_read
)

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Manages generation, delivery, and read-state for user job opportunity notifications.
    """
    @staticmethod
    def notify_user_of_new_job(user_id: str, job: dict) -> dict:
        """
        Creates and persists a notification for a newly detected job if not already notified.
        Prevents duplicate notifications via deterministic notification IDs.
        """
        if not user_id or not job or not job.get("id"):
            return None

        notif_dict = create_job_notification_dict(user_id, job)
        saved = save_user_notification(user_id, notif_dict)
        logger.info(f"NotificationService: Created notification '{notif_dict['id']}' for user '{user_id}'.")
        return saved

    @staticmethod
    def get_notifications(user_id: str) -> dict:
        """
        Fetches all notifications and unread count for a given user.
        """
        all_notifs = get_user_notifications(user_id)
        unread_count = sum(1 for n in all_notifs if not n.get("read"))
        return {
            "notifications": all_notifs,
            "unread_count": unread_count,
            "total_count": len(all_notifs)
        }

    @staticmethod
    def mark_as_read(user_id: str, notification_id: str) -> bool:
        return mark_notification_read(user_id, notification_id)

    @staticmethod
    def mark_all_as_read(user_id: str) -> int:
        return mark_all_user_notifications_read(user_id)
