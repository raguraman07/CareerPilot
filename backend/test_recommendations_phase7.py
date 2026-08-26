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

from recommendation_routes import MOCK_RECOMMENDATIONS_DB
from career_goal_routes import MOCK_CAREER_GOALS_DB
from profile_routes import MOCK_PROFILES_DB
from learning_plan_routes import MOCK_LEARNING_PLANS_DB
from services.recommendation_service import (
    validate_recommendations_json,
    sanitize_official_url,
    generate_fallback_recommendations
)

class TestRecommendationsPhase7(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_RECOMMENDATIONS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_LEARNING_PLANS_DB.clear()

        self.db_patcher = patch('recommendation_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_RECOMMENDATIONS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_LEARNING_PLANS_DB.clear()

    def test_official_url_sanitizer(self):
        # Valid domain passed
        self.assertEqual(
            sanitize_official_url("https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/", "Microsoft"),
            "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/"
        )
        self.assertEqual(
            sanitize_official_url("https://aws.amazon.com/certification/certified-cloud-practitioner/", "AWS"),
            "https://aws.amazon.com/certification/certified-cloud-practitioner/"
        )

        # Invalid/fake domain sanitized to official provider root
        self.assertEqual(
            sanitize_official_url("https://fake-scam-cert-site.com/azure", "Microsoft"),
            "https://learn.microsoft.com/en-us/credentials/"
        )
        self.assertEqual(
            sanitize_official_url("https://random-blog.com/aws", "AWS"),
            "https://aws.amazon.com/certification/"
        )

    def test_schema_validator(self):
        valid = {
            "certifications": {
                "must_complete": [{"id": "c1"}],
                "recommended": [],
                "advanced": []
            },
            "projects": {
                "beginner": [{"id": "p1"}],
                "intermediate": [],
                "advanced": []
            }
        }
        self.assertTrue(validate_recommendations_json(valid))

        invalid = {"certifications": {}}
        self.assertFalse(validate_recommendations_json(invalid))

    def test_fallback_generator_grounding(self):
        goal = {"company_name": "Microsoft", "job_role": "Cloud Engineer", "experience_level": "Fresher"}
        profile = {"full_name": "Jane Cloud"}
        learning_plan = {
            "phases": [
                {
                    "skills": [
                        {"name": "Docker", "status": "NEEDS_IMPROVEMENT"}
                    ]
                }
            ]
        }

        recs = generate_fallback_recommendations(goal, profile, {}, {}, learning_plan)
        self.assertEqual(recs["target_company"], "Microsoft")
        self.assertEqual(recs["target_role"], "Cloud Engineer")
        
        # Check project tier counts: at least 2 beginner, 3 intermediate, 2 advanced
        self.assertGreaterEqual(len(recs["projects"]["beginner"]), 2)
        self.assertGreaterEqual(len(recs["projects"]["intermediate"]), 3)
        self.assertGreaterEqual(len(recs["projects"]["advanced"]), 2)

        # Confirm official URLs on all certs
        for tier in ["must_complete", "recommended", "advanced"]:
            for cert in recs["certifications"][tier]:
                self.assertTrue(cert["official_url"].startswith("https://"))

    def test_unauthorized_endpoints(self):
        res1 = self.client.post('/api/recommendations/generate', json={})
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.get('/api/recommendations')
        self.assertEqual(res2.status_code, 401)

        res3 = self.client.get('/api/certifications')
        self.assertEqual(res3.status_code, 401)

        res4 = self.client.get('/api/projects')
        self.assertEqual(res4.status_code, 401)

    @patch('recommendation_routes.get_auth_uid')
    def test_recommendation_flow_end_to_end(self, mock_uid):
        mock_uid.return_value = "user-phase7-test"

        # 1. Setup Active Career Goal
        MOCK_CAREER_GOALS_DB["goal-p7"] = {
            "id": "goal-p7",
            "user_id": "user-phase7-test",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher",
            "status": "active"
        }

        # 2. Generate Recommendations
        res_gen = self.client.post('/api/recommendations/generate', headers={'Authorization': 'Bearer token'}, json={})
        self.assertEqual(res_gen.status_code, 201)
        gen_data = res_gen.get_json()
        self.assertTrue(gen_data["success"])
        self.assertIn("data", gen_data)
        self.assertEqual(gen_data["data"]["target_company"], "Microsoft")

        # 3. Fetch Recommendations
        res_get = self.client.get('/api/recommendations', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_get.status_code, 200)
        get_data = res_get.get_json()
        self.assertTrue(get_data["success"])
        self.assertIn("certifications", get_data["data"])
        self.assertIn("projects", get_data["data"])

        # 4. Fetch Certifications Only
        res_certs = self.client.get('/api/certifications', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_certs.status_code, 200)
        certs_data = res_certs.get_json()
        self.assertIn("must_complete", certs_data)

        # 5. Fetch Projects Only
        res_projs = self.client.get('/api/projects', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_projs.status_code, 200)
        projs_data = res_projs.get_json()
        self.assertIn("intermediate", projs_data)

if __name__ == '__main__':
    unittest.main()
