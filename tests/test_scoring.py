"""
Comprehensive unit tests for the multi-dimensional scoring system.
"""

import pytest
import math
from typing import List, Dict
from unittest.mock import Mock, patch

from debate_claim_extractor.pipeline.models import Claim, ExtractionResult
from debate_claim_extractor.fact_checking.fact_models import FactCheckResult, VerificationStatus
from debate_claim_extractor.fallacy_detection.fallacy_models import FallacyResult, FallacyType, FallacySeverity
from debate_claim_extractor.scoring import (
    ScoringPipeline, ScoringConfig, SpeakerScore, DebateScore, ArgumentScore,
    ScoringResult
)
from debate_claim_extractor.scoring.scorers import (
    DebateQualityScorer, SpeakerCredibilityScorer, ArgumentStrengthScorer,
    OverallDebateScorer
)


class TestScoringConfig:
    """Test scoring configuration validation and defaults."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ScoringConfig()
        assert config.claim_confidence_weight == 0.3
        assert config.fact_check_weight == 0.4
        assert config.fallacy_penalty_weight == 0.3
        assert config.high_confidence_threshold == 0.7
        assert config.medium_confidence_threshold == 0.5
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ScoringConfig(
            claim_confidence_weight=0.5,
            fact_check_weight=0.3,
            fallacy_penalty_weight=0.2,
            high_confidence_threshold=0.8,
            medium_confidence_threshold=0.6
        )
        assert config.claim_confidence_weight == 0.5
        assert config.fact_check_weight == 0.3
        assert config.fallacy_penalty_weight == 0.2
        assert config.high_confidence_threshold == 0.8
        assert config.medium_confidence_threshold == 0.6
    
    def test_config_validation(self):
        """Test configuration validation with invalid values."""
        from pydantic import ValidationError
        
        # Test weight validation
        with pytest.raises(ValidationError):
            ScoringConfig(claim_confidence_weight=-0.1)
        
        with pytest.raises(ValidationError):
            ScoringConfig(fact_check_weight=1.5)
        
        # Test threshold validation
        with pytest.raises(ValidationError):
            ScoringConfig(high_confidence_threshold=-0.1)
        
        with pytest.raises(ValidationError):
            ScoringConfig(medium_confidence_threshold=1.5)


class TestDebateQualityScorer:
    """Test the debate quality scoring algorithms."""
    
    @pytest.fixture
    def scorer(self):
        return DebateQualityScorer(ScoringConfig())
    
    @pytest.fixture
    def sample_claims(self):
        return [
            Claim(
                id="claim_1", type="statistical", text="GDP grew by 3.2%",
                speaker="SPEAKER_A", confidence=0.8,
                sentence_id="sent_1", turn_id=1, char_start=0, char_end=15
            ),
            Claim(
                id="claim_2", type="factual", text="Climate change is real",
                speaker="SPEAKER_B", confidence=0.9,
                sentence_id="sent_2", turn_id=2, char_start=16, char_end=38
            ),
            Claim(
                id="claim_3", type="comparative", text="Plan A is better than Plan B",
                speaker="SPEAKER_A", confidence=0.6,
                sentence_id="sent_3", turn_id=3, char_start=39, char_end=67
            )
        ]
    
    def test_information_quality_without_fact_checking(self, scorer, sample_claims):
        """Test information quality calculation without fact-checking."""
        quality_score = scorer.calculate_information_quality(sample_claims)
        
        # Should be average confidence: (0.8 + 0.9 + 0.6) / 3 = 0.767
        expected_score = (0.8 + 0.9 + 0.6) / 3
        assert abs(quality_score - expected_score) < 0.01
    
    def test_information_quality_with_fact_checking(self, scorer, sample_claims):
        """Test information quality with fact-checking boost."""
        fact_results = [
            FactCheckResult(
                claim_id="claim_1", service_name="test", query="GDP", claim_text="GDP grew by 3.2%",
                status=VerificationStatus.LIKELY_TRUE, confidence=0.8, verification_score=0.8
            ),
            FactCheckResult(
                claim_id="claim_2", service_name="test", query="climate", claim_text="Climate change is real",
                status=VerificationStatus.VERIFIED_TRUE, confidence=0.9, verification_score=0.95
            )
        ]
        
        quality_score = scorer.calculate_information_quality(sample_claims, fact_results)
        
        # Should have positive boost from verified claims
        base_confidence = (0.8 + 0.9 + 0.6) / 3  # 0.767
        assert quality_score > base_confidence
    
    def test_logical_consistency_no_fallacies(self, scorer):
        """Test logical consistency with no fallacies."""
        consistency_score = scorer.calculate_logical_consistency(fallacies=[], total_claims=5)
        assert consistency_score == 1.0
    
    def test_logical_consistency_with_fallacies(self, scorer):
        """Test logical consistency with various fallacies."""
        fallacies = [
            FallacyResult(
                id="f1", type=FallacyType.AD_HOMINEM, text="You're wrong",
                speaker="SPEAKER_A", confidence=0.8, severity=FallacySeverity.HIGH
            ),
            FallacyResult(
                id="f2", type=FallacyType.FALSE_DILEMMA, text="Either this or that",
                speaker="SPEAKER_B", confidence=0.7, severity=FallacySeverity.MEDIUM
            )
        ]
        
        consistency_score = scorer.calculate_logical_consistency(fallacies, total_claims=10)
        
        # Should be less than 1.0 due to fallacy penalties
        assert consistency_score < 1.0
        assert consistency_score > 0.0  # But not zero
    
    def test_factual_accuracy_mixed_results(self, scorer):
        """Test factual accuracy with mixed verification results."""
        fact_results = [
            FactCheckResult(
                claim_id="c1", service_name="test", query="test1", claim_text="claim1",
                status=VerificationStatus.VERIFIED_TRUE, confidence=0.9, verification_score=1.0
            ),
            FactCheckResult(
                claim_id="c2", service_name="test", query="test2", claim_text="claim2", 
                status=VerificationStatus.LIKELY_FALSE, confidence=0.8, verification_score=0.2
            ),
            FactCheckResult(
                claim_id="c3", service_name="test", query="test3", claim_text="claim3",
                status=VerificationStatus.MIXED, confidence=0.7, verification_score=0.5
            )
        ]
        
        accuracy_score = scorer.calculate_factual_accuracy(fact_results)
        
        # Should be between 0 and 1
        assert 0.0 <= accuracy_score <= 1.0
        # Should be around the weighted average
        assert 0.4 <= accuracy_score <= 0.8
    
    def test_empty_inputs(self, scorer):
        """Test scoring with empty inputs."""
        assert scorer.calculate_information_quality([]) == 0.0
        assert scorer.calculate_logical_consistency(None, 0) == 1.0
        assert scorer.calculate_factual_accuracy(None) == 0.5
        assert scorer.calculate_factual_accuracy([]) == 0.5


class TestSpeakerCredibilityScorer:
    """Test individual speaker scoring."""
    
    @pytest.fixture
    def scorer(self):
        return SpeakerCredibilityScorer(ScoringConfig())
    
    @pytest.fixture
    def multi_speaker_claims(self):
        return [
            Claim(
                id="c1", type="factual", text="Statement 1", speaker="ALICE",
                confidence=0.8, sentence_id="s1", turn_id=1, char_start=0, char_end=11
            ),
            Claim(
                id="c2", type="statistical", text="Statement 2", speaker="ALICE", 
                confidence=0.9, sentence_id="s2", turn_id=1, char_start=12, char_end=23
            ),
            Claim(
                id="c3", type="comparative", text="Statement 3", speaker="BOB",
                confidence=0.6, sentence_id="s3", turn_id=2, char_start=24, char_end=35
            ),
            Claim(
                id="c4", type="causal", text="Statement 4", speaker="BOB",
                confidence=0.7, sentence_id="s4", turn_id=2, char_start=36, char_end=47
            )
        ]
    
    def test_speaker_grouping(self, scorer, multi_speaker_claims):
        """Test that claims are properly grouped by speaker."""
        speaker_scores = scorer.calculate_speaker_scores(multi_speaker_claims)
        
        assert "ALICE" in speaker_scores
        assert "BOB" in speaker_scores
        
        alice_score = speaker_scores["ALICE"]
        bob_score = speaker_scores["BOB"]
        
        assert alice_score.total_claims == 2
        assert bob_score.total_claims == 2
    
    def test_confidence_calculation(self, scorer, multi_speaker_claims):
        """Test speaker confidence calculations."""
        speaker_scores = scorer.calculate_speaker_scores(multi_speaker_claims)
        
        alice_score = speaker_scores["ALICE"]
        bob_score = speaker_scores["BOB"]
        
        # ALICE: (0.8 + 0.9) / 2 = 0.85
        assert abs(alice_score.claim_confidence - 0.85) < 0.01
        
        # BOB: (0.6 + 0.7) / 2 = 0.65  
        assert abs(bob_score.claim_confidence - 0.65) < 0.01
    
    def test_fallacy_penalty_calculation(self, scorer, multi_speaker_claims):
        """Test fallacy penalty calculations for speakers."""
        fallacies = [
            FallacyResult(
                id="f1", type=FallacyType.AD_HOMINEM, text="Attack",
                speaker="ALICE", confidence=0.9, severity=FallacySeverity.HIGH
            )
        ]
        
        speaker_scores = scorer.calculate_speaker_scores(
            multi_speaker_claims, fallacies=fallacies
        )
        
        alice_score = speaker_scores["ALICE"]
        bob_score = speaker_scores["BOB"]
        
        # ALICE should have fallacy penalty
        assert alice_score.fallacies_committed == 1
        assert alice_score.fallacy_penalty > 0
        
        # BOB should have no penalty
        assert bob_score.fallacies_committed == 0
        assert bob_score.fallacy_penalty == 0
    
    def test_credibility_score_calculation(self, scorer, multi_speaker_claims):
        """Test overall credibility score calculation."""
        speaker_scores = scorer.calculate_speaker_scores(multi_speaker_claims)
        
        for speaker, score in speaker_scores.items():
            # Credibility should be between 0 and 1
            assert 0.0 <= score.credibility_score <= 1.0
            
            # Should incorporate confidence, fact-checking, and fallacy penalty
            assert isinstance(score.credibility_score, float)


class TestArgumentStrengthScorer:
    """Test argument strength scoring."""
    
    @pytest.fixture  
    def scorer(self):
        return ArgumentStrengthScorer(ScoringConfig())
    
    @pytest.fixture
    def high_confidence_claims(self):
        return [
            Claim(
                id="c1", type="statistical", text="Strong statistical claim",
                speaker="SPEAKER", confidence=0.9,
                sentence_id="s1", turn_id=1, char_start=0, char_end=25
            ),
            Claim(
                id="c2", type="factual", text="Well-supported factual claim",
                speaker="SPEAKER", confidence=0.8,
                sentence_id="s2", turn_id=1, char_start=26, char_end=54
            ),
            Claim(
                id="c3", type="comparative", text="Weak comparison",
                speaker="SPEAKER", confidence=0.4,  # Below medium threshold
                sentence_id="s3", turn_id=1, char_start=55, char_end=70
            )
        ]
    
    def test_argument_filtering_by_confidence(self, scorer, high_confidence_claims):
        """Test that only high-confidence claims become arguments."""
        config = ScoringConfig(medium_confidence_threshold=0.5)
        scorer = ArgumentStrengthScorer(config)
        
        argument_scores = scorer.calculate_argument_scores(high_confidence_claims)
        
        # Should only analyze 2 claims (0.9 and 0.8 confidence, not 0.4)
        assert len(argument_scores) == 2
    
    def test_evidence_score_with_fact_checking(self, scorer, high_confidence_claims):
        """Test evidence scoring with fact-checking results."""
        fact_results = [
            FactCheckResult(
                claim_id="c1", service_name="test", query="test", claim_text="test",
                status=VerificationStatus.VERIFIED_TRUE, confidence=0.9, verification_score=0.95
            )
        ]
        
        argument_scores = scorer.calculate_argument_scores(
            high_confidence_claims, fact_results=fact_results
        )
        
        # Find the argument that was fact-checked
        fact_checked_arg = next(
            (arg for arg in argument_scores if "c1" in arg.claim_ids), None
        )
        
        assert fact_checked_arg is not None
        assert fact_checked_arg.evidence_score > 0.5  # Should be boosted by verification
        assert fact_checked_arg.verified_claims_count == 1
    
    def test_logic_score_with_fallacies(self, scorer, high_confidence_claims):
        """Test logic scoring with fallacy penalties."""
        fallacies = [
            FallacyResult(
                id="f1", type=FallacyType.STRAW_MAN, text="Strawman attack",
                target_claim_id="c1", confidence=0.8, severity=FallacySeverity.MEDIUM
            )
        ]
        
        argument_scores = scorer.calculate_argument_scores(
            high_confidence_claims, fallacies=fallacies
        )
        
        # Find the argument that was targeted by fallacy
        fallacy_targeted_arg = next(
            (arg for arg in argument_scores if "c1" in arg.claim_ids), None
        )
        
        assert fallacy_targeted_arg is not None
        assert fallacy_targeted_arg.logic_score < 1.0  # Should be penalized
        assert fallacy_targeted_arg.fallacies_count == 1
    
    def test_relevance_and_clarity_scoring(self, scorer, high_confidence_claims):
        """Test relevance and clarity components."""
        argument_scores = scorer.calculate_argument_scores(high_confidence_claims)
        
        for arg_score in argument_scores:
            # All scores should be between 0 and 1
            assert 0.0 <= arg_score.relevance_score <= 1.0
            assert 0.0 <= arg_score.clarity_score <= 1.0
            assert 0.0 <= arg_score.strength_score <= 1.0
    
    def test_composite_strength_score(self, scorer, high_confidence_claims):
        """Test that strength score is properly weighted combination."""
        argument_scores = scorer.calculate_argument_scores(high_confidence_claims)
        
        for arg_score in argument_scores:
            # Manually calculate expected strength score
            expected_strength = (
                arg_score.evidence_score * 0.4 +
                arg_score.logic_score * 0.3 +
                arg_score.relevance_score * 0.2 +
                arg_score.clarity_score * 0.1
            )
            
            assert abs(arg_score.strength_score - expected_strength) < 0.001


class TestScoringPipeline:
    """Test the complete scoring pipeline."""
    
    @pytest.fixture
    def pipeline(self):
        return ScoringPipeline()
    
    @pytest.fixture
    def complete_test_data(self):
        """Complete test dataset with claims, fact-checks, and fallacies."""
        claims = [
            Claim(
                id="c1", type="statistical", text="Test claim 1",
                speaker="ALICE", confidence=0.8,
                sentence_id="s1", turn_id=1, char_start=0, char_end=12
            ),
            Claim(
                id="c2", type="factual", text="Test claim 2",
                speaker="BOB", confidence=0.7,
                sentence_id="s2", turn_id=2, char_start=13, char_end=25
            )
        ]
        
        fact_results = [
            FactCheckResult(
                claim_id="c1", service_name="test", query="test", claim_text="Test claim 1",
                status=VerificationStatus.LIKELY_TRUE, confidence=0.8, verification_score=0.8
            )
        ]
        
        fallacies = [
            FallacyResult(
                id="f1", type=FallacyType.FALSE_DILEMMA, text="False choice",
                speaker="BOB", confidence=0.7, severity=FallacySeverity.MEDIUM
            )
        ]
        
        return claims, fact_results, fallacies
    
    def test_direct_scoring_success(self, pipeline, complete_test_data):
        """Test successful direct scoring."""
        claims, fact_results, fallacies = complete_test_data
        
        result = pipeline.score_claims_directly(
            claims=claims,
            fact_results=fact_results,
            fallacies=fallacies,
            source="test"
        )
        
        assert result.scoring_performed is True
        assert result.scoring_error is None
        assert result.debate_score is not None
        assert result.processing_time_seconds >= 0
        assert result.source == "test"
    
    def test_extraction_result_integration(self, pipeline, complete_test_data):
        """Test integration with ExtractionResult."""
        claims, fact_results, fallacies = complete_test_data
        
        extraction_result = ExtractionResult(claims=claims)
        extraction_result.fact_check_results = fact_results
        extraction_result.fallacies = fallacies
        
        result = pipeline.score_extraction_result(extraction_result, source="integration_test")
        
        assert result.scoring_performed is True
        assert result.debate_score is not None
        assert result.source == "integration_test"
    
    def test_error_handling(self, pipeline):
        """Test error handling with invalid inputs."""
        # Test with invalid claim data
        invalid_claims = [None]  # This should cause an error
        
        with patch.object(pipeline.scorer, 'calculate_debate_score', side_effect=Exception("Test error")):
            result = pipeline.score_claims_directly(claims=invalid_claims)
            
            assert result.scoring_performed is False
            assert result.scoring_error is not None
            assert "Test error" in result.scoring_error
    
    def test_summary_generation(self, pipeline, complete_test_data):
        """Test that summary is properly generated."""
        claims, fact_results, fallacies = complete_test_data
        
        result = pipeline.score_claims_directly(
            claims=claims,
            fact_results=fact_results,
            fallacies=fallacies
        )
        
        summary = result.summary
        
        # Check required summary fields
        required_fields = [
            "overall_score", "overall_rating", "information_quality",
            "logical_consistency", "factual_accuracy", "engagement_quality",
            "strengths", "weaknesses", "recommendations"
        ]
        
        for field in required_fields:
            assert field in summary
    
    def test_performance_timing(self, pipeline, complete_test_data):
        """Test that performance timing is recorded."""
        claims, fact_results, fallacies = complete_test_data
        
        result = pipeline.score_claims_directly(
            claims=claims,
            fact_results=fact_results, 
            fallacies=fallacies
        )
        
        # Processing time should be recorded and reasonable
        assert result.processing_time_seconds >= 0
        assert result.processing_time_seconds < 10  # Should be very fast for test data


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions."""
    
    def test_empty_inputs(self):
        """Test scoring with completely empty inputs."""
        pipeline = ScoringPipeline()
        
        result = pipeline.score_claims_directly(
            claims=[],
            fact_results=[],
            fallacies=[]
        )
        
        assert result.scoring_performed is True
        assert result.debate_score.total_claims == 0
        assert result.debate_score.total_fallacies == 0
        assert result.debate_score.overall_score >= 0
    
    def test_extreme_confidence_values(self):
        """Test with extreme confidence values."""
        claims = [
            Claim(
                id="c1", type="factual", text="Zero confidence claim",
                speaker="SPEAKER", confidence=0.0,
                sentence_id="s1", turn_id=1, char_start=0, char_end=19
            ),
            Claim(
                id="c2", type="factual", text="Perfect confidence claim", 
                speaker="SPEAKER", confidence=1.0,
                sentence_id="s2", turn_id=1, char_start=20, char_end=44
            )
        ]
        
        pipeline = ScoringPipeline()
        result = pipeline.score_claims_directly(claims=claims)
        
        assert result.scoring_performed is True
        # Should handle extreme values gracefully
        assert 0.0 <= result.debate_score.overall_score <= 1.0
    
    def test_very_long_texts(self):
        """Test with very long claim texts."""
        long_text = "This is a very long claim " * 100  # 2600+ characters
        
        claims = [
            Claim(
                id="c1", type="factual", text=long_text,
                speaker="SPEAKER", confidence=0.7,
                sentence_id="s1", turn_id=1, char_start=0, char_end=len(long_text)
            )
        ]
        
        pipeline = ScoringPipeline()
        result = pipeline.score_claims_directly(claims=claims)
        
        assert result.scoring_performed is True
        # Should handle long texts without crashing
        assert result.debate_score.argument_scores[0].clarity_score < 1.0  # Should be penalized for length
    
    def test_many_speakers(self):
        """Test with many different speakers."""
        claims = []
        for i in range(20):  # 20 different speakers
            claims.append(
                Claim(
                    id=f"c{i}", type="factual", text=f"Claim from speaker {i}",
                    speaker=f"SPEAKER_{i}", confidence=0.7,
                    sentence_id=f"s{i}", turn_id=i, char_start=i*20, char_end=(i+1)*20
                )
            )
        
        pipeline = ScoringPipeline()
        result = pipeline.score_claims_directly(claims=claims)
        
        assert result.scoring_performed is True
        assert len(result.debate_score.speaker_scores) == 20
        # Engagement should be high due to speaker diversity
        assert result.debate_score.engagement_quality > 0.5


class TestMathematicalValidation:
    """Test mathematical correctness of scoring algorithms."""
    
    def test_score_ranges(self):
        """Test that all scores are within valid ranges."""
        # Create test data with known extreme cases
        claims = [
            Claim(
                id="c1", type="statistical", text="Test", speaker="A", confidence=1.0,
                sentence_id="s1", turn_id=1, char_start=0, char_end=4
            )
        ]
        
        fact_results = [
            FactCheckResult(
                claim_id="c1", service_name="test", query="test", claim_text="Test",
                status=VerificationStatus.VERIFIED_TRUE, confidence=1.0, verification_score=1.0
            )
        ]
        
        pipeline = ScoringPipeline()
        result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results)
        
        score = result.debate_score
        
        # All scores should be in [0, 1] range
        assert 0.0 <= score.overall_score <= 1.0
        assert 0.0 <= score.information_quality <= 1.0
        assert 0.0 <= score.logical_consistency <= 1.0
        assert 0.0 <= score.factual_accuracy <= 1.0
        assert 0.0 <= score.engagement_quality <= 1.0
        
        # Speaker scores should also be in valid range
        for speaker_score in score.speaker_scores.values():
            assert 0.0 <= speaker_score.credibility_score <= 1.0
            assert 0.0 <= speaker_score.claim_accuracy <= 1.0
            assert 0.0 <= speaker_score.fallacy_penalty <= 1.0
        
        # Argument scores should be in valid range
        for arg_score in score.argument_scores:
            assert 0.0 <= arg_score.strength_score <= 1.0
            assert 0.0 <= arg_score.evidence_score <= 1.0
            assert 0.0 <= arg_score.logic_score <= 1.0
            assert 0.0 <= arg_score.relevance_score <= 1.0
            assert 0.0 <= arg_score.clarity_score <= 1.0
    
    def test_weight_impact(self):
        """Test that configuration weights actually impact scores."""
        claims = [
            Claim(
                id="c1", type="factual", text="Test claim", speaker="SPEAKER", confidence=0.5,
                sentence_id="s1", turn_id=1, char_start=0, char_end=10
            )
        ]
        
        fallacies = [
            FallacyResult(
                id="f1", type=FallacyType.AD_HOMINEM, text="Attack",
                speaker="SPEAKER", confidence=0.8, severity=FallacySeverity.HIGH
            )
        ]
        
        # High fallacy penalty weight
        config1 = ScoringConfig(fallacy_penalty_weight=0.8, claim_confidence_weight=0.1, fact_check_weight=0.1)
        pipeline1 = ScoringPipeline(config1)
        result1 = pipeline1.score_claims_directly(claims=claims, fallacies=fallacies)
        
        # Low fallacy penalty weight
        config2 = ScoringConfig(fallacy_penalty_weight=0.1, claim_confidence_weight=0.8, fact_check_weight=0.1)
        pipeline2 = ScoringPipeline(config2)  
        result2 = pipeline2.score_claims_directly(claims=claims, fallacies=fallacies)
        
        # Speaker credibility with high fallacy penalty should be lower than with low fallacy penalty
        speaker1_credibility = result1.debate_score.speaker_scores["SPEAKER"].credibility_score
        speaker2_credibility = result2.debate_score.speaker_scores["SPEAKER"].credibility_score
        assert speaker1_credibility < speaker2_credibility
    
    def test_score_monotonicity(self):
        """Test that better inputs lead to better scores."""
        # Create two scenarios: one objectively better than the other
        
        # Scenario 1: Low confidence, false claims, many fallacies
        claims1 = [
            Claim(
                id="c1", type="factual", text="Dubious claim", speaker="SPEAKER", confidence=0.3,
                sentence_id="s1", turn_id=1, char_start=0, char_end=13
            )
        ]
        fact_results1 = [
            FactCheckResult(
                claim_id="c1", service_name="test", query="test", claim_text="Dubious claim",
                status=VerificationStatus.LIKELY_FALSE, confidence=0.9, verification_score=0.1
            )
        ]
        fallacies1 = [
            FallacyResult(
                id="f1", type=FallacyType.AD_HOMINEM, text="Attack 1",
                speaker="SPEAKER", confidence=0.9, severity=FallacySeverity.HIGH
            ),
            FallacyResult(
                id="f2", type=FallacyType.STRAW_MAN, text="Attack 2", 
                speaker="SPEAKER", confidence=0.8, severity=FallacySeverity.HIGH
            )
        ]
        
        # Scenario 2: High confidence, true claims, no fallacies
        claims2 = [
            Claim(
                id="c1", type="factual", text="Strong claim", speaker="SPEAKER", confidence=0.9,
                sentence_id="s1", turn_id=1, char_start=0, char_end=12
            )
        ]
        fact_results2 = [
            FactCheckResult(
                claim_id="c1", service_name="test", query="test", claim_text="Strong claim",
                status=VerificationStatus.VERIFIED_TRUE, confidence=0.9, verification_score=0.95
            )
        ]
        fallacies2 = []
        
        pipeline = ScoringPipeline()
        
        result1 = pipeline.score_claims_directly(claims=claims1, fact_results=fact_results1, fallacies=fallacies1)
        result2 = pipeline.score_claims_directly(claims=claims2, fact_results=fact_results2, fallacies=fallacies2)
        
        # Scenario 2 should score better than scenario 1
        assert result2.debate_score.overall_score > result1.debate_score.overall_score
        assert result2.debate_score.information_quality > result1.debate_score.information_quality
        assert result2.debate_score.logical_consistency > result1.debate_score.logical_consistency
        assert result2.debate_score.factual_accuracy > result1.debate_score.factual_accuracy


class TestRegressionAndBenchmarks:
    """Test for performance regressions and benchmark known results."""
    
    def test_known_benchmark_case(self):
        """Test against a known benchmark case with expected results."""
        # This is the exact same test case from our integration test
        claims = [
            Claim(
                id="claim_1", type="statistical", text="Unemployment decreased by 15% last year",
                speaker="CANDIDATE_A", confidence=0.85,
                sentence_id="sent_1", turn_id=1, char_start=0, char_end=38
            ),
            Claim(
                id="claim_2", type="factual", text="Climate change is caused by human activity",
                speaker="CANDIDATE_A", confidence=0.9,
                sentence_id="sent_2", turn_id=1, char_start=39, char_end=82
            ),
            Claim(
                id="claim_3", type="comparative", text="Our healthcare system is better than Canada's",
                speaker="CANDIDATE_B", confidence=0.6,
                sentence_id="sent_3", turn_id=2, char_start=83, char_end=129
            ),
            Claim(
                id="claim_4", type="historical", text="The 2008 financial crisis was caused by deregulation",
                speaker="CANDIDATE_B", confidence=0.75,
                sentence_id="sent_4", turn_id=2, char_start=130, char_end=184
            )
        ]
        
        fact_results = [
            FactCheckResult(
                claim_id="claim_1", service_name="test_service", query="unemployment decreased",
                claim_text="Unemployment decreased by 15% last year",
                status=VerificationStatus.LIKELY_FALSE, confidence=0.8, verification_score=0.2
            ),
            FactCheckResult(
                claim_id="claim_2", service_name="test_service", query="climate change human activity",
                claim_text="Climate change is caused by human activity",
                status=VerificationStatus.LIKELY_TRUE, confidence=0.9, verification_score=0.9
            ),
            FactCheckResult(
                claim_id="claim_4", service_name="test_service", query="2008 financial crisis deregulation",
                claim_text="The 2008 financial crisis was caused by deregulation",
                status=VerificationStatus.MIXED, confidence=0.6, verification_score=0.5
            )
        ]
        
        fallacies = [
            FallacyResult(
                id="fallacy_1", type=FallacyType.AD_HOMINEM,
                text="You can't trust him because he's a typical politician",
                speaker="CANDIDATE_B", target_claim_id="claim_1", confidence=0.85, severity=FallacySeverity.HIGH
            ),
            FallacyResult(
                id="fallacy_2", type=FallacyType.FALSE_DILEMMA,
                text="Either we cut taxes or the economy will collapse",
                speaker="CANDIDATE_A", confidence=0.7, severity=FallacySeverity.MEDIUM
            )
        ]
        
        config = ScoringConfig(
            claim_confidence_weight=0.3,
            fact_check_weight=0.4,
            fallacy_penalty_weight=0.3
        )
        
        pipeline = ScoringPipeline(config)
        result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
        
        # These are the expected benchmark results (within tolerance)
        assert abs(result.debate_score.overall_score - 0.649) < 0.01
        assert abs(result.debate_score.information_quality - 0.750) < 0.01  
        assert abs(result.debate_score.logical_consistency - 0.841) < 0.01
        assert abs(result.debate_score.factual_accuracy - 0.513) < 0.01
        assert abs(result.debate_score.engagement_quality - 0.426) < 0.01
        
        # Statistical validation
        assert result.debate_score.total_claims == 4
        assert result.debate_score.verified_claims == 1
        assert result.debate_score.false_claims == 1
        assert result.debate_score.total_fallacies == 2
        
        # Speaker performance validation
        assert len(result.debate_score.speaker_scores) == 2
        assert "CANDIDATE_A" in result.debate_score.speaker_scores
        assert "CANDIDATE_B" in result.debate_score.speaker_scores
        
        candidate_a_score = result.debate_score.speaker_scores["CANDIDATE_A"]
        candidate_b_score = result.debate_score.speaker_scores["CANDIDATE_B"]
        
        # CANDIDATE_A should have better credibility (less severe fallacy)
        assert candidate_a_score.credibility_score > candidate_b_score.credibility_score
        
        # Both should have same accuracy (50%)
        assert abs(candidate_a_score.claim_accuracy - 0.5) < 0.01
        assert abs(candidate_b_score.claim_accuracy - 0.5) < 0.01
    
    def test_performance_benchmark(self):
        """Test performance with larger datasets."""
        import time
        
        # Create larger test dataset
        claims = []
        fact_results = []
        fallacies = []
        
        for i in range(100):  # 100 claims
            claims.append(
                Claim(
                    id=f"claim_{i}", type="factual", text=f"Test claim {i}",
                    speaker=f"SPEAKER_{i % 5}", confidence=0.5 + (i % 5) * 0.1,
                    sentence_id=f"sent_{i}", turn_id=i, char_start=i*20, char_end=(i+1)*20
                )
            )
            
            if i % 3 == 0:  # Every 3rd claim gets fact-checked
                fact_results.append(
                    FactCheckResult(
                        claim_id=f"claim_{i}", service_name="test", query=f"query {i}",
                        claim_text=f"Test claim {i}",
                        status=VerificationStatus.LIKELY_TRUE if i % 2 == 0 else VerificationStatus.LIKELY_FALSE,
                        confidence=0.7, verification_score=0.8 if i % 2 == 0 else 0.3
                    )
                )
            
            if i % 7 == 0:  # Every 7th gets a fallacy
                fallacies.append(
                    FallacyResult(
                        id=f"fallacy_{i}", type=FallacyType.FALSE_DILEMMA, text=f"Fallacy {i}",
                        speaker=f"SPEAKER_{i % 5}", confidence=0.6, severity=FallacySeverity.MEDIUM
                    )
                )
        
        pipeline = ScoringPipeline()
        
        start_time = time.time()
        result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time (less than 1 second for 100 claims)
        assert processing_time < 1.0
        assert result.scoring_performed is True
        
        # Should handle all the data correctly
        assert result.debate_score.total_claims == 100
        assert len(result.debate_score.speaker_scores) == 5  # 5 unique speakers
        assert result.debate_score.total_fallacies == len(fallacies)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
