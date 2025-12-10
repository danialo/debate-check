"""Reference resolution artifact with first-class uncertainty."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from .base import Artifact


class ResolutionStatus(Enum):
    """Status of reference resolution."""

    TENTATIVE = auto()  # Best guess, not committed
    COMMITTED = auto()  # High confidence, locked in
    AMBIGUOUS = auto()  # Multiple valid candidates, needs human
    UNRESOLVED = auto()  # No candidates found


@dataclass
class TentativeResolution(Artifact):
    """
    Reference resolution with uncertainty tracking.

    Stored BOTH internally (for method decisions) AND emitted as artifact
    (for output traceability).
    """

    source_text: str = ""
    ref_type: str = ""  # PRONOUN, DEMONSTRATIVE, DEFINITE_NP

    # Resolution result
    status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    winner: Optional[str] = None  # Entity ID or None
    confidence: float = 0.0

    # Provenance
    candidates: list[dict[str, Any]] = field(default_factory=list)
    scoring_features: dict[str, float] = field(default_factory=dict)
    reason: str = ""
    method_path: list[str] = field(default_factory=list)

    # Control
    allow_auto_commit: bool = True

    def should_commit(self, threshold: float = 0.85) -> bool:
        """Check if resolution meets commit threshold."""
        return (
            self.status == ResolutionStatus.TENTATIVE
            and self.confidence >= threshold
            and self.allow_auto_commit
        )
