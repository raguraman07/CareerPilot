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

from career_goal_routes import MOCK_CAREER_GOALS_DB

class TestCareerGoalPhase1(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_CAREER_GOALS_DB.clear()
        # Patch handle_db_op to run fallback (mock mode) during unit testing
        self.db_patcher = patch('career_goal_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_CAREER_GOALS_DB.clear()

    @patch('career_goal_routes.get_auth_uid')
    def test_create_career_goal_success(self, mock_uid):
        mock_uid.return_value = "user-alice-123"

        payload = {
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher",
            "target_location": "India",
            "target_timeline": "6 Months"
        }

        res = self.client.post('/api/career-goals', json=payload, headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        goal = data.get("career_goal")
        self.assertEqual(goal["user_id"], "user-alice-123")
        self.assertEqual(goal["company_name"], "Microsoft")
        self.assertEqual(goal["job_role"], "Cloud Engineer")
        self.assertEqual(goal["experience_level"], "Fresher")
        self.assertEqual(goal["target_location"], "India")
        self.assertEqual(goal["target_timeline"], "6 Months")
        self.assertEqual(goal["status"], "active")

    @patch('career_goal_routes.get_auth_uid')
    def test_create_career_goal_missing_required_fields(self, mock_uid):
        mock_uid.return_value = "user-alice-123"

        # Missing job_role
        payload = {
            "company_name": "Microsoft",
            "experience_level": "Fresher"
        }
        res = self.client.post('/api/career-goals', json=payload, headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())

    def test_create_career_goal_unauthorized(self):
        res = self.client.post('/api/career-goals', json={"company_name": "Google"})
        self.assertEqual(res.status_code, 401)

    @patch('career_goal_routes.get_auth_uid')
    def test_get_current_career_goal_none(self, mock_uid):
        mock_uid.return_value = "user-alice-123"
        res = self.client.get('/api/career-goals/current', headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIsNone(data.get("career_goal"))

    @patch('career_goal_routes.get_auth_uid')
    def test_get_current_career_goal_found(self, mock_uid):
        mock_uid.return_value = "user-alice-123"

        create_res = self.client.post('/api/career-goals', json={
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher",
            "target_location": "India",
            "target_timeline": "6 Months"
        }, headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(create_res.status_code, 201)

        get_res = self.client.get('/api/career-goals/current', headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(get_res.status_code, 200)
        data = get_res.get_json()
        self.assertIsNotNone(data.get("career_goal"))
        self.assertEqual(data["career_goal"]["company_name"], "Microsoft")

    @patch('career_goal_routes.get_auth_uid')
    def test_update_career_goal_success(self, mock_uid):
        mock_uid.return_value = "user-alice-123"

        create_res = self.client.post('/api/career-goals', json={
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher"
        }, headers={'Authorization': 'Bearer fake-token'})
        goal_id = create_res.get_json()["career_goal"]["id"]

        update_res = self.client.put(f'/api/career-goals/{goal_id}', json={
            "target_timeline": "1 Year",
            "experience_level": "1-2 Years"
        }, headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(update_res.status_code, 200)
        updated = update_res.get_json()["career_goal"]
        self.assertEqual(updated["target_timeline"], "1 Year")
        self.assertEqual(updated["experience_level"], "1-2 Years")

    @patch('career_goal_routes.get_auth_uid')
    def test_update_career_goal_forbidden_for_other_user(self, mock_uid):
        mock_uid.return_value = "user-alice-123"
        create_res = self.client.post('/api/career-goals', json={
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher"
        }, headers={'Authorization': 'Bearer fake-token'})
        goal_id = create_res.get_json()["career_goal"]["id"]

        # Switch to Bob
        mock_uid.return_value = "user-bob-456"
        update_res = self.client.put(f'/api/career-goals/{goal_id}', json={
            "company_name": "Amazon"
        }, headers={'Authorization': 'Bearer fake-token'})
        self.assertEqual(update_res.status_code, 403)

if __name__ == '__main__':
    unittest.main()
