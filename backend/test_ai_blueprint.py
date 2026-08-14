import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Ensure backend directory is in path
sys.path.append(os.path.dirname(__file__))

# Set dummy environment variables for tests
os.environ["GEMINI_API_KEY"] = "dummy-key-for-testing"

import importlib.util
# Load app.py module explicitly to resolve naming collision with the app/ package folder
backend_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(backend_dir, "app.py")
spec = importlib.util.spec_from_file_location("app_module", app_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)
app = app_module.app

from app.blueprints.ai.gemini_service import validate_analysis_json, REQUIRED_KEYS

class TestAIBlueprint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_json_validation_helper(self):
        """Tests the validate_analysis_json helper function for schema correctness."""
        valid_sample = {
            "resume_summary": "Strong developer",
            "technical_skills": ["Python", "Flask"],
            "soft_skills": ["Communication"],
            "strengths": ["Clean code"],
            "weaknesses": ["No unit tests"],
            "missing_skills": ["Docker"],
            "improvements": ["Add tests"],
            "recommended_roles": ["Backend Developer"],
            "career_recommendations": ["Learn Kubernetes"]
        }
        self.assertTrue(validate_analysis_json(valid_sample))

        # Test missing key
        invalid_sample = valid_sample.copy()
        del invalid_sample["career_recommendations"]
        self.assertFalse(validate_analysis_json(invalid_sample))

        # Test non-array key
        invalid_type_sample = valid_sample.copy()
        invalid_type_sample["technical_skills"] = "Python, Flask"
        self.assertFalse(validate_analysis_json(invalid_type_sample))

    @patch('resume_routes.supabase_admin.auth.get_user')
    @patch('app.blueprints.ai.routes.handle_supabase_op')
    @patch('app.blueprints.ai.db_service.handle_supabase_op')
    def test_analyze_resume_endpoint(self, mock_db_service_op, mock_routes_op, mock_get_user):
        # 1. Mock Authentication
        mock_user = MagicMock()
        mock_user.user.id = "mock-user-123"
        mock_get_user.return_value = mock_user

        # 2. Mock Resume retrieval (extracted_text)
        mock_routes_op.return_value = {
            "extracted_text": "Experienced Python Software Engineer with Flask, JavaScript, SQL. Developed web apps.",
            "filename": "test_resume.pdf",
            "user_id": "mock-user-123"
        }

        # 3. Mock Database check for cached analysis & insert
        mock_db_service_op.side_effect = lambda callback, fallback: fallback()

        # 4. Trigger analyze-resume POST
        response = self.client.post(
            '/api/ai/analyze-resume',
            headers={"Authorization": "Bearer mock-jwt-token"},
            json={"resume_id": "mock-resume-uuid-456"}
        )

        self.assertEqual(response.status_code, 201)
        res_json = response.get_json()
        self.assertTrue(res_json.get("success"))
        self.assertIn("analysis", res_json)
        self.assertIn("analysis_results", res_json)
        self.assertEqual(res_json["resume_id"], "mock-resume-uuid-456")

        # Verify all 9 required keys exist in returned analysis_results
        results = res_json["analysis_results"]
        for key in REQUIRED_KEYS:
            self.assertIn(key, results)

    @patch('resume_routes.supabase_admin.auth.get_user')
    @patch('app.blueprints.ai.db_service.handle_supabase_op')
    def test_get_analysis_by_resume_endpoint(self, mock_db_service_op, mock_get_user):
        # 1. Mock Authentication
        mock_user = MagicMock()
        mock_user.user.id = "mock-user-123"
        mock_get_user.return_value = mock_user

        # 2. Mock DB select for resume analysis
        mock_db_service_op.side_effect = lambda callback, fallback: fallback()

        # 3. Trigger GET /api/ai/analysis/<resume_id>
        response = self.client.get(
            '/api/ai/analysis/mock-resume-uuid-456',
            headers={"Authorization": "Bearer mock-jwt-token"}
        )

        self.assertIn(response.status_code, [200, 404])

    @patch('resume_routes.supabase_admin.auth.get_user')
    @patch('app.blueprints.ai.db_service.handle_supabase_op')
    def test_history_endpoint(self, mock_db_service_op, mock_get_user):
        # 1. Mock Authentication
        mock_user = MagicMock()
        mock_user.user.id = "mock-user-123"
        mock_get_user.return_value = mock_user

        # 2. Mock DB select for history
        mock_db_service_op.side_effect = lambda callback, fallback: fallback()

        # 3. Trigger history GET
        response = self.client.get(
            '/api/ai/history',
            headers={"Authorization": "Bearer mock-jwt-token"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), list)

    def test_unauthenticated_request_rejected(self):
        """Unauthenticated requests must be rejected with 401."""
        response = self.client.post(
            '/api/ai/analyze-resume',
            json={"resume_id": "mock-resume-uuid-456"}
        )
        self.assertEqual(response.status_code, 401)

if __name__ == '__main__':
    unittest.main()
