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

from services.interview_service import (
    generate_interview_session,
    evaluate_interview_answer
)

# Resumes for 3 distinct domains
RESUME_A_SOFTWARE_DEV = """
Jane Doe - Senior Python Backend Engineer
Summary: Software engineer specializing in building high-concurrency microservices with Python, Flask, and PostgreSQL.
Technical Skills: Python, Flask, FastAPI, PostgreSQL, Redis, Celery, Docker, Linux, Git.
Projects: CareerPilot AI REST API microservices platform.
Education: B.S. in Computer Science.
"""

RESUME_B_DATA_ANALYST = """
Alex Smith - Senior Data Analyst & BI Consultant
Summary: Insight-driven Data Analyst with 5+ years experience building executive visual dashboards in Tableau and R.
Technical Skills: SQL, R, Python (Pandas, NumPy), Tableau, PowerBI, Excel VBA, Regression Analysis.
Projects: Retail Executive Dashboard tracking $50M revenue streams.
Education: M.S. in Applied Statistics.
"""

RESUME_C_UIUX_DESIGNER = """
Morgan Lee - Lead UI/UX Designer & Product Strategist
Summary: User-centered Product Designer crafting intuitive digital experiences, design systems, and Figma interactive prototypes.
Technical Skills: Figma, Adobe XD, Sketch, Wireframing, Prototyping, Usability Testing, Information Architecture.
Projects: Mobile Banking app UI/UX redesign.
Education: B.A. in Graphic Design & Human-Computer Interaction.
"""

JOB_DEV = "Backend Engineer required to build microservices in Python Flask with PostgreSQL."
JOB_DATA = "Data Analyst required to build executive dashboards in Tableau using SQL queries."
JOB_UX = "Lead UX Designer required to design Figma wireframes and mobile app interfaces."


class TestInterviewPhase8(unittest.TestCase):

    @patch('services.interview_service.genai_client')
    @patch('services.interview_service.is_gemini_configured', True)
    def test_dynamic_question_generation_across_domains(self, mock_genai_client):
        """Tests that 3 distinct resumes and job descriptions generate meaningfully different questions."""

        # 1. Technical Backend Session
        mock_resp_1 = MagicMock()
        mock_resp_1.text = json.dumps({
            "interview_title": "Python Backend Interview",
            "difficulty": "Intermediate",
            "interview_type": "Technical",
            "questions": [
                {
                    "id": 1,
                    "category": "Technical",
                    "question": "Can you explain the architecture of your CareerPilot AI project built with Flask?",
                    "why_this_question": "Tests hands-on Flask REST API experience.",
                    "what_interviewer_is_evaluating": "Microservices design and Python knowledge.",
                    "answer_guidance": "Explain route handlers, database integration, and scalability.",
                    "follow_up_questions": ["How did you optimize PostgreSQL query performance?"]
                }
            ],
            "overall_preparation_tips": ["Review Flask blueprints and database connection pooling."],
            "areas_to_prepare": ["Flask microservices", "PostgreSQL indexing"],
            "potential_weaknesses": ["Docker container orchestration"],
            "summary": "Tailored technical backend interview."
        })

        # 2. Data Analyst Session
        mock_resp_2 = MagicMock()
        mock_resp_2.text = json.dumps({
            "interview_title": "Data Analyst Interview",
            "difficulty": "Intermediate",
            "interview_type": "Mixed",
            "questions": [
                {
                    "id": 1,
                    "category": "Project-based",
                    "question": "How did you design the Retail Executive Dashboard in Tableau to track $50M revenue streams?",
                    "why_this_question": "Evaluates BI dashboard design and data aggregation skills.",
                    "what_interviewer_is_evaluating": "Tableau competency and business impact.",
                    "answer_guidance": "Discuss SQL aggregation, Tableau visualization parameters, and stakeholder adoption.",
                    "follow_up_questions": ["How did you ensure real-time data freshness?"]
                }
            ],
            "overall_preparation_tips": ["Be ready to detail SQL window functions and Tableau LOD calculations."],
            "areas_to_prepare": ["SQL complex joins", "Tableau parameters"],
            "potential_weaknesses": ["No cloud data warehouse experience mentioned"],
            "summary": "Tailored data analyst interview."
        })

        # 3. UI/UX Designer Session
        mock_resp_3 = MagicMock()
        mock_resp_3.text = json.dumps({
            "interview_title": "Product Design Interview",
            "difficulty": "Intermediate",
            "interview_type": "Mixed",
            "questions": [
                {
                    "id": 1,
                    "category": "Design",
                    "question": "Walk me through your design process for the Mobile Banking app redesign in Figma.",
                    "why_this_question": "Assesses user research, wireframing, and component library creation.",
                    "what_interviewer_is_evaluating": "User-centered design methodology.",
                    "answer_guidance": "Explain user personas, usability testing findings, and Figma design tokens.",
                    "follow_up_questions": ["How did you measure usability improvements?"]
                }
            ],
            "overall_preparation_tips": ["Prepare portfolio walk-through focusing on design trade-offs."],
            "areas_to_prepare": ["Figma design tokens", "Usability testing methodology"],
            "potential_weaknesses": ["Front-end coding limitations"],
            "summary": "Tailored UX designer interview."
        })

        mock_genai_client.models.generate_content.side_effect = [mock_resp_1, mock_resp_2, mock_resp_3]

        sess_1 = generate_interview_session(RESUME_A_SOFTWARE_DEV, JOB_DEV, "Backend Engineer")
        sess_2 = generate_interview_session(RESUME_B_DATA_ANALYST, JOB_DATA, "Data Analyst")
        sess_3 = generate_interview_session(RESUME_C_UIUX_DESIGNER, JOB_UX, "Product UX Designer")

        # Assert questions are meaningfully different
        self.assertIn("CareerPilot AI", sess_1["questions"][0]["question"])
        self.assertIn("Tableau", sess_2["questions"][0]["question"])
        self.assertIn("Figma", sess_3["questions"][0]["question"])

    @patch('services.interview_service.genai_client')
    @patch('services.interview_service.is_gemini_configured', True)
    def test_answer_evaluation(self, mock_genai_client):
        """Verifies semantic evaluation of practice interview answers."""
        mock_eval_resp = MagicMock()
        mock_eval_resp.text = json.dumps({
            "score": 85,
            "strengths": ["Clear explanation of Flask blueprint routing", "Good detail on error handling"],
            "weaknesses": ["Did not mention database transaction rollback strategy"],
            "feedback": "Strong technical explanation of API architecture.",
            "improved_answer_guidance": "Mention transaction rollbacks during database writes.",
            "follow_up_question": "How do you handle rate-limiting under high API traffic?"
        })
        mock_genai_client.models.generate_content.return_value = mock_eval_resp

        eval_result = evaluate_interview_answer(
            question_text="How do you structure REST APIs in Flask?",
            candidate_answer="I use Flask Blueprints to split routes logically and SQLAlchemy for DB access.",
            why_this_question="Tests Flask API architecture.",
            answer_guidance="Explain blueprints and database handling."
        )

        self.assertEqual(eval_result["score"], 85)
        self.assertIn("Flask blueprint", eval_result["strengths"][0])

    def test_flask_interview_endpoints(self):
        """Verifies Flask authentication protection for Phase 8 API endpoints."""
        client = app.test_client()

        res_gen = client.post('/api/interview/generate', json={})
        self.assertEqual(res_gen.status_code, 401)

        res_hist = client.get('/api/interview/history')
        self.assertEqual(res_hist.status_code, 401)


if __name__ == '__main__':
    unittest.main()
