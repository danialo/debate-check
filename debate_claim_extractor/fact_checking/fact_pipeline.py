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
        
        self.logger.info(f"Verifying {len(claims)} claims")
        
        # Process claims in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(5)  # Limit concurrent verifications
        
        async def verify_with_limit(claim):
            async with semaphore:
                return await self.verify_claim(claim)
        
        tasks = [verify_with_limit(claim) for claim in claims]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, AggregatedVerification):
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Claim verification error: {result}")
        
        self.logger.info(f"Completed fact-checking for {len(valid_results)}/{len(claims)} claims")
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
        
        # Create summary
        summary = self._create_summary(results, overall_status, primary_sources)
        
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
                       primary_sources: List) -> str:
        """Create human-readable summary of verification results"""
        
        if not results:
            return "No fact-checking results available."
        
        service_names = [r.service_name for r in results]
        source_count = sum(len(r.sources) for r in results)
        
        summary_parts = [
            f"Checked with {len(results)} service(s): {', '.join(service_names)}.",
            f"Found {source_count} fact-checking source(s)."
        ]
        
        # Add status description
        status_descriptions = {
            VerificationStatus.VERIFIED_TRUE: "Multiple sources confirm this claim as accurate.",
            VerificationStatus.LIKELY_TRUE: "Evidence suggests this claim is likely true.",
            VerificationStatus.MIXED: "Sources show mixed evidence for this claim.",
            VerificationStatus.LIKELY_FALSE: "Evidence suggests this claim is likely false.",
            VerificationStatus.VERIFIED_FALSE: "Multiple sources confirm this claim as false.",
            VerificationStatus.UNVERIFIED: "No verification information found for this claim."
        }
        
        if status in status_descriptions:
            summary_parts.append(status_descriptions[status])
        
        # Add primary source info
        if primary_sources:
            top_source = primary_sources[0]
            summary_parts.append(f"Primary source: {top_source.name}.")
        
        return " ".join(summary_parts)
    
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
