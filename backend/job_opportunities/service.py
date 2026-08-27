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
    1. Retrieving authenticated user's target role & dream company.
    2. Querying configured JobProvider (clean empty handling when unconfigured).
    3. Normalizing, deduplicating, and filtering by target role.
    4. Prioritizing dream company opportunities.
    5. Triggering notifications for genuinely new jobs.
    """
    def __init__(self, provider: BaseJobProvider = None):
        self.provider = provider or ExternalJobProvider()

    def get_user_target_career_context(self, user_id: str) -> tuple:
        """
        Fetches the user's active target role and dream company from Firestore `career_goals`.
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
        Returns a clean unconfigured response if provider is not yet active.
        """
        target_role, dream_company, location_pref = self.get_user_target_career_context(user_id)

        is_configured = self.provider.is_configured()

        # If provider is not configured, do NOT invent mock jobs. Return clean status.
        if not is_configured:
            # Check if any previously cached real jobs exist in Firestore
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
                raw_results = self.provider.search_jobs(target_role=target_role, location=location_pref)
                all_jobs = []
                for r in raw_results:
                    norm = normalize_job_dict(r, getattr(self.provider, "provider_name", "external"))
                    saved = save_job_opportunity(norm)
                    all_jobs.append(saved)
                    # Trigger notification for new job
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
                logger.error(f"Error fetching jobs from provider: {ex}")
                all_jobs = get_all_active_jobs()

        # Apply filtering & dream company prioritization
        filtered = filter_and_prioritize_jobs(
            jobs=all_jobs,
            target_role=target_role,
            dream_company=dream_company,
            client_filters=client_filters
        )

        return {
            "success": True,
            "provider_configured": is_configured,
            **filtered,
            "message": "Opportunities loaded successfully." if (filtered["total_count"] > 0 or is_configured) else "Live job opportunities will appear once a job provider is connected."
        }

    def get_opportunity_detail(self, job_id: str) -> dict:
        """
        Retrieves detailed information for a single job opportunity.
        """
        job = get_job_by_id(job_id)
        return job
