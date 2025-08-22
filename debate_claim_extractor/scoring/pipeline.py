"""
Scoring pipeline that integrates with the existing claim extraction system.
"""

import logging
import time
from typing import Optional, Dict, Any

from ..pipeline.models import ExtractionResult
from ..fact_checking.fact_models import FactCheckResult
from ..fallacy_detection.fallacy_models import FallacyResult
from .models import ScoringConfig, ScoringResult, DebateScore
from .scorers import OverallDebateScorer

logger = logging.getLogger(__name__)


class ScoringPipeline:
    """Main pipeline for calculating multi-dimensional debate scores."""
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        """Initialize the scoring pipeline."""
        self.config = config or ScoringConfig()
        self.scorer = OverallDebateScorer(self.config)
        
        logger.info("Scoring pipeline initialized")
        logger.info(f"Scoring weights - Claim confidence: {self.config.claim_confidence_weight}, "
                   f"Fact check: {self.config.fact_check_weight}, "
                   f"Fallacy penalty: {self.config.fallacy_penalty_weight}")
    
    def score_extraction_result(self, 
                              extraction_result: ExtractionResult,
                              source: Optional[str] = None) -> ScoringResult:
        """
        Calculate comprehensive scores for an extraction result.
        
        Args:
            extraction_result: The result from claim extraction pipeline
            source: Optional source identifier
            
        Returns:
            ScoringResult with comprehensive debate metrics
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting scoring for {len(extraction_result.claims)} claims")
            
            # Extract data from extraction result
            claims = extraction_result.claims
            
            # Get fact-checking results if available
            fact_results = []
            if hasattr(extraction_result, 'fact_check_results') and extraction_result.fact_check_results:
                fact_results = self._convert_fact_results(extraction_result.fact_check_results)
                logger.info(f"Found {len(fact_results)} fact-check results")
            
            # Get fallacy results if available
            fallacies = []
            if hasattr(extraction_result, 'fallacies') and extraction_result.fallacies:
                fallacies = extraction_result.fallacies
                logger.info(f"Found {len(fallacies)} fallacy results")
            
            # Calculate comprehensive debate score
            debate_score = self.scorer.calculate_debate_score(claims, fact_results, fallacies)
            
            # Create scoring result
            processing_time = time.time() - start_time
            
            scoring_result = ScoringResult(
                debate_score=debate_score,
                config=self.config,
                source=source,
                processing_time_seconds=processing_time,
                scoring_performed=True
            )
            
            # Generate summary for quick access
            scoring_result.summary = self._generate_summary(debate_score)
            
            logger.info(f"Scoring completed in {processing_time:.2f}s")
            logger.info(f"Overall debate score: {debate_score.overall_score:.3f} ({self._interpret_overall_score(debate_score.overall_score)})")
            
            return scoring_result
            
        except Exception as e:
            logger.error(f"Error during scoring: {e}")
            
            # Return error result
            processing_time = time.time() - start_time
            return ScoringResult(
                config=self.config,
                source=source,
                processing_time_seconds=processing_time,
                scoring_performed=False,
                scoring_error=str(e)
            )
    
    def score_claims_directly(self,
                            claims: list,
                            fact_results: Optional[list] = None,
                            fallacies: Optional[list] = None,
                            source: Optional[str] = None) -> ScoringResult:
        """
        Score claims directly without going through ExtractionResult.
        
        Useful for testing or when you have raw claim data.
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting direct scoring for {len(claims)} claims")
            
            # Calculate comprehensive debate score
            debate_score = self.scorer.calculate_debate_score(claims, fact_results or [], fallacies or [])
            
            # Create scoring result
            processing_time = time.time() - start_time
            
            scoring_result = ScoringResult(
                debate_score=debate_score,
                config=self.config,
                source=source,
                processing_time_seconds=processing_time,
                scoring_performed=True
            )
            
            # Generate summary
            scoring_result.summary = self._generate_summary(debate_score)
            
            logger.info(f"Direct scoring completed in {processing_time:.2f}s")
            return scoring_result
            
        except Exception as e:
            logger.error(f"Error during direct scoring: {e}")
            
            processing_time = time.time() - start_time
            return ScoringResult(
                config=self.config,
                source=source,
                processing_time_seconds=processing_time,
                scoring_performed=False,
                scoring_error=str(e)
            )
    
    def _generate_summary(self, debate_score: DebateScore) -> Dict[str, Any]:
        """Generate a quick summary of the debate scores."""
        summary = {
            # Overall metrics
            "overall_score": round(debate_score.overall_score, 3),
            "overall_rating": self._interpret_overall_score(debate_score.overall_score),
            
            # Component scores
            "information_quality": round(debate_score.information_quality, 3),
            "logical_consistency": round(debate_score.logical_consistency, 3),
            "factual_accuracy": round(debate_score.factual_accuracy, 3),
            "engagement_quality": round(debate_score.engagement_quality, 3),
            
            # Statistics
            "total_claims": debate_score.total_claims,
            "verified_claims": debate_score.verified_claims,
            "false_claims": debate_score.false_claims,
            "total_fallacies": debate_score.total_fallacies,
            
            # Speaker performance
            "speaker_count": len(debate_score.speaker_scores),
            "top_speaker": self._get_top_speaker(debate_score.speaker_scores),
            
            # Argument analysis
            "argument_count": len(debate_score.argument_scores),
            "avg_argument_strength": self._calculate_avg_argument_strength(debate_score.argument_scores),
            
            # Quick insights
            "strengths": self._identify_strengths(debate_score),
            "weaknesses": self._identify_weaknesses(debate_score),
            "recommendations": self._generate_recommendations(debate_score)
        }
        
        return summary
    
    def _interpret_overall_score(self, score: float) -> str:
        """Convert overall score to human-readable rating."""
        if score >= 0.85:
            return "excellent"
        elif score >= 0.70:
            return "good"
        elif score >= 0.55:
            return "fair"
        elif score >= 0.40:
            return "poor"
        else:
            return "very_poor"
    
    def _get_top_speaker(self, speaker_scores: Dict[str, Any]) -> Optional[str]:
        """Identify the top-performing speaker."""
        if not speaker_scores:
            return None
        
        top_speaker = max(speaker_scores.keys(), 
                         key=lambda s: speaker_scores[s].credibility_score)
        return top_speaker
    
    def _calculate_avg_argument_strength(self, argument_scores: list) -> float:
        """Calculate average argument strength."""
        if not argument_scores:
            return 0.0
        
        total_strength = sum(arg.strength_score for arg in argument_scores)
        return round(total_strength / len(argument_scores), 3)
    
    def _identify_strengths(self, debate_score: DebateScore) -> list:
        """Identify key strengths of the debate."""
        strengths = []
        
        if debate_score.information_quality >= 0.7:
            strengths.append("High information quality")
        
        if debate_score.logical_consistency >= 0.8:
            strengths.append("Strong logical consistency")
        
        if debate_score.factual_accuracy >= 0.7:
            strengths.append("Good factual accuracy")
        
        if debate_score.engagement_quality >= 0.7:
            strengths.append("Engaging discussion")
        
        if len(debate_score.speaker_scores) >= 3:
            strengths.append("Multiple perspectives represented")
        
        # Check for high-confidence claims
        high_conf_claims = debate_score.confidence_distribution.get('high', 0)
        if high_conf_claims > debate_score.total_claims * 0.3:
            strengths.append("Many high-confidence claims")
        
        return strengths
    
    def _identify_weaknesses(self, debate_score: DebateScore) -> list:
        """Identify key weaknesses of the debate."""
        weaknesses = []
        
        if debate_score.information_quality < 0.4:
            weaknesses.append("Low information quality")
        
        if debate_score.logical_consistency < 0.6:
            weaknesses.append("Logical fallacies present")
        
        if debate_score.factual_accuracy < 0.5:
            weaknesses.append("Factual accuracy concerns")
        
        if debate_score.engagement_quality < 0.4:
            weaknesses.append("Limited engagement quality")
        
        # Check fallacy rate
        if debate_score.total_claims > 0:
            fallacy_rate = debate_score.total_fallacies / debate_score.total_claims
            if fallacy_rate > 0.2:
                weaknesses.append("High fallacy rate")
        
        # Check for false claims
        if debate_score.false_claims > debate_score.total_claims * 0.2:
            weaknesses.append("Significant false claims")
        
        return weaknesses
    
    def _generate_recommendations(self, debate_score: DebateScore) -> list:
        """Generate recommendations for improvement."""
        recommendations = []
        
        if debate_score.information_quality < 0.6:
            recommendations.append("Focus on higher-quality, well-supported claims")
        
        if debate_score.logical_consistency < 0.7:
            recommendations.append("Avoid logical fallacies and strengthen reasoning")
        
        if debate_score.factual_accuracy < 0.6:
            recommendations.append("Verify claims against reliable sources")
        
        if debate_score.engagement_quality < 0.6:
            recommendations.append("Improve debate structure and participant engagement")
        
        # Speaker-specific recommendations
        if debate_score.speaker_scores:
            low_performing_speakers = [
                speaker for speaker, score in debate_score.speaker_scores.items()
                if score.credibility_score < 0.5
            ]
            if low_performing_speakers:
                recommendations.append(f"Speaker(s) {', '.join(low_performing_speakers)} should focus on accuracy and evidence")
        
        return recommendations
    
    def _convert_fact_results(self, fact_results: list) -> list:
        """
        Convert fact-check results from dictionaries to FactCheckResult objects.
        
        This handles compatibility between serialized results and objects.
        """
        from ..fact_checking.fact_models import FactCheckResult, VerificationStatus
        
        converted_results = []
        for result in fact_results:
            if isinstance(result, dict):
                # Create a simple fact-check result with the overall status
                converted_result = FactCheckResult(
                    claim_id=result.get('claim_id', ''),
                    service_name='aggregated',
                    query=result.get('claim_text', ''),
                    claim_text=result.get('claim_text', ''),
                    status=VerificationStatus(result.get('overall_status', 'unverified')),
                    confidence=result.get('confidence', 0.5),
                    verification_score=result.get('overall_score', 0.5)
                )
                converted_results.append(converted_result)
            else:
                # Assume it's already a FactCheckResult object
                converted_results.append(result)
        
        return converted_results


def add_scoring_to_extraction_result(extraction_result: ExtractionResult,
                                   scoring_config: Optional[ScoringConfig] = None) -> ExtractionResult:
    """
    Add scoring information to an existing ExtractionResult.
    
    This function modifies the extraction result in-place to add scoring data.
    """
    pipeline = ScoringPipeline(scoring_config)
    scoring_result = pipeline.score_extraction_result(extraction_result)
    
    # Add scoring data to extraction result
    if not hasattr(extraction_result, 'scoring_result'):
        # Create new field if it doesn't exist
        extraction_result.scoring_result = scoring_result
    else:
        extraction_result.scoring_result = scoring_result
    
    return extraction_result
