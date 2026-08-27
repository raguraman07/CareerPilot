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
from services.roadmap_pdf_service import generate_roadmap_pdf_bytes

# Sample candidate career data for 3 distinct domain candidates
CANDIDATE_A_BACKEND = {
    "career_goal": {"company_name": "Microsoft", "job_role": "Cloud Engineer"},
    "profile": {"education": {"highest_education": "B.Tech", "specialization": "Computer Science"}, "skills": {"programming_languages": ["Python", "Bash"]}},
    "resumes": [{"extracted_text": "Jane Doe - Python Backend Dev. Skills: Python, Flask, SQL."}],
    "analyses": [{"summary": "Backend dev", "technical_skills": ["Python", "Flask", "SQL"], "missing_skills": ["Kubernetes", "Azure"]}],
    "ats_scores": [{"ats_score": 85, "missing_keywords": ["Terraform"]}],
    "job_matches": [{"job_title": "Cloud Engineer", "match_score": 80, "missing_skills": ["Kubernetes"]}],
    "interviews": []
}

CANDIDATE_B_DATA = {
    "career_goal": {"company_name": "Google", "job_role": "Data Analyst"},
    "profile": {"education": {"highest_education": "B.Sc", "specialization": "Statistics"}, "skills": {"programming_languages": ["SQL", "R"]}},
    "resumes": [{"extracted_text": "Alex Smith - Data Analyst. Skills: SQL, R, Tableau."}],
    "analyses": [{"summary": "Data analyst", "technical_skills": ["SQL", "Tableau"], "missing_skills": ["PowerBI", "BigQuery"]}],
    "ats_scores": [{"ats_score": 88, "missing_keywords": ["DAX"]}],
    "job_matches": [{"job_title": "Lead Data Analyst", "match_score": 90, "missing_skills": ["PowerBI"]}],
    "interviews": []
}

CANDIDATE_C_UX = {
    "career_goal": {"company_name": "Adobe", "job_role": "Product Designer"},
    "profile": {"education": {"highest_education": "B.Des", "specialization": "Design"}, "skills": {"programming_languages": ["HTML", "CSS"]}},
    "resumes": [{"extracted_text": "Morgan Lee - UI/UX Designer. Skills: Figma, Adobe XD."}],
    "analyses": [{"summary": "UX designer", "technical_skills": ["Figma", "Adobe XD"], "missing_skills": ["Design Tokens"]}],
    "ats_scores": [{"ats_score": 90, "missing_keywords": ["Design Systems"]}],
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
        """Verifies that Candidate A, Candidate B, and Candidate C generate meaningfully different roadmaps with new schema."""
        
        # 1. Candidate A Response
        resp_a = MagicMock()
        resp_a.text = json.dumps({
            "career_goal": {"company": "Microsoft", "role": "Cloud Engineer"},
            "current_readiness": {"score": 80, "summary": "Backend Python dev needing Kubernetes & Azure."},
            "roadmap_duration": "10–12 weeks",
            "skill_gaps": [
                {
                    "skill": "Kubernetes",
                    "importance": "High",
                    "reason": "Essential for container orchestration at Microsoft.",
                    "current_level": "Beginner",
                    "target_level": "Production Ready"
                }
            ],
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Container Orchestration & Cloud Infrastructure",
                    "duration": "3 weeks",
                    "objective": "Master Kubernetes and Docker deployments on Azure.",
                    "skills": [
                        {"name": "Kubernetes", "priority": "High", "reason": "Required for Cloud Engineer role", "what_to_learn": "Pod lifecycle, Helm"}
                    ],
                    "languages": ["Python", "Bash"],
                    "technologies": ["Kubernetes", "Docker", "Azure"],
                    "tools": ["Git", "Terraform"],
                    "core_subjects": ["Computer Networks", "Distributed Systems"],
                    "certifications": [{"name": "AZ-104 Azure Administrator", "provider": "Microsoft", "priority": "High", "url": "https://learn.microsoft.com"}],
                    "projects": [{"title": "Cloud Infrastructure Deployment", "difficulty": "Intermediate", "skills": ["Kubernetes", "Terraform"]}],
                    "milestone": "Deploy microservice cluster to Azure"
                }
            ],
            "final_readiness": {"technical_skills": ["Kubernetes", "Azure"], "interview_ready": False}
        })

        # 2. Candidate B Response
        resp_b = MagicMock()
        resp_b.text = json.dumps({
            "career_goal": {"company": "Google", "role": "Data Analyst"},
            "current_readiness": {"score": 88, "summary": "Data Analyst needing PowerBI and BigQuery."},
            "roadmap_duration": "8–10 weeks",
            "skill_gaps": [
                {
                    "skill": "PowerBI",
                    "importance": "High",
                    "reason": "Required for enterprise reporting and executive dashboards.",
                    "current_level": "Beginner",
                    "target_level": "Advanced DAX"
                }
            ],
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Advanced DAX & BigQuery Analytics",
                    "duration": "2 weeks",
                    "objective": "Build enterprise DAX models.",
                    "skills": [
                        {"name": "PowerBI", "priority": "High", "reason": "Required for enterprise reporting", "what_to_learn": "DAX measures and data modeling"}
                    ],
                    "languages": ["SQL", "R"],
                    "technologies": ["BigQuery", "PowerBI"],
                    "tools": ["Tableau", "Git"],
                    "core_subjects": ["Data Warehousing", "Statistical Methods"],
                    "certifications": [{"name": "Google Data Analytics Professional", "provider": "Google", "priority": "High", "url": "https://coursera.org"}],
                    "projects": [{"title": "Executive Revenue BI Dashboard", "difficulty": "Intermediate", "skills": ["PowerBI", "DAX"]}],
                    "milestone": "Publish executive data model"
                }
            ],
            "final_readiness": {"technical_skills": ["PowerBI", "BigQuery"], "interview_ready": False}
        })

        # 3. Candidate C Response
        resp_c = MagicMock()
        resp_c.text = json.dumps({
            "career_goal": {"company": "Adobe", "role": "Product Designer"},
            "current_readiness": {"score": 92, "summary": "UX Designer needing Design Tokens and Design Systems."},
            "roadmap_duration": "6–8 weeks",
            "skill_gaps": [
                {
                    "skill": "Design Tokens",
                    "importance": "High",
                    "reason": "Required for scalable cross-platform UI systems at Adobe.",
                    "current_level": "Beginner",
                    "target_level": "Design Tokens Architecture"
                }
            ],
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Design System Tokens & Governance",
                    "duration": "2 weeks",
                    "objective": "Build multi-platform design tokens.",
                    "skills": [
                        {"name": "Design Tokens", "priority": "High", "reason": "Required for scalable UI engineering", "what_to_learn": "Figma Tokens, JSON architecture"}
                    ],
                    "languages": ["CSS", "HTML"],
                    "technologies": ["Figma", "Storybook"],
                    "tools": ["Zeroheight", "Git"],
                    "core_subjects": ["Human-Computer Interaction", "Typography"],
                    "certifications": [],
                    "projects": [{"title": "Enterprise Design System", "difficulty": "Advanced", "skills": ["Figma", "Design Tokens"]}],
                    "milestone": "Publish design token library"
                }
            ],
            "final_readiness": {"technical_skills": ["Design Tokens"], "interview_ready": False}
        })

        mock_fetch.side_effect = [CANDIDATE_A_BACKEND, CANDIDATE_B_DATA, CANDIDATE_C_UX]
        mock_genai_client.models.generate_content.side_effect = [resp_a, resp_b, resp_c]

        rm_a = generate_career_roadmap("user-a", "Cloud Engineer")
        rm_b = generate_career_roadmap("user-b", "Data Analyst")
        rm_c = generate_career_roadmap("user-c", "Product Designer")

        self.assertEqual(rm_a["career_goal"]["company"], "Microsoft")
        self.assertEqual(rm_a["career_goal"]["role"], "Cloud Engineer")
        self.assertEqual(rm_a["phases"][0]["skills"][0]["name"], "Kubernetes")
        self.assertEqual(rm_a["skill_gaps"][0]["skill"], "Kubernetes")

        self.assertEqual(rm_b["career_goal"]["company"], "Google")
        self.assertEqual(rm_b["phases"][0]["skills"][0]["name"], "PowerBI")
        self.assertEqual(rm_b["skill_gaps"][0]["skill"], "PowerBI")

        self.assertEqual(rm_c["career_goal"]["company"], "Adobe")
        self.assertEqual(rm_c["phases"][0]["skills"][0]["name"], "Design Tokens")
        self.assertEqual(rm_c["skill_gaps"][0]["skill"], "Design Tokens")

    def test_pdf_generation_bytes(self):
        """Verifies that generate_roadmap_pdf_bytes returns valid non-empty PDF bytes starting with %PDF-."""
        sample_roadmap = {
            "career_goal": {"company": "Microsoft", "role": "Cloud Engineer"},
            "current_readiness": {"score": 75, "summary": "Strong fundamentals, needs cloud specialization."},
            "roadmap_duration": "10–12 weeks",
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Cloud Fundamentals",
                    "duration": "2 weeks",
                    "objective": "Build Azure & Linux foundations",
                    "skills": [{"name": "Linux", "priority": "High", "reason": "Core requirement", "what_to_learn": "Bash, permissions"}],
                    "languages": ["Python", "Bash"],
                    "technologies": ["Linux", "Docker"],
                    "tools": ["Git"],
                    "core_subjects": ["Operating Systems"],
                    "certifications": [{"name": "AZ-900", "provider": "Microsoft", "priority": "High", "reason": "Baseline cert", "url": "https://microsoft.com"}],
                    "projects": [{"title": "Cloud VM Provisioning", "difficulty": "Beginner", "skills": ["Linux", "Python"], "what_to_build": "Automated script", "expected_outcome": "Working repo"}],
                    "milestone": "Complete 3 automated scripts"
                }
            ],
            "recommended_projects": [{"title": "Cloud VM Provisioning", "difficulty": "Beginner", "skills": ["Linux", "Python"], "what_to_build": "Automated script", "expected_outcome": "Working repo"}]
        }

        pdf_bytes = generate_roadmap_pdf_bytes(sample_roadmap)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(len(pdf_bytes) > 500)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_flask_auth_protection(self):
        """Verifies Flask authentication protection for Phase 10 API endpoints."""
        client = app.test_client()

        res_gen = client.post('/api/career-roadmap/generate', json={})
        self.assertEqual(res_gen.status_code, 401)

        res_hist = client.get('/api/career-roadmap')
        self.assertEqual(res_hist.status_code, 401)

        res_latest = client.get('/api/career-roadmap/latest')
        self.assertEqual(res_latest.status_code, 401)

        res_pdf = client.post('/api/career-roadmap/sample-id/export-pdf')
        self.assertEqual(res_pdf.status_code, 401)


if __name__ == '__main__':
    unittest.main()

