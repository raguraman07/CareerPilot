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

from interview_routes import MOCK_INTERVIEW_SESSIONS_DB
from career_goal_routes import MOCK_CAREER_GOALS_DB
from profile_routes import MOCK_PROFILES_DB
from learning_plan_routes import MOCK_LEARNING_PLANS_DB
from services.interview_service import (
    validate_interview_questions_json,
    generate_fallback_interview_questions,
    evaluate_interview_answer_ai,
    finalize_interview_session_evaluation
)

class TestInterviewPhase6(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_INTERVIEW_SESSIONS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_LEARNING_PLANS_DB.clear()

        self.db_patcher = patch('interview_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_INTERVIEW_SESSIONS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_LEARNING_PLANS_DB.clear()

    def test_schema_validator(self):
        valid = {
            "questions": [
                {
                    "question_id": "q1",
                    "category": "technical",
                    "difficulty": "MEDIUM",
                    "topic": "Docker",
                    "question": "How do you containerize a Flask app?",
                    "why_this_question": "Required for cloud deployment",
                    "expected_areas": ["Dockerfile", "Compose"]
                }
            ]
        }
        self.assertTrue(validate_interview_questions_json(valid))

        invalid = {"questions": [{"question_id": "q1"}]}
        self.assertFalse(validate_interview_questions_json(invalid))

    def test_fallback_interview_questions_grounding(self):
        goal = {"company_name": "Microsoft", "job_role": "Cloud Engineer", "experience_level": "Fresher"}
        profile = {
            "full_name": "Jane Cloud",
            "projects": [{"title": "CareerPilot AI", "technologies": ["Flask", "PostgreSQL"]}]
        }
        learning_plan = {
            "phases": [
                {
                    "skills": [
                        {"name": "Docker", "status": "VERIFIED"},
                        {"name": "Kubernetes", "status": "NEEDS_IMPROVEMENT"}
                    ]
                }
            ]
        }

        res = generate_fallback_interview_questions(goal, profile, {}, {}, learning_plan, session_type="MOCK_INTERVIEW", num_questions=8)
        self.assertEqual(res["target_company"], "Microsoft")
        self.assertEqual(res["target_role"], "Cloud Engineer")
        self.assertEqual(len(res["questions"]), 8)

        # Confirm grounding: references verified/weak skills & project
        topics = [q["topic"] for q in res["questions"]]
        questions_text = " ".join([q["question"] for q in res["questions"]])
        self.assertTrue(any("Docker" in t for t in topics))
        self.assertIn("CareerPilot AI", questions_text)

    def test_single_answer_evaluation(self):
        q_data = {
            "question": "Explain Docker container networking and port binding.",
            "category": "technical",
            "topic": "Docker",
            "expected_areas": ["Bridge network", "Port mapping (-p)", "Host network"]
        }
        ans = "Docker uses bridge networks by default to isolate containers and port mapping with -p to expose host ports."
        eval_res = evaluate_interview_answer_ai(q_data, ans, role="Cloud Engineer", company="Microsoft")
        
        self.assertIn("score", eval_res)
        self.assertIn("technical_accuracy", eval_res)
        self.assertIn("strengths", eval_res)
        self.assertIn("missing_points", eval_res)
        self.assertTrue(eval_res["score"] > 0)

    def test_unauthorized_interview_endpoints(self):
        res1 = self.client.post('/api/interview/generate', json={})
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.post('/api/interview/fake-id/answer', json={})
        self.assertEqual(res2.status_code, 401)

        res3 = self.client.post('/api/interview/fake-id/complete')
        self.assertEqual(res3.status_code, 401)

        res4 = self.client.get('/api/interview/history')
        self.assertEqual(res4.status_code, 401)

    @patch('interview_routes.get_auth_uid')
    def test_interview_training_end_to_end_flow(self, mock_uid):
        mock_uid.return_value = "user-phase6-test"

        # 1. Setup Goal & Profile
        MOCK_CAREER_GOALS_DB["goal-p6"] = {
            "id": "goal-p6",
            "user_id": "user-phase6-test",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher",
            "status": "active"
        }
        MOCK_PROFILES_DB["user-phase6-test"] = {
            "id": "user-phase6-test",
            "user_id": "user-phase6-test",
            "full_name": "Bob Candidate",
            "projects": [{"title": "CareerPilot AI", "technologies": ["Python", "Flask"]}]
        }

        # 2. Generate Interview Session
        res_gen = self.client.post('/api/interview/generate', headers={'Authorization': 'Bearer token'}, json={
            "session_type": "DAILY_PRACTICE",
            "num_questions": 5
        })
        self.assertEqual(res_gen.status_code, 201)
        gen_data = res_gen.get_json()
        self.assertTrue(gen_data["success"])
        session_id = gen_data["session_id"]
        questions = gen_data["questions"]
        self.assertEqual(len(questions), 5)

        # 3. Submit Answers for all questions
        for q in questions:
            res_ans = self.client.post(f'/api/interview/{session_id}/answer', headers={'Authorization': 'Bearer token'}, json={
                "question_id": q["question_id"],
                "answer": "Structured response detailing architecture principles, trade-offs, and practical deployment in CareerPilot AI."
            })
            self.assertEqual(res_ans.status_code, 200)
            self.assertIn("evaluation", res_ans.get_json())

        # 4. Finalize Interview Session
        res_comp = self.client.post(f'/api/interview/{session_id}/complete', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_comp.status_code, 200)
        comp_data = res_comp.get_json()
        self.assertTrue(comp_data["success"])
        self.assertIn("overall_score", comp_data)
        self.assertIn("readiness_level", comp_data)
        self.assertIn("performance_breakdown", comp_data)
        self.assertIn("personalized_improvement_plan", comp_data)

        # 5. Fetch Session History
        res_hist = self.client.get('/api/interview/history', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_hist.status_code, 200)
        hist_list = res_hist.get_json()
        self.assertEqual(len(hist_list), 1)
        self.assertEqual(hist_list[0]["session_id"], session_id)

        # 6. Fetch Readiness Summary
        res_readiness = self.client.get('/api/interview/readiness', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_readiness.status_code, 200)
        readiness_data = res_readiness.get_json()
        self.assertTrue(readiness_data["readiness_score"] > 0)
        self.assertEqual(readiness_data["total_sessions"], 1)

        # 7. User Ownership Isolation Check
        mock_uid.return_value = "user-other"
        res_unauth = self.client.get(f'/api/interview/{session_id}', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_unauth.status_code, 403)

if __name__ == '__main__':
    unittest.main()
