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

from knowledge_assessment_routes import MOCK_SKILL_ASSESSMENTS_DB
from learning_plan_routes import MOCK_LEARNING_PLANS_DB
from career_goal_routes import MOCK_CAREER_GOALS_DB
from profile_routes import MOCK_PROFILES_DB
from services.knowledge_assessment_service import (
    validate_generated_assessment_json,
    sanitize_questions_for_client,
    generate_fallback_skill_assessment,
    evaluate_assessment_submission
)

class TestKnowledgeAssessmentPhase5(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_SKILL_ASSESSMENTS_DB.clear()
        MOCK_LEARNING_PLANS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        
        self.db_patcher = patch('knowledge_assessment_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_SKILL_ASSESSMENTS_DB.clear()
        MOCK_LEARNING_PLANS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()

    def test_schema_validator(self):
        valid = {
            "questions": [
                {
                    "id": "q1",
                    "type": "mcq",
                    "question": "What is Docker?",
                    "options": ["Container engine", "OS", "Browser", "Game"],
                    "correct_answer": "Container engine",
                    "explanation": "Docker is a containerization engine.",
                    "difficulty": "EASY",
                    "topic": "Containers"
                },
                {
                    "id": "q2",
                    "type": "true_false",
                    "question": "Containers share the OS kernel.",
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": "Containers share host kernel.",
                    "difficulty": "EASY",
                    "topic": "Kernel"
                },
                {
                    "id": "q3",
                    "type": "short_answer",
                    "question": "Explain Docker volume.",
                    "expected_concepts": ["Persistent storage", "Managed by Docker"],
                    "correct_answer": "Volumes persist data independent of containers.",
                    "explanation": "Volumes bypass copy-on-write storage.",
                    "difficulty": "MEDIUM",
                    "topic": "Volumes"
                }
            ]
        }
        self.assertTrue(validate_generated_assessment_json(valid))

        invalid = {"questions": [{"id": "q1"}]}
        self.assertFalse(validate_generated_assessment_json(invalid))

    def test_sanitize_questions_strips_answer_keys(self):
        raw_questions = [
            {
                "id": "q1",
                "type": "mcq",
                "question": "Which command runs a container?",
                "options": ["docker run", "docker stop"],
                "correct_answer": "docker run",
                "expected_concepts": ["run command"],
                "rubric": {"accuracy": 4},
                "explanation": "Runs container",
                "difficulty": "EASY",
                "topic": "Containers"
            }
        ]
        sanitized = sanitize_questions_for_client(raw_questions)
        self.assertEqual(len(sanitized), 1)
        q = sanitized[0]
        self.assertNotIn("correct_answer", q)
        self.assertNotIn("expected_concepts", q)
        self.assertNotIn("rubric", q)
        self.assertNotIn("explanation", q)
        self.assertIn("question", q)
        self.assertIn("options", q)

    def test_deterministic_scoring_and_evaluation(self):
        doc = {
            "skill_name": "Docker",
            "questions": [
                {
                    "id": "q1",
                    "type": "mcq",
                    "question": "Command to run container?",
                    "correct_answer": "docker run",
                    "topic": "CLI"
                },
                {
                    "id": "q2",
                    "type": "true_false",
                    "question": "Containers share kernel?",
                    "correct_answer": "True",
                    "topic": "Architecture"
                },
                {
                    "id": "q3",
                    "type": "short_answer",
                    "question": "Explain container isolation and runtime security.",
                    "expected_concepts": ["Namespaces", "Cgroups"],
                    "topic": "Security"
                }
            ]
        }

        # Case 1: Pass scenario
        answers_pass = {
            "q1": "docker run",
            "q2": "True",
            "q3": "Namespaces provide process isolation while cgroups manage resource limits."
        }
        eval_pass = evaluate_assessment_submission(doc, answers_pass, role="Cloud Engineer")
        self.assertGreaterEqual(eval_pass["score"], 75)
        self.assertTrue(eval_pass["passed"])
        self.assertEqual(eval_pass["status"], "PASSED")
        self.assertIn("CLI", eval_pass["strengths"])

        # Case 2: Needs improvement scenario
        answers_fail = {
            "q1": "wrong answer",
            "q2": "False",
            "q3": ""
        }
        eval_fail = evaluate_assessment_submission(doc, answers_fail, role="Cloud Engineer")
        self.assertLess(eval_fail["score"], 75)
        self.assertFalse(eval_fail["passed"])
        self.assertEqual(eval_fail["status"], "NEEDS_IMPROVEMENT")
        self.assertTrue(len(eval_fail["weak_areas"]) > 0)

    def test_unauthorized_endpoints(self):
        res1 = self.client.post('/api/skill-assessment/generate', json={})
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.get('/api/skill-assessment/fake-id')
        self.assertEqual(res2.status_code, 401)

        res3 = self.client.post('/api/skill-assessment/fake-id/submit', json={})
        self.assertEqual(res3.status_code, 401)

        res4 = self.client.get('/api/skill-assessment/history')
        self.assertEqual(res4.status_code, 401)

    @patch('knowledge_assessment_routes.get_auth_uid')
    def test_assessment_flow_end_to_end_and_plan_verification(self, mock_uid):
        mock_uid.return_value = "user-test-phase5"

        # 1. Setup Active Career Goal
        MOCK_CAREER_GOALS_DB["goal-p5"] = {
            "id": "goal-p5",
            "user_id": "user-test-phase5",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "status": "active"
        }

        # 2. Setup Active Learning Plan
        MOCK_LEARNING_PLANS_DB["plan-p5"] = {
            "id": "plan-p5",
            "user_id": "user-test-phase5",
            "overall_progress": 50,
            "status": "active",
            "phases": [
                {
                    "phase_id": "p1",
                    "skills": [
                        {
                            "skill_id": "sk-docker-1",
                            "name": "Docker",
                            "status": "COMPLETED",
                            "topics": ["Containers", "Images", "Networking"]
                        }
                    ]
                }
            ]
        }

        # 3. Generate Assessment
        res_gen = self.client.post('/api/skill-assessment/generate', headers={'Authorization': 'Bearer token'}, json={
            "skill_id": "sk-docker-1",
            "skill_name": "Docker"
        })
        self.assertEqual(res_gen.status_code, 201)
        gen_data = res_gen.get_json()
        self.assertTrue(gen_data["success"])
        assess_id = gen_data["assessment_id"]
        questions = gen_data["questions"]
        self.assertTrue(len(questions) >= 3)
        
        # Verify no answers leaked in client payload
        for q in questions:
            self.assertNotIn("correct_answer", q)
            self.assertNotIn("explanation", q)

        # 4. Submit Assessment Answers
        # Fetch the server doc to create passing answers
        server_doc = MOCK_SKILL_ASSESSMENTS_DB[assess_id]
        passing_answers = {}
        for q in server_doc["questions"]:
            if q["type"] in ["mcq", "true_false", "scenario"]:
                passing_answers[q["id"]] = q["correct_answer"]
            else:
                passing_answers[q["id"]] = "Docker provides container isolation using Linux kernel namespaces and cgroups."

        res_sub = self.client.post(f'/api/skill-assessment/{assess_id}/submit', headers={'Authorization': 'Bearer token'}, json={
            "answers": passing_answers
        })
        self.assertEqual(res_sub.status_code, 200)
        sub_data = res_sub.get_json()
        self.assertTrue(sub_data["success"])
        self.assertTrue(sub_data["passed"])
        self.assertEqual(sub_data["skill_status_updated"], "VERIFIED")

        # 5. Check Learning Plan Skill status was updated to VERIFIED
        updated_plan = MOCK_LEARNING_PLANS_DB["plan-p5"]
        docker_skill = updated_plan["phases"][0]["skills"][0]
        self.assertEqual(docker_skill["status"], "VERIFIED")

        # 6. Fetch Result Endpoint
        res_res = self.client.get(f'/api/skill-assessment/{assess_id}/result', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_res.status_code, 200)
        res_data = res_res.get_json()
        self.assertTrue(res_data["success"])
        self.assertTrue(len(res_data["question_results"]) >= 3)

        # 7. Fetch History Endpoint
        res_hist = self.client.get('/api/skill-assessment/history', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_hist.status_code, 200)
        hist_data = res_hist.get_json()
        self.assertTrue(len(hist_data["history"]) >= 1)

        # 8. User Ownership Check
        mock_uid.return_value = "user-other"
        res_other = self.client.get(f'/api/skill-assessment/{assess_id}', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_other.status_code, 403)

if __name__ == '__main__':
    unittest.main()
