"""
CareerPilot AI — Adzuna Job Discovery & Ingestion Service
Integrates with the Adzuna Jobs API strictly via backend environment variables.
"""
import os
import re
import logging
import urllib.parse
import requests
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()
backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(backend_env):
    load_dotenv(backend_env)

logger = logging.getLogger(__name__)

class AdzunaService:
    """
    Service client for querying the official Adzuna Job Search API.
    Credentials and country are loaded exclusively from backend environment variables:
      - ADZUNA_APP_ID
      - ADZUNA_APP_KEY
      - ADZUNA_COUNTRY (defaults to 'in' if not specified)
    """

    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def __init__(self, app_id: str = None, app_key: str = None, country: str = None):
        self.app_id = (app_id if app_id is not None else os.getenv("ADZUNA_APP_ID", "")).strip()
        self.app_key = (app_key if app_key is not None else os.getenv("ADZUNA_APP_KEY", "")).strip()
        self.country = (country if country is not None else os.getenv("ADZUNA_COUNTRY", "in")).strip().lower() or "in"

    def is_configured(self) -> bool:
        """
        Validates if valid Adzuna API credentials are provided.
        """
        if not self.app_id or not self.app_key:
            return False
        if self.app_id.startswith("your_") or self.app_key.startswith("your_"):
            return False
        return True

    def _clean_text(self, text: str) -> str:
        """Helper to remove HTML markup and normalize whitespace."""
        if not text:
            return ""
        clean = re.sub(r'<[^>]+>', ' ', text)
        return ' '.join(clean.split()).strip()

    def search_jobs(self, query: str, location: str = None, page: int = 1, results_per_page: int = 20) -> list:
        """
        Queries Adzuna API for job postings using supported query parameters.
        Returns a list of raw job dictionaries.
        """
        if not self.is_configured():
            logger.warning("AdzunaService: API credentials not configured.")
            return []

        if not query:
            return []

        endpoint = f"{self.BASE_URL}/{self.country}/search/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": query.strip(),
            "results_per_page": min(max(1, results_per_page), 50),
            "content-type": "application/json"
        }

        if location and location.strip() and location.lower() != "remote":
            params["where"] = location.strip()

        try:
            logger.info(f"AdzunaService: Querying Adzuna ({self.country}) for '{query}' (loc: {location or 'Any'})...")
            response = requests.get(endpoint, params=params, timeout=12)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                logger.info(f"AdzunaService: Retrieved {len(results)} raw jobs.")
                return results
            elif response.status_code in (401, 403):
                logger.error(f"AdzunaService: Authentication error ({response.status_code}). Check ADZUNA_APP_ID and ADZUNA_APP_KEY.")
                return []
            else:
                logger.warning(f"AdzunaService: API returned status {response.status_code}: {response.text[:200]}")
                return []
        except requests.exceptions.Timeout:
            logger.warning("AdzunaService: Request timed out.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"AdzunaService: Network request error: {e}")
            return []
        except Exception as e:
            logger.error(f"AdzunaService: Unexpected error during search: {e}", exc_info=True)
            return []

    def normalize_adzuna_job(self, item: dict, dream_company: str = None) -> dict:
        """
        Transforms an Adzuna API job item into CareerPilot's standard normalized job structure.
        """
        if not isinstance(item, dict):
            return {}

        raw_id = str(item.get("id") or "").strip()
        job_id = f"adzuna_{raw_id}" if raw_id else f"adzuna_{abs(hash(item.get('redirect_url', '')))}"

        company_dict = item.get("company") if isinstance(item.get("company"), dict) else {}
        company_name = self._clean_text(company_dict.get("display_name") or "Direct Employer")

        location_dict = item.get("location") if isinstance(item.get("location"), dict) else {}
        location_name = self._clean_text(location_dict.get("display_name") or "Flexible / Remote")

        title = self._clean_text(item.get("title") or "Job Opportunity")
        description = self._clean_text(item.get("description") or "")
        posted_date = str(item.get("created") or "").strip()

        category_dict = item.get("category") if isinstance(item.get("category"), dict) else {}
        category = self._clean_text(category_dict.get("label") or "")

        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        contract_type = str(item.get("contract_type") or item.get("contract_time") or "").strip()

        # Check dream company match
        d_comp_norm = (dream_company or "").lower().strip()
        is_dream = bool(d_comp_norm and d_comp_norm in company_name.lower())

        app_url = str(item.get("redirect_url") or "").strip()

        # Extract skills/keywords from description if available
        skills = []
        common_tech = ["Python", "Java", "C++", "JavaScript", "TypeScript", "React", "Node.js", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "SQL", "Git", "Linux", "Terraform", "CI/CD", "REST API", "DevOps", "AI", "Machine Learning"]
        desc_lower = description.lower()
        for tech in common_tech:
            if re.search(r'\b' + re.escape(tech.lower()) + r'\b', desc_lower):
                skills.append(tech)

        return {
            "job_id": job_id,
            "id": job_id,
            "external_id": raw_id,
            "title": title,
            "company": company_name,
            "location": location_name,
            "description": description,
            "posted_date": posted_date,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "contract_type": contract_type or "Full-time",
            "employment_type": contract_type or "Full-time",
            "category": category,
            "skills": skills[:6],
            "source": "Adzuna",
            "application_url": app_url,
            "job_url": app_url,
            "is_dream_company": is_dream,
            "status": "active"
        }

    def fetch_relevant_jobs(self, target_role: str, dream_company: str = None, location: str = None) -> list:
        """
        Coordinates target-role discovery and dream-company prioritization.
        1. Performs primary query for the target job role.
        2. If dream company is provided, performs secondary targeted query.
        3. Normalizes and deduplicates results.
        4. Filters for role relevance (excluding unrelated roles).
        5. Sorts with dream company matches first, followed by recency.
        """
        if not target_role or not target_role.strip():
            logger.info("AdzunaService: No target role provided. Returning empty list.")
            return []

        target_role = target_role.strip()
        dream_company = (dream_company or "").strip()
        location = (location or "").strip()

        raw_jobs = []

        # 1. Secondary search: Dream company specific query (if dream company specified)
        if dream_company:
            dream_raw = self.search_jobs(
                query=f"{dream_company} {target_role}",
                location=location,
                results_per_page=20
            )
            raw_jobs.extend(dream_raw)

        # 2. Primary search: Target job role general query
        general_raw = self.search_jobs(
            query=target_role,
            location=location,
            results_per_page=30
        )
        raw_jobs.extend(general_raw)

        # Import role relevance filtering utility
        try:
            from job_opportunities.filters import is_role_relevant
        except ImportError:
            try:
                from backend.job_opportunities.filters import is_role_relevant
            except ImportError:
                def is_role_relevant(title, role):
                    return True

        normalized_jobs = []
        seen_keys = set()

        for item in raw_jobs:
            if not isinstance(item, dict):
                continue
            
            norm = self.normalize_adzuna_job(item, dream_company=dream_company)
            if not norm or not norm.get("title"):
                continue

            # Deduplication key: ID or application URL or title+company
            dedup_key = norm.get("job_id") or norm.get("application_url") or f"{norm.get('title')}_{norm.get('company')}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            # Filter for relevance to target role
            if not is_role_relevant(norm.get("title", ""), target_role):
                continue

            normalized_jobs.append(norm)

        # Sort: Dream company jobs first, then by posted date descending
        normalized_jobs.sort(
            key=lambda x: (1 if x.get("is_dream_company") else 0, x.get("posted_date") or ""),
            reverse=True
        )

        logger.info(f"AdzunaService: Found {len(normalized_jobs)} relevant jobs for '{target_role}' (Dream: {sum(1 for j in normalized_jobs if j.get('is_dream_company'))}).")
        return normalized_jobs
