"""Decomposition methods for transcripts and turns."""

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


@method(name="DecomposeTranscript", task="DECOMPOSE_TRANSCRIPT", base_cost=1.0)
class DecomposeTranscript(BaseMethod):
    """Root method: decompose transcript into speaker turns."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return len(state.speaker_turns) > 0

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        use_llm = task.params.get("use_llm", False)
        fact_check = task.params.get("fact_check", False)
        subtasks = []
        for i, turn in enumerate(state.speaker_turns):
            subtasks.append(
                Task.create(
                    task_type="PROCESS_TURN",
                    params={
                        "turn_index": i,
                        "speaker": turn.speaker,
                        "use_llm": use_llm,
                        "fact_check": fact_check,
                    },
                    span=turn.span,
                    parent=task,
                )
            )
        return subtasks


@method(name="ProcessTurn", task="PROCESS_TURN", base_cost=5.0)
class ProcessTurn(BaseMethod):
    """Process a single speaker turn: segment into argument parts."""

    # Discourse markers that indicate argument boundaries
    BOUNDARY_MARKERS = [
        r"\bbut\b",
        r"\bhowever\b",
        r"\bon the other hand\b",
        r"\bpushes back\b",
        r"\bdisagrees\b",
        r"\bcounters\b",
        r"\balthough\b",
        r"\bnevertheless\b",
        r"\byet\b",
    ]

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        turn_index = task.params.get("turn_index")
        return (
            turn_index is not None
            and 0 <= turn_index < len(state.speaker_turns)
        )

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        turn_index = task.params["turn_index"]
        use_llm = task.params.get("use_llm", False)
        fact_check = task.params.get("fact_check", False)
        turn = state.speaker_turns[turn_index]

        subtasks = []

        # 1. Register speaker as entity (for cross-turn reference resolution)
        subtasks.append(
            Task.create(
                task_type="REGISTER_SPEAKER_ENTITY",
                params={
                    "speaker": turn.speaker,
                    "turn_index": turn_index,
                },
                span=turn.span,
                parent=task,
            )
        )

        # 2. Push a scope for this turn
        subtasks.append(
            Task.create(
                task_type="PUSH_SCOPE",
                params={
                    "scope_type": "TURN",
                    "speaker": turn.speaker,
                    "scope_id": f"turn_{turn_index}_{uuid4().hex[:6]}",
                },
                span=turn.span,
                parent=task,
            )
        )

        # 3. Detect dialectic relation to previous turn (if any)
        if turn_index > 0:
            subtasks.append(
                Task.create(
                    task_type="DETECT_DIALECTIC_RELATION",
                    params={
                        "text": turn.text,
                        "speaker": turn.speaker,
                        "turn_index": turn_index,
                    },
                    span=turn.span,
                    parent=task,
                )
            )

        # 4. Build argument frame for this turn
        subtasks.append(
            Task.create(
                task_type="BUILD_ARGUMENT_FRAME",
                params={
                    "speaker": turn.speaker,
                    "turn_index": turn_index,
                },
                span=turn.span,
                parent=task,
            )
        )

        # 5. Extract claims (they get linked to the frame)
        segments = self._segment_text(turn.text, turn.span)

        for seg_text, seg_span in segments:
            subtasks.append(
                Task.create(
                    task_type="EXTRACT_CLAIMS_FROM_SEGMENT",
                    params={
                        "text": seg_text,
                        "speaker": turn.speaker,
                        "turn_index": turn_index,
                        "use_llm": use_llm,
                    },
                    span=seg_span,
                    parent=task,
                )
            )

        # 6. Detect and resolve references (pronouns, demonstratives)
        subtasks.append(
            Task.create(
                task_type="DETECT_REFERENCES",
                params={
                    "text": turn.text,
                    "speaker": turn.speaker,
                },
                span=turn.span,
                parent=task,
            )
        )

        # 7. Finalize frame with detected relation
        subtasks.append(
            Task.create(
                task_type="FINALIZE_FRAME",
                params={
                    "turn_index": turn_index,
                },
                span=turn.span,
                parent=task,
            )
        )

        # 8. Fact-check EMPIRICAL claims (if enabled)
        subtasks.append(
            Task.create(
                task_type="FACT_CHECK_TURN_CLAIMS",
                params={
                    "turn_index": turn_index,
                    "fact_check": fact_check,
                },
                span=turn.span,
                parent=task,
            )
        )

        # 9. Pop scope at the end
        subtasks.append(
            Task.create(
                task_type="POP_SCOPE",
                params={"scope_type": "TURN"},
                span=turn.span,
                parent=task,
            )
        )

        return subtasks

    def _segment_text(
        self, text: str, span: tuple[int, int]
    ) -> list[tuple[str, tuple[int, int]]]:
        """Segment text on discourse markers."""
        # Build combined pattern
        pattern = "|".join(f"({m})" for m in self.BOUNDARY_MARKERS)
        regex = re.compile(pattern, re.IGNORECASE)

        segments = []
        last_end = 0
        base_offset = span[0]

        for match in regex.finditer(text):
            # Include text before this marker
            if match.start() > last_end:
                seg_text = text[last_end : match.start()].strip()
                if seg_text:
                    segments.append(
                        (
                            seg_text,
                            (base_offset + last_end, base_offset + match.start()),
                        )
                    )
            last_end = match.start()

        # Include remaining text
        if last_end < len(text):
            seg_text = text[last_end:].strip()
            if seg_text:
                segments.append(
                    (seg_text, (base_offset + last_end, base_offset + len(text)))
                )

        # If no segments found, return the whole text
        if not segments:
            segments = [(text.strip(), span)]

        return segments


@method(name="PushScope", task="PUSH_SCOPE", base_cost=1.0)
class PushScope(BaseMethod):
    """Primitive: push a new scope onto the stack."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return "scope_type" in task.params and "speaker" in task.params

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...state.scope import Scope

        scope = Scope(
            scope_id=task.params.get("scope_id", f"scope_{uuid4().hex[:8]}"),
            scope_type=task.params["scope_type"],
            speaker=task.params["speaker"],
            parent_id=state.current_scope_id,
            span=task.span,
        )

        state.push_scope(scope)

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=[f"Pushed scope {scope.scope_id} ({scope.scope_type})"],
        )


@method(name="PopScope", task="POP_SCOPE", base_cost=1.0)
class PopScope(BaseMethod):
    """Primitive: pop the current scope from the stack."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return len(state.scope_stack) > 0

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        popped = state.pop_scope()

        if popped is None:
            return OperatorResult(
                status=OperatorStatus.FAILED,
                error="No scope to pop",
            )

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=[f"Popped scope {popped.scope_id} ({popped.scope_type})"],
        )
