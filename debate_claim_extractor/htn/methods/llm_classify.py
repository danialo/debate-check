"""LLM-assisted claim classification method."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..registry import method
from ..result import OperatorResult, OperatorStatus
from ..task import Task
from .base import BaseMethod

if TYPE_CHECKING:
    from ...state.discourse import DiscourseState


@method(name="LLMClassifyClaim", task="CLASSIFY_CLAIM_TYPE", base_cost=5.0, requires_llm=True)
class LLMClassifyClaim(BaseMethod):
    """Use LLM to classify claim type with higher accuracy."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        # Only applicable if LLM client is available
        return (
            state.llm_client is not None
            and "claim_id" in task.params
        )

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...artifacts.claim import AtomicClaim, ClaimType

        claim_id = task.params["claim_id"]
        claim = state.get_artifact(claim_id)

        if not claim or not isinstance(claim, AtomicClaim):
            return OperatorResult(
                status=OperatorStatus.FAILED,
                error=f"Claim {claim_id} not found",
            )

        # Call LLM for classification
        try:
            result = state.llm_client.classify_claim(claim.text)
            state.llm_calls += 1

            if result and "claim_type" in result:
                type_str = result["claim_type"].upper()
                try:
                    new_type = ClaimType[type_str]
                    old_type = claim.claim_type
                    claim.claim_type = new_type
                    claim.confidence = result.get("confidence", 0.85)

                    return OperatorResult(
                        status=OperatorStatus.SUCCESS,
                        state_mutations=[
                            f"LLM reclassified claim from {old_type} to {new_type}",
                            f"Confidence: {claim.confidence}",
                        ],
                    )
                except KeyError:
                    # Unknown claim type from LLM
                    pass

        except Exception as e:
            return OperatorResult(
                status=OperatorStatus.FAILED,
                error=f"LLM classification failed: {e}",
            )

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=["LLM classification returned no change"],
        )


@method(name="HeuristicClassifyClaim", task="CLASSIFY_CLAIM_TYPE", base_cost=10.0, requires_llm=False)
class HeuristicClassifyClaim(BaseMethod):
    """Fallback heuristic classification when LLM unavailable."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        return "claim_id" in task.params

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        # Already classified by ExtractAtomicClaim, no-op here
        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            state_mutations=["Using heuristic classification (already applied)"],
        )
