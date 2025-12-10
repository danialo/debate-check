"""Debate Claim Extractor package."""

__version__ = "0.3.0"
__author__ = "debate-check"

# HTN-based extraction (new)
from .htn import HTNPlanner, Task, PlannerBudgets, PlannerResult
from .state import DiscourseState, SpeakerTurn
from .artifacts import AtomicClaim, ClaimType, ArgumentFrame

__all__ = [
    "HTNPlanner",
    "Task",
    "PlannerBudgets",
    "PlannerResult",
    "DiscourseState",
    "SpeakerTurn",
    "AtomicClaim",
    "ClaimType",
    "ArgumentFrame",
]
