"""
CareerPilot AI — Job Opportunities Module Package
"""
from job_opportunities.routes import jobs_bp
from job_opportunities.service import JobOpportunityService
from job_opportunities.provider import BaseJobProvider, ExternalJobProvider

__all__ = ["jobs_bp", "JobOpportunityService", "BaseJobProvider", "ExternalJobProvider"]
