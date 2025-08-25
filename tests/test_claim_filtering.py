"""
Test suite for claim filtering and classification improvements
"""

import pytest
from debate_claim_extractor.pipeline.models import Claim, ClaimType, Sentence
from debate_claim_extractor.pipeline.claim_filters import (
    ConversationalFilter, 
    QuestionFilter, 
    HypotheticalFilter, 
    ClaimTypeClassifier,
    ImprovedClaimFilteringSystem
)
from debate_claim_extractor.pipeline.enhanced_postprocessor import EnhancedClaimPostprocessor


class TestConversationalFilter:
    """Test conversational filler filtering"""
    
    def test_filters_simple_fillers(self):
        filter_obj = ConversationalFilter()
        
        # Test cases that should be filtered out
        test_cases = [
            "yeah",
            "yes", 
            "no",
            "right",
            "okay",
            "mhm",
            "yeah right",
            "yes sure"
        ]
        
        for text in test_cases:
            claim = Claim(type=ClaimType.FACTUAL, text=text, speaker="TEST", 
                         sentence_id="123", turn_id=0, char_start=0, char_end=len(text))
            should_exclude, reason = filter_obj.should_exclude(text, claim)
            assert should_exclude, f"Should filter out: '{text}' - {reason}"
    
    def test_filters_topic_introductions(self):
        filter_obj = ConversationalFilter()
        
        # Test cases that should be filtered out as topic introductions
        test_cases = [
            "Charles I want to compare notes okay on free will",
            "I want to compare notes about determinism",
            "Bob I want to compare notes okay on philosophy"
        ]
        
        for text in test_cases:
            claim = Claim(type=ClaimType.FACTUAL, text=text, speaker="TEST", 
                         sentence_id="123", turn_id=0, char_start=0, char_end=len(text))
            should_exclude, reason = filter_obj.should_exclude(text, claim)
            assert should_exclude, f"Should filter out topic introduction: '{text}' - {reason}"
            assert "Topic introduction" in reason
    
    def test_allows_substantive_claims(self):
        filter_obj = ConversationalFilter()
        
        # Test cases that should NOT be filtered out
        test_cases = [
            "Climate change is real",
            "The data shows significant warming",
            "I believe free will exists in some form",
            "This policy will reduce emissions"
        ]
        
        for text in test_cases:
            claim = Claim(type=ClaimType.FACTUAL, text=text, speaker="TEST", 
                         sentence_id="123", turn_id=0, char_start=0, char_end=len(text))
            should_exclude, reason = filter_obj.should_exclude(text, claim)
            assert not should_exclude, f"Should NOT filter out: '{text}' - {reason}"


class TestQuestionFilter:
    """Test question filtering"""
    
    def test_filters_direct_questions(self):
        filter_obj = QuestionFilter()
        
        test_cases = [
            "What do you think about free will?",
            "How does this work?",
            "Are you sure about that?",
            "Do you have evidence for this claim?"
        ]
        
        for text in test_cases:
            claim = Claim(type=ClaimType.FACTUAL, text=text, speaker="TEST", 
                         sentence_id="123", turn_id=0, char_start=0, char_end=len(text))
            should_exclude, reason = filter_obj.should_exclude(text, claim)
            assert should_exclude, f"Should filter out question: '{text}' - {reason}"
    
    def test_allows_statements(self):
        filter_obj = QuestionFilter()
        
        test_cases = [
            "I think free will exists.",
            "The evidence suggests otherwise.", 
            "This is a factual claim.",
            "We need to consider the data."
        ]
        
        for text in test_cases:
            claim = Claim(type=ClaimType.FACTUAL, text=text, speaker="TEST", 
                         sentence_id="123", turn_id=0, char_start=0, char_end=len(text))
            should_exclude, reason = filter_obj.should_exclude(text, claim)
            assert not should_exclude, f"Should NOT filter out statement: '{text}' - {reason}"


class TestHypotheticalFilter:
    """Test hypothetical scenario filtering"""
    
    def test_filters_hypotheticals(self):
        filter_obj = HypotheticalFilter()
        
        test_cases = [
            "Let's say you're in a room with audience members",
            "Suppose we have a deterministic universe",
            "Imagine if free will didn't exist",
            "What if we could predict the future?",
            "For example, consider a football player"
        ]
        
        for text in test_cases:
            claim = Claim(type=ClaimType.FACTUAL, text=text, speaker="TEST", 
                         sentence_id="123", turn_id=0, char_start=0, char_end=len(text))
            should_exclude, reason = filter_obj.should_exclude(text, claim)
            assert should_exclude, f"Should filter out hypothetical: '{text}' - {reason}"
    
    def test_allows_direct_claims(self):
        filter_obj = HypotheticalFilter()
        
        test_cases = [
            "Climate change is caused by human activity",
            "The study found significant results",
            "Free will is an important philosophical concept",
            "This policy has been implemented successfully"
        ]
        
        for text in test_cases:
            claim = Claim(type=ClaimType.FACTUAL, text=text, speaker="TEST", 
                         sentence_id="123", turn_id=0, char_start=0, char_end=len(text))
            should_exclude, reason = filter_obj.should_exclude(text, claim)
            assert not should_exclude, f"Should NOT filter out direct claim: '{text}' - {reason}"


class TestClaimTypeClassifier:
    """Test philosophical vs empirical claim classification"""
    
    def test_identifies_philosophical_claims(self):
        classifier = ClaimTypeClassifier()
        
        test_cases = [
            "Free will is fundamental to human agency",
            "I believe moral responsibility requires choice",
            "Determinism challenges our notion of justice",
            "We should treat people with compassion",
            "This is ethically wrong",
        ]
        
        for text in test_cases:
            claim_type, should_fact_check, reason = classifier.classify_claim_nature(text, ClaimType.FACTUAL)
            assert claim_type == ClaimType.NORMATIVE, f"Should classify as normative: '{text}' - {reason}"
            assert not should_fact_check, f"Should not fact-check philosophical claim: '{text}'"
    
    def test_identifies_empirical_claims(self):
        classifier = ClaimTypeClassifier()
        
        test_cases = [
            "The study shows correlation between variables",
            "According to the research, temperatures have risen",
            "Data suggests this trend will continue", 
            "Evidence indicates a strong relationship"
        ]
        
        for text in test_cases:
            claim_type, should_fact_check, reason = classifier.classify_claim_nature(text, ClaimType.FACTUAL)
            assert claim_type == ClaimType.FACTUAL, f"Should remain factual: '{text}' - {reason}"
            assert should_fact_check, f"Should fact-check empirical claim: '{text}'"


class TestImprovedClaimFilteringSystem:
    """Test the integrated filtering system"""
    
    def test_filters_conversational_fillers(self):
        system = ImprovedClaimFilteringSystem()
        
        # Create test claims including fillers
        claims = [
            Claim(type=ClaimType.FACTUAL, text="yeah", speaker="SPEAKER_A", 
                 sentence_id="1", turn_id=0, char_start=0, char_end=4),
            Claim(type=ClaimType.FACTUAL, text="Climate change is real", speaker="SPEAKER_A", 
                 sentence_id="2", turn_id=0, char_start=5, char_end=27),
            Claim(type=ClaimType.FACTUAL, text="mhm", speaker="SPEAKER_B", 
                 sentence_id="3", turn_id=1, char_start=0, char_end=3),
            Claim(type=ClaimType.CAUSAL, text="I believe free will exists because we make choices", speaker="SPEAKER_B", 
                 sentence_id="4", turn_id=1, char_start=4, char_end=54)
        ]
        
        filtered_claims = system.filter_and_classify_claims(claims)
        
        # Should filter out conversational fillers
        assert len(filtered_claims) == 2, "Should filter out 2 conversational fillers"
        
        # Remaining claims should be substantive
        claim_texts = [claim.text for claim in filtered_claims]
        assert "yeah" not in claim_texts
        assert "mhm" not in claim_texts
        assert "Climate change is real" in claim_texts
        assert "I believe free will exists because we make choices" in claim_texts
    
    def test_classifies_philosophical_vs_empirical(self):
        system = ImprovedClaimFilteringSystem()
        
        claims = [
            Claim(type=ClaimType.FACTUAL, text="Free will is fundamental to human dignity", 
                 speaker="SPEAKER_A", sentence_id="1", turn_id=0, char_start=0, char_end=43),
            Claim(type=ClaimType.FACTUAL, text="The study measured brain activity in 100 subjects", 
                 speaker="SPEAKER_B", sentence_id="2", turn_id=1, char_start=0, char_end=49)
        ]
        
        filtered_claims = system.filter_and_classify_claims(claims)
        
        assert len(filtered_claims) == 2, "Should keep both claims"
        
        # Find each claim
        philosophical_claim = next(c for c in filtered_claims if "dignity" in c.text)
        empirical_claim = next(c for c in filtered_claims if "study" in c.text)
        
        # Check classifications
        assert philosophical_claim.type == ClaimType.NORMATIVE, "Should classify philosophical claim as normative"
        assert not philosophical_claim.should_fact_check, "Should not fact-check philosophical claim"
        
        assert empirical_claim.type == ClaimType.FACTUAL, "Should keep empirical claim as factual"
        assert empirical_claim.should_fact_check, "Should fact-check empirical claim"


def test_enhanced_postprocessor_integration():
    """Test that enhanced postprocessor correctly integrates filtering"""
    
    # Create test claims and sentences
    sentences = [
        Sentence(text="yeah", speaker="SPEAKER_A", turn_id=0, sentence_index=0, char_start=0, char_end=4),
        Sentence(text="Climate change is a serious threat", speaker="SPEAKER_A", turn_id=0, sentence_index=1, char_start=5, char_end=39),
        Sentence(text="I believe we have moral obligations to act", speaker="SPEAKER_B", turn_id=1, sentence_index=0, char_start=0, char_end=42)
    ]
    
    claims = [
        Claim(type=ClaimType.FACTUAL, text="yeah", speaker="SPEAKER_A", 
             sentence_id=sentences[0].id, turn_id=0, char_start=0, char_end=4),
        Claim(type=ClaimType.FACTUAL, text="Climate change is a serious threat", speaker="SPEAKER_A", 
             sentence_id=sentences[1].id, turn_id=0, char_start=5, char_end=39),
        Claim(type=ClaimType.FACTUAL, text="I believe we have moral obligations to act", speaker="SPEAKER_B", 
             sentence_id=sentences[2].id, turn_id=1, char_start=0, char_end=42)
    ]
    
    processor = EnhancedClaimPostprocessor(enable_filtering=True)
    processed_claims = processor.process(claims, sentences)
    
    # Should filter out "yeah" and classify the philosophical claim
    assert len(processed_claims) == 2, "Should filter out conversational filler"
    
    claim_texts = [claim.text for claim in processed_claims]
    assert "yeah" not in claim_texts, "Should filter out 'yeah'"
    assert "Climate change is a serious threat" in claim_texts
    assert "I believe we have moral obligations to act" in claim_texts
    
    # Check that philosophical claim was reclassified
    moral_claim = next(c for c in processed_claims if "moral obligations" in c.text)
    assert moral_claim.type == ClaimType.NORMATIVE, "Should classify moral claim as normative"
    assert not moral_claim.should_fact_check, "Should not fact-check normative claim"


if __name__ == "__main__":
    pytest.main([__file__])
