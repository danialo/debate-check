"""Entity and mention tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EntityMention:
    """A single mention of an entity in the transcript."""

    entity_id: str
    span: tuple[int, int]
    surface_form: str
    scope_id: Optional[str] = None


@dataclass
class Entity:
    """
    A canonical entity tracked across the transcript.

    Entities can be: PERSON, STUDY, CONCEPT, CLAIM
    """

    entity_id: str = ""
    canonical: str = ""
    aliases: set[str] = field(default_factory=set)
    entity_type: str = "UNKNOWN"  # PERSON, STUDY, CONCEPT, CLAIM
    first_mention_span: tuple[int, int] = (0, 0)
    introducing_speaker: Optional[str] = None
    mention_spans: list[tuple[int, int]] = field(default_factory=list)

    def add_alias(self, alias: str) -> None:
        """Add an alias for this entity."""
        self.aliases.add(alias.lower().strip())

    def matches(self, text: str) -> bool:
        """Check if text matches this entity's canonical name or aliases."""
        normalized = text.lower().strip()
        if normalized == self.canonical.lower():
            return True
        return normalized in self.aliases
