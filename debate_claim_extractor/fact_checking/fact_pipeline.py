"""
Core fact verification pipeline that orchestrates multiple fact-checking services
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from .fact_models import (
    FactCheckResult,
    AggregatedVerification, 
    FactCheckConfig,
    VerificationStatus,
    calculate_weighted_score,
    status_from_score
)
from .services import GoogleFactCheckService, LocalFactCheckService
from .services.wikipedia_service import WikipediaFactCheckService
from ..pipeline.models import Claim

logger = logging.getLogger(__name__)


class FactVerificationPipeline:
    """
    Core fact verification pipeline that orchestrates multiple fact-checking services
    """
    
    def __init__(self, config: Optional[FactCheckConfig] = None):
        """
        Initialize the fact verification pipeline
        
        Args:
            config: Configuration for fact-checking services
        """
        self.config = config or FactCheckConfig()
        self.services = []
        self.logger = logger.getChild("fact_pipeline")
        
        # Initialize services based on configuration
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize fact-checking services based on configuration"""
        self.services = []
        
        # Google Fact Check Tools
        if self.config.google_fact_check.get('enabled', True):
            try:
                google_service = GoogleFactCheckService(
                    api_key=self.config.google_fact_check.get('api_key'),
                    timeout_seconds=self.config.timeout_seconds
                )
                if google_service.is_available():
                    self.services.append(google_service)
                    self.logger.info("Google Fact Check service initialized")
                else:
                    self.logger.warning("Google Fact Check service not available (missing API key)")
            except Exception as e:
                self.logger.error(f"Failed to initialize Google Fact Check service: {e}")
        
        # Local database service
        if self.config.local_database.get('enabled', True):
            try:
                local_service = LocalFactCheckService(
                    database_path=self.config.local_database.get('database_path'),
                    timeout_seconds=self.config.timeout_seconds
                )
                if local_service.is_available():
                    self.services.append(local_service)
                    self.logger.info("Local database service initialized")
                else:
                    self.logger.warning("Local database service not available")
            except Exception as e:
                self.logger.error(f"Failed to initialize local database service: {e}")
        
        # Wikipedia service (always enabled if no config specified)
        wikipedia_enabled = self.config.wikipedia.get('enabled', True) if hasattr(self.config, 'wikipedia') else True
        if wikipedia_enabled:
            try:
                wikipedia_service = WikipediaFactCheckService(
                    timeout_seconds=self.config.timeout_seconds
                )
                # Initialize Wikipedia service (will be checked for availability during first use)
                self.services.append(wikipedia_service)
                self.logger.info("Wikipedia service initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Wikipedia service: {e}")
        
        self.logger.info(f"Initialized {len(self.services)} fact-checking service(s)")
    
    async def verify_claim(self, claim: Claim) -> AggregatedVerification:
        """
        Verify a single claim using all available services
        
        Args:
            claim: The claim to verify
            
        Returns:
            Aggregated verification result
        """
        if not self.services:
            self.logger.warning("No fact-checking services available")
            return self._create_empty_verification(claim)
        
        start_time = time.time()
        
        # Run all services in parallel
        tasks = []
        for service in self.services:
            task = asyncio.create_task(
                self._verify_with_service(service, claim.text),
                name=f"verify_{service.name}"
            )
            tasks.append(task)
        
        # Wait for all services to complete (with timeout)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config.timeout_seconds
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Fact-checking timeout for claim: {claim.text[:50]}...")
            # Cancel pending tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            results = []
        
        # Filter out exceptions and failed results
        valid_results = []
        for result in results:
            if isinstance(result, FactCheckResult) and result.status != VerificationStatus.ERROR:
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Service error: {result}")
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Aggregate results
        return self._aggregate_results(claim, valid_results, processing_time)
    
    async def verify_claims(self, claims: List[Claim]) -> List[AggregatedVerification]:
        """
        Verify multiple claims
        
        Args:
            claims: List of claims to verify
            
        Returns:
            List of aggregated verification results
        """
        if not claims:
            return []
        
        self.logger.info(f"Starting fact-checking for {len(claims)} claims")
        start_time = time.time()
        
        # Process claims in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(3)  # Reduced concurrency to be gentler on Wikipedia
        completed_count = 0
        
        async def verify_with_limit_and_progress(claim, index):
            nonlocal completed_count
            async with semaphore:
                result = await self.verify_claim(claim)
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == len(claims):
                    elapsed = time.time() - start_time
                    rate = completed_count / elapsed if elapsed > 0 else 0
                    remaining = len(claims) - completed_count
                    eta = remaining / rate if rate > 0 else 0
                    self.logger.info(f"Fact-checking progress: {completed_count}/{len(claims)} claims completed ({rate:.1f}/sec, ETA: {eta:.0f}s)")
                return result
        
        tasks = [verify_with_limit_and_progress(claim, i) for i, claim in enumerate(claims)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        error_count = 0
        for result in results:
            if isinstance(result, AggregatedVerification):
                valid_results.append(result)
            elif isinstance(result, Exception):
                error_count += 1
                self.logger.error(f"Claim verification error: {result}")
        
        elapsed = time.time() - start_time
        self.logger.info(f"Fact-checking completed in {elapsed:.1f}s: {len(valid_results)} successful, {error_count} errors")
        return valid_results
    
    async def _verify_with_service(self, service, claim_text: str) -> FactCheckResult:
        """
        Verify claim with a single service, handling errors gracefully
        
        Args:
            service: Fact-checking service
            claim_text: Text of the claim to verify
            
        Returns:
            FactCheckResult (may have error status)
        """
        try:
            self.logger.debug(f"Verifying with {service.name}: {claim_text[:50]}...")
            result = await service.verify_claim(claim_text)
            self.logger.debug(f"{service.name} result: {result.status.value}")
            return result
        except Exception as e:
            self.logger.error(f"Error in {service.name}: {e}")
            return service.create_error_result(claim_text, str(e))
    
    def _aggregate_results(self, 
                          claim: Claim, 
                          results: List[FactCheckResult],
                          processing_time: int) -> AggregatedVerification:
        """
        Aggregate results from multiple fact-checking services
        
        Args:
            claim: Original claim
            results: Results from fact-checking services
            processing_time: Total processing time in milliseconds
            
        Returns:
            Aggregated verification result
        """
        if not results:
            return self._create_empty_verification(claim, processing_time)
        
        # Check if this claim should have been filtered out
        filtered_explanation = self._check_filtered_claim(claim)
        
        # Calculate weighted overall score
        overall_score = calculate_weighted_score(results)
        overall_status = status_from_score(overall_score)
        
        # Calculate confidence based on agreement and source quality
        confidence = self._calculate_confidence(results, overall_score)
        
        # Extract all unique sources
        all_sources = []
        for result in results:
            all_sources.extend(result.sources)
        
        # Get primary sources (highest credibility)
        primary_sources = sorted(all_sources, key=lambda s: s.credibility_score, reverse=True)[:3]
        
        # Create summary (with filtering context if applicable)
        summary = self._create_summary(results, overall_status, primary_sources, claim, filtered_explanation)
        
        # Create friendly explanation for users
        friendly_explanation = self._create_friendly_explanation(results, overall_status, primary_sources, claim, filtered_explanation)
        
        return AggregatedVerification(
            claim_id=claim.id,
            claim_text=claim.text,
            overall_status=overall_status,
            overall_score=overall_score,
            confidence=confidence,
            fact_check_results=results,
            sources_count=len(all_sources),
            services_used=[result.service_name for result in results],
            summary=summary,
            friendly_explanation=friendly_explanation,
            primary_sources=primary_sources,
            processing_time_ms=processing_time
        )
    
    def _calculate_confidence(self, results: List[FactCheckResult], overall_score: float) -> float:
        """
        Calculate confidence in the aggregated result
        
        Args:
            results: Individual fact-check results
            overall_score: Aggregated verification score
            
        Returns:
            Confidence score (0.0-1.0)
        """
        if not results:
            return 0.0
        
        # Base confidence from number of sources
        base_confidence = min(0.8, len(results) * 0.3)
        
        # Agreement bonus: higher confidence if sources agree
        scores = [r.verification_score for r in results]
        if len(scores) > 1:
            score_variance = sum((score - overall_score) ** 2 for score in scores) / len(scores)
            agreement_bonus = max(0, 0.3 - score_variance)  # Less variance = higher bonus
            base_confidence += agreement_bonus
        
        # Source quality bonus
        total_credibility = sum(
            sum(s.credibility_score for s in result.sources) / max(len(result.sources), 1)
            for result in results
        )
        avg_credibility = total_credibility / len(results)
        quality_bonus = (avg_credibility - 0.5) * 0.2  # Scale credibility to bonus
        base_confidence += quality_bonus
        
        return min(0.95, max(0.1, base_confidence))  # Clamp to reasonable range
    
    def _create_summary(self, 
                       results: List[FactCheckResult],
                       status: VerificationStatus,
                       primary_sources: List,
                       claim: Optional[Claim] = None,
                       filtered_explanation: Optional[str] = None) -> str:
        """Create human-readable summary of verification results with detailed explanations"""
        
        if not results:
            return "No fact-checking results available."
        
        service_names = [r.service_name for r in results]
        source_count = sum(len(r.sources) for r in results)
        
        summary_parts = [
            f"Checked with {len(results)} service(s): {', '.join(service_names)}.",
            f"Found {source_count} fact-checking source(s)."
        ]
        
        # If this claim should have been filtered, explain that first
        if filtered_explanation:
            summary_parts.append(filtered_explanation)
        else:
            # Enhanced status descriptions with evidence details
            detailed_explanation = self._create_detailed_status_explanation(results, status, primary_sources)
            summary_parts.append(detailed_explanation)
        
        return " ".join(summary_parts)
    
    def _create_detailed_status_explanation(self, 
                                           results: List[FactCheckResult],
                                           status: VerificationStatus,
                                           primary_sources: List) -> str:
        """Create detailed explanation incorporating evidence from fact-checking services"""
        
        # Extract explanations from individual services
        service_explanations = []
        source_details = []
        
        for result in results:
            if result.explanation and result.explanation.strip():
                # Clean up the explanation
                clean_explanation = result.explanation.strip()
                if len(clean_explanation) > 150:
                    clean_explanation = clean_explanation[:147] + "..."
                service_explanations.append(f"{result.service_name}: {clean_explanation}")
            
            # Collect specific source details for false claims
            if status in [VerificationStatus.LIKELY_FALSE, VerificationStatus.VERIFIED_FALSE]:
                for source in result.sources:
                    if hasattr(source, 'name') and source.name:
                        source_details.append(source.name)
        
        # Create status-specific explanations
        base_explanations = {
            VerificationStatus.VERIFIED_TRUE: "Multiple sources confirm this claim as accurate.",
            VerificationStatus.LIKELY_TRUE: "Evidence suggests this claim is likely true.",
            VerificationStatus.MIXED: "Sources show mixed evidence for this claim.",
            VerificationStatus.LIKELY_FALSE: self._create_false_claim_explanation(service_explanations, source_details),
            VerificationStatus.VERIFIED_FALSE: self._create_false_claim_explanation(service_explanations, source_details, is_verified=True),
            VerificationStatus.UNVERIFIED: "No verification information found for this claim."
        }
        
        explanation_parts = []
        
        # Add base explanation
        if status in base_explanations:
            explanation_parts.append(base_explanations[status])
        
        # Add service explanations for true/mixed claims if available
        if status in [VerificationStatus.VERIFIED_TRUE, VerificationStatus.LIKELY_TRUE, VerificationStatus.MIXED]:
            if service_explanations:
                explanation_parts.append(f"Details: {service_explanations[0]}")
        
        # Add primary source info for non-false claims
        if status not in [VerificationStatus.LIKELY_FALSE, VerificationStatus.VERIFIED_FALSE] and primary_sources:
            top_source = primary_sources[0]
            explanation_parts.append(f"Primary source: {top_source.name}.")
        
        return " ".join(explanation_parts)
    
    def _create_false_claim_explanation(self, 
                                       service_explanations: List[str],
                                       source_details: List[str],
                                       is_verified: bool = False) -> str:
        """Create detailed explanation for false claims with specific evidence"""
        
        if is_verified:
            base_msg = "Multiple sources confirm this claim as false."
        else:
            base_msg = "Evidence suggests this claim is likely false."
        
        # If we have specific explanations from services, use them
        if service_explanations:
            # Find the most informative explanation
            best_explanation = max(service_explanations, key=len)
            if "No fact-checks found" not in best_explanation and "No similar claims found" not in best_explanation:
                return f"{base_msg} {best_explanation}"
        
        # If we have source names, mention them
        if source_details:
            unique_sources = list(set(source_details))[:3]  # Limit to 3 sources
            if len(unique_sources) == 1:
                return f"{base_msg} Contradicted by {unique_sources[0]}."
            elif len(unique_sources) > 1:
                return f"{base_msg} Contradicted by sources including {', '.join(unique_sources)}."
        
        # Fallback to base message
        return base_msg
    
    def _check_filtered_claim(self, claim: Claim) -> Optional[str]:
        """Check if a claim should have been filtered and create an explanation"""
        
        # Check if claim has filtering information
        if hasattr(claim, 'should_fact_check') and claim.should_fact_check is False:
            reason = getattr(claim, 'classification_reason', 'Unknown reason')
            
            # Create a helpful explanation about why this claim was fact-checked anyway
            explanations = {
                # Conversational fillers
                "Pure conversational filler": "This appears to be a conversational filler rather than a factual claim, so the fact-checking result may not be meaningful.",
                "Conversational pattern": "This appears to be conversational speech rather than a factual claim, so the fact-checking result may not be meaningful.",
                "Topic introduction": "This appears to be a topic introduction rather than a factual claim, so the fact-checking result may not be meaningful.",
                "Too short and non-substantive": "This text is too short to contain a meaningful factual claim, so the fact-checking result may not be meaningful.",
                
                # Questions
                "Direct question": "This is a question rather than a factual claim, so the fact-checking result may not be meaningful.",
                "Question pattern detected": "This appears to be a question rather than a factual claim, so the fact-checking result may not be meaningful.",
                
                # Hypothetical scenarios
                "Hypothetical scenario": "This appears to be a hypothetical scenario rather than a factual claim, so the fact-checking result may not be meaningful.",
                
                # Mangled text
                "Text corruption detected": "This text appears to be corrupted or incomplete, so the fact-checking result may not be meaningful.",
                "Mangled text pattern": "This text appears to be incomplete or corrupted, so the fact-checking result may not be meaningful.",
                "Suspiciously long unpunctuated text": "This text appears to be corrupted or concatenated, so the fact-checking result may not be meaningful.",
                "Too many filler words": "This text contains too many filler words to be a clear factual claim, so the fact-checking result may not be meaningful."
            }
            
            # Find best matching explanation
            for key, explanation in explanations.items():
                if key.lower() in reason.lower():
                    return explanation
            
            # Default explanation if no specific match
            return f"This text was identified as non-factual content ({reason}), so the fact-checking result may not be meaningful."
        
        return None
    
    def _create_friendly_explanation(self, 
                                    results: List[FactCheckResult],
                                    status: VerificationStatus,
                                    primary_sources: List,
                                    claim: Optional[Claim] = None,
                                    filtered_explanation: Optional[str] = None) -> str:
        """Create a user-friendly explanation in simple terms"""
        
        # Handle filtered claims first
        if filtered_explanation:
            if "conversational filler" in filtered_explanation.lower():
                return "⚠️ This doesn't appear to be a factual claim - it looks like conversational speech."
            elif "question" in filtered_explanation.lower():
                return "⚠️ This is a question, not a claim that can be fact-checked."
            elif "hypothetical" in filtered_explanation.lower():
                return "⚠️ This appears to be a hypothetical scenario rather than a factual claim."
            elif "corrupted" in filtered_explanation.lower() or "incomplete" in filtered_explanation.lower():
                return "⚠️ This text appears to be incomplete or corrupted, making fact-checking unreliable."
            elif "too short" in filtered_explanation.lower():
                return "⚠️ This text is too brief to contain a meaningful factual claim."
            else:
                return "⚠️ This text was flagged as non-factual content, so the fact-checking results may not be meaningful."
        
        # Handle different verification statuses
        if status == VerificationStatus.VERIFIED_TRUE:
            if primary_sources:
                source_names = [s.name for s in primary_sources[:2]]
                return f"✅ This claim is **TRUE**. Reliable sources like {' and '.join(source_names)} confirm it."
            else:
                return "✅ This claim is **TRUE** according to multiple fact-checking sources."
        
        elif status == VerificationStatus.LIKELY_TRUE:
            if primary_sources:
                source_names = [s.name for s in primary_sources[:2]]
                return f"✅ This claim is **likely TRUE**. Sources like {' and '.join(source_names)} support it."
            else:
                return "✅ This claim is **likely TRUE** based on available evidence."
        
        elif status == VerificationStatus.MIXED:
            return "🔄 This claim has **MIXED EVIDENCE**. Some sources support it while others contradict it. More research may be needed."
        
        elif status == VerificationStatus.LIKELY_FALSE:
            # Extract key evidence for false claims
            evidence_parts = []
            
            # Look for specific contradictory evidence
            for result in results:
                if result.explanation and "contradicted" in result.explanation.lower():
                    evidence_parts.append("contradictory evidence found")
                    break
                elif result.sources:
                    source_names = [s.name for s in result.sources[:2]]
                    evidence_parts.append(f"sources like {' and '.join(source_names)} disagree")
                    break
            
            if evidence_parts:
                return f"❌ This claim is **likely FALSE**. Fact-checkers found {evidence_parts[0]}."
            else:
                return "❌ This claim is **likely FALSE** according to fact-checking sources."
        
        elif status == VerificationStatus.VERIFIED_FALSE:
            if primary_sources:
                source_names = [s.name for s in primary_sources[:2]]
                return f"❌ This claim is **FALSE**. Multiple reliable sources including {' and '.join(source_names)} have debunked it."
            else:
                return "❌ This claim is **FALSE** - it has been thoroughly debunked by fact-checkers."
        
        elif status == VerificationStatus.UNVERIFIED:
            return "🔍 This claim could **NOT BE VERIFIED**. No reliable fact-checking information was found."
        
        # Fallback
        return "🔍 Unable to determine the accuracy of this claim based on available information."
    
    def _create_empty_verification(self,
                                  claim: Claim, 
                                  processing_time: int = 0) -> AggregatedVerification:
        """Create verification result when no services are available"""
        
        return AggregatedVerification(
            claim_id=claim.id,
            claim_text=claim.text,
            overall_status=VerificationStatus.UNVERIFIED,
            overall_score=0.5,  # Neutral
            confidence=0.0,
            fact_check_results=[],
            sources_count=0,
            services_used=[],
            summary="Fact-checking services not available.",
            primary_sources=[],
            processing_time_ms=processing_time
        )
    
    async def close(self):
        """Close all services and clean up resources"""
        for service in self.services:
            if hasattr(service, 'close'):
                try:
                    await service.close()
                except Exception as e:
                    self.logger.error(f"Error closing {service.name}: {e}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status information about all services"""
        status = {
            'total_services': len(self.services),
            'services': []
        }
        
        for service in self.services:
            service_status = {
                'name': service.name,
                'available': service.is_available(),
                'type': service.__class__.__name__
            }
            
            # Add service-specific info
            if hasattr(service, 'get_database_stats'):
                service_status['database_stats'] = service.get_database_stats()
            
            status['services'].append(service_status)
        
        return status
