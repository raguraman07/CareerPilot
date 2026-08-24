import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(__file__))

os.environ["GEMINI_API_KEY"] = "dummy-key-for-testing"

import importlib.util
backend_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(backend_dir, "app.py")
spec = importlib.util.spec_from_file_location("app_module", app_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)
app = app_module.app

from services.rag_service import build_rag_context, generate_rag_answer

# Sample test data structures representing Firestore documents for User A and User B
USER_A_DATA = {
    "resumes": [
        {
            "id": "res-a1",
            "filename": "Jane_Doe_Backend_Resume.pdf",
            "uploaded_at": "2026-08-20T10:00:00Z",
            "extracted_text": "Jane Doe - Senior Python Backend Engineer. Projects: CareerPilot AI REST API platform with Flask and Redis."
        }
    ],
    "analyses": [
        {
            "id": "ana-a1",
            "summary": "Senior Python Engineer",
            "technical_skills": ["Python", "Flask", "Redis", "PostgreSQL"],
            "strengths": ["REST API Architecture"],
            "weaknesses": ["No automated testing mentioned"],
            "recommendations": ["Add PyTest suite"]
        }
    ],
    "ats_scores": [
        {
            "id": "ats-a1",
            "ats_score": 88,
            "found_keywords": ["Python", "Flask", "API"],
            "missing_keywords": ["Kubernetes", "CI/CD"],
            "warnings": ["Low keyword density for cloud tools"],
            "recommendations": ["Add Docker deployment details"]
        }
    ],
    "job_matches": [
        {
            "id": "jm-a1",
            "job_title": "Senior Backend Developer",
            "match_score": 85,
            "match_level": "Strong Match",
            "matching_skills": ["Python", "Flask", "PostgreSQL"],
            "missing_skills": ["Kubernetes"],
            "skill_gaps": [{"skill": "Kubernetes", "reason": "Required for production deployment"}],
            "recommendations": ["Complete Kubernetes tutorial"]
        }
    ],
    "interviews": [
        {
            "id": "int-a1",
            "job_title": "Senior Backend Developer",
            "interview_type": "Technical",
            "difficulty": "Intermediate",
            "preparation_tips": ["Focus on Flask microservices architecture"],
            "potential_weaknesses": ["Container orchestration gap"],
            "overall_score": 82
        }
    ]
}

USER_B_DATA = {
    "resumes": [
        {
            "id": "res-b1",
            "filename": "Alex_Smith_Data_Analyst.pdf",
            "uploaded_at": "2026-08-21T10:00:00Z",
            "extracted_text": "Alex Smith - Lead Data Analyst. Projects: Tableau Executive Revenue Dashboard tracking $50M streams."
        }
    ],
    "analyses": [],
    "ats_scores": [],
    "job_matches": [],
    "interviews": []
}


class TestRagPhase9(unittest.TestCase):

    def test_rag_context_building_and_intent_filtering(self):
        """Verifies that RAG intent filtering selects only relevant data sources."""
        # 1. Resume Query
        ctx_res, sources_res = build_rag_context(USER_A_DATA, "What projects are listed on my resume?")
        self.assertIn("CareerPilot AI REST API", ctx_res)
        self.assertIn("Resume Content", sources_res)

        # 2. ATS Query
        ctx_ats, sources_ats = build_rag_context(USER_A_DATA, "What was my ATS score and missing keywords?")
        self.assertIn("88/100", ctx_ats)
        self.assertIn("Kubernetes", ctx_ats)
        self.assertIn("ATS Score Analysis", sources_ats)

        # 3. Job Match Query
        ctx_jm, sources_jm = build_rag_context(USER_A_DATA, "What skills am I missing for my backend job match?")
        self.assertIn("Kubernetes", ctx_jm)
        self.assertIn("Job Match & Skill Gaps", sources_jm)

        # 4. Interview Query
        ctx_int, sources_int = build_rag_context(USER_A_DATA, "What should I prepare for my upcoming interview?")
        self.assertIn("Flask microservices architecture", ctx_int)
        self.assertIn("Interview Preparation", sources_int)

    def test_user_data_isolation(self):
        """TEST 4: Verifies User A's data does not leak into User B's context."""
        ctx_a, _ = build_rag_context(USER_A_DATA, "Tell me about my resume")
        ctx_b, _ = build_rag_context(USER_B_DATA, "Tell me about my resume")

        self.assertIn("Jane Doe", ctx_a)
        self.assertNotIn("Alex Smith", ctx_a)

        self.assertIn("Alex Smith", ctx_b)
        self.assertNotIn("Jane Doe", ctx_b)

    @patch('services.rag_service.genai_client')
    @patch('services.rag_service.is_gemini_configured', True)
    @patch('services.rag_service.fetch_user_career_data')
    def test_generate_rag_answer_with_mock_data(self, mock_fetch_data, mock_genai_client):
        """Verifies full RAG execution pipeline with Gemini AI."""
        mock_fetch_data.return_value = USER_A_DATA

        mock_resp = MagicMock()
        mock_resp.text = "Based on your latest backend job match, the primary skill you are missing is Kubernetes."
        mock_genai_client.models.generate_content.return_value = mock_resp

        reply, sources = generate_rag_answer("user-a-123", "What skills am I missing?")

        self.assertIn("Kubernetes", reply)
        self.assertIn("Job Match & Skill Gaps", sources)

    def test_flask_auth_protection(self):
        """Verifies Flask authentication protection for Phase 9 API endpoints."""
        client = app.test_client()

        res_chat = client.post('/api/career-assistant/chat', json={})
        self.assertEqual(res_chat.status_code, 401)

        res_history = client.get('/api/career-assistant/chats')
        self.assertEqual(res_history.status_code, 401)


if __name__ == '__main__':
    unittest.main()
