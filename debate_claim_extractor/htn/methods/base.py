"""Base class for HTN methods."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..result import OperatorResult, OperatorStatus
from ..task import Task

if TYPE_CHECKING:
    from ...state.discourse import DiscourseState


class BaseMethod(ABC):
    """
    Base class for all HTN methods.

    Subclasses should:
    1. Use @method decorator for registration
    2. Implement preconditions()
    3. Implement decompose() - return subtasks or [] for primitives
    4. Optionally override cost()
    5. Implement execute() for primitives
    """

    _method_name: str = "BaseMethod"
    _task_type: str = ""
    _base_cost: float = 10.0
    _requires_llm: bool = False

    @abstractmethod
    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        """Return True if method is applicable in current state."""
        ...

    def cost(self, state: "DiscourseState", task: Task) -> float:
        """
        Dynamic cost for method selection.

        Override for state-dependent scoring.
        """
        base = self._base_cost
        if self._requires_llm:
            base += 200.0
        return base + (task.depth * 1.0)

    @abstractmethod
    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        """
        Decompose task into subtasks.

        For compound methods: return list of subtasks
        For primitive operators: return []
        """
        ...

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        """
        Execute primitive operator.

        Only called when decompose() returns [].
        Override for primitives.
        """
        return OperatorResult(
            status=OperatorStatus.FAILED,
            error="execute() not implemented for compound method",
        )
