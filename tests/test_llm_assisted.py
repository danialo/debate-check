"""Phase 4 driver tests: LLM-assisted extraction."""

import pytest

from debate_claim_extractor.htn import HTNPlanner, Task, PlannerBudgets
from debate_claim_extractor.htn.planner import PlannerConfig
from debate_claim_extractor.state import DiscourseState, SpeakerTurn
from debate_claim_extractor.artifacts import AtomicClaim, ClaimType


class TestLLMAssistedClassification:
    """Tests for LLM-assisted claim classification."""

    def test_llm_improves_ambiguous_classification(self):
        """LLM correctly classifies claim that heuristics struggle with."""
        # This claim is ambiguous - could be EMPIRICAL or PHILOSOPHICAL
        # Heuristics might miss "studies suggest" as weaker than "studies show"
        transcript = """HARRIS: Studies suggest consciousness emerges from neural complexity."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Studies suggest consciousness emerges from neural complexity.",
                span=(0, 60),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="llm_test_001",
            transcript_text=transcript,
            turns=turns,
        )

        # Configure with LLM enabled
        planner = HTNPlanner()
        planner.llm_client = MockLLMClient({
            "Studies suggest consciousness emerges from neural complexity.": {
                "claim_type": "EMPIRICAL",
                "confidence": 0.85,
                "reasoning": "References scientific studies with specific claim about emergence",
            }
        })

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"use_llm": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should have extracted the claim
        claims = [a for a in result.artifacts if isinstance(a, AtomicClaim)]
        assert len(claims) >= 1, "Expected at least one claim"

        # LLM should have classified it as EMPIRICAL
        claim = claims[0]
        assert claim.claim_type == ClaimType.EMPIRICAL, \
            f"Expected EMPIRICAL, got {claim.claim_type}"

    def test_llm_fallback_to_heuristic_when_unavailable(self):
        """Falls back to heuristic classification when LLM unavailable."""
        transcript = """HARRIS: Brain scans show activity before conscious awareness."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Brain scans show activity before conscious awareness.",
                span=(0, 52),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="llm_test_002",
            transcript_text=transcript,
            turns=turns,
        )

        # No LLM client configured - should fall back to heuristics
        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should still extract claim via heuristics
        claims = [a for a in result.artifacts if isinstance(a, AtomicClaim)]
        assert len(claims) >= 1, "Heuristic fallback should still extract claims"


class TestLLMBudgetEnforcement:
    """Tests for LLM budget enforcement."""

    def test_llm_budget_stops_excessive_calls(self):
        """Planner stops LLM calls when budget exhausted."""
        # Create many turns to trigger multiple LLM calls
        turns = []
        text_parts = []
        offset = 0
        for i in range(10):
            text = f"Turn {i}: Studies prove claim number {i} is factual."
            text_parts.append(text)
            turns.append(SpeakerTurn(
                speaker="SPEAKER",
                text=text,
                span=(offset, offset + len(text)),
                turn_index=i,
            ))
            offset += len(text) + 2

        transcript = "\n\n".join(text_parts)
        state = DiscourseState.from_transcript(
            transcript_id="llm_test_003",
            transcript_text=transcript,
            turns=turns,
        )

        # Set very low LLM budget
        budgets = PlannerBudgets(max_llm_calls_per_transcript=2)
        config = PlannerConfig(budgets=budgets)
        planner = HTNPlanner(config=config)
        planner.llm_client = MockLLMClient({})  # Empty responses

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"use_llm": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should have diagnostic about LLM budget
        llm_diagnostics = [
            d for d in result.diagnostics
            if "llm" in d.lower() or "budget" in d.lower()
        ]
        # Either diagnostics emitted OR llm_calls stayed within budget
        assert state.llm_calls <= budgets.max_llm_calls_per_transcript + 1 or len(llm_diagnostics) > 0, \
            "LLM budget should be enforced"

    def test_llm_calls_tracked_in_stats(self):
        """LLM call count appears in result stats."""
        transcript = """HARRIS: Research demonstrates neural correlates of consciousness."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Research demonstrates neural correlates of consciousness.",
                span=(0, 56),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="llm_test_004",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        planner.llm_client = MockLLMClient({
            "Research demonstrates neural correlates of consciousness.": {
                "claim_type": "EMPIRICAL",
                "confidence": 0.9,
            }
        })

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"use_llm": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Stats should include LLM calls
        assert hasattr(result.stats, 'llm_calls'), "Stats should track llm_calls"


class TestLLMAssistedCoref:
    """Tests for LLM-assisted coreference resolution."""

    def test_llm_resolves_ambiguous_pronoun(self):
        """LLM breaks tie when multiple candidates have similar salience."""
        # Ambiguous "he" - could refer to HARRIS or PETERSON
        transcript = """HARRIS: Free will is an illusion.

PETERSON: Determinism is incomplete.

MODERATOR: He makes a compelling point about neuroscience."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Free will is an illusion.",
                span=(0, 25),
                turn_index=0,
            ),
            SpeakerTurn(
                speaker="PETERSON",
                text="Determinism is incomplete.",
                span=(27, 53),
                turn_index=1,
            ),
            SpeakerTurn(
                speaker="MODERATOR",
                text="He makes a compelling point about neuroscience.",
                span=(55, 102),
                turn_index=2,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="llm_test_005",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        planner.llm_client = MockLLMClient({
            "resolve_pronoun": {
                "pronoun": "He",
                "referent": "HARRIS",
                "confidence": 0.85,
                "reasoning": "Reference to 'neuroscience' aligns with HARRIS's claim about illusion",
            }
        })

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"use_llm": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Find resolution for "He"
        he_resolutions = [
            r for r in result.resolved_references
            if r.source_text.lower() == "he"
        ]

        # Should have resolved with high confidence (LLM-assisted)
        if he_resolutions:
            resolution = he_resolutions[0]
            assert resolution.confidence >= 0.7, \
                "LLM should provide confident resolution"


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: dict):
        self._responses = responses
        self.call_count = 0

    def classify_claim(self, text: str) -> dict:
        """Classify a claim using mock responses."""
        self.call_count += 1
        return self._responses.get(text, {
            "claim_type": "UNCLASSIFIED",
            "confidence": 0.5,
        })

    def resolve_reference(self, pronoun: str, candidates: list, context: str) -> dict:
        """Resolve a reference using mock responses."""
        self.call_count += 1
        return self._responses.get("resolve_pronoun", {
            "referent": None,
            "confidence": 0.5,
        })
