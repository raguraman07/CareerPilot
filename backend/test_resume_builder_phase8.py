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

from resume_builder_routes import MOCK_BUILDER_RESUMES_DB
from career_goal_routes import MOCK_CAREER_GOALS_DB
from profile_routes import MOCK_PROFILES_DB
from services.resume_builder_service import (
    calculate_resume_scores,
    generate_fallback_targeted_resume,
    rewrite_section_content_ai
)

class TestResumeBuilderPhase8(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        MOCK_BUILDER_RESUMES_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()

        self.db_patcher = patch('resume_builder_routes.handle_db_op', side_effect=lambda cb, fb: fb())
        self.mock_handle_db_op = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.ctx.pop()
        MOCK_BUILDER_RESUMES_DB.clear()
        MOCK_CAREER_GOALS_DB.clear()
        MOCK_PROFILES_DB.clear()

    def test_score_calculation(self):
        resume_data = {
            "personal_info": {"full_name": "Jane", "email": "jane@example.com"},
            "professional_summary": "Aspiring Cloud Engineer with hands-on experience in Linux and Python.",
            "technical_skills": {
                "core": ["Python", "Linux", "Docker", "REST APIs"],
                "supporting": ["Git"]
            },
            "education": [{"degree": "B.S. CS"}],
            "projects": [{"title": "Cloud Pipeline"}]
        }
        scores = calculate_resume_scores(resume_data, target_role="Cloud Engineer", target_company="Microsoft")
        self.assertGreaterEqual(scores["ats_score"], 70)
        self.assertGreaterEqual(scores["role_alignment_score"], 70)
        self.assertEqual(scores["completeness_score"], 100)

    def test_fallback_targeted_resume_grounding(self):
        goal = {"company_name": "Microsoft", "job_role": "Cloud Engineer"}
        profile = {
            "full_name": "Bob Candidate",
            "email": "bob@example.com",
            "skills": ["Python", "Flask", "Linux"],
            "projects": [{"title": "CareerPilot AI", "technologies": ["Flask", "Docker"]}]
        }
        verified_skills = ["Python", "Linux"]

        res = generate_fallback_targeted_resume(goal, profile, verified_skills, [], [])
        self.assertEqual(res["target_company"], "Microsoft")
        self.assertEqual(res["target_role"], "Cloud Engineer")
        self.assertEqual(res["personal_info"]["full_name"], "Bob Candidate")

        # Verify core skills prioritize verified skills
        self.assertIn("Python", res["technical_skills"]["core"])
        self.assertIn("Linux", res["technical_skills"]["core"])
        # Verify projects use real project title
        self.assertEqual(res["projects"][0]["title"], "CareerPilot AI")

    def test_section_rewrite_fallback(self):
        content = "Made a flask api for user login."
        improved = rewrite_section_content_ai("bullet", content, "Software Engineer", "Microsoft")
        self.assertTrue(len(improved) > 0)

    def test_unauthorized_endpoints(self):
        res1 = self.client.post('/api/resume-builder/generate-targeted', json={})
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.get('/api/resume-builder/active')
        self.assertEqual(res2.status_code, 401)

        res3 = self.client.post('/api/resume-builder/save', json={})
        self.assertEqual(res3.status_code, 401)

        res4 = self.client.get('/api/resume-builder/history')
        self.assertEqual(res4.status_code, 401)

    @patch('resume_builder_routes.get_auth_uid')
    def test_resume_builder_end_to_end_flow(self, mock_uid):
        mock_uid.return_value = "user-phase8-builder-test"

        # 1. Setup Goal & Profile
        MOCK_CAREER_GOALS_DB["goal-p8"] = {
            "id": "goal-p8",
            "user_id": "user-phase8-builder-test",
            "company_name": "Microsoft",
            "job_role": "Cloud Engineer",
            "experience_level": "Fresher",
            "status": "active"
        }
        MOCK_PROFILES_DB["user-phase8-builder-test"] = {
            "id": "user-phase8-builder-test",
            "user_id": "user-phase8-builder-test",
            "full_name": "Jane Developer",
            "email": "jane@example.com",
            "skills": ["Python", "Linux", "Docker"],
            "projects": [{"title": "Cloud Platform", "technologies": ["Python", "Flask"]}]
        }

        # 2. Generate Targeted Resume
        res_gen = self.client.post('/api/resume-builder/generate-targeted', headers={'Authorization': 'Bearer token'}, json={})
        self.assertEqual(res_gen.status_code, 201)
        gen_data = res_gen.get_json()
        self.assertTrue(gen_data["success"])
        resume_id = gen_data["resume_id"]
        resume_doc = gen_data["resume"]
        self.assertEqual(resume_doc["target_company"], "Microsoft")

        # 3. Retrieve Active Resume
        res_active = self.client.get('/api/resume-builder/active', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_active.status_code, 200)
        active_data = res_active.get_json()
        self.assertTrue(active_data["success"])
        self.assertEqual(active_data["resume"]["id"], resume_id)

        # 4. Modify & Save Resume
        resume_doc["professional_summary"] = "Updated professional summary tailored specifically for Microsoft."
        res_save = self.client.post('/api/resume-builder/save', headers={'Authorization': 'Bearer token'}, json=resume_doc)
        self.assertEqual(res_save.status_code, 200)
        save_data = res_save.get_json()
        self.assertEqual(save_data["resume"]["professional_summary"], "Updated professional summary tailored specifically for Microsoft.")

        # 5. Rewrite Section Endpoint
        res_rewrite = self.client.post('/api/resume-builder/rewrite-section', headers={'Authorization': 'Bearer token'}, json={
            "section_type": "summary",
            "content": "Built python backend apps.",
            "target_role": "Cloud Engineer",
            "target_company": "Microsoft"
        })
        self.assertEqual(res_rewrite.status_code, 200)
        self.assertIn("improved", res_rewrite.get_json())

        # 6. Retrieve History
        res_hist = self.client.get('/api/resume-builder/history', headers={'Authorization': 'Bearer token'})
        self.assertEqual(res_hist.status_code, 200)
        hist_list = res_hist.get_json()
        self.assertEqual(len(hist_list), 1)

        # 7. AI Suggest Endpoint
        res_sug = self.client.post('/api/ai-suggest', json={
            "type": "summary",
            "text": "Proficient in Python and AWS.",
            "target_role": "Cloud Engineer",
            "target_company": "Microsoft"
        })
        self.assertEqual(res_sug.status_code, 200)
        self.assertTrue(res_sug.get_json()["success"])

        # 8. PDF Generation Endpoint
        res_pdf = self.client.post('/api/generate-pdf', json={
            "html": "<p>Bob Candidate - Cloud Engineer</p>",
            "filename": "Bob_Resume.pdf"
        })
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.mimetype, 'application/pdf')


if __name__ == '__main__':
    unittest.main()

