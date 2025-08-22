"""
Data models for multi-dimensional debate scoring system.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


class ScoreType(str, Enum):
    """Types of scores that can be calculated."""
    DEBATE_QUALITY = "debate_quality"
    SPEAKER_CREDIBILITY = "speaker_credibility"  
    ARGUMENT_STRENGTH = "argument_strength"
    OVERALL_DEBATE = "overall_debate"


class ScoringConfig(BaseModel):
    """Configuration for scoring system."""
    
    # Enable/disable different scoring types
    debate_quality_enabled: bool = True
    speaker_credibility_enabled: bool = True
    argument_strength_enabled: bool = True
    overall_debate_enabled: bool = True
    
    # Scoring weights and parameters
    claim_confidence_weight: float = 0.3
    fact_check_weight: float = 0.4
    fallacy_penalty_weight: float = 0.3
    
    # Thresholds
    high_confidence_threshold: float = 0.7
    medium_confidence_threshold: float = 0.5
    severe_fallacy_threshold: float = 0.8
    
    # Penalties
    fallacy_penalty_multiplier: float = 0.2
    unverified_claim_penalty: float = 0.1
    false_claim_penalty: float = 0.3


@dataclass
class SpeakerScore:
    """Score for an individual speaker's performance."""
    
    speaker: str
    credibility_score: float = 0.0
    
    # Component scores
    claim_accuracy: float = 0.0  # Based on fact-checking results
    claim_confidence: float = 0.0  # Average confidence of claims
    fallacy_penalty: float = 0.0  # Penalty for logical fallacies
    evidence_quality: float = 0.0  # Quality of supporting evidence
    
    # Statistics
    total_claims: int = 0
    verified_claims: int = 0
    false_claims: int = 0
    fallacies_committed: int = 0
    high_confidence_claims: int = 0
    
    # Detailed breakdowns
    claim_type_distribution: Dict[str, int] = field(default_factory=dict)
    fallacy_type_distribution: Dict[str, int] = field(default_factory=dict)
    verification_status_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass  
class ArgumentScore:
    """Score for argument quality and strength."""
    
    argument_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strength_score: float = 0.0
    
    # Component scores
    evidence_score: float = 0.0  # Quality of supporting evidence
    logic_score: float = 0.0  # Logical consistency (inverse of fallacies)
    relevance_score: float = 0.0  # Relevance to debate topic
    clarity_score: float = 0.0  # Clarity of presentation
    
    # Supporting data
    claims_count: int = 0
    verified_claims_count: int = 0
    fallacies_count: int = 0
    avg_claim_confidence: float = 0.0
    
    # Associated claims and fallacies
    claim_ids: List[str] = field(default_factory=list)
    fallacy_ids: List[str] = field(default_factory=list)


@dataclass
class DebateScore:
    """Overall debate quality and analysis scores."""
    
    debate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    overall_score: float = 0.0
    
    # Component scores
    information_quality: float = 0.0  # Quality of information presented
    logical_consistency: float = 0.0  # Absence of logical fallacies
    factual_accuracy: float = 0.0  # Fact-checking accuracy
    engagement_quality: float = 0.0  # Quality of debate engagement
    
    # Aggregate statistics
    total_claims: int = 0
    verified_claims: int = 0
    false_claims: int = 0
    mixed_claims: int = 0
    total_fallacies: int = 0
    
    # Speaker performance
    speaker_scores: Dict[str, SpeakerScore] = field(default_factory=dict)
    
    # Argument analysis
    argument_scores: List[ArgumentScore] = field(default_factory=list)
    
    # Score distributions
    confidence_distribution: Dict[str, int] = field(default_factory=dict)
    claim_type_distribution: Dict[str, int] = field(default_factory=dict)
    fallacy_severity_distribution: Dict[str, int] = field(default_factory=dict)


class ScoringResult(BaseModel):
    """Complete scoring result with all metrics and metadata."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Main scores
    debate_score: Optional[DebateScore] = None
    
    # Configuration used
    config: ScoringConfig = Field(default_factory=ScoringConfig)
    
    # Source information
    source: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    
    # Analysis metadata
    scoring_performed: bool = False
    scoring_error: Optional[str] = None
    
    # Summary metrics (for quick access)
    summary: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to handle datetime serialization."""
        data = super().model_dump(**kwargs)
        
        # Ensure datetime is serialized properly
        if 'generated_at' in data and isinstance(data['generated_at'], datetime):
            data['generated_at'] = data['generated_at'].isoformat()
            
        return data


# Utility functions for score interpretation
def interpret_score(score: float) -> str:
    """Convert numerical score to human-readable interpretation."""
    if score >= 0.8:
        return "excellent"
    elif score >= 0.6:
        return "good" 
    elif score >= 0.4:
        return "fair"
    elif score >= 0.2:
        return "poor"
    else:
        return "very_poor"


def get_score_color(score: float) -> str:
    """Get color code for score visualization."""
    if score >= 0.8:
        return "green"
    elif score >= 0.6:
        return "yellow-green"
    elif score >= 0.4:
        return "yellow"
    elif score >= 0.2:
        return "orange"
    else:
        return "red"


def calculate_percentile_rank(score: float, all_scores: List[float]) -> float:
    """Calculate percentile rank of a score within a distribution."""
    if not all_scores:
        return 0.0
    
    count_below = sum(1 for s in all_scores if s < score)
    count_equal = sum(1 for s in all_scores if s == score)
    
    percentile = (count_below + 0.5 * count_equal) / len(all_scores) * 100
    return round(percentile, 1)
