"""
Data models for claim extraction pipeline
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    """Types of claims that can be detected"""
    FACTUAL = "factual"
    STATISTICAL = "statistical"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    HISTORICAL = "historical"


class Sentence(BaseModel):
    """A sentence from the debate transcript with metadata"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    speaker: str
    turn_id: int
    sentence_index: int  # Position within the turn
    char_start: int
    char_end: int
    line_number: Optional[int] = None


class Claim(BaseModel):
    """A factual claim extracted from a debate sentence"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: ClaimType
    text: str
    speaker: str
    sentence_id: str
    turn_id: int
    char_start: int
    char_end: int
    context: Optional[str] = None  # Surrounding sentences for context
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    timestamp: Optional[str] = None
    
    # Fallacy detection integration (optional)
    fallacies: Optional[List[Dict[str, Any]]] = Field(default=None, description="Detected logical fallacies in this claim")
    fallacy_score: Optional[float] = Field(default=None, description="Overall fallacy confidence score")


class ExtractionResult(BaseModel):
    """Complete result from the claim extraction pipeline"""
    claims: List[Claim]
    meta: dict = Field(default_factory=dict)
    
    # Fact-checking data (optional)
    fact_checking_enabled: bool = Field(default=False, description="Whether fact-checking was performed")
    fact_check_results: Optional[List[Dict[str, Any]]] = Field(default=None, description="Aggregated fact-check results")
    
    # Fallacy detection data (optional)
    fallacy_detection_enabled: bool = Field(default=False, description="Whether fallacy detection was performed")
    fallacies: Optional[List[Dict[str, Any]]] = Field(default=None, description="Detected logical fallacies")
    fallacy_summary: Optional[Dict[str, Any]] = Field(default=None, description="Fallacy detection summary statistics")
    
    # Scoring data (optional)
    scoring_enabled: bool = Field(default=False, description="Whether scoring was performed")
    scoring_result: Optional[Dict[str, Any]] = Field(default=None, description="Multi-dimensional scoring results")
    
    def model_post_init(self, __context) -> None:
        """Add metadata after initialization"""
        if not self.meta:
            self.meta = {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "claims_count": len(self.claims),
                "speakers": list(set(claim.speaker for claim in self.claims)),
                "claim_types": {
                    claim_type.value: len([c for c in self.claims if c.type == claim_type])
                    for claim_type in ClaimType
                }
            }
