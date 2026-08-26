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

from assessment_routes import MOCK_ASSESSMENTS_DB, MOCK_TARGETS_DB
from career_goal_routes import MOCK_CAREER_GOALS_DB
from profile_routes import MOCK_PROFILES_DB
from resume_routes import MOCK_RESUMES_DB
from services.career_assessment_service import validate_assessment_json, generate_rule_based_fallback_assessment

class TestCareerAssessmentPhase3(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_ASSESSMENTS_DB.clear()
        MOCK_TARGETS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_RESUMES_DB.clear()
        # Patch handle_db_op to run fallback (mock mode) during unit testing
        self.db_patcher = patch('assessment_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_ASSESSMENTS_DB.clear()
        MOCK_TARGETS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_RESUMES_DB.clear()

    def test_schema_validator(self):
        valid = {
            "career_readiness_score": 70,
            "ats_score": 75,
            "summary": "Valid summary",
            "strong_matches": ["Python"],
            "partial_matches": ["Linux"],
            "skill_gaps": [{"skill": "Azure", "priority": "HIGH"}],
            "programming_language_gaps": [{"language": "Python", "status": "Already know"}],
            "knowledge_gaps": [{"topic": "Cloud Networks", "priority": "HIGH"}],
            "resume_gaps": ["Add metrics"],
            "certification_relevance": [{"name": "AZ-900", "type": "Recommended"}],
            "project_gaps": {"existing_strengths": ["Web"], "recommended_projects": []},
            "priority_actions": ["1. Learn Azure"]
        }
        self.assertTrue(validate_assessment_json(valid))

        invalid = {"summary": "Incomplete"}
        self.assertFalse(validate_assessment_json(invalid))

    def test_rule_based_fallback_assessment(self):
        goal = {"company_name": "Microsoft", "job_role": "Cloud Engineer"}
        profile = {
            "full_name": "John Doe",
            "skills": {"programming_languages": ["Python", "SQL"], "technical_skills": ["Linux", "Flask"]},
            "projects": [{"title": "CareerPilot AI"}]
        }
        resume = {"available": False, "extracted_text": ""}

        res = generate_rule_based_fallback_assessment(goal, profile, resume)
        self.assertIn("career_readiness_score", res)
        self.assertIn("ats_score", res)
        self.assertEqual(res["target_company"], "Microsoft")
        self.assertEqual(res["target_job_role"], "Cloud Engineer")
        self.assertTrue(len(res["strong_matches"]) > 0)
        self.assertTrue(len(res["skill_gaps"]) > 0)
        self.assertTrue(len(res["priority_actions"]) >= 3)

    @patch('assessment_routes.get_auth_uid')
    def test_assessment_no_goal_returns_400(self, mock_uid):
        mock_uid.return_value = "user-no-goal"
        res = self.client.post('/api/assessment/generate', headers={'Authorization': 'Bearer fake-token'}, json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("No active career goal found", res.get_json()["error"])

    @patch('assessment_routes.get_auth_uid')
    def test_assessment_generate_and_cache(self, mock_uid):
        mock_uid.return_value = "user-cloud-123"

        # 1. Setup active career goal
        MOCK_CAREER_GOALS_DB["goal-123"] = {
            "id": "goal-123",
            "user_id": "user-cloud-123",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher",
            "status": "active"
        }

        # 2. Setup candidate profile
        MOCK_PROFILES_DB["user-cloud-123"] = {
            "id": "user-cloud-123",
            "user_id": "user-cloud-123",
            "full_name": "Alice Cloud",
            "skills": {
                "programming_languages": ["Python", "SQL"],
                "technical_skills": ["Linux", "Flask"]
            },
            "projects": [{"title": "Web App", "technologies": ["Python", "Flask"]}],
            "completeness": 80,
            "updated_at": "2026-08-26T10:00:00Z"
        }

        # First Call: Generates fresh assessment
        res1 = self.client.post('/api/assessment/generate', headers={'Authorization': 'Bearer fake-token'}, json={})
        self.assertEqual(res1.status_code, 201)
        data1 = res1.get_json()
        self.assertTrue(data1["success"])
        self.assertFalse(data1["cached"])
        self.assertIn("assessment", data1)
        self.assertEqual(data1["assessment"]["target_company"], "Microsoft")

        # Second Call: Should hit cache
        res2 = self.client.post('/api/assessment/generate', headers={'Authorization': 'Bearer fake-token'}, json={})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertTrue(data2["success"])
        self.assertTrue(data2["cached"])

        # Fetch Current Assessment endpoint
        res_current = self.client.get('/api/assessment/current', headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res_current.status_code, 200)
        current_data = res_current.get_json()
        self.assertTrue(current_data["success"])
        self.assertIsNotNone(current_data["assessment"])

    def test_assessment_unauthorized(self):
        res = self.client.post('/api/assessment/generate', json={})
        self.assertEqual(res.status_code, 401)

        res2 = self.client.get('/api/assessment/current')
        self.assertEqual(res2.status_code, 401)

if __name__ == '__main__':
    unittest.main()
