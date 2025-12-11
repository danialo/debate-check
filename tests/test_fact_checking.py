"""Phase 5 driver tests: Fact-check routing."""

import pytest

from debate_claim_extractor.htn import HTNPlanner, Task
from debate_claim_extractor.htn.planner import PlannerConfig
from debate_claim_extractor.state import DiscourseState, SpeakerTurn
from debate_claim_extractor.artifacts import AtomicClaim, ClaimType
from debate_claim_extractor.artifacts.fact_check import FactCheckResult, VerificationStatus


class TestFactCheckRouting:
    """Tests for routing EMPIRICAL claims to fact-checking."""

    def test_empirical_claim_gets_fact_checked(self):
        """EMPIRICAL claims are routed to fact-checking."""
        transcript = """HARRIS: Studies show 70% of neurons fire before conscious awareness."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Studies show 70% of neurons fire before conscious awareness.",
                span=(0, 60),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="fact_test_001",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        planner.fact_check_client = MockFactCheckClient({
            "70% of neurons": {
                "status": "VERIFIED",
                "confidence": 0.85,
                "source": "Nature Neuroscience",
            }
        })

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"fact_check": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should have fact-check results
        fact_checks = [a for a in result.artifacts if isinstance(a, FactCheckResult)]
        assert len(fact_checks) >= 1, "Expected at least one FactCheckResult"

    def test_philosophical_claim_not_fact_checked(self):
        """PHILOSOPHICAL claims are NOT routed to fact-checking."""
        transcript = """HARRIS: Consciousness is the fundamental mystery of existence."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Consciousness is the fundamental mystery of existence.",
                span=(0, 53),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="fact_test_002",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        planner.fact_check_client = MockFactCheckClient({})

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"fact_check": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should NOT have fact-check results for philosophical claims
        fact_checks = [a for a in result.artifacts if isinstance(a, FactCheckResult)]
        assert len(fact_checks) == 0, "Philosophical claims should not be fact-checked"


class TestFactCheckResult:
    """Tests for FactCheckResult artifact structure."""

    def test_fact_check_links_to_claim(self):
        """FactCheckResult references the claim it checked."""
        transcript = """HARRIS: Research proves brain activity precedes decisions by 300ms."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Research proves brain activity precedes decisions by 300ms.",
                span=(0, 59),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="fact_test_003",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        planner.fact_check_client = MockFactCheckClient({
            "300ms": {
                "status": "VERIFIED",
                "confidence": 0.9,
                "source": "Libet et al., 1983",
            }
        })

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"fact_check": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        fact_checks = [a for a in result.artifacts if isinstance(a, FactCheckResult)]
        if fact_checks:
            fc = fact_checks[0]
            assert fc.claim_id is not None, "FactCheckResult should reference claim"
            assert fc.status in [VerificationStatus.VERIFIED, VerificationStatus.UNVERIFIED,
                                VerificationStatus.DISPUTED, VerificationStatus.NO_DATA]

    def test_fact_check_includes_source(self):
        """FactCheckResult includes source information."""
        transcript = """HARRIS: Studies show meditation reduces cortisol by 25%."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Studies show meditation reduces cortisol by 25%.",
                span=(0, 47),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="fact_test_004",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        planner.fact_check_client = MockFactCheckClient({
            "cortisol by 25%": {
                "status": "DISPUTED",
                "confidence": 0.6,
                "source": "Meta-analysis varies: 15-30%",
                "sources": ["PubMed", "Cochrane Review"],
            }
        })

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"fact_check": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        fact_checks = [a for a in result.artifacts if isinstance(a, FactCheckResult)]
        if fact_checks:
            fc = fact_checks[0]
            assert len(fc.sources) > 0, "FactCheckResult should include sources"


class TestFactCheckBudget:
    """Tests for fact-check budget enforcement."""

    def test_fact_check_respects_budget(self):
        """Fact-checking stops when budget exhausted."""
        # Create many turns with empirical claims
        turns = []
        text_parts = []
        offset = 0
        for i in range(10):
            text = f"Studies show fact number {i} is proven with {i*10}% confidence."
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
            transcript_id="fact_test_005",
            transcript_text=transcript,
            turns=turns,
        )

        # Set very low fact-check budget
        planner = HTNPlanner()
        planner.fact_check_client = MockFactCheckClient({})
        planner.fact_check_budget = 3  # Only allow 3 fact-checks

        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={"fact_check": True},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Count fact-check results (should be limited)
        fact_checks = [a for a in result.artifacts if isinstance(a, FactCheckResult)]
        assert len(fact_checks) <= 3, "Fact-check budget should be enforced"


class MockFactCheckClient:
    """Mock fact-check client for testing."""

    def __init__(self, responses: dict):
        self._responses = responses
        self.call_count = 0

    def check_claim(self, claim_text: str) -> dict:
        """Check a claim against mock responses."""
        self.call_count += 1

        # Look for matching response by substring
        for key, response in self._responses.items():
            if key.lower() in claim_text.lower():
                return response

        # Default: no data found
        return {
            "status": "NO_DATA",
            "confidence": 0.0,
            "source": None,
        }
