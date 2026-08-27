"""
CareerPilot AI — Test Suite for Adzuna Job & Hiring Notification Module
"""
import os
import unittest
from unittest.mock import patch, MagicMock
from services.adzuna_service import AdzunaService
from job_opportunities.provider import ExternalJobProvider, BaseJobProvider
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
    get_user_notifications
)

class TestAdzunaServiceAndJobOpportunities(unittest.TestCase):

    def setUp(self):
        MOCK_JOB_OPPORTUNITIES_DB.clear()
        MOCK_JOB_NOTIFICATIONS_DB.clear()

    def test_adzuna_service_is_configured_validation(self):
        """Verify AdzunaService accurately detects valid vs missing or placeholder credentials."""
        # Unconfigured
        srv_empty = AdzunaService(app_id="", app_key="")
        self.assertFalse(srv_empty.is_configured())

        # Placeholder
        srv_placeholder = AdzunaService(app_id="your_adzuna_id", app_key="your_adzuna_key")
        self.assertFalse(srv_placeholder.is_configured())

        # Valid
        srv_valid = AdzunaService(app_id="test_app_id", app_key="test_app_key", country="in")
        self.assertTrue(srv_valid.is_configured())

    def test_adzuna_service_normalization(self):
        """Verify Adzuna raw response is normalized into standardized job object."""
        service = AdzunaService(app_id="test_id", app_key="test_key", country="in")
        raw_item = {
            "id": "12345678",
            "title": "<strong>Cloud</strong> Engineer",
            "company": {"display_name": "Microsoft"},
            "location": {"display_name": "Bengaluru, Karnataka"},
            "description": "Looking for a Cloud Engineer with <b>Python</b>, AWS, and Docker skills.",
            "created": "2026-08-20T10:00:00Z",
            "salary_min": 1200000,
            "salary_max": 1800000,
            "contract_type": "permanent",
            "category": {"label": "IT Jobs"},
            "redirect_url": "https://www.adzuna.in/land/ad/12345678"
        }

        norm = service.normalize_adzuna_job(raw_item, dream_company="Microsoft")

        self.assertEqual(norm["job_id"], "adzuna_12345678")
        self.assertEqual(norm["title"], "Cloud Engineer")
        self.assertEqual(norm["company"], "Microsoft")
        self.assertEqual(norm["location"], "Bengaluru, Karnataka")
        self.assertEqual(norm["salary_min"], 1200000)
        self.assertEqual(norm["salary_max"], 1800000)
        self.assertEqual(norm["source"], "Adzuna")
        self.assertEqual(norm["application_url"], "https://www.adzuna.in/land/ad/12345678")
        self.assertTrue(norm["is_dream_company"])
        self.assertIn("Python", norm["skills"])
        self.assertIn("AWS", norm["skills"])
        self.assertIn("Docker", norm["skills"])

    @patch("services.adzuna_service.requests.get")
    def test_adzuna_search_jobs_success(self, mock_get):
        """Verify successful Adzuna API search parsing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "id": "ad_1",
                    "title": "Cloud Infrastructure Engineer",
                    "company": {"display_name": "Amazon"},
                    "location": {"display_name": "Hyderabad"},
                    "description": "Cloud infra role",
                    "redirect_url": "https://adzuna.in/ad1"
                },
                {
                    "id": "ad_2",
                    "title": "Cloud Operations Engineer",
                    "company": {"display_name": "Microsoft"},
                    "location": {"display_name": "Bengaluru"},
                    "description": "Azure cloud operations",
                    "redirect_url": "https://adzuna.in/ad2"
                }
            ]
        }
        mock_get.return_value = mock_resp

        service = AdzunaService(app_id="valid_id", app_key="valid_key", country="in")
        jobs = service.fetch_relevant_jobs(target_role="Cloud Engineer", dream_company="Microsoft")

        self.assertEqual(len(jobs), 2)
        # Microsoft is dream company so it should be prioritized at index 0
        self.assertEqual(jobs[0]["company"], "Microsoft")
        self.assertTrue(jobs[0]["is_dream_company"])
        self.assertEqual(jobs[1]["company"], "Amazon")
        self.assertFalse(jobs[1]["is_dream_company"])

    @patch("services.adzuna_service.requests.get")
    def test_adzuna_api_error_handling(self, mock_get):
        """Verify network errors and 401/403/500 responses return clean empty list without crashing."""
        service = AdzunaService(app_id="valid_id", app_key="valid_key", country="in")

        # 401 Unauthorized
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp
        results = service.search_jobs("Cloud Engineer")
        self.assertEqual(results, [])

        # Timeout Exception
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        results = service.search_jobs("Cloud Engineer")
        self.assertEqual(results, [])

    def test_target_role_variations_filtering(self):
        """Verify target role filtering matches relevant title variations and rejects unrelated roles."""
        target = "Cloud Engineer"

        # Valid variations
        self.assertTrue(is_role_relevant("Cloud Engineer", target))
        self.assertTrue(is_role_relevant("Junior Cloud Engineer", target))
        self.assertTrue(is_role_relevant("Associate Cloud Engineer", target))
        self.assertTrue(is_role_relevant("Cloud Infrastructure Engineer", target))
        self.assertTrue(is_role_relevant("Cloud Operations Engineer", target))
        self.assertTrue(is_role_relevant("Cloud Support Engineer", target))

        # Unrelated roles
        self.assertFalse(is_role_relevant("Graphic Designer", target))
        self.assertFalse(is_role_relevant("HR Manager", target))
        self.assertFalse(is_role_relevant("Accountant", target))
        self.assertFalse(is_role_relevant("Marketing Specialist", target))

    def test_dream_company_and_other_companies_partitioning(self):
        """Verify dream company listings and other company listings are both returned without restricting user."""
        jobs = [
            {"id": "j1", "company": "Microsoft", "title": "Cloud Engineer", "location": "Bengaluru"},
            {"id": "j2", "company": "Google", "title": "Cloud Infrastructure Engineer", "location": "Hyderabad"},
            {"id": "j3", "company": "AWS", "title": "Associate Cloud Engineer", "location": "Mumbai"},
            {"id": "j4", "company": "Accenture", "title": "Senior Accountant", "location": "Pune"}  # Rejection
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
        other_companies = [j["company"] for j in result["other_company_jobs"]]
        self.assertIn("Google", other_companies)
        self.assertIn("AWS", other_companies)

    def test_duplicate_removal(self):
        """Verify duplicate job postings across primary and secondary searches are deduplicated."""
        raw_items = [
            {
                "id": "1001",
                "title": "Cloud Engineer",
                "company": {"display_name": "Microsoft"},
                "redirect_url": "https://adzuna.in/ad1001"
            },
            {
                "id": "1001",  # duplicate ID
                "title": "Cloud Engineer",
                "company": {"display_name": "Microsoft"},
                "redirect_url": "https://adzuna.in/ad1001"
            }
        ]

        service = AdzunaService(app_id="test", app_key="test")
        with patch.object(service, "search_jobs", return_value=raw_items):
            jobs = service.fetch_relevant_jobs(target_role="Cloud Engineer", dream_company="Microsoft")
            self.assertEqual(len(jobs), 1)

    def test_frontend_security_no_api_keys(self):
        """Verify ADZUNA_APP_KEY is NEVER present in frontend JS/HTML files."""
        frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
        for root, _, files in os.walk(frontend_dir):
            for file in files:
                if file.endswith((".js", ".html", ".json", ".css")):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        self.assertNotIn("ADZUNA_APP_KEY", content, f"Secret key found in frontend file: {file}")
                        self.assertNotIn("adzuna_app_key", content.lower(), f"Secret key found in frontend file: {file}")

    def test_notification_tracking_in_firestore(self):
        """Verify new job opportunities trigger user notification records in Firestore."""
        user_id = "user_test_adzuna_456"
        job = {
            "id": "adzuna_8899",
            "company": "Microsoft",
            "title": "Cloud Engineer",
            "location": "Bengaluru",
            "application_url": "https://adzuna.in/ad8899"
        }

        notif = NotificationService.notify_user_of_new_job(user_id, job)
        self.assertIsNotNone(notif)
        self.assertEqual(notif["user_id"], user_id)
        self.assertEqual(notif["job_id"], "adzuna_8899")

        # Check retrieving notifications for user
        user_notifs = NotificationService.get_notifications(user_id)
        self.assertEqual(user_notifs["total_count"], 1)
        self.assertEqual(user_notifs["unread_count"], 1)

        # Mark as read
        NotificationService.mark_as_read(user_id, notif["id"])
        updated_notifs = NotificationService.get_notifications(user_id)
        self.assertEqual(updated_notifs["unread_count"], 0)


if __name__ == '__main__':
    unittest.main()
