"""
CareerPilot AI — Job Opportunity Core Orchestration Service
"""
import logging
from firebase_client import db
from job_opportunities.provider import ExternalJobProvider, BaseJobProvider
from job_opportunities.models import normalize_job_dict
from job_opportunities.filters import filter_and_prioritize_jobs
from job_opportunities.notification_service import NotificationService
from job_opportunities.firestore_service import (
    save_job_opportunity,
    get_all_active_jobs,
    get_job_by_id
)

logger = logging.getLogger(__name__)

class JobOpportunityService:
    """
    Core service responsible for:
    1. Retrieving authenticated user's target role & dream company from Firestore.
    2. Querying configured JobProvider (Adzuna) without creating fake mock jobs.
    3. Normalizing, deduplicating, and filtering by target role.
    4. Prioritizing dream company opportunities.
    5. Triggering notifications for genuinely new jobs in Firestore.
    """
    def __init__(self, provider: BaseJobProvider = None):
        self.provider = provider or ExternalJobProvider()

    def get_user_target_career_context(self, user_id: str) -> tuple:
        """
        Fetches the user's active target role, dream company, and location from Firestore `career_goals` or `profiles`.
        """
        target_role = ""
        dream_company = ""
        location_pref = ""

        if db is not None:
            try:
                goal_docs = db.collection("career_goals").where("user_id", "==", user_id).where("status", "==", "active").stream()
                goals = [d.to_dict() for d in goal_docs]
                if goals:
                    active = goals[0]
                    target_role = active.get("job_role", "").strip()
                    dream_company = active.get("company_name", "").strip()
                    location_pref = active.get("target_location", "").strip()
            except Exception as e:
                logger.warning(f"Error reading career_goals from Firestore: {e}")

            # Also check profile if not found in career goals
            if not target_role:
                try:
                    prof_doc = db.collection("profiles").document(user_id).get()
                    if prof_doc.exists:
                        pdata = prof_doc.to_dict() or {}
                        target_role = pdata.get("target_role") or pdata.get("desired_role") or ""
                        if not dream_company:
                            dream_company = pdata.get("dream_company") or pdata.get("target_company") or ""
                        if not location_pref:
                            location_pref = pdata.get("location") or ""
                except Exception as e:
                    logger.warning(f"Error reading profile from Firestore: {e}")

        if not target_role:
            from career_goal_routes import MOCK_CAREER_GOALS_DB
            active_mock = next((g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == user_id and g.get("status") == "active"), None)
            if active_mock:
                target_role = active_mock.get("job_role", "").strip()
                dream_company = active_mock.get("company_name", "").strip()
                location_pref = active_mock.get("target_location", "").strip()

        return target_role, dream_company, location_pref

    def fetch_and_sync_opportunities(self, user_id: str, client_filters: dict = None) -> dict:
        """
        Coordinates live search or cached results retrieval.
        Returns a clean unconfigured / empty response when appropriate.
        """
        target_role, dream_company, location_pref = self.get_user_target_career_context(user_id)

        # Empty state if user has no target role
        if not target_role:
            return {
                "success": True,
                "provider_configured": self.provider.is_configured(),
                "target_role": "",
                "dream_company": dream_company,
                "dream_company_jobs": [],
                "other_company_jobs": [],
                "total_count": 0,
                "dream_company_count": 0,
                "other_company_count": 0,
                "message": "Please complete your Career Goal to receive relevant job opportunities."
            }

        is_configured = self.provider.is_configured()

        # If provider is not configured, do NOT invent mock jobs. Return clean status.
        if not is_configured:
            cached_jobs = get_all_active_jobs()
            if not cached_jobs:
                return {
                    "success": True,
                    "provider_configured": False,
                    "target_role": target_role,
                    "dream_company": dream_company,
                    "dream_company_jobs": [],
                    "other_company_jobs": [],
                    "total_count": 0,
                    "dream_company_count": 0,
                    "other_company_count": 0,
                    "message": "Live job opportunities will appear once a job provider is connected."
                }
            all_jobs = cached_jobs
        else:
            try:
                if hasattr(self.provider, "fetch_relevant_jobs"):
                    raw_results = self.provider.fetch_relevant_jobs(
                        target_role=target_role,
                        dream_company=dream_company,
                        location=location_pref
                    )
                else:
                    raw_results = self.provider.search_jobs(
                        target_role=target_role,
                        location=location_pref
                    )

                all_jobs = []
                for r in raw_results:
                    norm = normalize_job_dict(r, getattr(self.provider, "provider_name", "adzuna"))
                    saved = save_job_opportunity(norm)
                    all_jobs.append(saved)
                    # Trigger user notification for new job
                    NotificationService.notify_user_of_new_job(user_id, saved)
            except NotImplementedError:
                return {
                    "success": True,
                    "provider_configured": False,
                    "target_role": target_role,
                    "dream_company": dream_company,
                    "dream_company_jobs": [],
                    "other_company_jobs": [],
                    "total_count": 0,
                    "dream_company_count": 0,
                    "other_company_count": 0,
                    "message": "Live job opportunities will appear once a job provider is connected."
                }
            except Exception as ex:
                logger.error(f"Error fetching jobs from provider: {ex}", exc_info=True)
                all_jobs = get_all_active_jobs()

        # Apply filtering & dream company prioritization
        filtered = filter_and_prioritize_jobs(
            jobs=all_jobs,
            target_role=target_role,
            dream_company=dream_company,
            client_filters=client_filters
        )

        total = filtered.get("total_count", 0)
        dream_cnt = filtered.get("dream_company_count", 0)

        if total == 0:
            msg = "No current openings found for your target role. Check again later."
        elif dream_company and dream_cnt == 0:
            msg = "No current opportunities found for your dream company. Here are other opportunities matching your target role."
        else:
            msg = "Opportunities loaded successfully."

        return {
            "success": True,
            "provider_configured": is_configured,
            **filtered,
            "message": msg
        }

    def get_opportunity_detail(self, job_id: str) -> dict:
        """
        Retrieves detailed information for a single job opportunity.
        """
        return get_job_by_id(job_id)
