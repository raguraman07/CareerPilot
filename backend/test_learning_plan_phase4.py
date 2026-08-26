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

from learning_plan_routes import MOCK_LEARNING_PLANS_DB
from career_goal_routes import MOCK_CAREER_GOALS_DB
from profile_routes import MOCK_PROFILES_DB
from assessment_routes import MOCK_ASSESSMENTS_DB
from resume_routes import MOCK_RESUMES_DB
from services.learning_plan_service import (
    validate_learning_plan_json,
    generate_rule_based_fallback_learning_plan,
    clean_and_normalize_learning_plan,
    generate_learning_plan_cache_hash
)

class TestLearningPlanPhase4(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_LEARNING_PLANS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_ASSESSMENTS_DB.clear()
        MOCK_RESUMES_DB.clear()
        
        # Patch handle_db_op to run fallback (mock mode) during unit testing
        self.db_patcher = patch('learning_plan_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_LEARNING_PLANS_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()
        MOCK_ASSESSMENTS_DB.clear()
        MOCK_RESUMES_DB.clear()

    def test_schema_validator(self):
        valid = {
            "plan_summary": "Solid learning roadmap for Cloud Engineer.",
            "overall_learning_priority": "HIGH",
            "phases": [
                {
                    "name": "Phase 1 — Foundations",
                    "description": "Core concepts",
                    "order": 1,
                    "skills": [
                        {
                            "name": "Docker",
                            "category": "Tools",
                            "priority": "HIGH",
                            "current_level": "BEGINNER",
                            "target_level": "INTERMEDIATE",
                            "why_needed": "Required for containers",
                            "topics": ["Containers", "Images"],
                            "practice_tasks": ["Containerize Flask app"],
                            "expected_outcome": "Build images",
                            "estimated_effort": "2 Weeks"
                        }
                    ]
                }
            ]
        }
        self.assertTrue(validate_learning_plan_json(valid))

        invalid = {"plan_summary": "Incomplete"}
        self.assertFalse(validate_learning_plan_json(invalid))

    def test_rule_based_fallback_learning_plan(self):
        goal = {"company_name": "Microsoft", "job_role": "Cloud Engineer", "target_timeline": "6 Months"}
        profile = {
            "full_name": "John Doe",
            "skills": {"programming_languages": ["Python", "SQL"], "technical_skills": ["Linux", "Flask"]},
            "projects": [{"title": "CareerPilot AI", "technologies": ["Flask", "Python"]}]
        }
        assessment = {
            "career_readiness_score": 60,
            "strong_matches": ["Python", "Linux"],
            "partial_matches": ["Flask"],
            "skill_gaps": [
                {
                    "skill": "Azure",
                    "priority": "HIGH",
                    "why": "Central cloud platform for Microsoft.",
                    "what_to_learn": ["IAM", "Virtual Networks", "App Services"],
                    "practice_task": "Deploy CareerPilot AI to Azure."
                },
                {
                    "skill": "Docker",
                    "priority": "HIGH",
                    "why": "Containerization standard.",
                    "what_to_learn": ["Dockerfile", "Compose"],
                    "practice_task": "Containerize CareerPilot AI."
                }
            ],
            "knowledge_gaps": [
                {"topic": "Cloud Networking", "priority": "HIGH", "relevance": "VPC & Subnets"}
            ]
        }

        plan = generate_rule_based_fallback_learning_plan(goal, profile, assessment)
        self.assertIn("plan_summary", plan)
        self.assertIn("phases", plan)
        self.assertTrue(len(plan["phases"]) >= 2)

        # Check skills in phases
        all_skill_names = [sk["name"] for p in plan["phases"] for sk in p["skills"]]
        self.assertTrue(any("Cloud Networking" in s for s in all_skill_names))
        self.assertTrue(any("Azure" in s for s in all_skill_names))

        # Check that practical tasks link to project
        all_tasks = [pt for p in plan["phases"] for sk in p["skills"] for pt in sk["practice_tasks"]]
        self.assertTrue(any("CareerPilot AI" in t for t in all_tasks))

    def test_learning_plan_unauthorized(self):
        res = self.client.post('/api/learning-plan/generate', json={})
        self.assertEqual(res.status_code, 401)

        res2 = self.client.get('/api/learning-plan/current')
        self.assertEqual(res2.status_code, 401)

        res3 = self.client.put('/api/learning-plan/progress', json={"skill_id": "test", "status": "COMPLETED"})
        self.assertEqual(res3.status_code, 401)

    @patch('learning_plan_routes.get_auth_uid')
    def test_learning_plan_missing_goal_returns_400(self, mock_uid):
        mock_uid.return_value = "user-no-goal"
        res = self.client.post('/api/learning-plan/generate', headers={'Authorization': 'Bearer fake-token'}, json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("No active career goal found", res.get_json()["error"])

    @patch('learning_plan_routes.get_auth_uid')
    def test_learning_plan_missing_assessment_returns_400(self, mock_uid):
        mock_uid.return_value = "user-no-assess"
        MOCK_CAREER_GOALS_DB["goal-1"] = {
            "id": "goal-1",
            "user_id": "user-no-assess",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "status": "active"
        }
        res = self.client.post('/api/learning-plan/generate', headers={'Authorization': 'Bearer fake-token'}, json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Complete your Career Assessment", res.get_json()["error"])

    @patch('learning_plan_routes.get_auth_uid')
    def test_learning_plan_generation_caching_and_progress_update(self, mock_uid):
        mock_uid.return_value = "user-full-test"

        # 1. Setup Active Career Goal
        MOCK_CAREER_GOALS_DB["goal-100"] = {
            "id": "goal-100",
            "user_id": "user-full-test",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher",
            "target_timeline": "6 Months",
            "status": "active"
        }

        # 2. Setup Profile
        MOCK_PROFILES_DB["user-full-test"] = {
            "id": "user-full-test",
            "user_id": "user-full-test",
            "full_name": "Alice Candidate",
            "skills": {
                "programming_languages": ["Python", "SQL"],
                "technical_skills": ["Linux", "Flask"]
            },
            "projects": [{"title": "CareerPilot AI", "technologies": ["Python", "Flask"]}],
            "completeness": 85,
            "updated_at": "2026-08-26T12:00:00Z"
        }

        # 3. Setup Phase 3 Assessment
        MOCK_ASSESSMENTS_DB["assess-100"] = {
            "id": "assess-100",
            "user_id": "user-full-test",
            "goal_id": "goal-100",
            "career_readiness_score": 62,
            "created_at": "2026-08-26T12:05:00Z",
            "assessment_result": {
                "career_readiness_score": 62,
                "ats_score": 70,
                "strong_matches": ["Python", "Linux"],
                "partial_matches": ["Flask"],
                "skill_gaps": [
                    {
                        "skill": "Azure",
                        "priority": "HIGH",
                        "why": "Microsoft's cloud platform.",
                        "what_to_learn": ["Virtual Machines", "Azure CLI", "Entra ID"],
                        "practice_task": "Deploy Flask project on Azure."
                    },
                    {
                        "skill": "Docker",
                        "priority": "HIGH",
                        "why": "Containerization standard.",
                        "what_to_learn": ["Dockerfile", "Docker Compose"],
                        "practice_task": "Containerize CareerPilot AI."
                    }
                ],
                "knowledge_gaps": [
                    {"topic": "Cloud Networking", "priority": "HIGH", "relevance": "Subnets and DNS"}
                ]
            }
        }

        # First Call: Fresh generation
        res1 = self.client.post('/api/learning-plan/generate', headers={'Authorization': 'Bearer fake-token'}, json={})
        self.assertEqual(res1.status_code, 201)
        data1 = res1.get_json()
        self.assertTrue(data1["success"])
        self.assertFalse(data1["cached"])
        self.assertIn("learning_plan", data1)
        plan = data1["learning_plan"]
        self.assertEqual(plan["target_company"], "Microsoft")
        self.assertEqual(plan["target_role"], "Cloud Engineer")
        self.assertEqual(plan["overall_progress"], 0)
        self.assertTrue(len(plan["phases"]) > 0)

        first_skill = plan["phases"][0]["skills"][0]
        skill_id = first_skill["skill_id"]

        # Second Call: Should hit cache
        res2 = self.client.post('/api/learning-plan/generate', headers={'Authorization': 'Bearer fake-token'}, json={})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertTrue(data2["success"])
        self.assertTrue(data2["cached"])

        # Fetch Current Plan Endpoint
        res_curr = self.client.get('/api/learning-plan/current', headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res_curr.status_code, 200)
        self.assertIsNotNone(res_curr.get_json()["learning_plan"])

        # Update Skill Progress to IN_PROGRESS
        res_up1 = self.client.put('/api/learning-plan/progress', headers={'Authorization': 'Bearer fake-token'}, json={
            "skill_id": skill_id,
            "status": "IN_PROGRESS"
        })
        self.assertEqual(res_up1.status_code, 200)

        # Update Skill Progress to COMPLETED
        res_up2 = self.client.put('/api/learning-plan/progress', headers={'Authorization': 'Bearer fake-token'}, json={
            "skill_id": skill_id,
            "status": "COMPLETED"
        })
        self.assertEqual(res_up2.status_code, 200)
        up_data = res_up2.get_json()
        self.assertTrue(up_data["overall_progress"] > 0)

        # User Isolation: Another user should not be able to update this user's plan
        mock_uid.return_value = "user-other"
        res_unauth = self.client.put('/api/learning-plan/progress', headers={'Authorization': 'Bearer fake-token'}, json={
            "plan_id": plan["id"],
            "skill_id": skill_id,
            "status": "COMPLETED"
        })
        self.assertEqual(res_unauth.status_code, 403)

if __name__ == '__main__':
    unittest.main()
