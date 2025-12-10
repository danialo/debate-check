"""Open reference tracking for coreference resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OpenReference:
    """
    An unresolved reference awaiting resolution.

    Types: PRONOUN, DEMONSTRATIVE, DEFINITE_NP, ELLIPSIS
    """

    ref_id: str
    ref_type: str  # PRONOUN, DEMONSTRATIVE, DEFINITE_NP, ELLIPSIS
    surface_form: str  # "this", "he", "the study", "[implicit]"
    span: tuple[int, int]
    scope_id: Optional[str] = None
    candidates: list[str] = field(default_factory=list)  # Candidate entity IDs
    scores: list[float] = field(default_factory=list)  # Parallel scores
