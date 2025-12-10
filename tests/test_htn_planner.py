"""Tests for HTN planner."""

import pytest

from debate_claim_extractor.htn import HTNPlanner, Task, PlannerBudgets
from debate_claim_extractor.htn.methods import decompose, claim  # noqa: F401 - triggers registration
from debate_claim_extractor.state import DiscourseState, SpeakerTurn


@pytest.fixture
def sample_transcript():
    """Simple debate transcript."""
    return """HARRIS: Free will is an illusion. Studies show that brain activity precedes conscious decision by 300 milliseconds.

PETERSON: But the methodology is flawed. The subjects were making arbitrary decisions, not meaningful ones."""


@pytest.fixture
def sample_state(sample_transcript):
    """Create DiscourseState from sample transcript."""
    turns = [
        SpeakerTurn(
            speaker="HARRIS",
            text="Free will is an illusion. Studies show that brain activity precedes conscious decision by 300 milliseconds.",
            span=(0, 120),
            turn_index=0,
        ),
        SpeakerTurn(
            speaker="PETERSON",
            text="But the methodology is flawed. The subjects were making arbitrary decisions, not meaningful ones.",
            span=(122, 220),
            turn_index=1,
        ),
    ]
    return DiscourseState.from_transcript(
        transcript_id="test_001",
        transcript_text=sample_transcript,
        turns=turns,
    )


class TestHTNPlanner:
    def test_planner_runs(self, sample_state):
        """Basic smoke test - planner runs without error."""
        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(sample_state.transcript_text)),
        )

        result = planner.run(root_task, sample_state)

        assert result is not None
        assert result.stats.tasks_executed > 0

    def test_planner_extracts_claims(self, sample_state):
        """Planner extracts claims from transcript."""
        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(sample_state.transcript_text)),
        )

        result = planner.run(root_task, sample_state)

        # Should extract at least one claim
        assert len(result.claims) > 0

        # Check claim properties
        for claim in result.claims:
            assert claim.text
            assert claim.claim_type is not None
            assert 0 <= claim.confidence <= 1

    def test_planner_respects_budgets(self, sample_state):
        """Planner stops when budget exceeded."""
        budgets = PlannerBudgets(max_tasks=5)
        planner = HTNPlanner(config=type("Config", (), {"budgets": budgets, "include_trace": True})())

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(sample_state.transcript_text)),
        )

        result = planner.run(root_task, sample_state)

        # Should stop at or before budget
        assert result.stats.tasks_executed <= budgets.max_tasks + 1

    def test_planner_produces_trace(self, sample_state):
        """Planner produces execution trace."""
        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(sample_state.transcript_text)),
        )

        result = planner.run(root_task, sample_state)

        assert len(result.trace) > 0

        # Should have method selection events
        method_events = [e for e in result.trace if e.event_type == "METHOD_SELECTED"]
        assert len(method_events) > 0


class TestTask:
    def test_task_dedup_key_stable(self):
        """Dedup key is stable across instances."""
        task1 = Task.create(
            task_type="TEST",
            params={"foo": "bar"},
            span=(0, 100),
        )
        task2 = Task.create(
            task_type="TEST",
            params={"foo": "bar"},
            span=(0, 100),
        )

        assert task1.compute_dedup_key() == task2.compute_dedup_key()

    def test_task_dedup_key_differs_on_params(self):
        """Dedup key differs when params differ."""
        task1 = Task.create(
            task_type="TEST",
            params={"foo": "bar"},
            span=(0, 100),
        )
        task2 = Task.create(
            task_type="TEST",
            params={"foo": "baz"},
            span=(0, 100),
        )

        assert task1.compute_dedup_key() != task2.compute_dedup_key()


class TestDiscourseState:
    def test_emit_artifact(self, sample_state):
        """State can emit and retrieve artifacts."""
        from debate_claim_extractor.artifacts import AtomicClaim, ClaimType

        claim = AtomicClaim(
            artifact_id="test_claim_001",
            text="Test claim",
            claim_type=ClaimType.EMPIRICAL,
            confidence=0.8,
            span=(0, 10),
        )

        artifact_id = sample_state.emit_artifact(claim)

        assert artifact_id == "test_claim_001"
        assert sample_state.get_artifact("test_claim_001") == claim

    def test_scope_stack(self, sample_state):
        """Scope stack push/pop works."""
        from debate_claim_extractor.state import Scope

        scope = Scope(
            scope_id="test_scope",
            scope_type="TURN",
            speaker="HARRIS",
            span=(0, 100),
        )

        sample_state.push_scope(scope)
        assert sample_state.current_scope_id == "test_scope"
        assert sample_state.current_speaker == "HARRIS"

        popped = sample_state.pop_scope()
        assert popped == scope
        assert sample_state.current_scope_id is None
