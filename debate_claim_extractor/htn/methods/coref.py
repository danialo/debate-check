"""Coreference resolution methods."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import uuid4

from ..canonicalize import entity_dedup_key
from ..registry import method
from ..result import OperatorResult, OperatorStatus
from ..task import Task
from .base import BaseMethod

if TYPE_CHECKING:
    from ...state.discourse import DiscourseState


# Pronoun patterns
PRONOUNS = {
    # Third person - need resolution
    "he": "PRONOUN",
    "him": "PRONOUN",
    "his": "PRONOUN",
    "she": "PRONOUN",
    "her": "PRONOUN",
    "hers": "PRONOUN",
    "they": "PRONOUN",
    "them": "PRONOUN",
    "their": "PRONOUN",
    "theirs": "PRONOUN",
    "it": "PRONOUN",
    "its": "PRONOUN",
}

DEMONSTRATIVES = {
    "this": "DEMONSTRATIVE",
    "that": "DEMONSTRATIVE",
    "these": "DEMONSTRATIVE",
    "those": "DEMONSTRATIVE",
}

# Pattern to find pronouns/demonstratives at word boundaries
REFERENCE_PATTERN = re.compile(
    r"\b(" + "|".join(list(PRONOUNS.keys()) + list(DEMONSTRATIVES.keys())) + r")\b",
    re.IGNORECASE,
)


@method(name="RegisterSpeakerEntity", task="REGISTER_SPEAKER_ENTITY", base_cost=1.0)
class RegisterSpeakerEntity(BaseMethod):
    """Primitive: register a speaker as a PERSON entity."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        speaker = task.params.get("speaker")
        return speaker is not None and speaker != "UNKNOWN"

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...state.entity import Entity

        speaker = task.params["speaker"]
        turn_index = task.params.get("turn_index", 0)

        # Check if already registered
        existing = state.find_entity_by_name(speaker)
        if existing:
            # Boost salience
            state.boost_salience(existing.entity_id)
            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                state_mutations=[f"Boosted salience for existing entity {speaker}"],
            )

        # Create new entity
        entity = Entity(
            entity_id="",  # Will be set by register_entity
            canonical=speaker,
            aliases={speaker.lower(), speaker.upper()},
            entity_type="PERSON",
            first_mention_span=task.span,
            introducing_speaker=speaker,
            mention_spans=[task.span],
        )

        entity_id = state.register_entity(entity)
        state.boost_salience(entity_id)

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=[f"Registered speaker {speaker} as entity {entity_id}"],
        )


@method(name="DetectReferences", task="DETECT_REFERENCES", base_cost=3.0)
class DetectReferences(BaseMethod):
    """Detect pronouns and demonstratives in text segment."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        text = task.params.get("text", "")
        return len(text) > 0

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        """Find references and create resolution tasks for each."""
        text = task.params["text"]
        speaker = task.params.get("speaker", "UNKNOWN")
        base_offset = task.span[0]

        subtasks = []

        for match in REFERENCE_PATTERN.finditer(text):
            word = match.group(1).lower()
            ref_type = PRONOUNS.get(word) or DEMONSTRATIVES.get(word)

            # Skip first-person pronouns (I, my, me) - they refer to speaker
            if word in ("i", "my", "me", "we", "our", "us"):
                continue

            abs_start = base_offset + match.start()
            abs_end = base_offset + match.end()

            subtasks.append(
                Task.create(
                    task_type="RESOLVE_REFERENCE",
                    params={
                        "surface_form": match.group(1),
                        "ref_type": ref_type,
                        "speaker": speaker,
                    },
                    span=(abs_start, abs_end),
                    parent=task,
                )
            )

        return subtasks


@method(name="ResolveReference", task="RESOLVE_REFERENCE", base_cost=5.0)
class ResolveReference(BaseMethod):
    """Primitive: resolve a reference to an entity."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return "surface_form" in task.params and "ref_type" in task.params

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...artifacts.resolution import TentativeResolution, ResolutionStatus
        from ...state.reference import OpenReference

        surface_form = task.params["surface_form"]
        ref_type = task.params["ref_type"]
        current_speaker = task.params.get("speaker", state.current_speaker)

        # Create open reference
        ref_id = f"ref_{uuid4().hex[:8]}"
        open_ref = OpenReference(
            ref_id=ref_id,
            ref_type=ref_type,
            surface_form=surface_form,
            span=task.span,
            scope_id=state.current_scope_id,
        )
        state.register_open_reference(open_ref)

        # Find candidates
        candidates = self._find_candidates(state, ref_type, current_speaker)

        if not candidates:
            # No candidates - emit unresolved
            resolution = TentativeResolution(
                artifact_id=f"resolution_{ref_id}",
                source_text=surface_form,
                ref_type=ref_type,
                span=task.span,
                status=ResolutionStatus.UNRESOLVED,
                winner=None,
                confidence=0.0,
                candidates=[],
                reason="No candidates found in scope",
                method_path=state.get_method_path(task.task_id),
                created_by_task=task.task_id,
                created_by_method=self._method_name,
            )
            state.emit_artifact(resolution)
            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                artifacts_emitted=[resolution.artifact_id],
                state_mutations=[f"Unresolved reference: {surface_form}"],
            )

        # Score candidates (pass span to filter self-references)
        scored = self._score_candidates(state, ref_type, current_speaker, candidates, ref_span=task.span)
        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            # All candidates filtered out (e.g., self-references)
            resolution = TentativeResolution(
                artifact_id=f"resolution_{ref_id}",
                source_text=surface_form,
                ref_type=ref_type,
                span=task.span,
                status=ResolutionStatus.UNRESOLVED,
                winner=None,
                confidence=0.0,
                candidates=[],
                reason="All candidates filtered (self-reference)",
                method_path=state.get_method_path(task.task_id),
                created_by_task=task.task_id,
                created_by_method=self._method_name,
            )
            state.emit_artifact(resolution)
            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                artifacts_emitted=[resolution.artifact_id],
                state_mutations=[f"Unresolved reference (filtered): {surface_form}"],
            )

        best_entity_id, best_score, best_reasons = scored[0]

        # Determine status
        if best_score >= 0.85:
            status = ResolutionStatus.COMMITTED
        elif best_score >= 0.5:
            status = ResolutionStatus.TENTATIVE
        else:
            status = ResolutionStatus.AMBIGUOUS

        # Create resolution artifact
        resolution = TentativeResolution(
            artifact_id=f"resolution_{ref_id}",
            source_text=surface_form,
            ref_type=ref_type,
            span=task.span,
            status=status,
            winner=best_entity_id,
            confidence=best_score,
            candidates=[
                {"entity_id": eid, "score": score, "reasons": reasons}
                for eid, score, reasons in scored[:5]
            ],
            scoring_features={"top_score": best_score},
            reason="; ".join(best_reasons),
            method_path=state.get_method_path(task.task_id),
            created_by_task=task.task_id,
            created_by_method=self._method_name,
        )

        state.emit_artifact(resolution)
        state.resolve_reference(ref_id, resolution)

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            artifacts_emitted=[resolution.artifact_id],
            state_mutations=[f"Resolved '{surface_form}' -> {best_entity_id} ({best_score:.2f})"],
        )

    def _find_candidates(
        self,
        state: "DiscourseState",
        ref_type: str,
        current_speaker: str,
    ) -> list[str]:
        """Find candidate entities for resolution."""
        candidates = []

        # Get salient entities
        salient = state.get_salient_entities(limit=10)
        candidates.extend(salient)

        # For pronouns like "his/her", also look at other speakers
        if ref_type == "PRONOUN":
            for entity_id, entity in state.entities.items():
                if entity.entity_type == "PERSON" and entity_id not in candidates:
                    candidates.append(entity_id)

        return candidates

    def _score_candidates(
        self,
        state: "DiscourseState",
        ref_type: str,
        current_speaker: str,
        candidates: list[str],
        ref_span: tuple[int, int] | None = None,
    ) -> list[tuple[str, float, list[str]]]:
        """Score candidates for reference resolution."""
        scored = []

        for entity_id in candidates:
            entity = state.get_entity(entity_id)
            if not entity:
                continue

            # Skip entities that contain the reference (can't resolve to self)
            if ref_span and entity.first_mention_span:
                entity_start, entity_end = entity.first_mention_span
                ref_start, ref_end = ref_span
                if entity_start <= ref_start and ref_end <= entity_end:
                    continue  # Reference is inside this entity - skip

            score = 0.0
            reasons = []

            # Salience bonus
            salient = state.get_salient_entities(limit=5)
            if entity_id in salient:
                salience_rank = salient.index(entity_id)
                salience_bonus = 0.3 * (1 - salience_rank / 5)
                score += salience_bonus
                reasons.append(f"salient (rank {salience_rank + 1})")

            # For third-person pronouns (he/his/him, she/her), prefer other speakers
            surface_lower = ref_type.lower() if ref_type else ""
            if ref_type == "PRONOUN":
                if entity.entity_type == "PERSON":
                    # If entity is NOT the current speaker, it's a good candidate
                    # This is a strong signal for cross-turn pronoun resolution
                    if entity.canonical != current_speaker:
                        score += 0.6
                        reasons.append("other speaker (pronoun target)")
                    else:
                        # Current speaker using third-person about themselves is rare
                        score -= 0.2
                        reasons.append("same speaker (unlikely)")

            # For demonstratives, prefer recent claims/concepts
            if ref_type == "DEMONSTRATIVE":
                if entity.entity_type in ("CLAIM", "CONCEPT"):
                    score += 0.4
                    reasons.append("claim/concept (demonstrative target)")

            # Recency bonus based on first_mention_span
            # More recent = higher score
            if entity.first_mention_span:
                # Normalize by transcript length (rough heuristic)
                recency = entity.first_mention_span[0] / max(1, state.speaker_turns[-1].span[1] if state.speaker_turns else 1)
                recency_bonus = 0.2 * recency  # More recent = higher
                score += recency_bonus
                reasons.append(f"recency ({recency:.2f})")

            # Base score for being a candidate at all
            score += 0.1
            reasons.append("candidate")

            scored.append((entity_id, min(1.0, max(0.0, score)), reasons))

        return scored


@method(name="RegisterClaimAsEntity", task="REGISTER_CLAIM_ENTITY", base_cost=2.0)
class RegisterClaimAsEntity(BaseMethod):
    """Primitive: register a claim as a CLAIM entity for demonstrative resolution."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return "claim_text" in task.params

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...state.entity import Entity

        claim_text = task.params["claim_text"]
        speaker = task.params.get("speaker", state.current_speaker)

        # Create short canonical form
        canonical = claim_text[:50] + "..." if len(claim_text) > 50 else claim_text

        entity = Entity(
            entity_id="",
            canonical=canonical,
            aliases=set(),
            entity_type="CLAIM",
            first_mention_span=task.span,
            introducing_speaker=speaker,
            mention_spans=[task.span],
        )

        entity_id = state.register_entity(entity)
        state.boost_salience(entity_id)

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=[f"Registered claim as entity: {canonical[:30]}..."],
        )
