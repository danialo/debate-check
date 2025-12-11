"""HTN Planner - stack-based hierarchical task network execution."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Protocol, Any

from .budgets import BudgetStatus, PlannerBudgets
from .registry import get_methods_for_task
from .result import OperatorResult, OperatorStatus, PlannerResult, PlannerStats
from .task import Task
from .trace import TraceRecorder

if TYPE_CHECKING:
    from ..state.discourse import DiscourseState


class Method(Protocol):
    """Protocol for HTN methods."""

    _method_name: str
    _task_type: str
    _base_cost: float
    _requires_llm: bool

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        """Return True if method is applicable."""
        ...

    def cost(self, state: "DiscourseState", task: Task) -> float:
        """Dynamic cost for method selection."""
        ...

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        """Return subtasks (compound) or [] (primitive)."""
        ...

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        """Execute primitive operator."""
        ...


@dataclass
class PlannerConfig:
    """Configuration for HTN planner."""

    budgets: PlannerBudgets = field(default_factory=PlannerBudgets)
    include_trace: bool = True


class HTNPlanner:
    """
    Stack-based HTN planner with total-order execution.

    Decomposition is depth-first (stack-based).
    Method selection is cost-based among applicable methods.
    """

    def __init__(self, config: Optional[PlannerConfig] = None) -> None:
        self.config = config or PlannerConfig()
        self.budgets = self.config.budgets

        # Optional LLM client for assisted extraction
        self.llm_client: Optional[Any] = None

        # Optional fact-check client for verification
        self.fact_check_client: Optional[Any] = None
        self.fact_check_budget: int = 100

        # Execution state (reset on each run)
        self.task_stack: list[Task] = []
        self.seen_dedup_keys: set[str] = set()
        self.start_time_ms: int = 0
        self.backtrack_count: int = 0
        self.trace = TraceRecorder()

    def run(self, root_task: Task, state: "DiscourseState") -> PlannerResult:
        """
        Execute HTN planning from root task.

        Args:
            root_task: Initial task to decompose
            state: Discourse state (will be mutated by operators)

        Returns:
            PlannerResult with artifacts, diagnostics, and trace
        """
        # Reset execution state
        self.task_stack = [root_task]
        self.seen_dedup_keys = set()
        self.backtrack_count = 0
        self.start_time_ms = int(time.time() * 1000)
        self.trace.clear()

        # Pass LLM client and budget to state for methods to use
        state.llm_client = self.llm_client
        state.llm_budget = self.budgets.max_llm_calls_per_transcript

        # Pass fact-check client and budget to state
        state.fact_check_client = self.fact_check_client
        state.fact_check_budget = self.fact_check_budget
        state.fact_check_count = 0

        while self.task_stack:
            # Check hard budgets
            budget_status = self._check_hard_budgets(state)
            if budget_status != BudgetStatus.OK:
                self._emit_budget_diagnostic(budget_status, state)
                break

            task = self.task_stack.pop()  # LIFO: depth-first

            # Dedup check
            key = task.compute_dedup_key()
            if key in self.seen_dedup_keys:
                self.trace.log(
                    "DEDUP_SKIP",
                    {"task": task.task_type, "key": key},
                    task_id=task.task_id,
                    depth=task.depth,
                )
                continue
            self.seen_dedup_keys.add(key)

            # Select method
            method = self._select_method(state, task)
            if method is None:
                self._handle_no_method(state, task)
                continue

            # Record method for path tracking
            state.record_method(task.task_id, method._method_name, task.parent_task_id)

            self.trace.log(
                "METHOD_SELECTED",
                {"task": task.task_id, "method": method._method_name},
                task_id=task.task_id,
                method_name=method._method_name,
                depth=task.depth,
            )

            # Decompose
            subtasks = method.decompose(state, task)
            state.task_count += 1

            if not subtasks:
                # PRIMITIVE: Execute operator
                result = self._execute_operator(state, task, method)

                if result.status == OperatorStatus.FAILED:
                    self._handle_operator_failure(state, task, method, result)
                    continue

                self.trace.log(
                    "OPERATOR_EXECUTED",
                    {
                        "task": task.task_id,
                        "method": method._method_name,
                        "status": result.status.name,
                        "artifacts": result.artifacts_emitted,
                        "mutations": result.state_mutations,
                    },
                    task_id=task.task_id,
                    method_name=method._method_name,
                    depth=task.depth,
                )
            else:
                # COMPOUND: Enqueue subtasks
                subtasks = self._enforce_child_budgets(task, subtasks, state)

                self.trace.log(
                    "TASK_DECOMPOSED",
                    {
                        "task": task.task_id,
                        "method": method._method_name,
                        "subtask_count": len(subtasks),
                    },
                    task_id=task.task_id,
                    method_name=method._method_name,
                    depth=task.depth,
                )

                # Insert at front (reversed so first subtask is on top)
                for subtask in reversed(subtasks):
                    subtask.depth = task.depth + 1
                    subtask.parent_task_id = task.task_id
                    self.task_stack.append(subtask)

        return self._collect_results(state)

    def _select_method(
        self, state: "DiscourseState", task: Task
    ) -> Optional[Method]:
        """Select lowest-cost method with passing preconditions."""
        candidates = get_methods_for_task(task.task_type)
        applicable: list[tuple[float, Any]] = []

        for method_cls in candidates:
            method = method_cls()
            if method.preconditions(state, task):
                applicable.append((method.cost(state, task), method))

        if not applicable:
            return None

        applicable.sort(key=lambda x: x[0])
        return applicable[0][1]

    def _execute_operator(
        self, state: "DiscourseState", task: Task, method: Method
    ) -> OperatorResult:
        """Execute primitive with pre-check and error handling."""
        # Re-check preconditions (state may have mutated since selection)
        if not method.preconditions(state, task):
            return OperatorResult(
                status=OperatorStatus.SKIPPED,
                error="Preconditions invalidated before execution",
            )

        # Track LLM usage if applicable
        pre_llm_calls = state.llm_calls

        try:
            result = method.execute(state, task)
        except Exception as e:
            self.trace.log(
                "OPERATOR_EXCEPTION",
                {"task": task.task_id, "method": method._method_name, "error": str(e)},
                task_id=task.task_id,
            )
            return OperatorResult(status=OperatorStatus.FAILED, error=str(e))

        # Check soft LLM budget
        if method._requires_llm:
            if state.llm_calls > self.budgets.max_llm_calls_per_transcript:
                self.trace.log(
                    "SOFT_BUDGET_LLM_CALLS",
                    {
                        "current": state.llm_calls,
                        "limit": self.budgets.max_llm_calls_per_transcript,
                    },
                )

        return result

    def _handle_no_method(self, state: "DiscourseState", task: Task) -> None:
        """Handle case where no method matches."""
        self.trace.log(
            "NO_METHOD",
            {"task": task.task_id, "type": task.task_type},
            task_id=task.task_id,
            depth=task.depth,
        )

        # Emit diagnostic artifact
        from ..artifacts.diagnostic import DiagnosticArtifact

        diagnostic = DiagnosticArtifact(
            artifact_id=f"diag_no_method_{task.task_id}",
            diagnostic_type="NO_APPLICABLE_METHOD",
            message=f"No method found for task type {task.task_type}",
            context={"task_type": task.task_type, "params": task.params},
            span=task.span,
            severity="error",
        )
        state.emit_artifact(diagnostic)

    def _handle_operator_failure(
        self,
        state: "DiscourseState",
        task: Task,
        method: Method,
        result: OperatorResult,
    ) -> None:
        """Handle failed operator."""
        self.backtrack_count += 1

        self.trace.log(
            "OPERATOR_FAILED",
            {
                "task": task.task_id,
                "method": method._method_name,
                "error": result.error,
                "backtrack_count": self.backtrack_count,
            },
            task_id=task.task_id,
            depth=task.depth,
        )

        if self.backtrack_count >= self.budgets.max_backtracks_global:
            self.trace.log(
                "SOFT_BUDGET_BACKTRACKS",
                {
                    "count": self.backtrack_count,
                    "limit": self.budgets.max_backtracks_global,
                },
            )

            # Emit diagnostic
            from ..artifacts.diagnostic import DiagnosticArtifact

            diagnostic = DiagnosticArtifact(
                artifact_id=f"diag_backtrack_{task.task_id}",
                diagnostic_type="BACKTRACK_LIMIT",
                message=f"Backtrack limit reached at task {task.task_id}",
                context={"task": task.task_id, "method": method._method_name},
                span=task.span,
                severity="warning",
            )
            state.emit_artifact(diagnostic)

    def _enforce_child_budgets(
        self, parent: Task, subtasks: list[Task], state: "DiscourseState"
    ) -> list[Task]:
        """Apply budget limits before enqueueing subtasks."""
        # Max children per task
        if len(subtasks) > self.budgets.max_children_per_task:
            self.trace.log(
                "BUDGET_TRIM_CHILDREN",
                {
                    "task": parent.task_id,
                    "requested": len(subtasks),
                    "allowed": self.budgets.max_children_per_task,
                },
            )
            subtasks = subtasks[: self.budgets.max_children_per_task]

        # Max depth filter
        subtasks = [s for s in subtasks if parent.depth + 1 <= self.budgets.max_depth]

        # Remaining task budget
        remaining = self.budgets.max_tasks - state.task_count
        if len(subtasks) > remaining:
            subtasks = subtasks[:remaining]

        return subtasks

    def _check_hard_budgets(self, state: "DiscourseState") -> BudgetStatus:
        """Check hard budget limits."""
        if state.task_count >= self.budgets.max_tasks:
            return BudgetStatus.TASK_LIMIT

        elapsed_ms = int(time.time() * 1000) - self.start_time_ms
        if elapsed_ms >= self.budgets.global_time_budget_ms:
            return BudgetStatus.TIME_EXCEEDED

        return BudgetStatus.OK

    def _emit_budget_diagnostic(
        self, status: BudgetStatus, state: "DiscourseState"
    ) -> None:
        """Emit diagnostic for budget exceeded."""
        from ..artifacts.diagnostic import DiagnosticArtifact

        diagnostic = DiagnosticArtifact(
            artifact_id=f"diag_budget_{status.name.lower()}",
            diagnostic_type="HARD_BUDGET_EXCEEDED",
            message=f"Hard budget exceeded: {status.name}",
            context={
                "reason": status.name,
                "tasks_completed": state.task_count,
                "elapsed_ms": int(time.time() * 1000) - self.start_time_ms,
            },
            severity="error",
        )
        state.emit_artifact(diagnostic)

        self.trace.log(
            "HARD_BUDGET_EXCEEDED",
            {"reason": status.name, "tasks_completed": state.task_count},
        )

    def _collect_results(self, state: "DiscourseState") -> PlannerResult:
        """Gather final results after planning completes."""
        from ..artifacts.claim import AtomicClaim
        from ..artifacts.frame import ArgumentFrame
        from ..artifacts.resolution import TentativeResolution

        artifacts = state.collect_artifacts()

        # Separate by type
        claims = [a for a in artifacts if isinstance(a, AtomicClaim)]
        frames = [a for a in artifacts if isinstance(a, ArgumentFrame)]
        resolutions = [a for a in artifacts if isinstance(a, TentativeResolution)]

        # Collect diagnostics
        from ..artifacts.diagnostic import DiagnosticArtifact

        diagnostics = [
            {"type": a.diagnostic_type, "message": a.message, "context": a.context}
            for a in artifacts
            if isinstance(a, DiagnosticArtifact)
        ]

        return PlannerResult(
            success=len(diagnostics) == 0 or all(
                d.get("type") != "HARD_BUDGET_EXCEEDED" for d in diagnostics
            ),
            artifacts=artifacts,
            claims=claims,
            frames=frames,
            resolved_references=resolutions,
            unresolved_references=state.open_references,
            trace=self.trace.events if self.config.include_trace else [],
            stats=PlannerStats(
                tasks_executed=state.task_count,
                llm_calls=state.llm_calls,
                llm_tokens=state.llm_tokens_used,
                backtracks=self.backtrack_count,
                elapsed_ms=int(time.time() * 1000) - self.start_time_ms,
            ),
            diagnostics=diagnostics,
        )
