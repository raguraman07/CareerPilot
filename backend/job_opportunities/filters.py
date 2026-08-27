"""
CareerPilot AI — Target-Role & Dream-Company Filtering and Prioritization Engine
"""
import re

def is_role_relevant(job_title: str, target_role: str) -> bool:
    """
    Checks if a job title is relevant to the target role.
    Accepts closely related titles and seniority variations while rejecting unrelated roles.
    Example:
      Target Role: 'Cloud Engineer'
      Accepts: 'Cloud Engineer', 'Cloud Infrastructure Engineer', 'Junior Cloud Engineer', 'Cloud Support Engineer'
      Rejects: 'HR Manager', 'Graphic Designer', 'Accountant', 'Sales Representative'
    """
    if not job_title or not target_role:
        return False

    t_norm = target_role.lower().strip()
    j_norm = job_title.lower().strip()

    # Exact or substring match
    if t_norm in j_norm or j_norm in t_norm:
        return True

    # Tokenize core keywords (ignoring generic seniority prefixes)
    stop_words = {"junior", "senior", "lead", "staff", "associate", "principal", "intern", "trainee", "entry", "level", "ii", "iii", "i", "sr", "jr"}
    t_tokens = [w for w in re.findall(r'\w+', t_norm) if w not in stop_words and len(w) > 2]
    j_tokens = set(re.findall(r'\w+', j_norm))

    if not t_tokens:
        return True

    # Check if key core tokens are present
    match_count = sum(1 for tok in t_tokens if tok in j_tokens)
    return (match_count / len(t_tokens)) >= 0.5


def filter_and_prioritize_jobs(jobs: list, target_role: str, dream_company: str = None, client_filters: dict = None) -> dict:
    """
    Filters jobs by target role, prioritizes the dream company, and applies optional client-side filters.
    Returns:
    {
      "target_role": "...",
      "dream_company": "...",
      "dream_company_jobs": [...],
      "other_company_jobs": [...],
      "total_count": int,
      "dream_company_count": int,
      "other_company_count": int
    }
    """
    if not isinstance(jobs, list):
        jobs = []

    client_filters = client_filters or {}
    company_filter = str(client_filters.get("company_filter") or "ALL").upper()
    location_filter = str(client_filters.get("location") or "").lower().strip()
    exp_filter = str(client_filters.get("experience") or "").lower().strip()
    search_query = str(client_filters.get("search") or "").lower().strip()

    d_comp_norm = (dream_company or "").lower().strip()

    dream_company_jobs = []
    other_company_jobs = []

    for j in jobs:
        if not isinstance(j, dict):
            continue

        title = j.get("title", "")
        company = j.get("company", "")
        location = j.get("location", "")
        exp = j.get("experience", "")
        desc = j.get("description", "")

        # 1. Target Role Primary Filter
        if not is_role_relevant(title, target_role):
            continue

        # 2. Search Query Filter (if active)
        if search_query:
            combined_text = f"{title} {company} {location} {desc}".lower()
            if search_query not in combined_text:
                continue

        # 3. Location Filter (if active)
        if location_filter and location_filter != "all":
            if location_filter == "remote" and "remote" not in location.lower():
                continue
            elif location_filter != "remote" and location_filter not in location.lower():
                continue

        # 4. Experience Filter (if active)
        if exp_filter and exp_filter != "all":
            if exp_filter not in exp.lower():
                continue

        # 5. Dream Company vs Other Company Partitioning
        is_dream = bool(d_comp_norm and d_comp_norm in company.lower())

        if company_filter == "DREAM" and not is_dream:
            continue
        if company_filter == "OTHERS" and is_dream:
            continue

        if is_dream:
            dream_company_jobs.append(j)
        else:
            other_company_jobs.append(j)

    return {
        "target_role": target_role,
        "dream_company": dream_company,
        "dream_company_jobs": dream_company_jobs,
        "other_company_jobs": other_company_jobs,
        "total_count": len(dream_company_jobs) + len(other_company_jobs),
        "dream_company_count": len(dream_company_jobs),
        "other_company_count": len(other_company_jobs)
    }
