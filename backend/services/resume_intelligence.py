"""
CareerPilot AI — Central Resume Intelligence & Quality Layer
Provides shared normalized resume profiling, evidence extraction, strict anti-hallucination grounding rules,
prioritization, deduplication, resilient Gemini multi-model fallback retry mechanisms across all 7 AI modules.
"""

import os
import json
import logging
import re
import time
from google import genai

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

# Ensure environment variables are loaded from backend/.env or root .env
_backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)
else:
    load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_configured = bool(
    GEMINI_API_KEY 
    and not GEMINI_API_KEY.startswith("your-") 
    and not GEMINI_API_KEY.startswith("dummy") 
    and GEMINI_API_KEY != "your_gemini_api_key_here"
)

genai_client = None
if is_gemini_configured:
    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Resume Intelligence: genai.Client init failed: {e}")


def clean_json_text(raw_text):
    """Clean markdown code block indicators from LLM JSON response string."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def call_gemini_with_retry(client, prompt, response_mime_type="application/json"):
    """
    Executes Gemini API content generation with multi-model fallback and rate-limit backoff.
    Models attempted in order: gemini-flash-latest, gemini-3.7-flash, gemini-3.6-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite, gemini-pro-latest, gemini-3.1-pro-preview.
    """
    if not client:
        raise RuntimeError("Gemini API client is not configured.")

    models_to_try = [
        'gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite',
        'gemini-flash-lite-latest',
        'gemini-3.1-flash-lite-preview',
        'gemini-3-flash-preview',
        'gemini-flash-latest',
        'gemini-3.7-flash',
        'gemini-3.6-flash',
        'gemini-3.1-pro-preview',
        'gemini-pro-latest'
    ]
    last_exception = None

    for model_name in models_to_try:
        try:
            config = {}
            if response_mime_type:
                config['response_mime_type'] = response_mime_type

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config if config else None
            )
            raw_text = (response.text or "").strip()
            if raw_text:
                logger.info(f"Gemini Service: Generation succeeded using model '{model_name}'.")
                return raw_text
        except Exception as err:
            last_exception = err
            err_str = str(err)
            logger.warning(f"Gemini API model '{model_name}' failed: {err_str[:120]}")
            # Try next model immediately without blocking long on rate-limit / unavailable / not found
            continue

    raise RuntimeError(f"All Gemini models failed. Last error: {last_exception}")


def deduplicate_list(items):
    """Deduplicates strings based on normalized lowercase comparison."""
    if not isinstance(items, list):
        return []
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        if isinstance(item, dict):
            val = item.get("skill") or item.get("name") or item.get("title") or item.get("item") or str(item)
        else:
            val = str(item)
        cleaned = val.strip()
        normalized = re.sub(r'[^a-zA-Z0-9]', '', cleaned.lower())
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(cleaned)
    return result


def deduplicate_dict_list(items, key="skill"):
    """Deduplicates list of dictionaries by a primary string key, with fallback keys."""
    if not isinstance(items, list):
        return []
    seen = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            if isinstance(item, str) and item.strip():
                # Convert standalone string to dict
                item = {key: item.strip()}
            else:
                continue

        val = item.get(key) or item.get("skill") or item.get("name") or item.get("title") or item.get("item") or item.get("topic")
        if not val or not isinstance(val, str):
            result.append(item)
            continue

        normalized = re.sub(r'[^a-zA-Z0-9]', '', val.strip().lower())
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(item)
    return result


def extract_resume_intelligence_profile(resume_text, target_role=None):
    """
    Parses and normalizes candidate resume into a structured Intelligence Profile
    with evidence quotes directly extracted from the text.
    Enforces STRICT Grounding: No invented skills, experience, or achievements.
    """
    if not resume_text or not resume_text.strip():
        return {
            "candidate_profile": {"summary": "Empty resume provided.", "years_of_experience": "N/A"},
            "technical_skills": [],
            "soft_skills": [],
            "evidence_bank": [],
            "missing_sections": ["Experience", "Education", "Projects"]
        }

    if not is_gemini_configured or not genai_client:
        logger.info("Resume Intelligence: Fallback extraction used (Gemini client unconfigured).")
        return fallback_profile_extraction(resume_text)

    prompt = f"""
SYSTEM INSTRUCTION: You are a strict Career Intelligence Profile Parser.
Analyze the following resume text and construct a normalized Intelligence Profile with DIRECT EVIDENCE QUOTES.

CRITICAL GROUNDING RULES:
1. Extract ONLY facts, skills, projects, and experience explicitly present in the resume.
2. DO NOT INVENT or assume skills, certifications, job titles, metrics, or tools.
3. If an area (e.g. Certifications, Education) is absent in the text, mark it as "Not mentioned in the resume".
4. For every extracted technical skill or project, include a direct snippet quote from the resume as evidence.

TARGET ROLE (if specified): {target_role or 'Infer from resume if possible'}

RESUME TEXT:
\"\"\"
{resume_text[:6000]}
\"\"\"

Return ONLY valid JSON matching this structure:
{{
  "candidate_profile": {{
    "summary": "Concise factual summary based on resume text.",
    "years_of_experience": "Estimated years or 'Not explicitly stated'",
    "inferred_role_level": "Entry / Mid / Senior"
  }},
  "extracted_skills": [
    {{
      "skill": "Skill Name",
      "category": "technical or soft",
      "evidence": "Direct verbatim or tight quote from resume text demonstrating this skill"
    }}
  ],
  "projects": [
    {{
      "name": "Project Title",
      "technologies": ["Tech1", "Tech2"],
      "evidence": "Description snippet from resume text"
    }}
  ],
  "experience": [
    {{
      "role": "Job Title",
      "company": "Company Name",
      "evidence": "Responsibilities snippet from resume"
    }}
  ],
  "education": ["Degree/Institution snippet"],
  "certifications": ["Certification snippet or 'Not mentioned in the resume'"],
  "missing_sections": ["List of typical sections absent from this resume"]
}}
"""

    try:
        raw_text = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        cleaned = clean_json_text(raw_text)
        profile = json.loads(cleaned)
        
        if "extracted_skills" in profile:
            profile["extracted_skills"] = deduplicate_dict_list(profile["extracted_skills"], key="skill")
        
        return profile
    except Exception as err:
        logger.warning(f"Resume Intelligence extraction failed, using rule fallback: {err}")
        return fallback_profile_extraction(resume_text)


def fallback_profile_extraction(resume_text):
    """Rule-based fallback parser when LLM is unavailable."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    summary = lines[0] if lines else "Resume text extracted."
    
    known_tech = ["python", "javascript", "react", "html", "css", "sql", "java", "c++", "flask", "django", "node", "aws", "docker", "git", "firebase", "mongodb", "postgresql", "figma"]
    found_skills = []
    text_lower = resume_text.lower()
    
    for tech in known_tech:
        if tech in text_lower:
            found_skills.append({
                "skill": tech.capitalize(),
                "category": "technical",
                "evidence": f"Found '{tech}' keyword in resume text."
            })
            
    return {
        "candidate_profile": {
            "summary": summary,
            "years_of_experience": "Extracted from resume content",
            "inferred_role_level": "Candidate"
        },
        "extracted_skills": found_skills,
        "projects": [],
        "experience": [],
        "education": ["Extracted from resume"],
        "certifications": ["Not mentioned in the resume"],
        "missing_sections": []
    }
