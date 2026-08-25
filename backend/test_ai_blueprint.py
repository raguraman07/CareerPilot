import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(__file__))

os.environ["GEMINI_API_KEY"] = "dummy-key-for-testing"

import importlib.util
backend_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(backend_dir, "server.py") if os.path.exists(os.path.join(backend_dir, "server.py")) else os.path.join(backend_dir, "app.py")
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
            "resume_summary": "Strong backend developer",
            "technical_skills_found": ["Python", "Flask"],
            "soft_skills_found": ["Communication"],
            "strengths": ["Clean code"],
            "weaknesses": ["No unit tests"],
            "missing_skills": ["Docker"],
            "actionable_recommendations": ["Add unit tests"],
            "recommended_roles": ["Backend Engineer"]
        }
        self.assertTrue(validate_analysis_json(valid_sample))

        invalid_sample = valid_sample.copy()
        del invalid_sample["technical_skills_found"]
        self.assertFalse(validate_analysis_json(invalid_sample))

        invalid_type_sample = valid_sample.copy()
        invalid_type_sample["technical_skills_found"] = "Python, Flask"
        self.assertFalse(validate_analysis_json(invalid_type_sample))

    @patch('app.blueprints.ai.routes.analyze_resume_text')
    @patch('app.blueprints.ai.routes.get_auth_uid')
    @patch('app.blueprints.ai.routes.handle_db_op')
    @patch('app.blueprints.ai.db_service.handle_db_op')
    def test_analyze_resume_endpoint_success(self, mock_db_service_op, mock_routes_op, mock_get_uid, mock_analyze_text):
        mock_get_uid.return_value = "mock-user-123"

        mock_routes_op.return_value = {
            "extracted_text": "Experienced Python Software Engineer with Flask, JavaScript, SQL. Developed web apps.",
            "filename": "test_resume.pdf",
            "user_id": "mock-user-123"
        }

        mock_analyze_text.return_value = {
            "resume_summary": "Experienced Python engineer",
            "technical_skills_found": ["Python", "Flask", "SQL"],
            "technical_skills": ["Python", "Flask", "SQL"],
            "soft_skills_found": ["Problem Solving"],
            "soft_skills": ["Problem Solving"],
            "strengths": ["Strong backend skills"],
            "weaknesses": ["Needs test coverage"],
            "missing_skills": ["Docker"],
            "actionable_recommendations": ["Add pytest tests"],
            "improvements": ["Add pytest tests"],
            "recommended_roles": ["Backend Developer"],
            "career_recommendations": ["Learn Docker"]
        }

        mock_db_service_op.side_effect = lambda callback, fallback: fallback()

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

    @patch('app.blueprints.ai.gemini_service.is_gemini_configured', False)
    @patch('app.blueprints.ai.routes.get_auth_uid')
    @patch('app.blueprints.ai.routes.handle_db_op')
    def test_gemini_unavailable_returns_502(self, mock_routes_op, mock_get_uid):
        """Verifies that when Gemini is unavailable, 502 error is returned and no mock analysis is shown."""
        mock_get_uid.return_value = "mock-user-123"

        mock_routes_op.return_value = {
            "extracted_text": "Candidate text",
            "filename": "resume.pdf",
            "user_id": "mock-user-123"
        }

        response = self.client.post(
            '/api/ai/analyze-resume',
            headers={"Authorization": "Bearer mock-jwt-token"},
            json={"resume_id": "mock-resume-uuid-999"}
        )

        self.assertEqual(response.status_code, 502)
        res_json = response.get_json()
        self.assertFalse(res_json.get("success"))
        self.assertEqual(res_json.get("error"), "AI resume analysis is temporarily unavailable. Please try again.")

    def test_unauthenticated_request_rejected(self):
        """Unauthenticated requests must be rejected with 401."""
        response = self.client.post(
            '/api/ai/analyze-resume',
            json={"resume_id": "mock-resume-uuid-456"}
        )
        self.assertEqual(response.status_code, 401)

if __name__ == '__main__':
    unittest.main()
