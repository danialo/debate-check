"""Planner result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..artifacts.base import Artifact
    from ..artifacts.claim import AtomicClaim
    from ..artifacts.frame import ArgumentFrame
    from ..artifacts.resolution import TentativeResolution
    from ..state.reference import OpenReference
    from .trace import TraceEvent


class OperatorStatus(Enum):
    """Status of operator execution."""

    SUCCESS = auto()
    FAILED = auto()  # Recoverable, triggers backtrack
    BLOCKED = auto()  # Waiting on external (future: async)
    SKIPPED = auto()  # Preconditions invalidated mid-execution


@dataclass
class OperatorResult:
    """Result of primitive operator execution."""

    status: OperatorStatus
    artifacts_emitted: list[str] = field(default_factory=list)
    state_mutations: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PlannerStats:
    """Statistics from planner execution."""

    tasks_executed: int = 0
    llm_calls: int = 0
    llm_tokens: int = 0
    backtracks: int = 0
    elapsed_ms: int = 0


@dataclass
class PlannerResult:
    """Final result from HTN planner."""

    success: bool = True
    artifacts: list["Artifact"] = field(default_factory=list)
    claims: list["AtomicClaim"] = field(default_factory=list)
    frames: list["ArgumentFrame"] = field(default_factory=list)
    resolved_references: list["TentativeResolution"] = field(default_factory=list)
    unresolved_references: list["OpenReference"] = field(default_factory=list)
    trace: list["TraceEvent"] = field(default_factory=list)
    stats: PlannerStats = field(default_factory=PlannerStats)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
