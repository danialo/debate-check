"""Tests for coreference resolution - Phase 2 driver tests."""

import pytest

from debate_claim_extractor.htn import HTNPlanner, Task
from debate_claim_extractor.state import DiscourseState, SpeakerTurn
from debate_claim_extractor.artifacts import TentativeResolution


class TestCrossReferenceResolution:
    """Tests for cross-turn pronoun resolution."""

    def test_pronoun_resolves_to_previous_turn_entity(self):
        """'His methodology' in turn 2 should resolve to HARRIS from turn 1."""
        transcript = """HARRIS: Free will is an illusion. My studies prove this conclusively.

PETERSON: His methodology is fundamentally flawed."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Free will is an illusion. My studies prove this conclusively.",
                span=(0, 62),
                turn_index=0,
            ),
            SpeakerTurn(
                speaker="PETERSON",
                text="His methodology is fundamentally flawed.",
                span=(64, 104),
                turn_index=1,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="coref_test_001",
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

        # Should have at least one resolution
        resolutions = [
            a for a in result.artifacts
            if isinstance(a, TentativeResolution)
        ]
        assert len(resolutions) >= 1, "Expected at least one TentativeResolution artifact"

        # Find the "His" resolution (exact match to avoid matching "this")
        his_resolution = next(
            (r for r in resolutions if r.source_text.lower() == "his"),
            None
        )
        assert his_resolution is not None, "Expected resolution for 'His'"
        assert his_resolution.winner is not None, "Expected 'His' to resolve to an entity"

        # Should resolve to HARRIS (the previous speaker)
        resolved_entity = state.get_entity(his_resolution.winner)
        assert resolved_entity is not None, f"Entity {his_resolution.winner} not found"
        assert resolved_entity.canonical == "HARRIS", f"Expected HARRIS, got {resolved_entity.canonical}"
        assert his_resolution.confidence >= 0.7, f"Expected confidence >= 0.7, got {his_resolution.confidence}"


class TestDemonstrativeResolution:
    """Tests for demonstrative pronoun resolution (this, that, these)."""

    def test_this_resolves_to_previous_claim(self):
        """'this' should resolve to the claim in the previous sentence."""
        transcript = """HARRIS: Brain activity precedes conscious decision by 300 milliseconds. This proves free will is illusory."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="Brain activity precedes conscious decision by 300 milliseconds. This proves free will is illusory.",
                span=(0, 98),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="coref_test_002",
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

        # Should have resolution for "This"
        resolutions = [
            a for a in result.artifacts
            if isinstance(a, TentativeResolution)
        ]

        this_resolution = next(
            (r for r in resolutions if r.ref_type == "DEMONSTRATIVE"),
            None
        )
        assert this_resolution is not None, "Expected resolution for demonstrative 'This'"
        assert this_resolution.winner is not None, "Expected 'This' to resolve"
        # The resolved entity should be the claim about 300ms
        resolved_entity = state.get_entity(this_resolution.winner)
        assert resolved_entity is not None, f"Entity {this_resolution.winner} not found"
        assert resolved_entity.entity_type == "CLAIM", f"Expected CLAIM type, got {resolved_entity.entity_type}"
        assert "300" in resolved_entity.canonical or "brain" in resolved_entity.canonical.lower(), \
            f"Expected claim about brain/300ms, got: {resolved_entity.canonical}"


class TestEntityRegistration:
    """Tests for entity tracking during extraction."""

    def test_speaker_registered_as_entity(self):
        """Speakers should be registered as PERSON entities."""
        transcript = """HARRIS: Free will is an illusion.

PETERSON: I disagree."""

        turns = [
            SpeakerTurn(speaker="HARRIS", text="Free will is an illusion.", span=(0, 25), turn_index=0),
            SpeakerTurn(speaker="PETERSON", text="I disagree.", span=(27, 38), turn_index=1),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="entity_test_001",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        planner.run(root_task, state)

        # Both speakers should be registered as entities
        harris = state.find_entity_by_name("HARRIS")
        peterson = state.find_entity_by_name("PETERSON")

        assert harris is not None, "HARRIS should be registered as entity"
        assert peterson is not None, "PETERSON should be registered as entity"
        assert harris.entity_type == "PERSON"
        assert peterson.entity_type == "PERSON"


class TestSalienceTracking:
    """Tests for salience stack behavior."""

    def test_most_recent_entity_is_most_salient(self):
        """Most recently mentioned entity should be at top of salience stack."""
        transcript = """HARRIS: The Libet experiments showed something important. Benjamin Libet proved this in 1983."""

        turns = [
            SpeakerTurn(
                speaker="HARRIS",
                text="The Libet experiments showed something important. Benjamin Libet proved this in 1983.",
                span=(0, 85),
                turn_index=0,
            ),
        ]
        state = DiscourseState.from_transcript(
            transcript_id="salience_test_001",
            transcript_text=transcript,
            turns=turns,
        )

        planner = HTNPlanner()
        root_task = Task.create(
            task_type="DECOMPOSE_TRANSCRIPT",
            params={},
            span=(0, len(transcript)),
        )

        planner.run(root_task, state)

        # Get salient entities (no speaker filter - entities are tracked globally)
        salient = state.get_salient_entities(limit=5)

        # Should have some salient entities
        assert len(salient) > 0, "Expected some salient entities"

        # The most salient entity should be from this turn
        # Either a claim or HARRIS (the speaker)
        top_entity = state.get_entity(salient[0])
        assert top_entity is not None, "Top salient entity not found"
        assert top_entity.entity_type in ("CLAIM", "PERSON"), \
            f"Expected CLAIM or PERSON, got {top_entity.entity_type}"
