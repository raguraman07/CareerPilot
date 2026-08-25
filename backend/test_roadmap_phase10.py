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

from services.career_roadmap_service import generate_career_roadmap, get_readiness_label

# Sample candidate career data for 3 distinct domain candidates
CANDIDATE_A_BACKEND = {
    "resumes": [{"extracted_text": "Jane Doe - Python Backend Dev. Skills: Python, Flask, SQL."}],
    "analyses": [{"summary": "Backend dev"}],
    "ats_scores": [{"ats_score": 85}],
    "job_matches": [{"job_title": "Senior Backend Engineer", "match_score": 80, "missing_skills": ["Kubernetes"]}],
    "interviews": []
}

CANDIDATE_B_DATA = {
    "resumes": [{"extracted_text": "Alex Smith - Data Analyst. Skills: SQL, R, Tableau."}],
    "analyses": [{"summary": "Data analyst"}],
    "ats_scores": [{"ats_score": 88}],
    "job_matches": [{"job_title": "Lead Data Analyst", "match_score": 90, "missing_skills": ["PowerBI"]}],
    "interviews": []
}

CANDIDATE_C_UX = {
    "resumes": [{"extracted_text": "Morgan Lee - UI/UX Designer. Skills: Figma, Adobe XD."}],
    "analyses": [{"summary": "UX designer"}],
    "ats_scores": [{"ats_score": 90}],
    "job_matches": [{"job_title": "Lead Product Designer", "match_score": 92, "missing_skills": ["Design Tokens"]}],
    "interviews": []
}


class TestRoadmapPhase10(unittest.TestCase):

    def test_readiness_label_thresholds(self):
        """Verifies score interpretation thresholds."""
        self.assertEqual(get_readiness_label(95), "Highly Ready")
        self.assertEqual(get_readiness_label(82), "Strongly Prepared")
        self.assertEqual(get_readiness_label(65), "Developing")
        self.assertEqual(get_readiness_label(45), "Needs Improvement")
        self.assertEqual(get_readiness_label(20), "Early Stage")

    @patch('services.career_roadmap_service.genai_client')
    @patch('services.career_roadmap_service.is_gemini_configured', True)
    @patch('services.career_roadmap_service.fetch_user_career_data')
    def test_dynamic_roadmap_isolation_across_candidates(self, mock_fetch, mock_genai_client):
        """Verifies that Candidate A, Candidate B, and Candidate C generate meaningfully different roadmaps."""
        
        # 1. Candidate A Response
        resp_a = MagicMock()
        resp_a.text = json.dumps({
            "career_goal": "Senior Backend Engineer",
            "current_profile_summary": "Backend Python dev needing container orchestration.",
            "readiness_score": 80,
            "readiness_label": "Strongly Prepared",
            "current_strengths": ["Python REST APIs"],
            "priority_gaps": ["Kubernetes"],
            "roadmap": [
                {
                    "phase": 1,
                    "title": "Container Orchestration",
                    "objective": "Master Kubernetes deployments.",
                    "skills_to_develop": ["Kubernetes", "Docker"],
                    "activities": ["Deploy Minikube cluster"],
                    "project_ideas": ["Microservices K8s cluster"],
                    "success_criteria": ["Successful deployment"],
                    "status": "not_started"
                }
            ],
            "recommended_projects": ["K8s Microservices API"],
            "interview_preparation": ["Kubernetes pod networking"],
            "job_readiness_checklist": ["GitHub K8s repo"],
            "estimated_timeline": "4-6 weeks",
            "final_recommendations": ["Learn K8s basics first."]
        })

        # 2. Candidate B Response
        resp_b = MagicMock()
        resp_b.text = json.dumps({
            "career_goal": "Lead Data Analyst",
            "current_profile_summary": "Data Analyst needing PowerBI integration.",
            "readiness_score": 88,
            "readiness_label": "Strongly Prepared",
            "current_strengths": ["SQL Query Optimization", "Tableau"],
            "priority_gaps": ["PowerBI"],
            "roadmap": [
                {
                    "phase": 1,
                    "title": "PowerBI Dashboarding",
                    "objective": "Build executive DAX models.",
                    "skills_to_develop": ["PowerBI", "DAX"],
                    "activities": ["Build sales model in PowerBI"],
                    "project_ideas": ["Executive Revenue Dashboard"],
                    "success_criteria": ["Published PowerBI report"],
                    "status": "not_started"
                }
            ],
            "recommended_projects": ["PowerBI Executive Dashboard"],
            "interview_preparation": ["DAX measure calculations"],
            "job_readiness_checklist": ["PowerBI Portfolio"],
            "estimated_timeline": "2-4 weeks",
            "final_recommendations": ["Master DAX functions."]
        })

        # 3. Candidate C Response
        resp_c = MagicMock()
        resp_c.text = json.dumps({
            "career_goal": "Lead Product Designer",
            "current_profile_summary": "UX Designer needing Figma Design System tokens.",
            "readiness_score": 92,
            "readiness_label": "Highly Ready",
            "current_strengths": ["Figma Prototyping"],
            "priority_gaps": ["Design Tokens"],
            "roadmap": [
                {
                    "phase": 1,
                    "title": "Design System Architecture",
                    "objective": "Build component design tokens.",
                    "skills_to_develop": ["Figma Tokens", "Design System"],
                    "activities": ["Create design token library"],
                    "project_ideas": ["Enterprise Design System"],
                    "success_criteria": ["Published Figma UI kit"],
                    "status": "not_started"
                }
            ],
            "recommended_projects": ["Figma Enterprise UI Kit"],
            "interview_preparation": ["Design system governance"],
            "job_readiness_checklist": ["Figma Community file"],
            "estimated_timeline": "3-5 weeks",
            "final_recommendations": ["Publish UI kit on Figma."]
        })

        mock_fetch.side_effect = [CANDIDATE_A_BACKEND, CANDIDATE_B_DATA, CANDIDATE_C_UX]
        mock_genai_client.models.generate_content.side_effect = [resp_a, resp_b, resp_c]

        rm_a = generate_career_roadmap("user-a", "Senior Backend Engineer")
        rm_b = generate_career_roadmap("user-b", "Lead Data Analyst")
        rm_c = generate_career_roadmap("user-c", "Lead Product Designer")

        self.assertIn("Kubernetes", rm_a["priority_gaps"][0])
        self.assertIn("PowerBI", rm_b["priority_gaps"][0])
        self.assertIn("Design Tokens", rm_c["priority_gaps"][0])

    def test_flask_auth_protection(self):
        """Verifies Flask authentication protection for Phase 10 API endpoints."""
        client = app.test_client()

        res_gen = client.post('/api/career-roadmap/generate', json={})
        self.assertEqual(res_gen.status_code, 401)

        res_hist = client.get('/api/career-roadmap')
        self.assertEqual(res_hist.status_code, 401)


if __name__ == '__main__':
    unittest.main()
