"""Core data models for claim extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4


class ClaimType(str, Enum):
    FACTUAL = "factual"
    STATISTICAL = "statistical"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    HISTORICAL = "historical"


class ClaimCategory(str, Enum):
    EMPIRICAL = "empirical"
    NARRATIVE = "narrative"


@dataclass(slots=True)
class Utterance:
    """Single speaker turn produced by preprocessing."""

    speaker: str
    text: str
    line_number: int


@dataclass(slots=True)
class Sentence:
    """Sentence-level representation used by the extractor."""

    speech_id: str
    speaker: str
    text: str
    utterance_index: int
    sentence_index: int
    start_char: int
    end_char: int


@dataclass(slots=True)
class Claim:
    """Canonical factual/causal statement suitable for fact-checking."""

    text: str
    speaker: str
    claim_type: ClaimType
    category: ClaimCategory
    confidence: float
    source_sentence: Sentence
    origin: str = "heuristic"
    id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, str] = field(default_factory=dict)

    def anchor_level(self) -> str:
        return self.metadata.get("anchor_level", "standard")


@dataclass(slots=True)
class ExtractionResult:
    """Container returned by the pipeline."""

    claims: List[Claim]
    transcript_characters: int
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    diagnostics: Dict[str, object] = field(default_factory=dict)

    def summary(self) -> Dict[str, object]:
        """Return a lightweight, serialisable summary."""

        type_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}
        for claim in self.claims:
            key = claim.claim_type.value if isinstance(claim.claim_type, ClaimType) else str(claim.claim_type)
            type_counts[key] = type_counts.get(key, 0) + 1
            category_counts[claim.category.value] = category_counts.get(claim.category.value, 0) + 1

        return {
            "generated_at": self.generated_at.isoformat(),
            "claims": [
                {
                    "id": claim.id,
                    "text": claim.text,
                    "speaker": claim.speaker,
                    "type": claim.claim_type.value if isinstance(claim.claim_type, ClaimType) else claim.claim_type,
                    "confidence": claim.confidence,
                    "origin": claim.origin,
                    "metadata": claim.metadata,
                }
                for claim in self.claims
            ],
            "counts": {
                "total": len(self.claims),
                "by_type": type_counts,
                "by_category": category_counts,
            },
            "diagnostics": self.diagnostics,
        }
