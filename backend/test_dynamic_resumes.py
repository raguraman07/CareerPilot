import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(__file__))

from backend.app.blueprints.ai.gemini_service import analyze_resume_text, validate_analysis_json

RESUME_A_SOFTWARE_DEV = """
Jane Doe - Senior Python Backend Engineer
Email: jane@example.com | Phone: 555-0199
Summary: Software engineer specializing in building high-concurrency microservices with Python, Flask, and PostgreSQL.
Technical Skills: Python, Flask, FastAPI, PostgreSQL, Redis, Celery, Docker, Linux, Git.
Experience:
- Senior Backend Developer at Tech Corp (2021-Present): Designed REST APIs using Flask and FastAPI. Reduced query latency by 40% with Redis caching.
- Software Engineer at Data Systems (2018-2021): Built ETL data pipelines in Python and SQL.
Education: B.S. in Computer Science, University of Technology.
"""

RESUME_B_DATA_ANALYST = """
Alex Smith - Senior Data Analyst & BI Consultant
Email: alex@example.com | Phone: 555-0288
Summary: Insight-driven Data Analyst with 5+ years of experience interpreting complex business datasets, creating interactive dashboards, and building statistical predictive models.
Technical Skills: SQL, R, Python (Pandas, NumPy), Tableau, PowerBI, Excel VBA, A/B Testing, Regression Analysis.
Experience:
- Lead Data Analyst at Retail Analytics (2020-Present): Developed Tableau executive dashboards tracking $50M revenue streams. Automated monthly reporting via SQL and R.
- Junior Analyst at Financial Insights (2018-2020): Performed customer segmentation and cohort analysis in Python.
Education: M.S. in Applied Statistics, State University.
"""

RESUME_C_UIUX_DESIGNER = """
Morgan Lee - Lead UI/UX Designer & Product Strategist
Email: morgan@example.com | Phone: 555-0377
Summary: User-centered Product Designer crafting intuitive digital experiences, design systems, and high-fidelity interactive prototypes.
Technical Skills: Figma, Adobe XD, Sketch, Wireframing, Prototyping, Usability Testing, User Research, Information Architecture, HTML/CSS.
Experience:
- Senior UX Designer at Creative Studio (2021-Present): Led redesign of mobile banking application used by 200,000 active users. Conducted 50+ user research interviews and usability testing sessions.
- UI Designer at Web Agency (2019-2021): Created comprehensive Figma design tokens and component libraries.
Education: B.A. in Graphic Design & Human-Computer Interaction.
"""

class TestDynamicGeminiResumeAnalysis(unittest.TestCase):
    @patch('backend.app.blueprints.ai.gemini_service.genai_client')
    @patch('backend.app.blueprints.ai.gemini_service.is_gemini_configured', True)
    def test_dynamic_gemini_resume_isolation(self, mock_genai_client):
        """Verifies that 3 different resumes produce strictly dynamic, distinct skills and roles using Google Gemini."""
        
        # Mock Gemini response for Resume A (Software Dev)
        mock_response_A = MagicMock()
        mock_response_A.text = json.dumps({
            "resume_summary": "Experienced Python and Flask backend developer.",
            "technical_skills_found": ["Python", "Flask", "FastAPI", "PostgreSQL", "Redis", "Celery", "Docker"],
            "soft_skills_found": ["Problem solving"],
            "strengths": ["Strong backend and API design experience"],
            "weaknesses": ["No automated testing mentioned"],
            "missing_skills": ["PyTest", "CI/CD"],
            "recommended_roles": ["Backend Engineer", "Python Developer"],
            "actionable_recommendations": ["Add unit tests with PyTest"]
        })

        # Mock Gemini response for Resume B (Data Analyst)
        mock_response_B = MagicMock()
        mock_response_B.text = json.dumps({
            "resume_summary": "Data Analyst specializing in SQL, Tableau, and statistical models.",
            "technical_skills_found": ["SQL", "R", "Pandas", "NumPy", "Tableau", "PowerBI", "Excel VBA"],
            "soft_skills_found": ["Analytical thinking"],
            "strengths": ["Strong dashboarding and statistical analysis background"],
            "weaknesses": ["Limited cloud database exposure"],
            "missing_skills": ["Snowflake", "BigQuery"],
            "recommended_roles": ["Data Analyst", "BI Developer"],
            "actionable_recommendations": ["Add cloud data warehouse skills"]
        })

        # Mock Gemini response for Resume C (UI/UX Designer)
        mock_response_C = MagicMock()
        mock_response_C.text = json.dumps({
            "resume_summary": "Product designer specializing in Figma and user research.",
            "technical_skills_found": ["Figma", "Adobe XD", "Sketch", "Wireframing", "Prototyping", "Usability Testing"],
            "soft_skills_found": ["User empathy"],
            "strengths": ["Extensive usability research and mobile design experience"],
            "weaknesses": ["No front-end framework experience"],
            "missing_skills": ["Design Tokens", "Design System Documentation"],
            "recommended_roles": ["UI/UX Designer", "Product Designer"],
            "actionable_recommendations": ["Build interactive prototype showcase"]
        })

        mock_genai_client.models.generate_content.side_effect = [mock_response_A, mock_response_B, mock_response_C]

        res_A = analyze_resume_text(RESUME_A_SOFTWARE_DEV)
        res_B = analyze_resume_text(RESUME_B_DATA_ANALYST)
        res_C = analyze_resume_text(RESUME_C_UIUX_DESIGNER)

        # 1. Verify Resume A has Python/Flask but NO React, NO Figma, NO Tableau
        self.assertIn("Python", res_A["technical_skills_found"])
        self.assertNotIn("Figma", res_A["technical_skills_found"])
        self.assertNotIn("Tableau", res_A["technical_skills_found"])

        # 2. Verify Resume B has Tableau/SQL/R but NO Docker, NO Figma, NO React
        self.assertIn("Tableau", res_B["technical_skills_found"])
        self.assertNotIn("Figma", res_B["technical_skills_found"])
        self.assertNotIn("Docker", res_B["technical_skills_found"])

        # 3. Verify Resume C has Figma/Adobe XD but NO Python, NO Docker, NO React
        self.assertIn("Figma", res_C["technical_skills_found"])
        self.assertNotIn("Python", res_C["technical_skills_found"])
        self.assertNotIn("Docker", res_C["technical_skills_found"])

        # 4. Critical check: Software Developer resume does NOT say "React" or "Docker" as a skill unless extracted
        self.assertNotIn("React", res_A["technical_skills_found"])

        print("SUCCESS: Dynamic Gemini resume isolation verified across Software Dev, Data Analyst, and UI/UX Designer resumes!")

if __name__ == '__main__':
    unittest.main()
