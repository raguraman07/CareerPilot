"""
CareerPilot AI — Job Opportunity & Notification Data Models
"""
import hashlib
import datetime

def normalize_job_dict(raw: dict, provider_name: str = "external") -> dict:
    """
    Transforms raw provider responses into CareerPilot's standard normalized job schema.
    Guarantees no missing keys and stable identifier generation.
    """
    if not isinstance(raw, dict):
        raw = {}

    company = str(raw.get("company") or raw.get("company_name") or "Unknown Company").strip()
    title = str(raw.get("title") or raw.get("job_title") or "Job Title").strip()
    location = str(raw.get("location") or raw.get("job_location") or "Flexible / Remote").strip()
    ext_id = str(raw.get("external_id") or raw.get("id") or "").strip()

    # Generate stable fallback hash if external ID is not provided
    if not ext_id:
        hash_input = f"{provider_name}:{company.lower()}:{title.lower()}:{location.lower()}"
        ext_id = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    job_id = f"{provider_name}_{ext_id}"

    # Responsibilities and Qualifications parsing
    resps = raw.get("responsibilities") or []
    if isinstance(resps, str):
        resps = [r.strip() for r in resps.split("\n") if r.strip()]
    elif not isinstance(resps, list):
        resps = []

    quals = raw.get("qualifications") or []
    if isinstance(quals, str):
        quals = [q.strip() for q in quals.split("\n") if q.strip()]
    elif not isinstance(quals, list):
        quals = []

    skills = raw.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    elif not isinstance(skills, list):
        skills = []

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "id": job_id,
        "external_id": ext_id,
        "source": provider_name,
        "company": company,
        "title": title,
        "normalized_role": str(raw.get("normalized_role") or title).strip(),
        "location": location,
        "employment_type": str(raw.get("employment_type") or "Full-time").strip(),
        "experience": str(raw.get("experience") or raw.get("experience_level") or "Entry Level").strip(),
        "description": str(raw.get("description") or "").strip(),
        "responsibilities": resps,
        "qualifications": quals,
        "skills": skills,
        "posted_date": str(raw.get("posted_date") or now_iso[:10]).strip(),
        "deadline": str(raw.get("deadline") or "").strip(),
        "job_url": str(raw.get("job_url") or "").strip(),
        "application_url": str(raw.get("application_url") or raw.get("job_url") or "").strip(),
        "status": "active",
        "created_at": str(raw.get("created_at") or now_iso),
        "updated_at": now_iso
    }


def create_job_notification_dict(user_id: str, job: dict) -> dict:
    """
    Creates a user-isolated notification record for a newly detected unique job opportunity.
    """
    notif_id = f"notif_{user_id}_{job.get('id')}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    company = job.get("company", "Company")
    title = job.get("title", "Role")
    location = job.get("location", "Location")

    return {
        "id": notif_id,
        "user_id": user_id,
        "job_id": job.get("id"),
        "title": f"New Opportunity: {title}",
        "message": f"{company} posted a new {title} position in {location}.",
        "company": company,
        "role": title,
        "location": location,
        "employment_type": job.get("employment_type", "Full-time"),
        "job_url": job.get("job_url") or job.get("application_url") or "",
        "read": False,
        "created_at": now_iso
    }
