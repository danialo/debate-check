"""Planner budget configuration and status."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class BudgetStatus(Enum):
    """Status of budget checks."""

    OK = auto()
    DEPTH_EXCEEDED = auto()
    TASK_LIMIT = auto()
    TIME_EXCEEDED = auto()
    BACKTRACK_LIMIT = auto()


@dataclass
class PlannerBudgets:
    """
    Budget configuration for the HTN planner.

    Separates HARD (immediate stop) from SOFT (emit diagnostic, may continue) limits.
    """

    # Hard limits - planner stops immediately when exceeded
    max_tasks: int = 1000
    max_depth: int = 12
    max_children_per_task: int = 50
    global_time_budget_ms: int = 60000  # 1 minute

    # Soft limits - emit diagnostic, may continue with degradation
    max_backtracks_global: int = 20
    max_llm_calls_per_transcript: int = 100
    max_llm_tokens: int = 50000
