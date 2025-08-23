"""Unit tests for claim filters to prevent regressions."""

import pytest
from debate_claim_extractor.pipeline.claim_filters import (
    BiographicalFilter,
    TruncationFragmentFilter, 
    ShowIntroPleasantryFilter,
    SponsorContentFilter,
    MetadataFilter,
    MinimumContentFilter,
    PronounVaguenessFilter,
    DiscourseFragmentFilter
)
from debate_claim_extractor.pipeline.models import Claim, ClaimType


class TestBiographicalFilter:
    def test_drops_personal_aside(self):
        c = Claim(text="I graduated high school in 1976", type="factual", should_fact_check=True)
        f = BiographicalFilter()
        should_exclude, reason = f.should_exclude("I graduated high school in 1976", c)
        assert should_exclude is True
        assert "biographical aside" in reason.lower()

    def test_drops_personal_memory(self):
        c = Claim(text="I remember when Nixon was president", type="factual", should_fact_check=True)
        f = BiographicalFilter()
        should_exclude, reason = f.should_exclude("I remember when Nixon was president", c)
        assert should_exclude is True

    def test_rescues_external_fact(self):
        c = Claim(text="I said NASA's 2019 budget rose 5% to $22 billion", type="factual", should_fact_check=True)
        f = BiographicalFilter()
        # External, checkable proposition with numbers and proper nouns → keep
        should_exclude, reason = f.should_exclude("I said NASA's 2019 budget rose 5% to $22 billion", c)
        assert should_exclude is False

    def test_rescues_long_external_claim(self):
        c = Claim(text="I told him that SpaceX successfully landed the Falcon Heavy boosters in February 2018", type="factual", should_fact_check=True)
        f = BiographicalFilter()
        should_exclude, reason = f.should_exclude("I told him that SpaceX successfully landed the Falcon Heavy boosters in February 2018", c)
        assert should_exclude is False


class TestTruncationFragmentFilter:
    def test_truncation_midword_tail(self):
        c = Claim(text="no I remember because it was like the b", type="factual", should_fact_check=True)
        f = TruncationFragmentFilter()
        should_exclude, reason = f.should_exclude("no I remember because it was like the b", c)
        assert should_exclude is True
        assert "mid-word" in reason.lower()

    def test_ellipsis_truncation(self):
        c = Claim(text="and then he said...", type="factual", should_fact_check=True)
        f = TruncationFragmentFilter()
        should_exclude, reason = f.should_exclude("and then he said...", c)
        assert should_exclude is True
        assert "ellipsis" in reason.lower()

    def test_conjunction_tail(self):
        c = Claim(text="the evidence suggests that climate change because", type="factual", should_fact_check=True)
        f = TruncationFragmentFilter()
        should_exclude, reason = f.should_exclude("the evidence suggests that climate change because", c)
        assert should_exclude is True
        assert "conjunction tail" in reason.lower()

    def test_filler_conjunction_lead(self):
        c = Claim(text="um and then he", type="factual", should_fact_check=True)
        f = TruncationFragmentFilter()
        should_exclude, reason = f.should_exclude("um and then he", c)
        assert should_exclude is True
        assert "filler" in reason.lower()

    def test_preserves_complete_sentences(self):
        c = Claim(text="The experiment showed clear results.", type="factual", should_fact_check=True)
        f = TruncationFragmentFilter()
        should_exclude, reason = f.should_exclude("The experiment showed clear results.", c)
        assert should_exclude is False


class TestShowIntroPleasantryFilter:
    def test_intro_pleasantry_filter_intro(self):
        c = Claim(text="This is StarTalk — I'm Neil, your personal astrophysicist", type="factual", should_fact_check=True)
        f = ShowIntroPleasantryFilter()
        should_exclude, reason = f.should_exclude("This is StarTalk — I'm Neil, your personal astrophysicist", c)
        assert should_exclude is True
        assert "intro" in reason.lower()

    def test_meta_control(self):
        c = Claim(text="let's get back to the show", type="factual", should_fact_check=True)
        f = ShowIntroPleasantryFilter()
        should_exclude, reason = f.should_exclude("let's get back to the show", c)
        assert should_exclude is True

    def test_pleasantry(self):
        c = Claim(text="thank you very much", type="factual", should_fact_check=True)
        f = ShowIntroPleasantryFilter()
        should_exclude, reason = f.should_exclude("thank you very much", c)
        assert should_exclude is True

    def test_preserves_substantive_content(self):
        c = Claim(text="The research shows that climate change is accelerating", type="factual", should_fact_check=True)
        f = ShowIntroPleasantryFilter()
        should_exclude, reason = f.should_exclude("The research shows that climate change is accelerating", c)
        assert should_exclude is False


class TestSponsorContentFilter:
    def test_promotional_content(self):
        c = Claim(text="head over to groundnews.com and use code STARTALK", type="factual", should_fact_check=True)
        f = SponsorContentFilter()
        should_exclude, reason = f.should_exclude("head over to groundnews.com and use code STARTALK", c)
        assert should_exclude is True
        assert "promotional" in reason.lower()

    def test_url_detection(self):
        c = Claim(text="visit https://example.com for more info", type="factual", should_fact_check=True)
        f = SponsorContentFilter()
        should_exclude, reason = f.should_exclude("visit https://example.com for more info", c)
        assert should_exclude is True

    def test_discount_pattern(self):
        c = Claim(text="save 40% on the Vantage plan", type="factual", should_fact_check=True)
        f = SponsorContentFilter()
        should_exclude, reason = f.should_exclude("save 40% on the Vantage plan", c)
        assert should_exclude is True

    def test_stateful_blocking(self):
        state = {"in_sponsor": False}
        c = Claim(text="this episode is sponsored by GroundNews", type="factual", should_fact_check=True)
        f = SponsorContentFilter(state=state)
        
        # First line should start block
        should_exclude, reason = f.should_exclude("this episode is sponsored by GroundNews", c)
        assert should_exclude is True
        assert state["in_sponsor"] is True
        
        # Next line should be blocked
        c2 = Claim(text="regular content that should be blocked", type="factual", should_fact_check=True)
        should_exclude, reason = f.should_exclude("regular content that should be blocked", c2)
        assert should_exclude is True
        
        # End block line
        c3 = Claim(text="let's get back to the show", type="factual", should_fact_check=True)
        should_exclude, reason = f.should_exclude("let's get back to the show", c3)
        assert should_exclude is True
        assert state["in_sponsor"] is False


class TestMetadataFilter:
    def test_title_without_predicate(self):
        c = Claim(text="Neil deGrasse Tyson Astrophysicist StarTalk", type="factual", should_fact_check=True)
        f = MetadataFilter()
        should_exclude, reason = f.should_exclude("Neil deGrasse Tyson Astrophysicist StarTalk", c)
        assert should_exclude is True
        assert "title" in reason.lower()

    def test_rescued_by_factual_verb(self):
        c = Claim(text="Neil deGrasse Tyson argues that dark matter exists", type="factual", should_fact_check=True)
        f = MetadataFilter()
        should_exclude, reason = f.should_exclude("Neil deGrasse Tyson argues that dark matter exists", c)
        assert should_exclude is False

    def test_rhetorical_question(self):
        c = Claim(text="What's the point of this discussion?", type="factual", should_fact_check=True)
        f = MetadataFilter()
        should_exclude, reason = f.should_exclude("What's the point of this discussion?", c)
        assert should_exclude is True
        assert "rhetorical" in reason.lower()


class TestMinimumContentFilter:
    def test_too_short_unanchored(self):
        c = Claim(text="it is good", type="factual", should_fact_check=True)
        f = MinimumContentFilter()
        should_exclude, reason = f.should_exclude("it is good", c)
        assert should_exclude is True
        assert "short" in reason.lower()

    def test_anchored_content_preserved(self):
        c = Claim(text="NASA spent $22 billion", type="factual", should_fact_check=True)
        f = MinimumContentFilter()
        should_exclude, reason = f.should_exclude("NASA spent $22 billion", c)
        assert should_exclude is False

    def test_filler_lead_insufficient(self):
        c = Claim(text="um like it was", type="factual", should_fact_check=True)
        f = MinimumContentFilter()
        should_exclude, reason = f.should_exclude("um like it was", c)
        assert should_exclude is True
        assert "filler" in reason.lower()

    def test_no_predicate_signal(self):
        c = Claim(text="just random words without structure", type="factual", should_fact_check=True)
        f = MinimumContentFilter()
        should_exclude, reason = f.should_exclude("just random words without structure", c)
        assert should_exclude is True
        assert "predicate" in reason.lower()


class TestPronounVaguenessFilter:
    def test_vague_pronoun_without_concrete(self):
        c = Claim(text="he was really good at it", type="factual", should_fact_check=True)
        f = PronounVaguenessFilter()
        should_exclude, reason = f.should_exclude("he was really good at it", c)
        assert should_exclude is True
        assert "vague pronoun" in reason.lower()

    def test_rescued_by_concrete_noun(self):
        c = Claim(text="he was the president of the university", type="factual", should_fact_check=True)
        f = PronounVaguenessFilter()
        should_exclude, reason = f.should_exclude("he was the president of the university", c)
        assert should_exclude is False

    def test_specific_entity_reference(self):
        c = Claim(text="it was discovered by NASA in 2019", type="factual", should_fact_check=True)
        f = PronounVaguenessFilter()
        # No concrete noun in the allowlist, should be excluded
        should_exclude, reason = f.should_exclude("it was discovered by NASA in 2019", c)
        assert should_exclude is True  # "NASA" is not in the concrete_nouns list


class TestDiscourseFragmentFilter:
    def test_discourse_fragment(self):
        c = Claim(text="well so you know what I mean", type="factual", should_fact_check=True)
        f = DiscourseFragmentFilter()
        should_exclude, reason = f.should_exclude("well so you know what I mean", c)
        assert should_exclude is True
        assert "discourse" in reason.lower()

    def test_incomplete_sentence(self):
        c = Claim(text="it was good", type="factual", should_fact_check=True)
        f = DiscourseFragmentFilter()
        should_exclude, reason = f.should_exclude("it was good", c)
        assert should_exclude is True

    def test_anchored_content_preserved(self):
        c = Claim(text="well the 2019 NASA budget was $22 billion", type="factual", should_fact_check=True)
        f = DiscourseFragmentFilter()
        should_exclude, reason = f.should_exclude("well the 2019 NASA budget was $22 billion", c)
        assert should_exclude is False  # Anchored by number and proper noun

    def test_normative_claim_excluded(self):
        c = Claim(text="this approach is better than that one", type="normative", should_fact_check=False)
        f = DiscourseFragmentFilter()
        should_exclude, reason = f.should_exclude("this approach is better than that one", c)
        assert should_exclude is True
        assert "normative" in reason.lower()
