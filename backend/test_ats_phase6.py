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

from services.ats_service import (
    calculate_deterministic_ats_scores,
    validate_ats_json,
    REQUIRED_ATS_KEYS
)

SAMPLE_DYNAMIC_ATS_RESULTS = {
    "keyword_analysis": {
        "found_keywords": ["Python", "SQL", "Flask"],
        "missing_keywords": ["Docker"],
        "recommendations": ["Add Docker keywords."]
    },
    "skills_analysis": {
        "detected_skills": ["Python", "Flask", "SQL"],
        "missing_skills": ["Docker"],
        "recommendations": ["Group skills into categories."]
    },
    "experience_analysis": {
        "strengths": ["Clear reverse-chronological structure."],
        "weaknesses": ["Lacks quantifiable metrics."],
        "recommendations": ["Use STAR method."]
    },
    "education_analysis": {
        "strengths": ["Degree title and dates listed."],
        "recommendations": ["List academic honors."]
    },
    "structure_analysis": {
        "detected_sections": ["Experience", "Education", "Skills"],
        "missing_sections": ["Certifications"],
        "recommendations": ["Add Certifications section."]
    },
    "formatting_analysis": {
        "issues": ["Minor date spacing inconsistency."],
        "recommendations": ["Use standard fonts."]
    },
    "achievements_analysis": {
        "strengths": ["Delivered 2 applications."],
        "weaknesses": ["No numerical metrics."],
        "recommendations": ["Quantify impact with numbers."]
    },
    "overall_recommendations": ["Quantify experience with numbers."],
    "ats_warnings": ["Missing measurable impact metrics."]
}

class TestATSPhase6(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_json_validation_helper(self):
        """Validates that validate_ats_json checks for all 9 required ATS fields."""
        self.assertTrue(validate_ats_json(SAMPLE_DYNAMIC_ATS_RESULTS))
        
        invalid_sample = dict(SAMPLE_DYNAMIC_ATS_RESULTS)
        del invalid_sample["ats_warnings"]
        self.assertFalse(validate_ats_json(invalid_sample))

    def test_deterministic_scoring_formula(self):
        """Validates deterministic scoring algorithm logic and exact point bounds."""
        scores = calculate_deterministic_ats_scores(SAMPLE_DYNAMIC_ATS_RESULTS, "Sample resume text")
        
        self.assertIn("overall_score", scores)
        self.assertIn("keyword_score", scores)
        self.assertIn("skills_score", scores)
        self.assertIn("experience_score", scores)
        self.assertIn("structure_score", scores)
        self.assertIn("formatting_score", scores)
        self.assertIn("education_score", scores)
        self.assertIn("achievements_score", scores)
        self.assertIn("score_level", scores)

        self.assertTrue(0 <= scores["keyword_score"] <= 25)
        self.assertTrue(0 <= scores["skills_score"] <= 20)
        self.assertTrue(0 <= scores["experience_score"] <= 15)
        self.assertTrue(0 <= scores["structure_score"] <= 15)
        self.assertTrue(0 <= scores["formatting_score"] <= 10)
        self.assertTrue(0 <= scores["education_score"] <= 10)
        self.assertTrue(0 <= scores["achievements_score"] <= 5)
        self.assertTrue(0 <= scores["overall_score"] <= 100)

        calculated_sum = (
            scores["keyword_score"] + scores["skills_score"] +
            scores["experience_score"] + scores["structure_score"] +
            scores["formatting_score"] + scores["education_score"] +
            scores["achievements_score"]
        )
        self.assertEqual(scores["overall_score"], calculated_sum)

    @patch('ats_routes.run_gemini_ats_analysis')
    @patch('ats_routes.get_auth_uid')
    @patch('ats_routes.fetch_and_verify_resume')
    def test_analyze_ats_endpoint_success(self, mock_fetch_resume, mock_get_uid, mock_run_gemini):
        """Tests POST /api/ats/analyze/<resume_id> with valid authenticated session."""
        mock_get_uid.return_value = "firebase-user-uid-789"

        mock_fetch_resume.return_value = {
            "id": "resume-123",
            "user_id": "firebase-user-uid-789",
            "filename": "developer_resume.pdf",
            "extracted_text": "Experienced engineer with Python, SQL, and Flask."
        }

        mock_run_gemini.return_value = SAMPLE_DYNAMIC_ATS_RESULTS

        response = self.client.post(
            '/api/ats/analyze/resume-123',
            headers={"Authorization": "Bearer mock-firebase-token"},
            json={}
        )

        self.assertIn(response.status_code, [200, 201])
        res_json = response.get_json()
        self.assertTrue(res_json.get("success"))
        self.assertIn("overall_score", res_json)
        self.assertIn("score_level", res_json)

    @patch('ats_routes.get_auth_uid')
    @patch('ats_routes.fetch_and_verify_resume')
    def test_analyze_ats_empty_resume_error(self, mock_fetch_resume, mock_get_uid):
        """Tests that empty extracted resume text returns a 400 error response."""
        mock_get_uid.return_value = "firebase-user-uid-789"

        mock_fetch_resume.return_value = {
            "id": "resume-empty",
            "user_id": "firebase-user-uid-789",
            "filename": "scanned_empty.pdf",
            "extracted_text": ""
        }

        response = self.client.post(
            '/api/ats/analyze/resume-empty',
            headers={"Authorization": "Bearer mock-firebase-token"},
            json={}
        )

        self.assertEqual(response.status_code, 400)
        res_json = response.get_json()
        self.assertFalse(res_json.get("success"))
        self.assertIn("Resume text is unavailable for ATS analysis.", res_json.get("error"))

    def test_unauthorized_ats_request_rejected(self):
        """Unauthenticated requests must be rejected with 401."""
        response = self.client.post('/api/ats/analyze/resume-123')
        self.assertEqual(response.status_code, 401)

if __name__ == '__main__':
    unittest.main()
