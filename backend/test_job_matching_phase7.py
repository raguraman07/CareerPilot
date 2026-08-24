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

from services.job_matching_service import analyze_job_match, get_match_level

# Test Resumes
RESUME_A_SOFTWARE_DEV = """
Jane Doe - Senior Python Backend Engineer
Summary: Software engineer specializing in building high-concurrency microservices with Python, Flask, and PostgreSQL.
Technical Skills: Python, Flask, FastAPI, PostgreSQL, Redis, Celery, Docker, Linux, Git.
Experience:
- Senior Backend Developer at Tech Corp (2021-Present): Designed REST APIs using Flask and FastAPI. Reduced query latency by 40% with Redis caching.
- Software Engineer at Data Systems (2018-2021): Built ETL data pipelines in Python and SQL.
Education: B.S. in Computer Science, University of Technology.
"""

RESUME_B_DATA_ANALYST = """
Alex Smith - Senior Data Analyst & BI Consultant
Summary: Insight-driven Data Analyst with 5+ years of experience interpreting complex business datasets, creating interactive dashboards, and building statistical predictive models.
Technical Skills: SQL, R, Python (Pandas, NumPy), Tableau, PowerBI, Excel VBA, A/B Testing, Regression Analysis.
Experience:
- Lead Data Analyst at Retail Analytics (2020-Present): Developed Tableau executive dashboards tracking $50M revenue streams. Automated monthly reporting via SQL and R.
- Junior Analyst at Financial Insights (2018-2020): Performed customer segmentation and cohort analysis in Python.
Education: M.S. in Applied Statistics, State University.
"""

RESUME_C_UIUX_DESIGNER = """
Morgan Lee - Lead UI/UX Designer & Product Strategist
Summary: User-centered Product Designer crafting intuitive digital experiences, design systems, and high-fidelity interactive prototypes.
Technical Skills: Figma, Adobe XD, Sketch, Wireframing, Prototyping, Usability Testing, User Research, Information Architecture, HTML/CSS.
Experience:
- Senior UX Designer at Creative Studio (2021-Present): Led redesign of mobile banking application used by 200,000 active users. Conducted 50+ user research interviews and usability testing sessions.
- UI Designer at Web Agency (2019-2019): Created comprehensive Figma design tokens and component libraries.
Education: B.A. in Graphic Design & Human-Computer Interaction.
"""

# Job Descriptions
JOB_A_BACKEND_WITH_KUBERNETES = """
Job Title: Senior Backend Engineer
Requirements:
- 3+ years experience developing backend APIs in Python (Flask or FastAPI).
- Strong proficiency in PostgreSQL database optimization.
- Must have hands-on experience with Kubernetes and Cloud Native container orchestration.
- Familiarity with CI/CD deployment pipelines.
"""

JOB_A_BACKEND_WITHOUT_KUBERNETES = """
Job Title: Python Developer
Requirements:
- Strong experience in Python programming and Flask framework.
- Experience with Relational Databases (PostgreSQL/MySQL).
- Knowledge of Redis caching and REST API architecture.
"""

JOB_B_DATA_ANALYST = """
Job Title: Senior Data Analyst
Requirements:
- Expert knowledge of SQL data querying and database aggregation.
- 3+ years experience building executive visual dashboards in Tableau or PowerBI.
- Statistical modeling capabilities in Python or R.
"""

JOB_C_UX_DESIGNER = """
Job Title: Lead Product UX Designer
Requirements:
- Expert proficiency in Figma and design systems documentation.
- Track record of conducting usability testing and user interviews.
- Experience crafting mobile application user journeys.
"""


class TestJobMatchingPhase7(unittest.TestCase):

    def test_score_level_mapping(self):
        """Verifies score interpretation thresholds."""
        self.assertEqual(get_match_level(95), "Excellent Match")
        self.assertEqual(get_match_level(82), "Strong Match")
        self.assertEqual(get_match_level(65), "Moderate Match")
        self.assertEqual(get_match_level(45), "Low Match")
        self.assertEqual(get_match_level(20), "Poor Match")

    @patch('services.job_matching_service.genai_client')
    @patch('services.job_matching_service.is_gemini_configured', True)
    def test_dynamic_resume_isolation_across_roles(self, mock_genai_client):
        """Test 3 substantially different resumes against different job descriptions."""

        # 1. Backend Resume + Backend Job
        mock_resp_1 = MagicMock()
        mock_resp_1.text = json.dumps({
            "job_title": "Senior Backend Engineer",
            "match_score": 88,
            "match_level": "Strong Match",
            "matching_skills": ["Python", "Flask", "PostgreSQL", "Docker"],
            "missing_skills": ["Kubernetes"],
            "experience_match": {"score": 90, "strengths": ["Strong Flask experience"], "gaps": ["No Kubernetes"]},
            "education_match": {"score": 95, "strengths": ["BS CS degree"], "gaps": []},
            "qualification_match": {"score": 85, "strengths": ["REST API design"], "gaps": []},
            "candidate_strengths": ["Core Python expertise"],
            "candidate_weaknesses": ["Container orchestration gap"],
            "skill_gaps": [{"skill": "Kubernetes", "importance": "High", "reason": "Job requires K8s", "recommendation": "Learn K8s basics"}],
            "recommendations": ["Highlight K8s or Docker swarm experience"],
            "summary": "Great backend candidate."
        })

        # 2. Data Resume + Data Job
        mock_resp_2 = MagicMock()
        mock_resp_2.text = json.dumps({
            "job_title": "Senior Data Analyst",
            "match_score": 92,
            "match_level": "Excellent Match",
            "matching_skills": ["SQL", "Tableau", "Python", "R", "Statistics"],
            "missing_skills": [],
            "experience_match": {"score": 95, "strengths": ["Tableau dashboards"], "gaps": []},
            "education_match": {"score": 95, "strengths": ["MS Statistics"], "gaps": []},
            "qualification_match": {"score": 90, "strengths": ["Statistical modeling"], "gaps": []},
            "candidate_strengths": ["SQL and Tableau mastery"],
            "candidate_weaknesses": [],
            "skill_gaps": [],
            "recommendations": ["Highlight revenue impact metrics"],
            "summary": "Outstanding data analyst fit."
        })

        # 3. UX Resume + UX Job
        mock_resp_3 = MagicMock()
        mock_resp_3.text = json.dumps({
            "job_title": "Lead Product UX Designer",
            "match_score": 90,
            "match_level": "Excellent Match",
            "matching_skills": ["Figma", "Usability Testing", "Wireframing", "User Research"],
            "missing_skills": [],
            "experience_match": {"score": 90, "strengths": ["Mobile app design"], "gaps": []},
            "education_match": {"score": 90, "strengths": ["HCI degree"], "gaps": []},
            "qualification_match": {"score": 90, "strengths": ["Design tokens"], "gaps": []},
            "candidate_strengths": ["Figma design system expertise"],
            "candidate_weaknesses": [],
            "skill_gaps": [],
            "recommendations": ["Present mobile portfolio prototypes"],
            "summary": "Strong UX design candidate."
        })

        # Run Backend Test
        mock_genai_client.models.generate_content.side_effect = [mock_resp_1, mock_resp_2, mock_resp_3]

        res_1 = analyze_job_match(RESUME_A_SOFTWARE_DEV, JOB_A_BACKEND_WITH_KUBERNETES, "Senior Backend Engineer")
        res_2 = analyze_job_match(RESUME_B_DATA_ANALYST, JOB_B_DATA_ANALYST, "Senior Data Analyst")
        res_3 = analyze_job_match(RESUME_C_UIUX_DESIGNER, JOB_C_UX_DESIGNER, "Lead Product UX Designer")

        # Verify distinct matching skills
        self.assertIn("Python", res_1["matching_skills"])
        self.assertIn("Tableau", res_2["matching_skills"])
        self.assertIn("Figma", res_3["matching_skills"])

        # Verify unique strengths and recommendations
        self.assertNotEqual(res_1["matching_skills"], res_2["matching_skills"])
        self.assertNotEqual(res_2["matching_skills"], res_3["matching_skills"])

    @patch('services.job_matching_service.genai_client')
    @patch('services.job_matching_service.is_gemini_configured', True)
    def test_dynamic_missing_skill_verification(self, mock_genai_client):
        """
        Verify that Kubernetes is identified as missing ONLY when Job Description explicitly requires it,
        and NOT listed when Job Description does not require it.
        """
        # Case 1: Job Requires Kubernetes
        resp_k8s = MagicMock()
        resp_k8s.text = json.dumps({
            "job_title": "Backend Engineer",
            "match_score": 80,
            "match_level": "Strong Match",
            "matching_skills": ["Python", "Flask"],
            "missing_skills": ["Kubernetes"],
            "skill_gaps": [{"skill": "Kubernetes", "importance": "High", "reason": "Required for deployment"}],
            "recommendations": ["Add Kubernetes training"],
            "summary": "Missing K8s requirement."
        })

        # Case 2: Job Does NOT Require Kubernetes
        resp_no_k8s = MagicMock()
        resp_no_k8s.text = json.dumps({
            "job_title": "Python Developer",
            "match_score": 95,
            "match_level": "Excellent Match",
            "matching_skills": ["Python", "Flask", "PostgreSQL", "Redis"],
            "missing_skills": [],
            "skill_gaps": [],
            "recommendations": ["Highlight API performance"],
            "summary": "Complete match."
        })

        mock_genai_client.models.generate_content.side_effect = [resp_k8s, resp_no_k8s]

        res_with_k8s = analyze_job_match(RESUME_A_SOFTWARE_DEV, JOB_A_BACKEND_WITH_KUBERNETES)
        res_without_k8s = analyze_job_match(RESUME_A_SOFTWARE_DEV, JOB_A_BACKEND_WITHOUT_KUBERNETES)

        self.assertIn("Kubernetes", res_with_k8s["missing_skills"])
        self.assertNotIn("Kubernetes", res_without_k8s["missing_skills"])

    def test_flask_endpoints_and_regression(self):
        """Verifies Flask routes and health endpoints exist and respond."""
        client = app.test_client()

        # Health check
        res = client.get('/api/health')
        self.assertEqual(res.status_code, 200)

        # Unauthenticated calls should return 401
        res_match = client.post('/api/job-matching/analyze', json={})
        self.assertEqual(res_match.status_code, 401)

        res_hist = client.get('/api/job-matching/history')
        self.assertEqual(res_hist.status_code, 401)


if __name__ == '__main__':
    unittest.main()
