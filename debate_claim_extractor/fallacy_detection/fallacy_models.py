"""
Data models for logical fallacy detection system.
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import uuid


class FallacyType(Enum):
    """Enumeration of logical fallacy types that can be detected."""
    
    # Core fallacies (Phase 1)
    AD_HOMINEM = "ad_hominem"
    STRAW_MAN = "straw_man" 
    FALSE_DILEMMA = "false_dilemma"
    APPEAL_TO_AUTHORITY = "appeal_to_authority"
    SLIPPERY_SLOPE = "slippery_slope"
    
    # Advanced fallacies (Phase 2)
    RED_HERRING = "red_herring"
    APPEAL_TO_EMOTION = "appeal_to_emotion"
    BANDWAGON = "bandwagon"
    CIRCULAR_REASONING = "circular_reasoning"
    HASTY_GENERALIZATION = "hasty_generalization"
    
    # Additional fallacies
    TU_QUOQUE = "tu_quoque"  # "You too" fallacy
    FALSE_CAUSE = "false_cause"  # Post hoc ergo propter hoc
    APPEAL_TO_IGNORANCE = "appeal_to_ignorance"
    BEGGING_THE_QUESTION = "begging_the_question"
    NO_TRUE_SCOTSMAN = "no_true_scotsman"


class FallacySeverity(Enum):
    """Severity levels for detected fallacies."""
    LOW = "low"        # Minor logical inconsistency
    MEDIUM = "medium"  # Clear fallacy but not egregious
    HIGH = "high"      # Severe logical error or manipulation


@dataclass
class FallacyResult:
    """
    Represents a detected logical fallacy in a debate transcript.
    """
    
    # Identification
    id: str
    type: FallacyType
    text: str
    speaker: Optional[str] = None
    
    # Location and context
    target_claim_id: Optional[str] = None  # Associated claim if any
    sentence_id: Optional[str] = None
    turn_id: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    context: Optional[str] = None
    
    # Detection metadata
    confidence: float = 0.0
    patterns_matched: List[str] = None
    explanation: str = ""
    severity: FallacySeverity = FallacySeverity.MEDIUM
    
    # Timestamps
    timestamp: Optional[datetime] = None
    detected_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize default values after creation."""
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.patterns_matched is None:
            self.patterns_matched = []
        if self.detected_at is None:
            self.detected_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert fallacy result to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "text": self.text,
            "speaker": self.speaker,
            "target_claim_id": self.target_claim_id,
            "sentence_id": self.sentence_id,
            "turn_id": self.turn_id,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "context": self.context,
            "confidence": self.confidence,
            "patterns_matched": self.patterns_matched,
            "explanation": self.explanation,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FallacyResult':
        """Create FallacyResult from dictionary."""
        # Parse datetime fields
        timestamp = None
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        
        detected_at = None
        if data.get('detected_at'):
            detected_at = datetime.fromisoformat(data['detected_at'].replace('Z', '+00:00'))
        
        return cls(
            id=data['id'],
            type=FallacyType(data['type']),
            text=data['text'],
            speaker=data.get('speaker'),
            target_claim_id=data.get('target_claim_id'),
            sentence_id=data.get('sentence_id'),
            turn_id=data.get('turn_id'),
            char_start=data.get('char_start'),
            char_end=data.get('char_end'),
            context=data.get('context'),
            confidence=data.get('confidence', 0.0),
            patterns_matched=data.get('patterns_matched', []),
            explanation=data.get('explanation', ''),
            severity=FallacySeverity(data.get('severity', 'medium')),
            timestamp=timestamp,
            detected_at=detected_at
        )


@dataclass 
class FallacyDetectionSummary:
    """
    Summary statistics for fallacy detection results.
    """
    
    total_fallacies: int = 0
    by_type: Dict[str, int] = None
    by_speaker: Dict[str, int] = None
    by_severity: Dict[str, int] = None
    average_confidence: float = 0.0
    high_confidence_count: int = 0  # Confidence >= 0.8
    medium_confidence_count: int = 0  # 0.5 <= confidence < 0.8
    low_confidence_count: int = 0   # confidence < 0.5
    
    def __post_init__(self):
        """Initialize default values."""
        if self.by_type is None:
            self.by_type = {}
        if self.by_speaker is None:
            self.by_speaker = {}
        if self.by_severity is None:
            self.by_severity = {}
    
    @classmethod
    def from_fallacies(cls, fallacies: List[FallacyResult]) -> 'FallacyDetectionSummary':
        """Create summary from list of fallacy results."""
        if not fallacies:
            return cls()
        
        # Count by type
        by_type = {}
        for fallacy in fallacies:
            fallacy_type = fallacy.type.value
            by_type[fallacy_type] = by_type.get(fallacy_type, 0) + 1
        
        # Count by speaker
        by_speaker = {}
        for fallacy in fallacies:
            if fallacy.speaker:
                by_speaker[fallacy.speaker] = by_speaker.get(fallacy.speaker, 0) + 1
        
        # Count by severity
        by_severity = {}
        for fallacy in fallacies:
            severity = fallacy.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # Calculate confidence statistics
        confidences = [f.confidence for f in fallacies if f.confidence > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        high_conf = len([f for f in fallacies if f.confidence >= 0.8])
        medium_conf = len([f for f in fallacies if 0.5 <= f.confidence < 0.8])
        low_conf = len([f for f in fallacies if f.confidence < 0.5])
        
        return cls(
            total_fallacies=len(fallacies),
            by_type=by_type,
            by_speaker=by_speaker,
            by_severity=by_severity,
            average_confidence=round(avg_confidence, 3),
            high_confidence_count=high_conf,
            medium_confidence_count=medium_conf,
            low_confidence_count=low_conf
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary for JSON serialization."""
        return {
            "total_fallacies": self.total_fallacies,
            "by_type": self.by_type,
            "by_speaker": self.by_speaker, 
            "by_severity": self.by_severity,
            "average_confidence": self.average_confidence,
            "confidence_distribution": {
                "high": self.high_confidence_count,
                "medium": self.medium_confidence_count,
                "low": self.low_confidence_count
            }
        }


# Fallacy explanation templates for user education
FALLACY_EXPLANATIONS = {
    FallacyType.AD_HOMINEM: {
        "name": "Ad Hominem Attack",
        "description": "Attacking the person making the argument rather than addressing the argument itself.",
        "why_problematic": "Personal attacks don't address the validity of the argument and distract from substantive debate.",
        "example": "Instead of addressing the policy proposal, saying 'You're just a corrupt politician.'"
    },
    
    FallacyType.STRAW_MAN: {
        "name": "Straw Man Fallacy", 
        "description": "Misrepresenting or oversimplifying someone's argument to make it easier to attack.",
        "why_problematic": "Distorts the actual position being debated and avoids engaging with the real argument.",
        "example": "Responding to a healthcare reform proposal with 'So you want to destroy all healthcare.'"
    },
    
    FallacyType.FALSE_DILEMMA: {
        "name": "False Dilemma/False Dichotomy",
        "description": "Presenting only two options when more alternatives exist.",
        "why_problematic": "Oversimplifies complex issues and eliminates nuanced solutions.",
        "example": "Saying 'Either you support this bill or you hate America' when many other positions are possible."
    },
    
    FallacyType.APPEAL_TO_AUTHORITY: {
        "name": "Appeal to Authority (Inappropriate)",
        "description": "Using authority figures inappropriately to support arguments or citing vague expertise.",
        "why_problematic": "Authority alone doesn't make a claim true, especially if the authority isn't relevant to the topic.",
        "example": "Saying 'Many experts agree' without citing specific, relevant experts or studies."
    },
    
    FallacyType.SLIPPERY_SLOPE: {
        "name": "Slippery Slope Fallacy",
        "description": "Arguing that one event will inevitably lead to a chain of negative consequences.",
        "why_problematic": "Assumes inevitability without evidence and discourages consideration of measured approaches.",
        "example": "Arguing that any gun control will inevitably lead to complete weapon confiscation."
    },
    
    FallacyType.RED_HERRING: {
        "name": "Red Herring",
        "description": "Introducing irrelevant information to distract from the main issue.",
        "why_problematic": "Derails productive discussion and avoids addressing the actual topic.",
        "example": "When discussing education funding, suddenly shifting to talk about unrelated historical events."
    },
    
    FallacyType.APPEAL_TO_EMOTION: {
        "name": "Appeal to Emotion (Inappropriate)",
        "description": "Using emotional manipulation instead of logical reasoning to support an argument.",
        "why_problematic": "Emotions, while important, shouldn't replace logical analysis of policies and proposals.",
        "example": "Using 'think of the children' without providing logical reasoning for the proposed solution."
    }
}


def get_fallacy_explanation(fallacy_type: FallacyType) -> Dict[str, str]:
    """Get educational explanation for a fallacy type."""
    return FALLACY_EXPLANATIONS.get(fallacy_type, {
        "name": fallacy_type.value.replace('_', ' ').title(),
        "description": "Logical error in reasoning.",
        "why_problematic": "Weakens the strength of arguments and debate quality.",
        "example": "Various forms depending on the specific fallacy type."
    })
