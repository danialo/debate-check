"""
Main claim extraction pipeline integrating all components
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional

from .models import ExtractionResult
from .preprocessor import DebatePreprocessor
from .segmenter import DebateSegmenter
from .claim_detector import DebateClaimDetector
from .postprocessor import ClaimPostprocessor
from ..fact_checking import FactVerificationPipeline, FactCheckConfig

logger = logging.getLogger(__name__)


class ClaimExtractionPipeline:
    """
    Main pipeline for extracting claims from debate transcripts.
    
    Pipeline flow:
    1. Preprocessing: Clean text and identify speakers
    2. Segmentation: Split into sentences with position tracking
    3. Claim Detection: Apply rule-based detectors to find claims
    4. Post-processing: Deduplicate and add context
    5. Return structured results
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the pipeline with optional configuration.
        
        Args:
            config_path: Path to YAML configuration file (future enhancement)
        """
        self.config_path = config_path
        
        # Initialize components
        logger.info("Initializing claim extraction pipeline")
        
        self.preprocessor = DebatePreprocessor()
        self.segmenter = DebateSegmenter()
        self.claim_detector = DebateClaimDetector()
        self.postprocessor = ClaimPostprocessor()
        
        # Fact-checking pipeline (initialized on-demand)
        self.fact_pipeline = None
        
        logger.info("Pipeline initialization complete")
    
    def extract(self, text: str, source: str = "unknown") -> ExtractionResult:
        """
        Extract claims from debate transcript text.
        
        Args:
            text: Raw debate transcript text
            source: Source identifier for metadata
            
        Returns:
            ExtractionResult with claims and metadata
        """
        try:
            logger.info(f"Starting claim extraction for source: {source}")
            
            # Step 1: Preprocessing
            logger.debug("Step 1: Preprocessing text")
            utterances = self.preprocessor.process(text)
            
            if not utterances:
                logger.warning("No utterances found after preprocessing")
                return ExtractionResult(
                    claims=[],
                    meta={"source": source, "error": "No utterances found"}
                )
            
            # Step 2: Segmentation
            logger.debug("Step 2: Segmenting into sentences")
            sentences = self.segmenter.segment(utterances)
            
            if not sentences:
                logger.warning("No sentences found after segmentation")
                return ExtractionResult(
                    claims=[],
                    meta={"source": source, "error": "No sentences found"}
                )
            
            # Step 3: Claim Detection
            logger.debug("Step 3: Detecting claims")
            raw_claims = self.claim_detector.detect_claims(sentences)
            
            # Step 4: Post-processing
            logger.debug("Step 4: Post-processing claims")
            final_claims = self.postprocessor.process(raw_claims, sentences)
            
            # Step 5: Create results
            result = ExtractionResult(claims=final_claims)
            result.meta.update({
                "source": source,
                "utterances_processed": len(utterances),
                "sentences_processed": len(sentences),
                "raw_claims_detected": len(raw_claims)
            })
            
            logger.info(f"Extraction complete: {len(final_claims)} final claims from {source}")
            return result
            
        except Exception as e:
            logger.error(f"Pipeline failed for source {source}: {e}")
            logger.exception("Full traceback:")
            
            # Return error result instead of raising
            return ExtractionResult(
                claims=[],
                meta={
                    "source": source,
                    "error": str(e),
                    "pipeline_failed": True
                }
            )
    
    def extract_with_fact_checking(self, 
                                  text: str, 
                                  source: str = "unknown",
                                  fact_config: Optional[FactCheckConfig] = None) -> ExtractionResult:
        """
        Extract claims with integrated fact-checking.
        
        Args:
            text: Raw debate transcript text
            source: Source identifier for metadata
            fact_config: Fact-checking configuration
            
        Returns:
            ExtractionResult with claims and fact-checking data
        """
        # First, extract claims normally
        result = self.extract(text, source)
        
        if not result.claims:
            logger.info("No claims to fact-check")
            return result
        
        # Run fact-checking if claims were found
        try:
            logger.info(f"Starting fact-checking for {len(result.claims)} claims")
            
            # Use asyncio to run fact-checking
            fact_results = asyncio.run(self._run_fact_checking(result.claims, fact_config))
            
            # Update result with fact-checking data
            result.fact_checking_enabled = True
            result.fact_check_results = [fr.model_dump() for fr in fact_results]
            
            # Update metadata
            result.meta.update({
                "fact_checking_performed": True,
                "fact_checked_claims": len(fact_results),
                "fact_checking_services": list(set(
                    service for fr in fact_results for service in fr.services_used
                )),
                "verification_summary": {
                    status: len([fr for fr in fact_results if fr.overall_status == status])
                    for status in ["verified_true", "likely_true", "mixed", "likely_false", "verified_false", "unverified"]
                }
            })
            
            logger.info(f"Fact-checking complete for {len(fact_results)} claims")
            
        except Exception as e:
            logger.error(f"Fact-checking failed: {e}")
            logger.exception("Fact-checking traceback:")
            
            # Update result to indicate fact-checking failed
            result.meta.update({
                "fact_checking_attempted": True,
                "fact_checking_error": str(e)
            })
        
        return result
    
    async def _run_fact_checking(self, claims, fact_config):
        """Run fact-checking in async context"""
        # Initialize fact-checking pipeline if needed
        if self.fact_pipeline is None:
            self.fact_pipeline = FactVerificationPipeline(fact_config)
        
        try:
            # Verify all claims
            fact_results = await self.fact_pipeline.verify_claims(claims)
            return fact_results
        finally:
            # Clean up if needed
            if self.fact_pipeline:
                await self.fact_pipeline.close()
    
    def get_fact_checking_status(self):
        """Get status of fact-checking services"""
        if self.fact_pipeline is None:
            return {"status": "not_initialized"}
        
        return self.fact_pipeline.get_service_status()
