"""
CareerPilot AI — Job Provider Interface and Base Abstraction
"""
import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseJobProvider(ABC):
    """
    Abstract Job Provider interface.
    Real external job APIs (Adzuna, JSearch, Jooble, etc.) will implement this interface.
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
    Placeholder External Job Provider implementation.
    Reads configuration from environment variables without hardcoded credentials.
    Does NOT connect to any external API until configured in future phases.
    """
    def __init__(self):
        self.provider_name = os.getenv("JOB_PROVIDER", "").strip()
        self.api_key = os.getenv("JOB_API_KEY", "").strip()
        self.base_url = os.getenv("JOB_API_BASE_URL", "").strip()

    def is_configured(self) -> bool:
        """Checks if a valid provider name and API key are configured."""
        return bool(self.provider_name and self.api_key and not self.api_key.startswith("your_"))

    def search_jobs(self, target_role: str, location: str = None, page: int = 1, limit: int = 20) -> list:
        """
        Executes job search via the configured external provider.
        Raises NotImplementedError if no provider is currently active.
        """
        if not self.is_configured():
            logger.info("ExternalJobProvider: Job API provider has not been configured yet.")
            raise NotImplementedError("Job API provider has not been configured yet.")

        # Future integration point for real Job API calls
        logger.info(f"ExternalJobProvider: Querying {self.provider_name} for role '{target_role}'...")
        # (Real provider implementation will be connected here in future phase)
        return []
