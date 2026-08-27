import logging
try:
    from backend.firebase_client import db
except ImportError:
    from firebase_client import db

logger = logging.getLogger(__name__)

def fetch_user_career_data(uid):
    """
    Retrieves all relevant Firestore documents for the authenticated user across:
    1. Career Goals
    2. Profile / Education / Skills / Projects / Certs
    3. Resumes
    4. Resume Analyses
    5. ATS Scores
    6. Job Matches
    7. Interview Sessions
    """
    context_data = {
        "career_goal": None,
        "profile": None,
        "resumes": [],
        "analyses": [],
        "ats_scores": [],
        "job_matches": [],
        "interviews": []
    }

    if db is None:
        # DB offline fallback from mock in-memory stores if any
        return _fetch_mock_career_data(uid)

    try:
        # 1. Career Goals (active)
        goal_docs = db.collection("career_goals").where("user_id", "==", uid).where("status", "==", "active").stream()
        goals = [d.to_dict() for d in goal_docs]
        if goals:
            goals.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
            context_data["career_goal"] = goals[0]

        # 2. Candidate Profile
        prof_doc = db.collection("profiles").document(uid).get()
        if prof_doc.exists:
            context_data["profile"] = prof_doc.to_dict()

        # 3. Resumes
        res_docs = db.collection("resumes").where("user_id", "==", uid).stream()
        for doc in res_docs:
            d = doc.to_dict()
            context_data["resumes"].append({
                "id": d.get("id", doc.id),
                "filename": d.get("filename", "Resume.pdf"),
                "uploaded_at": d.get("uploaded_at", ""),
                "extracted_text": (d.get("extracted_text") or d.get("text") or "")[:2500]  # Cap for context efficiency
            })

        # Sort resumes by upload date
        context_data["resumes"].sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)

        # 4. Resume Analyses
        ana_docs = db.collection("resume_analyses").where("user_id", "==", uid).stream()
        for doc in ana_docs:
            d = doc.to_dict()
            res_json = d.get("analysis_results") or {}
            skills_block = res_json.get("skills") if isinstance(res_json.get("skills"), dict) else {}
            context_data["analyses"].append({
                "id": d.get("id", doc.id),
                "summary": res_json.get("resume_summary") or res_json.get("professional_summary", {}).get("quality") or "",
                "technical_skills": res_json.get("technical_skills_found") or skills_block.get("technical_skills_found") or [],
                "missing_skills": res_json.get("missing_skills") or skills_block.get("missing_skills") or [],
                "strengths": res_json.get("strengths") or [],
                "weaknesses": res_json.get("weaknesses") or [],
                "recommendations": res_json.get("actionable_recommendations") or [],
                "created_at": d.get("created_at", "")
            })

        # 5. ATS Scores
        ats_docs = db.collection("resume_ats_scores").where("user_id", "==", uid).stream()
        for doc in ats_docs:
            d = doc.to_dict()
            res_json = d.get("ats_results") or {}
            kw_analysis = res_json.get("keyword_analysis") or {}
            context_data["ats_scores"].append({
                "id": d.get("id", doc.id),
                "ats_score": d.get("overall_score") or d.get("ats_score") or 0,
                "found_keywords": kw_analysis.get("found_keywords") or [],
                "missing_keywords": kw_analysis.get("missing_keywords") or [],
                "warnings": res_json.get("ats_warnings") or [],
                "recommendations": res_json.get("overall_recommendations") or [],
                "created_at": d.get("created_at", "")
            })

        # 6. Job Matches
        jm_docs = db.collection("job_matches").where("user_id", "==", uid).stream()
        for doc in jm_docs:
            d = doc.to_dict()
            context_data["job_matches"].append({
                "id": d.get("id", doc.id),
                "job_title": d.get("job_title") or "Target Job",
                "job_description": (d.get("job_description") or "")[:1500],
                "match_score": d.get("match_score") or d.get("match_percentage") or 0,
                "match_level": d.get("match_level") or "Moderate Match",
                "matching_skills": d.get("matching_skills") or [],
                "missing_skills": d.get("missing_skills") or [],
                "skill_gaps": d.get("skill_gaps") or [],
                "candidate_strengths": d.get("candidate_strengths") or [],
                "candidate_weaknesses": d.get("candidate_weaknesses") or [],
                "recommendations": d.get("recommendations") or [],
                "summary": d.get("summary") or "",
                "created_at": d.get("created_at", "")
            })

        # 7. Interview Preparation Sessions
        int_docs = db.collection("interview_sessions").where("user_id", "==", uid).stream()
        for doc in int_docs:
            d = doc.to_dict()
            context_data["interviews"].append({
                "id": d.get("id", doc.id),
                "job_title": d.get("job_title") or "Position",
                "interview_type": d.get("interview_type") or "Mixed",
                "difficulty": d.get("difficulty") or "Intermediate",
                "questions": [q.get("question") for q in (d.get("questions") or []) if isinstance(q, dict)],
                "preparation_tips": d.get("overall_preparation_tips") or [],
                "potential_weaknesses": d.get("potential_weaknesses") or [],
                "overall_score": d.get("overall_score"),
                "evaluations": [a.get("evaluation") for a in (d.get("answers") or []) if isinstance(a, dict) and a.get("evaluation")],
                "created_at": d.get("created_at", "")
            })

    except Exception as err:
        logger.error(f"Error fetching user career data from Firestore for RAG: {err}")

    return context_data


def _fetch_mock_career_data(uid):
    """Fallback fetcher for mock DB environment."""
    try:
        from backend.career_goal_routes import MOCK_CAREER_GOALS_DB
        from backend.profile_routes import MOCK_PROFILES_DB
        from backend.resume_routes import MOCK_RESUMES_DB
        from backend.jobmatch_routes import MOCK_JOBMATCH_DB
        from backend.interview_routes import MOCK_INTERVIEW_DB
    except ImportError:
        from career_goal_routes import MOCK_CAREER_GOALS_DB
        from profile_routes import MOCK_PROFILES_DB
        from resume_routes import MOCK_RESUMES_DB
        from jobmatch_routes import MOCK_JOBMATCH_DB
        from interview_routes import MOCK_INTERVIEW_DB

    context_data = {
        "career_goal": next((g for g in MOCK_CAREER_GOALS_DB.values() if g.get("user_id") == uid and g.get("status") == "active"), None),
        "profile": MOCK_PROFILES_DB.get(uid),
        "resumes": [],
        "analyses": [],
        "ats_scores": [],
        "job_matches": [],
        "interviews": []
    }

    for r in MOCK_RESUMES_DB.values():
        if r.get("user_id") == uid:
            context_data["resumes"].append({
                "id": r["id"],
                "filename": r.get("filename", "Resume.pdf"),
                "uploaded_at": r.get("uploaded_at", ""),
                "extracted_text": (r.get("extracted_text") or r.get("text") or "")[:2500]
            })

    for m in MOCK_JOBMATCH_DB.values():
        if m.get("user_id") == uid:
            context_data["job_matches"].append({
                "id": m["id"],
                "job_title": m.get("job_title", "Job Match"),
                "job_description": (m.get("job_description") or "")[:1500],
                "match_score": m.get("match_score") or m.get("match_percentage") or 0,
                "match_level": m.get("match_level", "Moderate Match"),
                "matching_skills": m.get("matching_skills", []),
                "missing_skills": m.get("missing_skills", []),
                "skill_gaps": m.get("skill_gaps", []),
                "candidate_strengths": m.get("candidate_strengths", []),
                "candidate_weaknesses": m.get("candidate_weaknesses", []),
                "recommendations": m.get("recommendations", []),
                "summary": m.get("summary", ""),
                "created_at": m.get("created_at", "")
            })

    for i in MOCK_INTERVIEW_DB.values():
        if i.get("user_id") == uid:
            context_data["interviews"].append({
                "id": i["id"],
                "job_title": i.get("job_title", "Interview"),
                "interview_type": i.get("interview_type", "Mixed"),
                "difficulty": i.get("difficulty", "Intermediate"),
                "questions": [q.get("question") for q in (i.get("questions") or []) if isinstance(q, dict)],
                "preparation_tips": i.get("overall_preparation_tips", []),
                "potential_weaknesses": i.get("potential_weaknesses", []),
                "overall_score": i.get("overall_score"),
                "evaluations": [a.get("evaluation") for a in (i.get("answers") or []) if isinstance(a, dict) and a.get("evaluation")],
                "created_at": i.get("created_at", "")
            })

    return context_data

