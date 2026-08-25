import os
import json
import logging
import re

logger = logging.getLogger(__name__)

# Official Google GenAI SDK (google-genai)
try:
    from google import genai
except ImportError:
    genai = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_configured = bool(
    GEMINI_API_KEY 
    and not GEMINI_API_KEY.startswith("your-") 
    and not GEMINI_API_KEY.startswith("dummy") 
    and GEMINI_API_KEY != "your_gemini_api_key_here"
)

genai_client = None

if is_gemini_configured and genai is not None:
    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("ATS Service: Official google.genai client initialized.")
    except Exception as client_err:
        logger.warning(f"ATS Service: google.genai client initialization failed: {client_err}")
elif not is_gemini_configured:
    logger.warning("ATS Service: GEMINI_API_KEY is not configured or is placeholder.")

REQUIRED_ATS_KEYS = [
    "keyword_analysis",
    "skills_analysis",
    "experience_analysis",
    "education_analysis",
    "structure_analysis",
    "formatting_analysis",
    "achievements_analysis",
    "overall_recommendations",
    "ats_warnings"
]


def clamp(value, min_val, max_val):
    """Clamps a numeric value between min_val and max_val."""
    return max(min_val, min(max_val, value))


def calculate_deterministic_ats_scores(ats_results, resume_text=""):
    """
    Computes deterministic backend sub-scores and overall score based on 
    Gemini's dynamic structured analysis JSON and resume metrics.

    Weighting:
      - Keyword Optimization       = 25 points
      - Skills Relevance           = 20 points
      - Experience Relevance       = 15 points
      - Resume Structure           = 15 points
      - ATS Formatting             = 10 points
      - Education & Certifications = 10 points
      - Achievements              = 5 points
      Total = 100 points
    """
    kw_analysis = ats_results.get("keyword_analysis") or {}
    found_kw = kw_analysis.get("found_keywords") or []
    missing_kw = kw_analysis.get("missing_keywords") or []
    
    total_kw_count = len(found_kw) + len(missing_kw)
    kw_ratio = (len(found_kw) / total_kw_count) if total_kw_count > 0 else 0.6
    kw_volume_factor = min(1.0, len(found_kw) / 8.0)
    keyword_score = clamp(round(25 * (0.65 * kw_ratio + 0.35 * kw_volume_factor)), 2, 25)

    sk_analysis = ats_results.get("skills_analysis") or {}
    detected_sk = sk_analysis.get("detected_skills") or []
    missing_sk = sk_analysis.get("missing_skills") or []
    
    total_sk_count = len(detected_sk) + len(missing_sk)
    sk_ratio = (len(detected_sk) / total_sk_count) if total_sk_count > 0 else 0.65
    sk_volume_factor = min(1.0, len(detected_sk) / 7.0)
    skills_score = clamp(round(20 * (0.7 * sk_ratio + 0.3 * sk_volume_factor)), 2, 20)

    exp_analysis = ats_results.get("experience_analysis") or {}
    exp_strengths = exp_analysis.get("strengths") or []
    exp_weaknesses = exp_analysis.get("weaknesses") or []
    base_exp = 10
    exp_score_calc = base_exp + (len(exp_strengths) * 2.5) - (len(exp_weaknesses) * 2.0)
    experience_score = clamp(round(exp_score_calc), 2, 15)

    str_analysis = ats_results.get("structure_analysis") or {}
    detected_sec = str_analysis.get("detected_sections") or []
    missing_sec = str_analysis.get("missing_sections") or []
    total_sec = len(detected_sec) + len(missing_sec)
    sec_ratio = (len(detected_sec) / total_sec) if total_sec > 0 else 0.8
    structure_score = clamp(round(15 * sec_ratio), 3, 15)

    fmt_analysis = ats_results.get("formatting_analysis") or {}
    fmt_issues = fmt_analysis.get("issues") or []
    formatting_score = clamp(10 - (len(fmt_issues) * 2), 2, 10)

    edu_analysis = ats_results.get("education_analysis") or {}
    edu_strengths = edu_analysis.get("strengths") or []
    base_edu = 6 if edu_strengths else 4
    education_score = clamp(round(base_edu + len(edu_strengths) * 2), 2, 10)

    ach_analysis = ats_results.get("achievements_analysis") or {}
    ach_strengths = ach_analysis.get("strengths") or []
    ach_weaknesses = ach_analysis.get("weaknesses") or []
    base_ach = 3 if ach_strengths else 2
    achievements_score = clamp(round(base_ach + len(ach_strengths) * 1.5 - len(ach_weaknesses) * 1.0), 1, 5)

    overall_score = clamp(
        keyword_score + skills_score + experience_score + 
        structure_score + formatting_score + education_score + achievements_score,
        0, 100
    )

    if overall_score >= 90:
        score_level = "Excellent ATS Compatibility"
    elif overall_score >= 75:
        score_level = "Strong ATS Compatibility"
    elif overall_score >= 60:
        score_level = "Needs Improvement"
    elif overall_score >= 40:
        score_level = "Poor ATS Compatibility"
    else:
        score_level = "Very Poor ATS Compatibility"

    return {
        "overall_score": overall_score,
        "keyword_score": keyword_score,
        "skills_score": skills_score,
        "experience_score": experience_score,
        "structure_score": structure_score,
        "formatting_score": formatting_score,
        "education_score": education_score,
        "achievements_score": achievements_score,
        "score_level": score_level
    }


def validate_ats_json(data):
    """Validates that Gemini returned valid JSON containing all 9 required fields."""
    if not isinstance(data, dict):
        return False
    for k in REQUIRED_ATS_KEYS:
        if k not in data:
            logger.warning(f"ATS Service Validation: Missing key '{k}' in response.")
            return False
    return True


def clean_json_text(raw_text):
    """Strips markdown ```json headers and extra spaces."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def run_gemini_ats_analysis(resume_text):
    """
    Calls Google Gemini to perform dynamic semantic ATS audit on resume text.
    No hardcoded mock responses are returned if Gemini fails.
    Returns structured analysis JSON or raises RuntimeError.
    """
    if not is_gemini_configured or not genai_client:
        logger.error("ATS Service: GEMINI_API_KEY is missing or invalid. AI service unavailable.")
        raise RuntimeError("AI analysis is temporarily unavailable. Please try again.")

    prompt = f"""
You are an expert Applicant Tracking System (ATS) resume evaluator and professional resume reviewer.
Analyze the following candidate resume text carefully and thoroughly.

Evaluate:
- Keyword optimization & industry terms found in the candidate's actual background
- Technical skills and soft skills relevance
- Work experience bullet point strengths and weaknesses
- Education and certifications completeness
- Resume sections and structural completeness
- ATS formatting compatibility and parser pitfalls
- Measurable achievements and STAR method metrics
- Critical ATS warnings and high-impact actionable recommendations

CRITICAL CONSTRAINTS:
- You must NOT invent or hallucinate information not present in the resume text.
- Do NOT use a predefined list of technologies or skills.
- Analyze ONLY the supplied resume text.
- You MUST return ONLY a raw valid JSON object.
- Do NOT return Markdown or wrap inside ```json codeblocks.
- Do NOT include any conversational text or commentary outside the JSON.

REQUIRED JSON STRUCTURE:
{{
  "keyword_analysis": {{
    "found_keywords": ["Detected Keyword 1", "Detected Keyword 2"],
    "missing_keywords": ["Inferred Missing Keyword 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "skills_analysis": {{
    "detected_skills": ["Detected Skill 1", "Detected Skill 2"],
    "missing_skills": ["Inferred Missing Skill 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "experience_analysis": {{
    "strengths": ["Experience Strength 1"],
    "weaknesses": ["Experience Weakness 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "education_analysis": {{
    "strengths": ["Education Strength 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "structure_analysis": {{
    "detected_sections": ["Detected Section 1"],
    "missing_sections": ["Missing Section 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "formatting_analysis": {{
    "issues": ["Formatting Issue 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "achievements_analysis": {{
    "strengths": ["Achievement Strength 1"],
    "weaknesses": ["Achievement Weakness 1"],
    "recommendations": ["Recommendation 1"]
  }},
  "overall_recommendations": ["Recommendation 1", "Recommendation 2"],
  "ats_warnings": ["Warning 1"]
}}

Resume Text to Analyze:
{resume_text}
"""

    from backend.services.resume_intelligence import call_gemini_with_retry, deduplicate_list
    try:
        logger.info("ATS Service: Invoking Gemini API with multi-model fallback...")
        raw_text = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        cleaned = clean_json_text(raw_text)
        parsed = json.loads(cleaned)
        if validate_ats_json(parsed):
            logger.info("ATS Service: Gemini response validated successfully.")
            parsed["overall_recommendations"] = deduplicate_list(parsed.get("overall_recommendations", []))
            parsed["ats_warnings"] = deduplicate_list(parsed.get("ats_warnings", []))
            return parsed
        else:
            logger.warning("ATS Service: Response validation failed.")
    except Exception as err:
        logger.error(f"ATS Service: Gemini call error: {err}")

    logger.error("ATS Service: All Gemini API attempts failed or returned invalid JSON.")
    raise RuntimeError("AI analysis is temporarily unavailable. Please try again.")
