#!/usr/bin/env python3
"""
Quick test script to validate the multi-dimensional scoring system.
"""

import sys
import logging
from typing import List

# Add the current directory to Python path for imports
sys.path.insert(0, '.')

from debate_claim_extractor.pipeline.models import Claim, ExtractionResult
from debate_claim_extractor.fact_checking.fact_models import (
    FactCheckResult, AggregatedVerification, VerificationStatus
)
from debate_claim_extractor.fallacy_detection.fallacy_models import (
    FallacyResult, FallacyType, FallacySeverity
)
from debate_claim_extractor.scoring import (
    ScoringPipeline, ScoringConfig, SpeakerScore, DebateScore
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_claims() -> List[Claim]:
    """Create sample claims for testing."""
    claims = [
        Claim(
            id="claim_1",
            type="statistical",
            text="Unemployment decreased by 15% last year",
            speaker="CANDIDATE_A",
            confidence=0.85,
            sentence_id="sent_1",
            turn_id=1,
            char_start=0,
            char_end=38
        ),
        Claim(
            id="claim_2", 
            type="factual",
            text="Climate change is caused by human activity",
            speaker="CANDIDATE_A",
            confidence=0.9,
            sentence_id="sent_2",
            turn_id=1,
            char_start=39,
            char_end=82
        ),
        Claim(
            id="claim_3",
            type="comparative", 
            text="Our healthcare system is better than Canada's",
            speaker="CANDIDATE_B",
            confidence=0.6,
            sentence_id="sent_3",
            turn_id=2,
            char_start=83,
            char_end=129
        ),
        Claim(
            id="claim_4",
            type="historical",
            text="The 2008 financial crisis was caused by deregulation",
            speaker="CANDIDATE_B", 
            confidence=0.75,
            sentence_id="sent_4",
            turn_id=2,
            char_start=130,
            char_end=184
        )
    ]
    return claims


def create_test_fact_results() -> List[FactCheckResult]:
    """Create sample fact-checking results."""
    fact_results = [
        FactCheckResult(
            claim_id="claim_1",
            service_name="test_service",
            query="unemployment decreased",
            claim_text="Unemployment decreased by 15% last year",
            status=VerificationStatus.LIKELY_FALSE,
            confidence=0.8,
            verification_score=0.2,
            explanation="BLS data shows unemployment decreased by only 8%"
        ),
        FactCheckResult(
            claim_id="claim_2",
            service_name="test_service",
            query="climate change human activity",
            claim_text="Climate change is caused by human activity",
            status=VerificationStatus.LIKELY_TRUE,
            confidence=0.9,
            verification_score=0.9,
            explanation="Scientific consensus supports this claim"
        ),
        FactCheckResult(
            claim_id="claim_4",
            service_name="test_service", 
            query="2008 financial crisis deregulation",
            claim_text="The 2008 financial crisis was caused by deregulation",
            status=VerificationStatus.MIXED,
            confidence=0.6,
            verification_score=0.5,
            explanation="Multiple factors contributed to the crisis"
        )
    ]
    return fact_results


def create_test_fallacies() -> List[FallacyResult]:
    """Create sample fallacy results."""
    fallacies = [
        FallacyResult(
            id="fallacy_1",
            type=FallacyType.AD_HOMINEM,
            text="You can't trust him because he's a typical politician",
            speaker="CANDIDATE_B",
            target_claim_id="claim_1",
            confidence=0.85,
            severity=FallacySeverity.HIGH,
            patterns_matched=["personal_attack"]
        ),
        FallacyResult(
            id="fallacy_2",
            type=FallacyType.FALSE_DILEMMA,
            text="Either we cut taxes or the economy will collapse",
            speaker="CANDIDATE_A", 
            confidence=0.7,
            severity=FallacySeverity.MEDIUM,
            patterns_matched=["false_dilemma"]
        )
    ]
    return fallacies


def test_scoring_system():
    """Test the multi-dimensional scoring system."""
    logger.info("🧪 Testing Multi-Dimensional Scoring System")
    
    # Create test data
    claims = create_test_claims()
    fact_results = create_test_fact_results()
    fallacies = create_test_fallacies()
    
    logger.info(f"Test data: {len(claims)} claims, {len(fact_results)} fact-check results, {len(fallacies)} fallacies")
    
    # Create scoring pipeline
    config = ScoringConfig(
        claim_confidence_weight=0.3,
        fact_check_weight=0.4,
        fallacy_penalty_weight=0.3
    )
    
    pipeline = ScoringPipeline(config)
    
    # Test direct scoring
    logger.info("\n📊 Running direct scoring...")
    scoring_result = pipeline.score_claims_directly(
        claims=claims,
        fact_results=fact_results,
        fallacies=fallacies,
        source="test_data"
    )
    
    if not scoring_result.scoring_performed:
        logger.error(f"❌ Scoring failed: {scoring_result.scoring_error}")
        return False
    
    # Display results
    debate_score = scoring_result.debate_score
    summary = scoring_result.summary
    
    logger.info(f"✅ Scoring completed in {scoring_result.processing_time_seconds:.3f}s")
    logger.info(f"\n📈 Overall Results:")
    logger.info(f"  Overall Score: {debate_score.overall_score:.3f} ({summary['overall_rating']})")
    logger.info(f"  Information Quality: {debate_score.information_quality:.3f}")
    logger.info(f"  Logical Consistency: {debate_score.logical_consistency:.3f}")
    logger.info(f"  Factual Accuracy: {debate_score.factual_accuracy:.3f}")
    logger.info(f"  Engagement Quality: {debate_score.engagement_quality:.3f}")
    
    logger.info(f"\n📊 Statistics:")
    logger.info(f"  Total Claims: {debate_score.total_claims}")
    logger.info(f"  Verified Claims: {debate_score.verified_claims}")
    logger.info(f"  False Claims: {debate_score.false_claims}")
    logger.info(f"  Total Fallacies: {debate_score.total_fallacies}")
    
    # Speaker scores
    logger.info(f"\n🗣️ Speaker Performance:")
    for speaker, score in debate_score.speaker_scores.items():
        logger.info(f"  {speaker}: {score.credibility_score:.3f}")
        logger.info(f"    - Claims: {score.total_claims}, Accuracy: {score.claim_accuracy:.3f}")
        logger.info(f"    - Fallacies: {score.fallacies_committed}, Penalty: {score.fallacy_penalty:.3f}")
    
    # Argument scores
    logger.info(f"\n⚖️ Argument Strength:")
    logger.info(f"  Arguments Analyzed: {len(debate_score.argument_scores)}")
    if debate_score.argument_scores:
        avg_strength = sum(arg.strength_score for arg in debate_score.argument_scores) / len(debate_score.argument_scores)
        logger.info(f"  Average Strength: {avg_strength:.3f}")
    
    # Summary insights
    logger.info(f"\n💡 Analysis Summary:")
    if summary.get('strengths'):
        logger.info(f"  Strengths: {', '.join(summary['strengths'])}")
    if summary.get('weaknesses'):
        logger.info(f"  Weaknesses: {', '.join(summary['weaknesses'])}")
    if summary.get('recommendations'):
        logger.info(f"  Recommendations:")
        for rec in summary['recommendations']:
            logger.info(f"    - {rec}")
    
    logger.info(f"\n✅ Scoring system test completed successfully!")
    return True


def test_extraction_result_integration():
    """Test scoring integration with ExtractionResult."""
    logger.info("\n🔗 Testing ExtractionResult Integration")
    
    # Create mock extraction result
    claims = create_test_claims()
    extraction_result = ExtractionResult(claims=claims)
    
    # Add fact-checking and fallacy results
    extraction_result.fact_check_results = create_test_fact_results()
    extraction_result.fallacies = create_test_fallacies()
    
    # Test scoring
    pipeline = ScoringPipeline()
    scoring_result = pipeline.score_extraction_result(extraction_result, source="integration_test")
    
    if not scoring_result.scoring_performed:
        logger.error(f"❌ Integration scoring failed: {scoring_result.scoring_error}")
        return False
    
    logger.info(f"✅ Integration test passed! Overall score: {scoring_result.debate_score.overall_score:.3f}")
    return True


if __name__ == "__main__":
    logger.info("🚀 Starting Scoring System Tests\n")
    
    try:
        # Test 1: Direct scoring
        success1 = test_scoring_system()
        
        # Test 2: Integration with ExtractionResult
        success2 = test_extraction_result_integration()
        
        if success1 and success2:
            logger.info("\n🎉 All tests passed! Scoring system is working correctly.")
            sys.exit(0)
        else:
            logger.error("\n❌ Some tests failed.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
