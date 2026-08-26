import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(__file__))

import importlib.util
backend_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(backend_dir, "server.py") if os.path.exists(os.path.join(backend_dir, "server.py")) else os.path.join(backend_dir, "app.py")
spec = importlib.util.spec_from_file_location("app_module", app_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)
app = app_module.app

from profile_routes import MOCK_PROFILES_DB, calculate_profile_completeness
from career_goal_routes import MOCK_CAREER_GOALS_DB
from resume_routes import MOCK_RESUMES_DB

class TestProfilePhase2(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_PROFILES_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_RESUMES_DB.clear()
        # Patch handle_db_op to run fallback (mock mode) during unit testing
        self.db_patcher = patch('profile_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_PROFILES_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_RESUMES_DB.clear()

    def test_completeness_calculation(self):
        # 1. Empty profile
        empty_profile = {}
        self.assertEqual(calculate_profile_completeness(empty_profile), 0)

        # 2. Fresher with basic details and 0 projects/certs/resume
        fresher_profile = {
            "full_name": "Alice",
            "email": "alice@example.com",
            "location": "India",
            "education": {
                "highest_education": "B.Tech",
                "institution": "Tech University"
            },
            "career_information": {
                "current_status": "Fresher"
            },
            "skills": {
                "programming_languages": ["Python", "JavaScript"],
                "technical_skills": ["SQL"]
            }
        }
        # Personal (15) + Education (20) + Status (15) + Skills 3+ (25) = 75
        self.assertEqual(calculate_profile_completeness(fresher_profile), 75)

        # 3. Full profile with project & certification
        full_profile = {
            **fresher_profile,
            "projects": [{"title": "Cloud App", "description": "Serverless"}],
            "certifications": [{"name": "AWS Certified"}]
        }
        # 75 + Projects (15) + Cert (10) = 100
        self.assertEqual(calculate_profile_completeness(full_profile), 100)

    @patch('profile_routes.get_auth_uid')
    def test_get_profile_default(self, mock_uid):
        mock_uid.return_value = "user-alice-123"
        res = self.client.get('/api/profile', headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["profile"]["user_id"], "user-alice-123")
        self.assertEqual(data["profile"]["completeness"], 0)

    @patch('profile_routes.get_auth_uid')
    def test_update_profile_success(self, mock_uid):
        mock_uid.return_value = "user-alice-123"

        payload = {
            "full_name": "Alice Smith",
            "email": "alice@test.com",
            "phone": "+91 9999988888",
            "location": "Mumbai",
            "education": {
                "highest_education": "B.Tech",
                "degree": "B.Tech in CS",
                "specialization": "Computer Science",
                "institution": "IIT Bombay",
                "graduation_year": "2024"
            },
            "career_information": {
                "current_status": "Fresher",
                "years_of_experience": "0",
                "current_role": "Aspiring Cloud Engineer"
            },
            "skills": {
                "programming_languages": ["Python", "Java"],
                "technical_skills": ["Docker", "Linux"],
                "tools_and_technologies": ["Git", "VS Code"],
                "soft_skills": ["Teamwork"]
            },
            "projects": [
                {
                    "title": "CareerPilot AI",
                    "description": "AI Career platform",
                    "technologies": ["Python", "Flask"]
                }
            ],
            "certifications": [
                {
                    "name": "Azure Fundamentals",
                    "issuing_organization": "Microsoft"
                }
            ]
        }

        res = self.client.put('/api/profile', json=payload, headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        profile = data["profile"]
        self.assertEqual(profile["full_name"], "Alice Smith")
        self.assertEqual(profile["education"]["highest_education"], "B.Tech")
        self.assertEqual(profile["career_information"]["current_status"], "Fresher")
        self.assertEqual(len(profile["skills"]["programming_languages"]), 2)
        self.assertEqual(len(profile["projects"]), 1)
        self.assertEqual(profile["completeness"], 100)

    def test_profile_unauthorized(self):
        res = self.client.get('/api/profile')
        self.assertEqual(res.status_code, 401)

        res_put = self.client.put('/api/profile', json={"full_name": "Hacker"})
        self.assertEqual(res_put.status_code, 401)

    @patch('profile_routes.get_auth_uid')
    def test_ai_career_context_builder(self, mock_uid):
        mock_uid.return_value = "user-alice-123"

        # 1. Setup mock goal
        MOCK_CAREER_GOALS_DB["goal-1"] = {
            "id": "goal-1",
            "user_id": "user-alice-123",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "status": "active"
        }

        # 2. Setup mock profile
        MOCK_PROFILES_DB["user-alice-123"] = {
            "id": "user-alice-123",
            "user_id": "user-alice-123",
            "full_name": "Alice Smith",
            "career_information": {"current_status": "Fresher"},
            "skills": {"technical_skills": ["Linux", "AWS"]}
        }

        # 3. Setup mock resume
        MOCK_RESUMES_DB["res-1"] = {
            "id": "res-1",
            "user_id": "user-alice-123",
            "filename": "alice_resume.pdf",
            "extracted_text": "Experienced in Python and Linux.",
            "uploaded_at": "2026-08-26T10:00:00Z"
        }

        res = self.client.get('/api/profile/context', headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["career_goal"]["company_name"], "Microsoft")
        self.assertEqual(data["candidate"]["full_name"], "Alice Smith")
        self.assertTrue(data["resume"]["available"])
        self.assertIn("Python and Linux", data["resume"]["extracted_text"])

if __name__ == '__main__':
    unittest.main()
