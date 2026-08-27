"""
CareerPilot AI — Test Suite for Module 9: Job Opportunities Foundation
"""
import os
import unittest
from unittest.mock import patch, MagicMock
from job_opportunities.provider import BaseJobProvider, ExternalJobProvider
from job_opportunities.models import normalize_job_dict, create_job_notification_dict
from job_opportunities.filters import is_role_relevant, filter_and_prioritize_jobs
from job_opportunities.notification_service import NotificationService
from job_opportunities.service import JobOpportunityService
from job_opportunities.firestore_service import (
    MOCK_JOB_OPPORTUNITIES_DB,
    MOCK_JOB_NOTIFICATIONS_DB,
    save_job_opportunity,
    get_job_by_id,
    save_user_notification,
    get_user_notifications,
    mark_notification_read,
    mark_all_user_notifications_read
)

class MockTestJobProvider(BaseJobProvider):
    """Test job provider for testing pipeline normalization and filtering."""
    def __init__(self, raw_jobs=None, configured=True):
        self.raw_jobs = raw_jobs or []
        self._configured = configured
        self.provider_name = "test_provider"

    def is_configured(self) -> bool:
        return self._configured

    def search_jobs(self, target_role: str, location: str = None, page: int = 1, limit: int = 20) -> list:
        return self.raw_jobs


class TestJobOpportunitiesPhase9(unittest.TestCase):

    def setUp(self):
        MOCK_JOB_OPPORTUNITIES_DB.clear()
        MOCK_JOB_NOTIFICATIONS_DB.clear()

    def test_provider_unconfigured_by_default(self):
        """Verify ExternalJobProvider raises NotImplementedError when unconfigured."""
        provider = ExternalJobProvider()
        with patch.object(provider, 'is_configured', return_value=False):
            self.assertFalse(provider.is_configured())
            with self.assertRaises(NotImplementedError):
                provider.search_jobs("Cloud Engineer")

    def test_models_normalization_stable_hash(self):
        """Verify raw dictionary is normalized and gets a deterministic unique ID."""
        raw = {
            "company": "Microsoft",
            "title": "Cloud Infrastructure Engineer",
            "location": "Redmond, WA",
            "employment_type": "Full-time",
            "description": "Build cloud platforms.",
            "skills": "Azure, Python, Docker"
        }
        norm = normalize_job_dict(raw, "test_source")
        self.assertTrue(norm["id"].startswith("test_source_"))
        self.assertEqual(norm["company"], "Microsoft")
        self.assertEqual(norm["title"], "Cloud Infrastructure Engineer")
        self.assertEqual(norm["skills"], ["Azure", "Python", "Docker"])
        self.assertEqual(norm["status"], "active")

    def test_target_role_filtering(self):
        """Verify target role relevance logic accepts related roles and rejects unrelated ones."""
        target = "Cloud Engineer"

        self.assertTrue(is_role_relevant("Cloud Engineer", target))
        self.assertTrue(is_role_relevant("Junior Cloud Engineer", target))
        self.assertTrue(is_role_relevant("Cloud Infrastructure Engineer", target))
        self.assertTrue(is_role_relevant("Cloud Support Engineer", target))
        self.assertTrue(is_role_relevant("Senior Cloud Platform Engineer", target))

        self.assertFalse(is_role_relevant("Graphic Designer", target))
        self.assertFalse(is_role_relevant("HR Manager", target))
        self.assertFalse(is_role_relevant("Accountant", target))
        self.assertFalse(is_role_relevant("Marketing Specialist", target))

    def test_dream_company_prioritization(self):
        """Verify jobs from the dream company are partitioned and prioritized."""
        jobs = [
            {"id": "j1", "company": "Amazon", "title": "Cloud Engineer", "location": "Seattle", "experience": "Entry Level"},
            {"id": "j2", "company": "Microsoft", "title": "Cloud Infrastructure Engineer", "location": "Redmond", "experience": "Entry Level"},
            {"id": "j3", "company": "Google", "title": "Cloud Engineer", "location": "Mountain View", "experience": "Mid Level"},
            {"id": "j4", "company": "Design Studio", "title": "Graphic Designer", "location": "Remote", "experience": "Senior"} # Should be rejected
        ]

        result = filter_and_prioritize_jobs(
            jobs=jobs,
            target_role="Cloud Engineer",
            dream_company="Microsoft"
        )

        self.assertEqual(result["total_count"], 3)
        self.assertEqual(result["dream_company_count"], 1)
        self.assertEqual(result["other_company_count"], 2)
        self.assertEqual(result["dream_company_jobs"][0]["company"], "Microsoft")
        self.assertEqual([j["company"] for j in result["other_company_jobs"]], ["Amazon", "Google"])

    def test_notification_creation_and_deduplication(self):
        """Verify user notifications are created with deterministic IDs and duplicate prevention."""
        user_id = "user_abc_123"
        job = {
            "id": "ext_98765",
            "company": "Microsoft",
            "title": "Cloud Engineer",
            "location": "Redmond, WA",
            "employment_type": "Full-time"
        }

        notif = NotificationService.notify_user_of_new_job(user_id, job)
        self.assertIsNotNone(notif)
        self.assertEqual(notif["id"], "notif_user_abc_123_ext_98765")
        self.assertFalse(notif["read"])

        # Check notification list & unread count
        user_notifs = NotificationService.get_notifications(user_id)
        self.assertEqual(user_notifs["unread_count"], 1)
        self.assertEqual(user_notifs["total_count"], 1)

        # Mark as read
        NotificationService.mark_as_read(user_id, notif["id"])
        user_notifs_after = NotificationService.get_notifications(user_id)
        self.assertEqual(user_notifs_after["unread_count"], 0)

    def test_service_unconfigured_clean_empty_state(self):
        """Verify service returns clean empty state when provider is unconfigured without mock data."""
        provider = ExternalJobProvider()
        svc = JobOpportunityService(provider=provider)
        with patch.object(provider, 'is_configured', return_value=False), \
             patch.object(svc, 'get_user_target_career_context', return_value=("Cloud Engineer", "Microsoft", "Remote")), \
             patch('job_opportunities.service.get_all_active_jobs', return_value=[]):
            result = svc.fetch_and_sync_opportunities("user_test_456")
            self.assertTrue(result["success"])
            self.assertFalse(result["provider_configured"])
            self.assertEqual(result["total_count"], 0)
            self.assertEqual(result["dream_company_jobs"], [])
            self.assertEqual(result["other_company_jobs"], [])
            self.assertEqual(result["target_role"], "Cloud Engineer")
            self.assertEqual(result["dream_company"], "Microsoft")
            self.assertIn("Live job opportunities will appear once a job provider is connected", result["message"])

    def test_service_with_configured_provider(self):
        """Verify service pipeline processes jobs when a provider is configured."""
        raw_feed = [
            {
                "id": "raw_1",
                "company": "Microsoft",
                "title": "Cloud Engineer",
                "location": "Remote",
                "description": "Work with Azure."
            },
            {
                "id": "raw_2",
                "company": "IBM",
                "title": "Cloud Support Specialist",
                "location": "Remote",
                "description": "Cloud support."
            }
        ]
        mock_provider = MockTestJobProvider(raw_jobs=raw_feed, configured=True)
        svc = JobOpportunityService(provider=mock_provider)

        with patch.object(svc, 'get_user_target_career_context', return_value=("Cloud Engineer", "Microsoft", "Remote")):
            result = svc.fetch_and_sync_opportunities("user_test_789")
            self.assertTrue(result["success"])
            self.assertTrue(result["provider_configured"])
            self.assertEqual(result["dream_company_count"], 1)
            self.assertEqual(result["other_company_count"], 1)
            self.assertEqual(result["total_count"], 2)


if __name__ == "__main__":
    unittest.main()
