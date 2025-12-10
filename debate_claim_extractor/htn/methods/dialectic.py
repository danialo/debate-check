"""Dialectic structure methods - support/rebuttal detection."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import uuid4

from ..registry import method
from ..result import OperatorResult, OperatorStatus
from ..task import Task
from .base import BaseMethod

if TYPE_CHECKING:
    from ...state.discourse import DiscourseState


# Discourse markers for relation detection
REBUTTAL_MARKERS = [
    r"^\s*but\b",
    r"^\s*however\b",
    r"\bhowever,",
    r"\byet\b",
    r"\balthough\b",
    r"\bdisagrees?\b",
    r"\bwrong\b",
    r"\bincorrect\b",
    r"\bthat's not\b",
    r"\bthat argument\b",
    r"\bignores?\b",
]

SUPPORT_MARKERS = [
    r"\bbecause\b",
    r"\btherefore\b",
    r"\bthus\b",
    r"\bproves?\s+that\b",
    r"\bshows?\s+that\b",
    r"\bevidence\s+(that|for)\b",
    r"\bdemonstrates?\b",
    r"\bsince\b",
]


@method(name="BuildArgumentFrame", task="BUILD_ARGUMENT_FRAME", base_cost=3.0)
class BuildArgumentFrame(BaseMethod):
    """Primitive: create an ArgumentFrame for a turn."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return "speaker" in task.params

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...artifacts.frame import ArgumentFrame

        speaker = task.params["speaker"]
        turn_index = task.params.get("turn_index", 0)
        frame_type = task.params.get("frame_type", "CLAIM")
        parent_frame_id = task.params.get("parent_frame_id")

        frame_id = f"frame_{turn_index}_{uuid4().hex[:6]}"

        frame = ArgumentFrame(
            artifact_id=frame_id,
            summary=f"{speaker}'s argument",
            frame_type=frame_type,
            speaker=speaker,
            span=task.span,
            parent_frame_id=parent_frame_id,
            child_claim_ids=[],  # Will be populated by LinkClaimToFrame
            child_frame_ids=[],
            method_path=state.get_method_path(task.task_id),
            created_by_task=task.task_id,
            created_by_method=self._method_name,
        )

        state.emit_artifact(frame)

        # Store frame ID for later claim linking
        if not hasattr(state, "_current_frame_id"):
            state._current_frame_id = None
        state._current_frame_id = frame_id

        # Track frames by turn for cross-turn linking
        if not hasattr(state, "_turn_frames"):
            state._turn_frames = {}
        state._turn_frames[turn_index] = frame_id

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            artifacts_emitted=[frame_id],
            state_mutations=[f"Created {frame_type} frame for {speaker}"],
        )


@method(name="DetectDialecticRelation", task="DETECT_DIALECTIC_RELATION", base_cost=2.0)
class DetectDialecticRelation(BaseMethod):
    """Detect if current turn rebuts or supports previous turn."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        text = task.params.get("text", "")
        turn_index = task.params.get("turn_index", 0)
        # Need text and a previous turn to relate to
        return len(text) > 0 and turn_index > 0

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        text = task.params["text"]
        turn_index = task.params["turn_index"]
        text_lower = text.lower()

        relation_type = None
        confidence = 0.0
        reasons = []

        # Check for rebuttal markers
        for pattern in REBUTTAL_MARKERS:
            if re.search(pattern, text_lower):
                relation_type = "REBUTTAL"
                confidence = 0.8
                reasons.append(f"rebuttal marker: {pattern}")
                break

        # Check for support markers (if not already rebuttal)
        if not relation_type:
            for pattern in SUPPORT_MARKERS:
                if re.search(pattern, text_lower):
                    relation_type = "SUPPORT"
                    confidence = 0.7
                    reasons.append(f"support marker: {pattern}")
                    break

        if not relation_type:
            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                state_mutations=["No dialectic relation detected"],
            )

        # Find previous turn's frame
        prev_frame_id = None
        if hasattr(state, "_turn_frames"):
            prev_frame_id = state._turn_frames.get(turn_index - 1)

        # Store detected relation for BuildArgumentFrame to use
        if not hasattr(state, "_pending_relation"):
            state._pending_relation = {}
        state._pending_relation[turn_index] = {
            "type": relation_type,
            "parent_frame_id": prev_frame_id,
            "confidence": confidence,
            "reasons": reasons,
        }

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=[
                f"Detected {relation_type} relation (conf={confidence:.2f}): {'; '.join(reasons)}"
            ],
        )


@method(name="LinkClaimToFrame", task="LINK_CLAIM_TO_FRAME", base_cost=1.0)
class LinkClaimToFrame(BaseMethod):
    """Primitive: link a claim to its parent frame."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return "claim_id" in task.params

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...artifacts.frame import ArgumentFrame

        claim_id = task.params["claim_id"]
        frame_id = task.params.get("frame_id") or getattr(state, "_current_frame_id", None)

        if not frame_id:
            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                state_mutations=["No frame to link claim to"],
            )

        # Get frame and add claim
        frame = state.get_artifact(frame_id)
        if frame and isinstance(frame, ArgumentFrame):
            if claim_id not in frame.child_claim_ids:
                frame.child_claim_ids.append(claim_id)

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=[f"Linked claim {claim_id} to frame {frame_id}"],
        )


@method(name="FinalizeFrame", task="FINALIZE_FRAME", base_cost=1.0)
class FinalizeFrame(BaseMethod):
    """Primitive: finalize frame with detected relation type."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return "turn_index" in task.params

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...artifacts.frame import ArgumentFrame

        turn_index = task.params["turn_index"]

        # Get the frame for this turn
        frame_id = None
        if hasattr(state, "_turn_frames"):
            frame_id = state._turn_frames.get(turn_index)

        if not frame_id:
            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                state_mutations=["No frame to finalize"],
            )

        frame = state.get_artifact(frame_id)
        if not frame or not isinstance(frame, ArgumentFrame):
            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                state_mutations=["Frame not found"],
            )

        # Apply pending relation if any
        if hasattr(state, "_pending_relation"):
            relation = state._pending_relation.get(turn_index)
            if relation:
                frame.frame_type = relation["type"]
                frame.parent_frame_id = relation["parent_frame_id"]
                frame.confidence = relation["confidence"]

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=[f"Finalized frame {frame_id} as {frame.frame_type}"],
        )
