"""
Fact-checking models for claim verification results and metadata
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class VerificationStatus(str, Enum):
    """Status of fact-checking verification"""
    VERIFIED_TRUE = "verified_true"
    LIKELY_TRUE = "likely_true" 
    MIXED = "mixed"
    LIKELY_FALSE = "likely_false"
    VERIFIED_FALSE = "verified_false"
    UNVERIFIED = "unverified"
    ERROR = "error"


class SourceType(str, Enum):
    """Type of fact-checking source"""
    PROFESSIONAL_FACT_CHECKER = "professional"  # PolitiFact, FactCheck.org
    ACADEMIC = "academic"  # ClaimBuster, research papers
    NEWS_ORGANIZATION = "news"  # Reuters, AP News
    GOVERNMENT = "government"  # Official statistics, reports
    LOCAL_DATABASE = "local"  # Our curated database


class VerificationSource(BaseModel):
    """Information about a fact-checking source"""
    name: str = Field(description="Name of the fact-checking organization")
    url: Optional[str] = Field(None, description="URL to the fact-check article")
    source_type: SourceType = Field(description="Type of fact-checking source")
    credibility_score: float = Field(
        ge=0.0, le=1.0, 
        description="Credibility score of this source (0.0-1.0)"
    )
    date_published: Optional[datetime] = Field(None, description="When the fact-check was published")
    author: Optional[str] = Field(None, description="Author of the fact-check")
    
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Custom serialization to handle datetime"""
        # Set exclude_none to handle Optional fields better
        kwargs.setdefault('exclude_none', False)
        data = super().model_dump(**kwargs)
        if self.date_published:
            data['date_published'] = self.date_published.isoformat()
        elif 'date_published' in data:
            data['date_published'] = None
        return data


class FactCheckResult(BaseModel):
    """Result from a single fact-checking service"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_id: Optional[str] = Field(None, description="ID of the claim being verified")
    service_name: str = Field(description="Name of the fact-checking service")
    query: str = Field(description="Query text sent to the service")
    claim_text: str = Field(description="Original claim text being verified")
    
    # Verification results
    status: VerificationStatus = Field(description="Verification status")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in this verification result (0.0-1.0)"
    )
    verification_score: float = Field(
        ge=0.0, le=1.0,
        description="Numeric verification score (0.0=false, 1.0=true)"
    )
    
    # Evidence and sources
    sources: List[VerificationSource] = Field(default_factory=list)
    explanation: Optional[str] = Field(None, description="Explanation of the verification")
    related_claims: List[str] = Field(
        default_factory=list, 
        description="Related claims found during verification"
    )
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    processing_time_ms: Optional[int] = Field(None, description="Time taken to process")
    api_response_raw: Optional[Dict[str, Any]] = Field(
        None, 
        description="Raw API response for debugging"
    )
    
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Custom serialization to handle datetime"""
        data = super().model_dump(**kwargs)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AggregatedVerification(BaseModel):
    """Aggregated verification result from multiple sources"""
    claim_id: str = Field(description="ID of the claim being verified")
    claim_text: str = Field(description="Original claim text")
    
    # Aggregated results
    overall_status: VerificationStatus = Field(description="Overall verification status")
    overall_score: float = Field(
        ge=0.0, le=1.0,
        description="Aggregated verification score (0.0=false, 1.0=true)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the aggregated result"
    )
    
    # Individual results
    fact_check_results: List[FactCheckResult] = Field(default_factory=list)
    sources_count: int = Field(default=0, description="Number of sources consulted")
    services_used: List[str] = Field(default_factory=list)
    
    # Summary
    summary: Optional[str] = Field(None, description="Summary of verification findings")
    primary_sources: List[VerificationSource] = Field(
        default_factory=list,
        description="Most credible sources for this verification"
    )
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    processing_time_ms: Optional[int] = Field(None)
    
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Custom serialization to handle datetime"""
        data = super().model_dump(**kwargs)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class FactCheckConfig(BaseModel):
    """Configuration for fact-checking services"""
    enabled: bool = True
    timeout_seconds: int = 10
    max_results_per_service: int = 5
    min_confidence_threshold: float = 0.3
    
    # Service-specific configs
    google_fact_check: Dict[str, Any] = Field(default_factory=dict)
    claimbuster: Dict[str, Any] = Field(default_factory=dict)
    local_database: Dict[str, Any] = Field(default_factory=dict)
    
    # Caching
    caching_enabled: bool = True
    cache_ttl_hours: int = 24
    max_cache_entries: int = 1000


# Utility functions for scoring
def calculate_weighted_score(results: List[FactCheckResult]) -> float:
    """
    Calculate weighted verification score from multiple results
    
    Args:
        results: List of fact-check results
        
    Returns:
        Weighted average score (0.0-1.0)
    """
    if not results:
        return 0.5  # Neutral score if no results
    
    # Filter out zero-confidence results to avoid skewing
    meaningful_results = [r for r in results if r.confidence > 0.01]
    
    if not meaningful_results:
        # If all results have zero confidence, take the best verification score
        return max(r.verification_score for r in results)
    
    total_weight = 0.0
    weighted_sum = 0.0
    
    for result in meaningful_results:
        # Weight by confidence and source credibility
        weight = result.confidence
        if result.sources:
            avg_credibility = sum(s.credibility_score for s in result.sources) / len(result.sources)
            weight *= avg_credibility
        else:
            # If no sources, use a base credibility
            weight *= 0.5
        
        # Give a minimum weight to prevent complete exclusion
        weight = max(weight, 0.1)
        
        weighted_sum += result.verification_score * weight
        total_weight += weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0.5


def status_from_score(score: float) -> VerificationStatus:
    """Convert numeric score to verification status"""
    if score >= 0.75:
        return VerificationStatus.VERIFIED_TRUE
    elif score >= 0.45:  # Lowered threshold for LIKELY_TRUE
        return VerificationStatus.LIKELY_TRUE
    elif score >= 0.25:  # Adjusted MIXED threshold
        return VerificationStatus.MIXED
    elif score >= 0.1:
        return VerificationStatus.LIKELY_FALSE
    else:
        return VerificationStatus.VERIFIED_FALSE


# Source credibility mapping
SOURCE_CREDIBILITY_SCORES = {
    # Professional fact-checkers
    "politifact.com": 0.9,
    "factcheck.org": 0.9,
    "snopes.com": 0.85,
    "factchecker.poynter.org": 0.9,
    "washingtonpost.com/news/fact-checker": 0.85,
    
    # News organizations
    "reuters.com": 0.8,
    "ap.org": 0.8,
    "bbc.com": 0.75,
    "npr.org": 0.75,
    
    # Academic/Research
    "claimbuster": 0.7,  # Academic but automated
    "academic_paper": 0.9,
    
    # Government sources
    "census.gov": 0.85,
    "bls.gov": 0.85,
    "cdc.gov": 0.85,
    
    # Default fallbacks
    "unknown": 0.5,
    "local_database": 0.6
}


def get_source_credibility(source_name: str) -> float:
    """Get credibility score for a source by name or domain"""
    source_name = source_name.lower()
    
    # Check exact matches first
    if source_name in SOURCE_CREDIBILITY_SCORES:
        return SOURCE_CREDIBILITY_SCORES[source_name]
    
    # Check domain matches
    for domain, score in SOURCE_CREDIBILITY_SCORES.items():
        if domain in source_name:
            return score
    
    # Default unknown source credibility
    return SOURCE_CREDIBILITY_SCORES["unknown"]
