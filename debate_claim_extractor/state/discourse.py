"""Discourse state - the mutable blackboard for HTN planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .entity import Entity
from .scope import Scope, SalienceFrame
from .reference import OpenReference
from ..htn.canonicalize import entity_dedup_key

if TYPE_CHECKING:
    from ..artifacts.base import Artifact
    from ..artifacts.resolution import TentativeResolution


@dataclass
class SpeakerTurn:
    """A single speaker turn from preprocessing."""

    speaker: str
    text: str
    span: tuple[int, int]
    turn_index: int = 0


@dataclass
class DiscourseState:
    """
    Mutable state passed through the HTN planner.

    Operators READ and MUTATE this directly.
    Artifacts are EMITTED here and collected at end.
    """

    # --- Input (immutable after init) ---
    transcript_id: str = ""
    transcript_text: str = ""
    speaker_turns: list[SpeakerTurn] = field(default_factory=list)

    # --- Entity tracking (mutable) ---
    entities: dict[str, Entity] = field(default_factory=dict)

    # --- Scope management (mutable) ---
    scope_stack: list[Scope] = field(default_factory=list)
    salience_stack: list[SalienceFrame] = field(default_factory=list)
    current_scope_id: Optional[str] = None
    current_speaker: Optional[str] = None

    # --- Reference resolution (mutable) ---
    open_references: list[OpenReference] = field(default_factory=list)
    resolved_references: dict[str, "TentativeResolution"] = field(default_factory=dict)

    # --- Artifact emission (append-only) ---
    _emitted_artifacts: list["Artifact"] = field(default_factory=list)
    _artifact_index: dict[str, "Artifact"] = field(default_factory=dict)

    # --- Execution bookkeeping ---
    task_count: int = 0
    llm_calls: int = 0
    llm_tokens_used: int = 0

    # --- Method path tracking ---
    _method_paths: dict[str, list[str]] = field(default_factory=dict)

    # =========================================================================
    # Artifact API
    # =========================================================================

    def emit_artifact(self, artifact: "Artifact") -> str:
        """
        Emit an artifact. Returns artifact ID.

        Called by operators to produce output.
        """
        if artifact.artifact_id in self._artifact_index:
            # Dedup: return existing
            return artifact.artifact_id

        self._emitted_artifacts.append(artifact)
        self._artifact_index[artifact.artifact_id] = artifact
        return artifact.artifact_id

    def get_artifact(self, artifact_id: str) -> Optional["Artifact"]:
        """Retrieve emitted artifact by ID."""
        return self._artifact_index.get(artifact_id)

    def collect_artifacts(self) -> list["Artifact"]:
        """Final collection at planner end."""
        return list(self._emitted_artifacts)

    # =========================================================================
    # Entity API
    # =========================================================================

    def register_entity(self, entity: Entity) -> str:
        """Register or merge entity. Returns canonical ID."""
        dedup_key = entity_dedup_key(entity.canonical)

        if dedup_key in self.entities:
            # Merge: update existing with new mentions
            existing = self.entities[dedup_key]
            existing.mention_spans.extend(entity.mention_spans)
            existing.aliases.update(entity.aliases)
            return existing.entity_id

        entity.entity_id = dedup_key
        self.entities[dedup_key] = entity
        return dedup_key

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        return self.entities.get(entity_id)

    def find_entity_by_name(self, name: str) -> Optional[Entity]:
        """Find entity by canonical name or alias."""
        for entity in self.entities.values():
            if entity.matches(name):
                return entity
        return None

    # =========================================================================
    # Scope API
    # =========================================================================

    def push_scope(self, scope: Scope) -> None:
        """Enter a new scope."""
        self.scope_stack.append(scope)
        self.current_scope_id = scope.scope_id
        self.current_speaker = scope.speaker

        # Push salience frame
        self.salience_stack.append(
            SalienceFrame(scope_id=scope.scope_id, speaker=scope.speaker)
        )

    def pop_scope(self) -> Optional[Scope]:
        """Exit current scope."""
        if not self.scope_stack:
            return None

        popped = self.scope_stack.pop()
        if self.salience_stack:
            self.salience_stack.pop()

        self.current_scope_id = (
            self.scope_stack[-1].scope_id if self.scope_stack else None
        )
        self.current_speaker = (
            self.scope_stack[-1].speaker if self.scope_stack else None
        )

        return popped

    def current_scope(self) -> Optional[Scope]:
        """Get current scope."""
        return self.scope_stack[-1] if self.scope_stack else None

    # =========================================================================
    # Salience API
    # =========================================================================

    def boost_salience(self, entity_id: str) -> None:
        """Boost entity salience in current frame."""
        if self.salience_stack:
            self.salience_stack[-1].boost(entity_id)

    def get_salient_entities(
        self, speaker: Optional[str] = None, limit: int = 5
    ) -> list[str]:
        """Get most salient entities, optionally filtered by speaker."""
        result: list[str] = []

        for frame in reversed(self.salience_stack):
            if speaker is None or frame.speaker == speaker:
                for entity_id in frame.entities:
                    if entity_id not in result:
                        result.append(entity_id)
                    if len(result) >= limit:
                        return result

        return result

    # =========================================================================
    # Reference API
    # =========================================================================

    def register_open_reference(self, ref: OpenReference) -> None:
        """Track an unresolved reference."""
        self.open_references.append(ref)

    def resolve_reference(self, ref_id: str, resolution: "TentativeResolution") -> None:
        """Record resolution for an open reference."""
        self.resolved_references[ref_id] = resolution
        # Remove from open list
        self.open_references = [
            r for r in self.open_references if r.ref_id != ref_id
        ]

    # =========================================================================
    # Method Path Tracking
    # =========================================================================

    def record_method(
        self, task_id: str, method_name: str, parent_task_id: Optional[str]
    ) -> None:
        """Record method execution for path tracking."""
        parent_path = self._method_paths.get(parent_task_id, []) if parent_task_id else []
        self._method_paths[task_id] = parent_path + [method_name]

    def get_method_path(self, task_id: str) -> list[str]:
        """Get the method path for a task."""
        return self._method_paths.get(task_id, [])

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def from_transcript(
        cls,
        transcript_id: str,
        transcript_text: str,
        turns: list[SpeakerTurn],
    ) -> "DiscourseState":
        """Create state from preprocessed transcript."""
        return cls(
            transcript_id=transcript_id,
            transcript_text=transcript_text,
            speaker_turns=turns,
        )
