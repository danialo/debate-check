# HTN Planner Design Specification v1

## Overview

This document specifies the HTN (Hierarchical Task Network) planner for debate-check, an argument and claim decomposition engine for debate transcripts.

**Boundary Rule**: Debate-Check is a black box. Input: transcript. Output: artifacts (ArgumentFrames, AtomicClaims, lineage). Never expose the internal task stream across system boundaries.

---

## 1. Architecture Principles

### Shared Kernel (Reusable Across Systems)

- `Task`, `Method`, `Operator` base interfaces
- `PlannerBudgets`
- `TraceEvent` and trace recorder
- `canonical_hash()` utility

### Domain-Specific (Stays in Debate-Check)

- `DiscourseState`
- `ArgumentFrame`, `AtomicClaim`
- All method implementations

---

## 2. Core Data Structures

### 2.1 Task

```python
@dataclass
class Task:
    task_id: str
    task_type: str
    params: dict[str, Any]
    span: tuple[int, int]
    parent_task_id: Optional[str] = None
    parent_artifact_id: Optional[str] = None
    depth: int = 0
    budget_ms: int = 1000
    dedup_key: Optional[str] = None

    def compute_dedup_key(self) -> str:
        """
        Stable hash for deduplication within batch.

        INCLUDES: task_type, span, params_hash
        EXCLUDES: mutable state (defeats dedup purpose)
        """
        if self.dedup_key:
            return self.dedup_key

        key_data = {
            "type": self.task_type,
            "span": self.span,
            "params_hash": hashlib.sha256(
                json.dumps(self.params, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
        }
        return hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()[:24]

    @classmethod
    def create(
        cls,
        task_type: str,
        params: dict,
        span: tuple[int, int],
        parent: Optional['Task'] = None,
        **kwargs
    ) -> 'Task':
        """Factory with auto-generated ID and inherited context."""
        task_id = f"{task_type}_{uuid4().hex[:8]}"
        return cls(
            task_id=task_id,
            task_type=task_type,
            params=params,
            span=span,
            parent_task_id=parent.task_id if parent else None,
            parent_artifact_id=kwargs.get('parent_artifact_id'),
            depth=(parent.depth + 1) if parent else 0,
            budget_ms=kwargs.get('budget_ms', 1000),
            dedup_key=kwargs.get('dedup_key')
        )
```

### 2.2 Method Protocol

Methods and operators share the same protocol. The distinction is behavioral:
- **Compound methods**: `decompose()` returns subtasks, `execute()` is not called
- **Primitive operators**: `decompose()` returns `[]`, `execute()` IS called

```python
class OperatorStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()          # Recoverable, triggers backtrack
    BLOCKED = auto()         # Waiting on external (future: async)
    SKIPPED = auto()         # Preconditions invalidated mid-execution

@dataclass
class OperatorResult:
    """Result of primitive execution."""
    status: OperatorStatus
    artifacts_emitted: list[str] = None
    state_mutations: list[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        self.artifacts_emitted = self.artifacts_emitted or []
        self.state_mutations = self.state_mutations or []

class Method(Protocol):
    """
    Unified protocol for compound and primitive methods.
    """
    _method_name: str
    _task_type: str
    _base_cost: float
    _requires_llm: bool

    def preconditions(self, state: 'DiscourseState', task: 'Task') -> bool:
        """Return True if method is applicable."""
        ...

    def cost(self, state: 'DiscourseState', task: 'Task') -> float:
        """Dynamic cost for method selection."""
        ...

    def decompose(self, state: 'DiscourseState', task: 'Task') -> list['Task']:
        """
        Return subtasks for compound methods.
        Return [] for primitive operators (signals: call execute()).
        """
        ...

    def execute(self, state: 'DiscourseState', task: 'Task') -> OperatorResult:
        """
        Execute primitive operator. Only called when decompose() returns [].
        """
        raise NotImplementedError("Compound methods should not have execute() called")
```

### 2.3 Method Registration

```python
_METHOD_REGISTRY: dict[str, list[type]] = {}

def method(
    name: str,
    task: str,
    base_cost: float = 10.0,
    requires_llm: bool = False
):
    """Decorator for method registration."""
    def decorator(cls):
        cls._method_name = name
        cls._task_type = task
        cls._base_cost = base_cost
        cls._requires_llm = requires_llm

        if task not in _METHOD_REGISTRY:
            _METHOD_REGISTRY[task] = []
        _METHOD_REGISTRY[task].append(cls)
        return cls
    return decorator

def get_methods_for_task(task_type: str) -> list[type]:
    return _METHOD_REGISTRY.get(task_type, [])
```

---

## 3. Discourse State

The mutable blackboard passed through the planner. Operators READ and MUTATE this directly.

```python
@dataclass
class DiscourseState:
    # --- Input (immutable after init) ---
    transcript_id: str
    transcript_text: str
    speaker_turns: list['SpeakerTurn']

    # --- Entity tracking (mutable) ---
    entities: dict[str, 'Entity'] = field(default_factory=dict)
    entity_mentions: list['EntityMention'] = field(default_factory=list)

    # --- Scope management (mutable) ---
    scope_stack: list['Scope'] = field(default_factory=list)
    current_scope_id: Optional[str] = None

    # --- Reference resolution (mutable) ---
    open_references: list['OpenReference'] = field(default_factory=list)
    resolved_references: dict[str, 'TentativeResolution'] = field(default_factory=dict)

    # --- Argument structure (mutable) ---
    argument_frames: list['ArgumentFrame'] = field(default_factory=list)
    claims: list['AtomicClaim'] = field(default_factory=list)

    # --- Artifact emission (append-only) ---
    _emitted_artifacts: list['Artifact'] = field(default_factory=list)
    _artifact_index: dict[str, 'Artifact'] = field(default_factory=dict)

    # --- Execution bookkeeping ---
    task_count: int = 0
    llm_calls: int = 0
    llm_tokens_used: int = 0

    # --- API Methods ---

    def emit_artifact(self, artifact: 'Artifact') -> str:
        """Emit an artifact. Returns artifact ID."""
        if artifact.artifact_id in self._artifact_index:
            return artifact.artifact_id
        self._emitted_artifacts.append(artifact)
        self._artifact_index[artifact.artifact_id] = artifact
        return artifact.artifact_id

    def get_artifact(self, artifact_id: str) -> Optional['Artifact']:
        return self._artifact_index.get(artifact_id)

    def collect_artifacts(self) -> list['Artifact']:
        return list(self._emitted_artifacts)

    def register_entity(self, entity: 'Entity') -> str:
        """Register or merge entity. Returns canonical ID."""
        dedup_key = entity_dedup_key(entity.canonical)
        if dedup_key in self.entities:
            existing = self.entities[dedup_key]
            existing.mention_spans.extend(entity.mention_spans)
            return existing.entity_id
        entity.entity_id = dedup_key
        self.entities[dedup_key] = entity
        return dedup_key

    def push_scope(self, scope: 'Scope'):
        self.scope_stack.append(scope)
        self.current_scope_id = scope.scope_id

    def pop_scope(self) -> Optional['Scope']:
        if self.scope_stack:
            popped = self.scope_stack.pop()
            self.current_scope_id = (
                self.scope_stack[-1].scope_id if self.scope_stack else None
            )
            return popped
        return None

    def register_open_reference(self, ref: 'OpenReference'):
        self.open_references.append(ref)

    def resolve_reference(self, ref_id: str, resolution: 'TentativeResolution'):
        self.resolved_references[ref_id] = resolution
        self.open_references = [r for r in self.open_references if r.ref_id != ref_id]
```

---

## 4. Planner Budgets

Separates HARD (immediate stop) from SOFT (emit diagnostic, may continue) limits.

```python
@dataclass
class PlannerBudgets:
    # Hard limits
    max_tasks: int = 1000
    max_depth: int = 12
    max_children_per_task: int = 50
    global_time_budget_ms: int = 60000

    # Soft limits
    max_backtracks_global: int = 20
    max_llm_calls_per_transcript: int = 100
    max_llm_tokens: int = 50000

class BudgetStatus(Enum):
    OK = auto()
    DEPTH_EXCEEDED = auto()
    TASK_LIMIT = auto()
    TIME_EXCEEDED = auto()
    BACKTRACK_LIMIT = auto()
```

---

## 5. HTN Planner

Stack-based (total-order), depth-first execution.

```python
class HTNPlanner:
    def __init__(self, budgets: Optional[PlannerBudgets] = None):
        self.budgets = budgets or PlannerBudgets()
        self.task_stack: list[Task] = []
        self.seen_dedup_keys: set[str] = set()
        self.start_time_ms: int = 0
        self.backtrack_count: int = 0
        self.trace: TraceRecorder = TraceRecorder()

    def run(self, root_task: Task, state: DiscourseState) -> 'PlannerResult':
        self.start_time_ms = int(time.time() * 1000)
        self.task_stack.append(root_task)

        while self.task_stack:
            # Check hard budgets
            budget_status = self._check_hard_budgets(state)
            if budget_status != BudgetStatus.OK:
                self._emit_budget_diagnostic(budget_status, state)
                break

            task = self.task_stack.pop()  # LIFO: depth-first

            # Dedup
            key = task.compute_dedup_key()
            if key in self.seen_dedup_keys:
                self.trace.log("DEDUP_SKIP", {"task": task.task_type, "key": key})
                continue
            self.seen_dedup_keys.add(key)

            # Select method
            method = self._select_method(state, task)
            if method is None:
                self._handle_no_method(state, task)
                continue

            # Decompose
            subtasks = method.decompose(state, task)
            state.task_count += 1

            if not subtasks:
                # PRIMITIVE: Execute operator
                result = self._execute_operator(state, task, method)
                if result.status == OperatorStatus.FAILED:
                    self._handle_operator_failure(state, task, method, result)
                    continue
            else:
                # COMPOUND: Enqueue subtasks
                subtasks = self._enforce_child_budgets(task, subtasks, state)
                for subtask in reversed(subtasks):
                    subtask.depth = task.depth + 1
                    subtask.parent_task_id = task.task_id
                    self.task_stack.append(subtask)

        return self._collect_results(state)

    def _select_method(self, state: DiscourseState, task: Task) -> Optional[Method]:
        """Select lowest-cost method with passing preconditions."""
        candidates = get_methods_for_task(task.task_type)
        applicable = []

        for method_cls in candidates:
            method = method_cls()
            if method.preconditions(state, task):
                applicable.append((method.cost(state, task), method))

        if not applicable:
            return None

        applicable.sort(key=lambda x: x[0])
        return applicable[0][1]

    def _execute_operator(self, state: DiscourseState, task: Task, method: Method) -> OperatorResult:
        """Execute primitive with pre-check and error handling."""
        # Re-check preconditions (state may have mutated)
        if not method.preconditions(state, task):
            return OperatorResult(
                status=OperatorStatus.SKIPPED,
                error="Preconditions invalidated before execution"
            )

        try:
            result = method.execute(state, task)
        except Exception as e:
            return OperatorResult(status=OperatorStatus.FAILED, error=str(e))

        return result

    def _enforce_child_budgets(self, parent: Task, subtasks: list[Task], state: DiscourseState) -> list[Task]:
        if len(subtasks) > self.budgets.max_children_per_task:
            subtasks = subtasks[:self.budgets.max_children_per_task]
        subtasks = [s for s in subtasks if parent.depth + 1 <= self.budgets.max_depth]
        remaining = self.budgets.max_tasks - state.task_count
        if len(subtasks) > remaining:
            subtasks = subtasks[:remaining]
        return subtasks

    def _check_hard_budgets(self, state: DiscourseState) -> BudgetStatus:
        if state.task_count >= self.budgets.max_tasks:
            return BudgetStatus.TASK_LIMIT
        elapsed_ms = int(time.time() * 1000) - self.start_time_ms
        if elapsed_ms >= self.budgets.global_time_budget_ms:
            return BudgetStatus.TIME_EXCEEDED
        return BudgetStatus.OK
```

---

## 6. Planner Result

```python
@dataclass
class PlannerStats:
    tasks_executed: int
    llm_calls: int
    llm_tokens: int
    backtracks: int
    elapsed_ms: int

@dataclass
class PlannerResult:
    success: bool
    artifacts: list['Artifact']
    argument_frames: list['ArgumentFrame']
    claims: list['AtomicClaim']
    resolved_references: list['TentativeResolution']
    unresolved_references: list['OpenReference']
    trace: list[TraceEvent]
    stats: PlannerStats
```

---

## 7. Artifacts

Base class with auto-set `artifact_type`:

```python
@dataclass
class Artifact(ABC):
    artifact_id: str
    artifact_type: str = field(init=False)
    created_by_task: Optional[str] = None
    created_by_method: Optional[str] = None

    def __post_init__(self):
        self.artifact_type = self.__class__.__name__

@dataclass
class AtomicClaim(Artifact):
    text: str
    span: tuple[int, int]
    parent_frame_id: Optional[str] = None
    scope_id: Optional[str] = None
    confidence: float = 1.0

@dataclass
class ArgumentFrame(Artifact):
    frame_type: str  # CLAIM, REBUTTAL, SUPPORT
    spans: list[tuple[int, int]] = field(default_factory=list)
    child_claim_ids: list[str] = field(default_factory=list)
    parent_frame_id: Optional[str] = None

@dataclass
class DiagnosticArtifact(Artifact):
    diagnostic_type: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)
```

---

## 8. TentativeResolution

First-class uncertainty tracking. Stored BOTH internally (for method decisions) AND emitted as artifact (for output traceability).

```python
class ResolutionStatus(Enum):
    TENTATIVE = auto()
    COMMITTED = auto()
    AMBIGUOUS = auto()
    UNRESOLVED = auto()

@dataclass
class TentativeResolution(Artifact):
    """Reference resolution with uncertainty."""
    source_span: tuple[int, int]
    source_text: str

    status: ResolutionStatus
    winner: Optional[str] = None
    confidence: float = 0.0

    candidates: list[dict[str, Any]] = field(default_factory=list)
    scoring_features: dict[str, float] = field(default_factory=dict)
    reason: str = ""
    method_path: list[str] = field(default_factory=list)

    allow_auto_commit: bool = True

    def should_commit(self, threshold: float = 0.85) -> bool:
        return (
            self.status == ResolutionStatus.TENTATIVE
            and self.confidence >= threshold
            and self.allow_auto_commit
        )
```

---

## 9. Canonical Hashing Utilities

```python
def canonicalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text

def canonical_hash(text: str) -> str:
    """SHA256 of canonicalized text."""
    return hashlib.sha256(canonicalize_text(text).encode('utf-8')).hexdigest()

def canonical_hash_short(text: str, length: int = 24) -> str:
    return canonical_hash(text)[:length]

def entity_dedup_key(canonical_name: str) -> str:
    return canonical_hash_short(canonical_name)

def claim_dedup_key(text: str, span: tuple[int, int]) -> str:
    combined = f"{canonical_hash(text)}:{span[0]}:{span[1]}"
    return hashlib.sha256(combined.encode()).hexdigest()[:24]

def llm_cache_key(prompt: str, schema_version: str, model: str) -> str:
    normalized = canonicalize_text(prompt)
    combined = f"v{schema_version}:{model}:{normalized}"
    return hashlib.sha256(combined.encode()).hexdigest()
```

---

## 10. Trace Events

```python
@dataclass
class TraceEvent:
    event_type: str
    timestamp_ms: int
    data: dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None
    method_name: Optional[str] = None
    depth: int = 0

class TraceRecorder:
    def __init__(self):
        self.events: list[TraceEvent] = []

    def log(self, event_type: str, data: dict, **kwargs):
        self.events.append(TraceEvent(
            event_type=event_type,
            timestamp_ms=int(time.time() * 1000),
            data=data,
            **kwargs
        ))

    def export_json(self) -> str:
        return json.dumps([e.__dict__ for e in self.events], indent=2)
```

---

## 11. File Structure

```
debate_check/
├── htn/
│   ├── __init__.py
│   ├── task.py                 # Task dataclass + dedup_key
│   ├── registry.py             # @method decorator + registry
│   ├── planner.py              # HTNPlanner (stack-based)
│   ├── budgets.py              # PlannerBudgets (hard/soft)
│   ├── result.py               # PlannerResult, PlannerStats, OperatorResult
│   ├── canonicalize.py         # Hashing utilities
│   ├── resolution.py           # TentativeResolution
│   ├── trace.py                # TraceEvent + TraceRecorder
│   └── methods/
│       ├── __init__.py
│       ├── base.py             # Method protocol + OperatorStatus
│       ├── coref.py            # Reference resolution
│       ├── decompose.py        # Argument decomposition
│       └── claim.py            # Claim extraction operators
├── state/
│   ├── __init__.py
│   ├── discourse.py            # DiscourseState
│   ├── entity.py               # Entity, EntityMention
│   ├── scope.py                # Scope
│   └── reference.py            # OpenReference
└── artifacts/
    ├── __init__.py
    ├── base.py                 # Artifact ABC
    ├── claim.py                # AtomicClaim
    ├── frame.py                # ArgumentFrame
    └── diagnostic.py           # DiagnosticArtifact
```

---

## 12. Phase 1 Implementation Checklist

Target: 2 weeks, one engineer

### Core Planner
- [ ] `htn/task.py` - Task dataclass with dedup_key
- [ ] `htn/registry.py` - @method decorator and registry
- [ ] `htn/budgets.py` - PlannerBudgets with hard/soft separation
- [ ] `htn/trace.py` - TraceEvent and TraceRecorder
- [ ] `htn/planner.py` - HTNPlanner with stack-based execution
- [ ] `htn/result.py` - PlannerResult, PlannerStats, OperatorResult

### State
- [ ] `state/discourse.py` - DiscourseState with emit/query API
- [ ] `state/entity.py` - Entity, EntityMention
- [ ] `state/scope.py` - Scope
- [ ] `state/reference.py` - OpenReference

### Artifacts
- [ ] `artifacts/base.py` - Artifact ABC
- [ ] `artifacts/claim.py` - AtomicClaim
- [ ] `artifacts/frame.py` - ArgumentFrame
- [ ] `artifacts/diagnostic.py` - DiagnosticArtifact

### Methods (Phase 1 subset)
- [ ] `htn/methods/base.py` - Method protocol, OperatorStatus
- [ ] `htn/methods/decompose.py` - DecomposeTranscript, ProcessTurn
- [ ] `htn/methods/claim.py` - ExtractAtomicClaim (primitive)

### Utilities
- [ ] `htn/canonicalize.py` - Hashing utilities
- [ ] `htn/resolution.py` - TentativeResolution

### Tests
- [ ] `tests/test_planner.py` - Planner execution tests
- [ ] `tests/test_methods.py` - Method precondition/cost tests
- [ ] `tests/test_dedup.py` - Deduplication tests

### Acceptance Criteria
- [ ] Sample transcript produces ArgumentFrames with claims
- [ ] Planner respects max_depth and global_time_budget_ms
- [ ] Dedup prevents duplicate task execution
- [ ] Trace captures all method selections and operator executions
- [ ] No LLM calls in Phase 1 flow

---

## 13. Claim Taxonomy

Route only EMPIRICAL to fact-checker by default:

```python
class ClaimType(Enum):
    EMPIRICAL = "empirical"          # Route to fact-checker
    METHODOLOGICAL = "methodological" # Route to logic/validity check
    NORMATIVE = "normative"          # Filter (value judgments)
    CONCEPTUAL = "conceptual"        # Filter (definitions)
    INTROSPECTIVE = "introspective"  # Filter (first-person mental states)
    PREDICTIVE = "predictive"        # Route to prediction tracker
    PHILOSOPHICAL = "philosophical"  # Filter (metaphysical)
    UNCLASSIFIED = "unclassified"    # Route to review queue
```

**Critical**: Default to `UNCLASSIFIED`, not `EMPIRICAL`.

---

## 14. Example Method Implementations

### Compound Method: DecomposeTranscript

```python
@method(name="DecomposeTranscript", task="DECOMPOSE_TRANSCRIPT", base_cost=1.0)
class DecomposeTranscript:
    def preconditions(self, state: DiscourseState, task: Task) -> bool:
        return len(state.speaker_turns) > 0

    def cost(self, state: DiscourseState, task: Task) -> float:
        return self._base_cost

    def decompose(self, state: DiscourseState, task: Task) -> list[Task]:
        subtasks = []
        for i, turn in enumerate(state.speaker_turns):
            subtasks.append(Task.create(
                task_type="PROCESS_TURN",
                params={"turn_index": i, "speaker": turn.speaker},
                span=turn.span,
                parent=task
            ))
        return subtasks

    def execute(self, state: DiscourseState, task: Task) -> OperatorResult:
        raise NotImplementedError("Compound method")
```

### Primitive Operator: ExtractAtomicClaim

```python
@method(name="ExtractAtomicClaim", task="EXTRACT_CLAIM", base_cost=5.0)
class ExtractAtomicClaim:
    def preconditions(self, state: DiscourseState, task: Task) -> bool:
        span = task.params.get("span")
        return span is not None and span[1] > span[0]

    def cost(self, state: DiscourseState, task: Task) -> float:
        span = task.params.get("span", (0, 0))
        return self._base_cost + ((span[1] - span[0]) / 100)

    def decompose(self, state: DiscourseState, task: Task) -> list[Task]:
        return []  # Primitive: signals execute()

    def execute(self, state: DiscourseState, task: Task) -> OperatorResult:
        span = task.params["span"]
        text = state.transcript_text[span[0]:span[1]]

        claim = AtomicClaim(
            artifact_id=f"claim_{claim_dedup_key(text, span)}",
            text=text,
            span=span,
            parent_frame_id=task.params.get("parent_frame_id"),
            scope_id=state.current_scope_id,
            confidence=0.8
        )

        state.emit_artifact(claim)
        state.claims.append(claim)

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            artifacts_emitted=[claim.artifact_id],
            state_mutations=[f"Added claim {claim.artifact_id}"]
        )
```

---

## Appendix A: Astra Compatibility Notes

This design is "Astra-compatible at the boundary":

| Astra Pattern | Debate-Check Equivalent |
|---------------|------------------------|
| `@method()` decorator | Same pattern adopted |
| `dedup_key` on tasks | Same pattern adopted |
| Total-order (stack) | Same pattern adopted |
| Budget enforcement | Same pattern adopted |
| SHA256 canonical hash | Same utility functions |
| `BeliefKernel` | `DiscourseState` (different domain) |
| `BeliefNode` | `AtomicClaim` (different domain) |

The task stream is NOT exposed across boundaries. Debate-check consumes transcripts and emits artifacts.
