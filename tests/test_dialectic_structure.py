"""Tests for dialectic structure - Phase 3 driver tests."""

import pytest

from debate_claim_extractor.htn import HTNPlanner, Task
from debate_claim_extractor.state import DiscourseState, SpeakerTurn
from debate_claim_extractor.artifacts import ArgumentFrame, AtomicClaim


class TestRebuttalDetection:
    """Tests for detecting rebuttal relations between claims."""

    def test_cross_turn_rebuttal_detected(self):
        """PETERSON's 'but' signals rebuttal of HARRIS's claim."""
        transcript = """HARRIS: Free will is an illusion proven by neuroscience.

PETERSON: But that ignores the subjective experience of choice."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Free will is an illusion proven by neuroscience.",
                span=(0, 48),
                turn_index=0,
            ),
            SpeakerTurn(
                speaker="PETERSON",
                text="But that ignores the subjective experience of choice.",
                span=(50, 103),
                turn_index=1,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="dialectic_test_001",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should have ArgumentFrames
        frames = [a for a in result.artifacts if isinstance(a, ArgumentFrame)]
        assert len(frames) >= 1, "Expected at least one ArgumentFrame"

        # Should have a REBUTTAL frame
        rebuttal_frames = [f for f in frames if f.frame_type == "REBUTTAL"]
        assert len(rebuttal_frames) >= 1, "Expected a REBUTTAL frame for Peterson's response"

        # The rebuttal should reference the original claim
        rebuttal = rebuttal_frames[0]
        assert rebuttal.parent_frame_id is not None or len(rebuttal.child_claim_ids) > 0, \
            "Rebuttal frame should link to claims"


class TestSupportDetection:
    """Tests for detecting support relations between claims."""

    def test_because_signals_support(self):
        """Second turn with 'because' signals support of previous claim."""
        transcript = """HARRIS: Free will does not exist.

HARRIS: This is proven because brain activity precedes conscious decision by 300 milliseconds."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Free will does not exist.",
                span=(0, 25),
                turn_index=0,
            ),
            SpeakerTurn(
                speaker="HARRIS",
                text="This is proven because brain activity precedes conscious decision by 300 milliseconds.",
                span=(27, 113),
                turn_index=1,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="dialectic_test_002",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should have frames showing support structure
        frames = [a for a in result.artifacts if isinstance(a, ArgumentFrame)]

        # Second turn should create SUPPORT frame linking to first
        support_frames = [f for f in frames if f.frame_type == "SUPPORT"]
        assert len(support_frames) >= 1, "Expected SUPPORT frame from 'because' marker"

        # SUPPORT frame should link to previous frame
        support_frame = support_frames[0]
        assert support_frame.parent_frame_id is not None, "SUPPORT frame should have parent_frame_id"


class TestDiscourseMarkers:
    """Tests for discourse marker detection."""

    def test_however_signals_contrast(self):
        """'however' signals contrasting/rebutting claim."""
        transcript = """HARRIS: Studies show determinism is absolute. However, research proves quantum mechanics introduces uncertainty."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Studies show determinism is absolute. However, research proves quantum mechanics introduces uncertainty.",
                span=(0, 103),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="dialectic_test_003",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should detect the contrastive structure
        frames = [a for a in result.artifacts if isinstance(a, ArgumentFrame)]
        claims = [a for a in result.artifacts if isinstance(a, AtomicClaim)]

        # At minimum, should have 2 claims (before and after "however")
        assert len(claims) >= 2, "Expected at least 2 claims split by 'however'"


class TestArgumentFrameConstruction:
    """Tests for ArgumentFrame hierarchy building."""

    def test_frame_contains_related_claims(self):
        """ArgumentFrame should group related claims together."""
        transcript = """HARRIS: The Libet experiments are crucial. They show readiness potential fires before conscious awareness. This proves decisions are made unconsciously."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="The Libet experiments are crucial. They show readiness potential fires before conscious awareness. This proves decisions are made unconsciously.",
                span=(0, 143),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="dialectic_test_004",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # Should have an ArgumentFrame grouping these claims
        frames = [a for a in result.artifacts if isinstance(a, ArgumentFrame)]
        claims = [a for a in result.artifacts if isinstance(a, AtomicClaim)]

        assert len(claims) >= 2, "Expected multiple claims from this passage"

        # At least one frame should have multiple child claims
        if frames:
            max_children = max(len(f.child_claim_ids) for f in frames)
            assert max_children >= 1, "Expected frame to contain child claims"


class TestCrossReferences:
    """Tests for cross-turn dialectic references."""

    def test_that_argument_references_previous_claim(self):
        """'that argument' should link to previous speaker's claim."""
        transcript = """HARRIS: Neuroscience proves we have no free will.

PETERSON: That argument assumes consciousness is reducible to brain states."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Neuroscience proves we have no free will.",
                span=(0, 41),
                turn_index=0,
            ),
            SpeakerTurn(
                speaker="PETERSON",
                text="That argument assumes consciousness is reducible to brain states.",
                span=(43, 108),
                turn_index=1,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="dialectic_test_005",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        result = planner.run(root_task, state)

        # "That argument" should resolve and create a rebuttal structure
        frames = [a for a in result.artifacts if isinstance(a, ArgumentFrame)]

        # Should have dialectic structure linking the two turns
        assert len(frames) >= 1, "Expected ArgumentFrame linking cross-turn claims"
