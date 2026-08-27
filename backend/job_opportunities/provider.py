"""
CareerPilot AI — Job Provider Interface & Real Adzuna Integration
"""
import os
import logging
from abc import ABC, abstractmethod

try:
    from services.adzuna_service import AdzunaService
except ImportError:
    try:
        from backend.services.adzuna_service import AdzunaService
    except ImportError:
        AdzunaService = None

logger = logging.getLogger(__name__)

class BaseJobProvider(ABC):
    """
    Abstract Job Provider interface.
    Real external job APIs (Adzuna, JSearch, etc.) implement this interface.
    """
    @abstractmethod
    def search_jobs(self, target_role: str, location: str = None, page: int = 1, limit: int = 20) -> list:
        """
        Queries jobs matching the target role and location.
        Returns a list of raw or standardized job dictionaries.
        """
        raise NotImplementedError("Job API provider search_jobs method not implemented.")

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider credentials and endpoint are configured."""
        raise NotImplementedError("Job API provider is_configured method not implemented.")


class ExternalJobProvider(BaseJobProvider):
    """
    Production External Job Provider implementing Adzuna API integration.
    Credentials are read from environment variables:
      - ADZUNA_APP_ID
      - ADZUNA_APP_KEY
      - ADZUNA_COUNTRY
    """
    def __init__(self):
        self.provider_name = "adzuna"
        if AdzunaService:
            self.service = AdzunaService()
        else:
            self.service = None

    def is_configured(self) -> bool:
        """Checks if Adzuna service has valid environment credentials configured."""
        if not self.service:
            return False
        return self.service.is_configured()

    def search_jobs(self, target_role: str, location: str = None, page: int = 1, limit: int = 20) -> list:
        """
        Queries real job postings from Adzuna API.
        """
        if not self.is_configured():
            logger.info("ExternalJobProvider: Adzuna API credentials have not been configured yet.")
            raise NotImplementedError("Adzuna API provider has not been configured yet.")

        return self.service.search_jobs(query=target_role, location=location, page=page, results_per_page=limit)

    def fetch_relevant_jobs(self, target_role: str, dream_company: str = None, location: str = None) -> list:
        """
        Orchestrates target-role and dream-company prioritized discovery from Adzuna.
        """
        if not self.is_configured():
            raise NotImplementedError("Adzuna API provider is not configured.")
        return self.service.fetch_relevant_jobs(target_role=target_role, dream_company=dream_company, location=location)
