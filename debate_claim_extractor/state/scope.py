"""Scope tracking for nested argument structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Scope:
    """
    A scope in the discourse structure.

    Scopes track:
    - Speaker turns
    - Nested arguments
    - Quoted speech
    - Hypotheticals
    """

    scope_id: str
    scope_type: str  # TURN, ARGUMENT, SUPPORT, REBUTTAL, QUOTE, HYPOTHETICAL
    speaker: str
    parent_id: Optional[str] = None
    span: tuple[int, int] = (0, 0)


@dataclass
class SalienceFrame:
    """
    Salience tracking within a scope.

    Entities are ordered by recency (most recent first).
    """

    scope_id: str
    speaker: str
    entities: list[str] = field(default_factory=list)  # Entity IDs, most recent first

    def boost(self, entity_id: str) -> None:
        """Move entity to top of salience stack."""
        if entity_id in self.entities:
            self.entities.remove(entity_id)
        self.entities.insert(0, entity_id)

    def top(self, n: int = 5) -> list[str]:
        """Get top N salient entities."""
        return self.entities[:n]
