"""Fact-checking methods for empirical claims."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from ..registry import method
from ..result import OperatorResult, OperatorStatus
from ..task import Task
from .base import BaseMethod

if TYPE_CHECKING:
    from ...state.discourse import DiscourseState


@method(name="FactCheckClaim", task="FACT_CHECK_CLAIM", base_cost=20.0)
class FactCheckClaim(BaseMethod):
    """Fact-check an empirical claim using external service."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        # Need claim_id and fact-check client
        claim_id = task.params.get("claim_id")
        if not claim_id:
            return False

        # Check fact-check budget
        fact_check_count = getattr(state, "fact_check_count", 0)
        fact_check_budget = getattr(state, "fact_check_budget", 100)
        if fact_check_count >= fact_check_budget:
            return False

        return state.fact_check_client is not None

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...artifacts.claim import AtomicClaim, ClaimType
        from ...artifacts.fact_check import FactCheckResult, VerificationStatus

        claim_id = task.params["claim_id"]
        claim = state.get_artifact(claim_id)

        if not claim or not isinstance(claim, AtomicClaim):
            return OperatorResult(
                status=OperatorStatus.FAILED,
                error=f"Claim {claim_id} not found",
            )

        # Only fact-check EMPIRICAL claims
        if claim.claim_type != ClaimType.EMPIRICAL:
            return OperatorResult(
                status=OperatorStatus.SKIPPED,
                state_mutations=[f"Skipped non-EMPIRICAL claim: {claim.claim_type}"],
            )

        # Call fact-check service
        try:
            response = state.fact_check_client.check_claim(claim.text)
            state.fact_check_count = getattr(state, "fact_check_count", 0) + 1

            # Parse response
            status_str = response.get("status", "NO_DATA").upper()
            try:
                status = VerificationStatus[status_str]
            except KeyError:
                status = VerificationStatus.NO_DATA

            # Create fact-check result artifact
            result = FactCheckResult(
                artifact_id=f"factcheck_{uuid4().hex[:12]}",
                claim_id=claim_id,
                claim_text=claim.text,
                status=status,
                confidence=response.get("confidence", 0.0),
                summary=response.get("source", ""),
                sources=response.get("sources", []),
                source_urls=response.get("urls", []),
                raw_response=response,
                method_path=state.get_method_path(task.task_id),
                created_by_task=task.task_id,
                created_by_method=self._method_name,
            )

            state.emit_artifact(result)

            return OperatorResult(
                status=OperatorStatus.SUCCESS,
                artifacts_emitted=[result.artifact_id],
                state_mutations=[f"Fact-checked claim: {status.value}"],
            )

        except Exception as e:
            return OperatorResult(
                status=OperatorStatus.FAILED,
                error=f"Fact-check failed: {e}",
            )


@method(name="SkipFactCheck", task="FACT_CHECK_CLAIM", base_cost=1.0)
class SkipFactCheck(BaseMethod):
    """Skip fact-checking when service unavailable."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        # Use this when no fact-check client available
        return state.fact_check_client is None

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=["Fact-check skipped: no client configured"],
        )


@method(name="FactCheckTurnClaims", task="FACT_CHECK_TURN_CLAIMS", base_cost=5.0)
class FactCheckTurnClaims(BaseMethod):
    """Fact-check all EMPIRICAL claims from a turn."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return task.params.get("fact_check", False)

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        from ...artifacts.claim import AtomicClaim, ClaimType

        turn_index = task.params.get("turn_index", 0)
        frame_id = None

        # Get frame for this turn
        if hasattr(state, "_turn_frames"):
            frame_id = state._turn_frames.get(turn_index)

        if not frame_id:
            return []

        # Get claims from this frame
        frame = state.get_artifact(frame_id)
        if not frame:
            return []

        subtasks = []
        for claim_id in frame.child_claim_ids:
            claim = state.get_artifact(claim_id)
            if claim and isinstance(claim, AtomicClaim):
                # Only fact-check EMPIRICAL claims
                if claim.claim_type == ClaimType.EMPIRICAL:
                    subtasks.append(
                        Task.create(
                            task_type="FACT_CHECK_CLAIM",
                            params={"claim_id": claim_id},
                            span=task.span,
                            parent=task,
                        )
                    )

        return subtasks


@method(name="SkipTurnFactCheck", task="FACT_CHECK_TURN_CLAIMS", base_cost=1.0)
class SkipTurnFactCheck(BaseMethod):
    """Skip fact-checking when disabled."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return not task.params.get("fact_check", False)

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=["Fact-check disabled for this task"],
        )
