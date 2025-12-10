"""Atomic claim artifact."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .base import Artifact


class ClaimType(str, Enum):
    """
    Claim taxonomy.

    Route only EMPIRICAL to fact-checker by default.
    UNCLASSIFIED goes to review queue.
    """

    EMPIRICAL = "empirical"  # Route to fact-checker
    METHODOLOGICAL = "methodological"  # Route to logic/validity check
    NORMATIVE = "normative"  # Filter (value judgments)
    CONCEPTUAL = "conceptual"  # Filter (definitions)
    INTROSPECTIVE = "introspective"  # Filter (first-person mental states)
    PREDICTIVE = "predictive"  # Route to prediction tracker
    PHILOSOPHICAL = "philosophical"  # Filter (metaphysical)
    UNCLASSIFIED = "unclassified"  # Route to review queue


@dataclass
class AtomicClaim(Artifact):
    """
    A single-predicate factual claim.

    This is the primary output of the extraction pipeline.
    """

    text: str = ""
    claim_type: ClaimType = ClaimType.UNCLASSIFIED
    confidence: float = 0.5
    confidence_reasons: list[str] = field(default_factory=list)
    method_path: list[str] = field(default_factory=list)
    requires_review: bool = True
    speaker: Optional[str] = None
    scope_id: Optional[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        # Auto-flag for review if unclassified or low confidence
        if self.claim_type == ClaimType.UNCLASSIFIED or self.confidence < 0.6:
            self.requires_review = True

    def is_checkable(self) -> bool:
        """Return True if this claim should be routed to fact-checker."""
        return self.claim_type in (
            ClaimType.EMPIRICAL,
            ClaimType.METHODOLOGICAL,
            ClaimType.PREDICTIVE,
        )
