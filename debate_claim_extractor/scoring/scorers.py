"""
Core scoring algorithms for multi-dimensional debate analysis.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

from ..pipeline.models import ExtractionResult, Claim
from ..fallacy_detection.fallacy_models import FallacyResult, FallacySeverity
from ..fact_checking.fact_models import FactCheckResult, VerificationStatus
from .models import (
    ScoringConfig, 
    SpeakerScore, 
    ArgumentScore, 
    DebateScore,
    interpret_score
)

logger = logging.getLogger(__name__)


class DebateQualityScorer:
    """Calculates overall debate quality based on information quality and logical consistency."""
    
    def __init__(self, config: ScoringConfig):
        self.config = config
    
    def calculate_information_quality(self, claims: List[Claim], fact_results: Optional[List[FactCheckResult]] = None) -> float:
        """Calculate information quality based on claim confidence and fact-checking."""
        if not claims:
            return 0.0
        
        # Base score from claim confidence
        confidence_scores = [claim.confidence for claim in claims]
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Boost from fact-checking if available
        fact_boost = 0.0
        if fact_results:
            fact_result_map = {fr.claim_id: fr for fr in fact_results}
            verified_count = 0
            false_count = 0
            
            for claim in claims:
                if claim.id in fact_result_map:
                    result = fact_result_map[claim.id]
                    # Handle both aggregated and individual fact check results
                    if hasattr(result, 'aggregated_verification') and result.aggregated_verification:
                        status = result.aggregated_verification.status
                    else:
                        status = result.status
                    if status == VerificationStatus.LIKELY_TRUE:
                        verified_count += 1
                    elif status == VerificationStatus.LIKELY_FALSE:
                        false_count += 1
            
            if len(claims) > 0:
                verification_rate = verified_count / len(claims)
                false_rate = false_count / len(claims)
                fact_boost = verification_rate * 0.3 - false_rate * 0.4
        
        # Combine confidence and fact-checking
        quality_score = avg_confidence + fact_boost
        return max(0.0, min(1.0, quality_score))
    
    def calculate_logical_consistency(self, fallacies: Optional[List[FallacyResult]] = None, total_claims: int = 0) -> float:
        """Calculate logical consistency (inverse of fallacy rate)."""
        if not fallacies or total_claims == 0:
            return 1.0  # Perfect consistency if no fallacies detected
        
        # Weight fallacies by severity
        severity_weights = {
            FallacySeverity.LOW: 0.1,
            FallacySeverity.MEDIUM: 0.3,
            FallacySeverity.HIGH: 0.5
        }
        
        weighted_fallacy_score = 0.0
        for fallacy in fallacies:
            weight = severity_weights.get(fallacy.severity, 0.3)
            weighted_fallacy_score += weight * fallacy.confidence
        
        # Normalize by claims count
        fallacy_penalty = weighted_fallacy_score / total_claims
        consistency_score = 1.0 - min(1.0, fallacy_penalty)
        
        return max(0.0, consistency_score)
    
    def calculate_factual_accuracy(self, fact_results: Optional[List[FactCheckResult]] = None) -> float:
        """Calculate factual accuracy based on verification results."""
        if not fact_results:
            return 0.5  # Neutral score if no fact-checking
        
        status_weights = {
            VerificationStatus.VERIFIED_TRUE: 1.0,
            VerificationStatus.LIKELY_TRUE: 0.8,
            VerificationStatus.MIXED: 0.5,
            VerificationStatus.LIKELY_FALSE: 0.2,
            VerificationStatus.VERIFIED_FALSE: 0.0,
            VerificationStatus.UNVERIFIED: 0.4
        }
        
        total_weighted_score = 0.0
        total_confidence = 0.0
        
        for result in fact_results:
            # Handle both aggregated and individual fact check results
            if hasattr(result, 'aggregated_verification') and result.aggregated_verification:
                status = result.aggregated_verification.status
                confidence = result.aggregated_verification.confidence
            else:
                status = result.status
                confidence = result.confidence
            
            weight = status_weights.get(status, 0.4)
            total_weighted_score += weight * confidence
            total_confidence += confidence
        
        if total_confidence == 0:
            return 0.5
        
        accuracy_score = total_weighted_score / total_confidence
        return max(0.0, min(1.0, accuracy_score))


class SpeakerCredibilityScorer:
    """Calculates individual speaker credibility and performance metrics."""
    
    def __init__(self, config: ScoringConfig):
        self.config = config
    
    def calculate_speaker_scores(self, 
                                claims: List[Claim], 
                                fact_results: Optional[List[FactCheckResult]] = None,
                                fallacies: Optional[List[FallacyResult]] = None) -> Dict[str, SpeakerScore]:
        """Calculate scores for all speakers."""
        # Group data by speaker
        speakers = set(claim.speaker for claim in claims if claim.speaker)
        speaker_claims = defaultdict(list)
        speaker_fact_results = defaultdict(list)
        speaker_fallacies = defaultdict(list)
        
        # Group claims by speaker
        for claim in claims:
            if claim.speaker:
                speaker_claims[claim.speaker].append(claim)
        
        # Group fact results by speaker
        if fact_results:
            claim_speaker_map = {claim.id: claim.speaker for claim in claims if claim.speaker}
            for result in fact_results:
                speaker = claim_speaker_map.get(result.claim_id)
                if speaker:
                    speaker_fact_results[speaker].append(result)
        
        # Group fallacies by speaker
        if fallacies:
            for fallacy in fallacies:
                if fallacy.speaker:
                    speaker_fallacies[fallacy.speaker].append(fallacy)
        
        # Calculate scores for each speaker
        speaker_scores = {}
        for speaker in speakers:
            speaker_scores[speaker] = self._calculate_single_speaker_score(
                speaker,
                speaker_claims[speaker],
                speaker_fact_results[speaker],
                speaker_fallacies[speaker]
            )
        
        return speaker_scores
    
    def _calculate_single_speaker_score(self,
                                       speaker: str,
                                       claims: List[Claim],
                                       fact_results: List[FactCheckResult],
                                       fallacies: List[FallacyResult]) -> SpeakerScore:
        """Calculate score for a single speaker."""
        score = SpeakerScore(speaker=speaker)
        
        if not claims:
            return score
        
        # Basic statistics
        score.total_claims = len(claims)
        score.fallacies_committed = len(fallacies)
        
        # Claim confidence
        confidences = [claim.confidence for claim in claims]
        score.claim_confidence = sum(confidences) / len(confidences)
        score.high_confidence_claims = sum(1 for c in confidences if c >= self.config.high_confidence_threshold)
        
        # Claim type distribution
        score.claim_type_distribution = Counter(claim.type for claim in claims)
        
        # Fact-checking accuracy
        if fact_results:
            fact_map = {fr.claim_id: fr for fr in fact_results}
            verified_count = 0
            false_count = 0
            status_counts = Counter()
            
            for claim in claims:
                if claim.id in fact_map:
                    result = fact_map[claim.id]
                    if hasattr(result, 'aggregated_verification') and result.aggregated_verification:
                        status = result.aggregated_verification.status
                    else:
                        status = result.status
                    status_counts[status.value] += 1
                    
                    if status == VerificationStatus.LIKELY_TRUE or status == VerificationStatus.VERIFIED_TRUE:
                        verified_count += 1
                    elif status == VerificationStatus.LIKELY_FALSE or status == VerificationStatus.VERIFIED_FALSE:
                        false_count += 1
            
            score.verified_claims = verified_count
            score.false_claims = false_count
            score.verification_status_distribution = dict(status_counts)
            
            # Calculate claim accuracy (0-1)
            total_fact_checked = len(fact_results)
            if total_fact_checked > 0:
                score.claim_accuracy = (verified_count + 0.5 * (total_fact_checked - verified_count - false_count)) / total_fact_checked
        
        # Fallacy penalty
        if fallacies:
            fallacy_types = Counter(f.type.value for f in fallacies)
            score.fallacy_type_distribution = dict(fallacy_types)
            
            # Weight fallacies by severity and confidence
            penalty = 0.0
            for fallacy in fallacies:
                severity_multiplier = {
                    FallacySeverity.LOW: 0.1,
                    FallacySeverity.MEDIUM: 0.3, 
                    FallacySeverity.HIGH: 0.5
                }.get(fallacy.severity, 0.3)
                penalty += severity_multiplier * fallacy.confidence
            
            # Normalize penalty by claims count
            score.fallacy_penalty = min(1.0, penalty / len(claims))
        
        # Calculate overall credibility score
        base_score = score.claim_confidence * self.config.claim_confidence_weight
        fact_check_boost = (score.claim_accuracy or 0.5) * self.config.fact_check_weight
        fallacy_penalty = score.fallacy_penalty * self.config.fallacy_penalty_weight
        
        score.credibility_score = max(0.0, min(1.0, base_score + fact_check_boost - fallacy_penalty))
        
        return score


class ArgumentStrengthScorer:
    """Calculates argument strength based on evidence quality and logical consistency."""
    
    def __init__(self, config: ScoringConfig):
        self.config = config
    
    def calculate_argument_scores(self,
                                 claims: List[Claim],
                                 fact_results: Optional[List[FactCheckResult]] = None,
                                 fallacies: Optional[List[FallacyResult]] = None) -> List[ArgumentScore]:
        """Calculate argument strength scores for claim clusters."""
        # For now, treat each high-confidence claim as a potential argument
        # In the future, this could use the clustering from YouTube pipeline
        
        argument_scores = []
        fact_map = {fr.claim_id: fr for fr in (fact_results or [])}
        
        # Group fallacies by target claim
        fallacy_map = defaultdict(list)
        for fallacy in (fallacies or []):
            if fallacy.target_claim_id:
                fallacy_map[fallacy.target_claim_id].append(fallacy)
        
        # Create argument for each significant claim
        for claim in claims:
            if claim.confidence >= self.config.medium_confidence_threshold:
                arg_score = self._calculate_single_argument_score(
                    claim, 
                    fact_map.get(claim.id),
                    fallacy_map.get(claim.id, [])
                )
                argument_scores.append(arg_score)
        
        return argument_scores
    
    def _calculate_single_argument_score(self,
                                       claim: Claim,
                                       fact_result: Optional[FactCheckResult],
                                       fallacies: List[FallacyResult]) -> ArgumentScore:
        """Calculate strength score for a single argument/claim."""
        score = ArgumentScore()
        score.claim_ids = [claim.id]
        score.claims_count = 1
        score.avg_claim_confidence = claim.confidence
        score.fallacies_count = len(fallacies)
        score.fallacy_ids = [f.id for f in fallacies if f.id]
        
        # Evidence score (based on fact-checking)
        if fact_result:
            if hasattr(fact_result, 'aggregated_verification') and fact_result.aggregated_verification:
                status = fact_result.aggregated_verification.status
                confidence = fact_result.aggregated_verification.confidence
            else:
                status = fact_result.status
                confidence = fact_result.confidence
            
            if status in [VerificationStatus.VERIFIED_TRUE, VerificationStatus.LIKELY_TRUE]:
                score.evidence_score = 0.5 + (confidence * 0.5)
                score.verified_claims_count = 1
            elif status == VerificationStatus.MIXED:
                score.evidence_score = 0.4 + (confidence * 0.2)
            else:
                score.evidence_score = max(0.1, 0.4 - (confidence * 0.3))
        else:
            # No fact-checking available, use claim confidence as proxy
            score.evidence_score = claim.confidence * 0.6
        
        # Logic score (inverse of fallacy penalty)
        if fallacies:
            fallacy_penalty = 0.0
            for fallacy in fallacies:
                severity_weight = {
                    FallacySeverity.LOW: 0.1,
                    FallacySeverity.MEDIUM: 0.3,
                    FallacySeverity.HIGH: 0.5
                }.get(fallacy.severity, 0.3)
                fallacy_penalty += severity_weight * fallacy.confidence
            
            score.logic_score = max(0.0, 1.0 - fallacy_penalty)
        else:
            score.logic_score = 1.0
        
        # Relevance score (based on claim type and confidence)
        type_relevance = {
            'statistical': 0.9,
            'factual': 0.8,
            'historical': 0.8,
            'causal': 0.7,
            'comparative': 0.7
        }
        base_relevance = type_relevance.get(claim.type, 0.6)
        score.relevance_score = base_relevance * claim.confidence
        
        # Clarity score (based on claim length and structure)
        text_length = len(claim.text)
        if 10 <= text_length <= 200:  # Sweet spot for clear claims
            length_factor = 1.0
        elif text_length < 10:
            length_factor = 0.5  # Too short
        else:
            length_factor = max(0.3, 1.0 - (text_length - 200) / 1000)  # Too long
        
        score.clarity_score = claim.confidence * length_factor
        
        # Overall strength score (weighted combination)
        score.strength_score = (
            score.evidence_score * 0.4 +
            score.logic_score * 0.3 +
            score.relevance_score * 0.2 +
            score.clarity_score * 0.1
        )
        
        return score


class OverallDebateScorer:
    """Combines all scoring dimensions into overall debate quality metrics."""
    
    def __init__(self, config: ScoringConfig):
        self.config = config
        self.quality_scorer = DebateQualityScorer(config)
        self.speaker_scorer = SpeakerCredibilityScorer(config)
        self.argument_scorer = ArgumentStrengthScorer(config)
    
    def calculate_debate_score(self,
                              claims: List[Claim],
                              fact_results: Optional[List[FactCheckResult]] = None,
                              fallacies: Optional[List[FallacyResult]] = None) -> DebateScore:
        """Calculate comprehensive debate score."""
        debate_score = DebateScore()
        
        # Basic statistics
        debate_score.total_claims = len(claims)
        debate_score.total_fallacies = len(fallacies or [])
        
        # Count verification statuses
        if fact_results:
            statuses = []
            for fr in fact_results:
                if hasattr(fr, 'aggregated_verification') and fr.aggregated_verification:
                    statuses.append(fr.aggregated_verification.status)
                else:
                    statuses.append(fr.status)
            
            status_counts = Counter(statuses)
            debate_score.verified_claims = (
                status_counts.get(VerificationStatus.VERIFIED_TRUE, 0) + 
                status_counts.get(VerificationStatus.LIKELY_TRUE, 0)
            )
            debate_score.false_claims = (
                status_counts.get(VerificationStatus.VERIFIED_FALSE, 0) + 
                status_counts.get(VerificationStatus.LIKELY_FALSE, 0)
            )
            debate_score.mixed_claims = status_counts.get(VerificationStatus.MIXED, 0)
        
        # Calculate component scores
        debate_score.information_quality = self.quality_scorer.calculate_information_quality(claims, fact_results)
        debate_score.logical_consistency = self.quality_scorer.calculate_logical_consistency(fallacies, len(claims))
        debate_score.factual_accuracy = self.quality_scorer.calculate_factual_accuracy(fact_results)
        
        # Engagement quality (based on claim diversity and speaker interaction)
        debate_score.engagement_quality = self._calculate_engagement_quality(claims, fallacies)
        
        # Speaker scores
        debate_score.speaker_scores = self.speaker_scorer.calculate_speaker_scores(claims, fact_results, fallacies)
        
        # Argument scores
        debate_score.argument_scores = self.argument_scorer.calculate_argument_scores(claims, fact_results, fallacies)
        
        # Score distributions
        debate_score.confidence_distribution = self._calculate_confidence_distribution(claims)
        debate_score.claim_type_distribution = Counter(claim.type for claim in claims)
        
        if fallacies:
            debate_score.fallacy_severity_distribution = Counter(f.severity.value for f in fallacies)
        
        # Overall score (weighted combination)
        debate_score.overall_score = (
            debate_score.information_quality * 0.3 +
            debate_score.logical_consistency * 0.25 +
            debate_score.factual_accuracy * 0.25 +
            debate_score.engagement_quality * 0.2
        )
        
        return debate_score
    
    def _calculate_engagement_quality(self, claims: List[Claim], fallacies: Optional[List[FallacyResult]]) -> float:
        """Calculate engagement quality based on diversity and interaction."""
        if not claims:
            return 0.0
        
        # Claim type diversity
        claim_types = set(claim.type for claim in claims)
        type_diversity = len(claim_types) / 5.0  # Max 5 claim types
        
        # Speaker diversity
        speakers = set(claim.speaker for claim in claims if claim.speaker)
        speaker_count = len(speakers)
        speaker_balance = min(1.0, speaker_count / 3.0)  # Good if 3+ speakers
        
        # Length and complexity
        avg_claim_length = sum(len(claim.text) for claim in claims) / len(claims)
        length_score = min(1.0, avg_claim_length / 100.0)  # Good if 100+ chars average
        
        # Reduce score for excessive fallacies
        fallacy_penalty = 0.0
        if fallacies:
            fallacy_rate = len(fallacies) / len(claims)
            fallacy_penalty = min(0.3, fallacy_rate * 0.5)
        
        engagement_score = (type_diversity * 0.4 + speaker_balance * 0.4 + length_score * 0.2) - fallacy_penalty
        return max(0.0, min(1.0, engagement_score))
    
    def _calculate_confidence_distribution(self, claims: List[Claim]) -> Dict[str, int]:
        """Calculate distribution of claim confidence levels."""
        distribution = {'high': 0, 'medium': 0, 'low': 0}
        
        for claim in claims:
            if claim.confidence >= self.config.high_confidence_threshold:
                distribution['high'] += 1
            elif claim.confidence >= self.config.medium_confidence_threshold:
                distribution['medium'] += 1
            else:
                distribution['low'] += 1
        
        return distribution
