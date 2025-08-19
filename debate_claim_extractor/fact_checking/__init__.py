"""
Fact-checking module for claim verification
"""

from .fact_models import (
    VerificationStatus,
    SourceType,
    VerificationSource,
    FactCheckResult,
    AggregatedVerification,
    FactCheckConfig,
    calculate_weighted_score,
    status_from_score,
    get_source_credibility
)
from .fact_pipeline import FactVerificationPipeline
from .services import (
    FactCheckService,
    GoogleFactCheckService,
    LocalFactCheckService
)

__all__ = [
    "VerificationStatus",
    "SourceType", 
    "VerificationSource",
    "FactCheckResult",
    "AggregatedVerification",
    "FactCheckConfig",
    "FactVerificationPipeline",
    "FactCheckService",
    "GoogleFactCheckService",
    "LocalFactCheckService",
    "calculate_weighted_score",
    "status_from_score",
    "get_source_credibility"
]
