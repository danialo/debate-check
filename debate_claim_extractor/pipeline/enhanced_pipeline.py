"""
Enhanced claim extraction pipeline with improved filtering and fact-checking routing
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional

from .models import ExtractionResult
from .preprocessor import DebatePreprocessor
from .segmenter import DebateSegmenter
from .claim_detector import DebateClaimDetector
from .enhanced_postprocessor import EnhancedClaimPostprocessor
from ..fact_checking import FactVerificationPipeline, FactCheckConfig
from ..fallacy_detection import DebateFallacyDetector, FallacyDetectionSummary
from ..scoring import ScoringPipeline

logger = logging.getLogger(__name__)


class EnhancedClaimExtractionPipeline:
    """
    Enhanced pipeline with intelligent claim filtering and appropriate fact-checking.
    
    Improvements over base pipeline:
    1. Filters out conversational fillers, questions, and hypotheticals
    2. Classifies claims as factual vs. normative/philosophical
    3. Only fact-checks claims that should be fact-checked
    4. Preserves claim metadata throughout pipeline
    """
    
    def __init__(self, config_path: Optional[Path] = None, enable_filtering: bool = True):
        """
        Initialize the enhanced pipeline.
        
        Args:
            config_path: Path to YAML configuration file (future enhancement)
            enable_filtering: Whether to enable intelligent claim filtering
        """
        self.config_path = config_path
        self.enable_filtering = enable_filtering
        
        # Initialize components
        logger.info("Initializing enhanced claim extraction pipeline")
        
        self.preprocessor = DebatePreprocessor()
        self.segmenter = DebateSegmenter()
        self.claim_detector = DebateClaimDetector()
        self.postprocessor = EnhancedClaimPostprocessor(enable_filtering=enable_filtering)
        
        # Analysis pipelines (initialized on-demand)
        self.fact_pipeline = None
        self.fallacy_detector = None
        self.scoring_pipeline = None
        
        logger.info(f"Enhanced pipeline initialization complete (filtering: {enable_filtering})")
    
    def extract(self, text: str, source: str = "unknown") -> ExtractionResult:
        """
        Extract claims from debate transcript text with intelligent filtering.
        
        Args:
            text: Raw debate transcript text
            source: Source identifier for metadata
            
        Returns:
            ExtractionResult with filtered and classified claims
        """
        try:
            logger.info(f"Starting enhanced claim extraction for source: {source}")
            
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
            
            # Step 4: Enhanced Post-processing (includes filtering and classification)
            logger.debug("Step 4: Enhanced post-processing with filtering")
            final_claims = self.postprocessor.process(raw_claims, sentences)
            
            # Step 5: Create results with enhanced metadata
            result = ExtractionResult(claims=final_claims)
            result.meta.update({
                "source": source,
                "processing_method": "enhanced_pipeline",
                "filtering_enabled": self.enable_filtering,
                "utterances_processed": len(utterances),
                "sentences_processed": len(sentences),
                "raw_claims_detected": len(raw_claims)
            })
            
            logger.info(f"Enhanced extraction complete: {len(final_claims)} final claims from {source}")
            return result
            
        except Exception as e:
            logger.error(f"Enhanced pipeline failed for source {source}: {e}")
            logger.exception("Full traceback:")
            
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
        Extract claims with intelligent fact-checking that respects claim classifications.
        
        Args:
            text: Raw debate transcript text
            source: Source identifier for metadata
            fact_config: Fact-checking configuration
            
        Returns:
            ExtractionResult with claims and selective fact-checking data
        """
        # First, extract and classify claims
        result = self.extract(text, source)
        
        if not result.claims:
            logger.info("No claims to fact-check")
            return result
        
        # Filter claims that should be fact-checked
        claims_to_check = []
        claims_skipped = []
        
        for claim in result.claims:
            if getattr(claim, 'should_fact_check', True):  # Default to fact-checking if not set
                claims_to_check.append(claim)
            else:
                claims_skipped.append(claim)
        
        logger.info(f"Fact-checking {len(claims_to_check)} claims, skipping {len(claims_skipped)} claims")
        
        # Run fact-checking on appropriate claims
        try:
            if claims_to_check:
                logger.info(f"Starting selective fact-checking for {len(claims_to_check)} claims")
                
                # Use asyncio to run fact-checking
                fact_results = asyncio.run(self._run_fact_checking(claims_to_check, fact_config))
                
                # Update result with fact-checking data
                result.fact_checking_enabled = True
                result.fact_check_results = [fr.model_dump() for fr in fact_results]
            else:
                logger.info("No claims require fact-checking after classification")
                result.fact_checking_enabled = True
                result.fact_check_results = []
            
            # Update metadata
            result.meta.update({
                "fact_checking_performed": True,
                "fact_checked_claims": len(claims_to_check),
                "fact_checking_skipped": len(claims_skipped),
                "selective_fact_checking": True,
                "verification_summary": self._create_verification_summary(result.fact_check_results) if claims_to_check else {}
            })
            
            logger.info(f"Selective fact-checking complete")
            
        except Exception as e:
            logger.error(f"Fact-checking failed: {e}")
            logger.exception("Fact-checking traceback:")
            
            result.meta.update({
                "fact_checking_attempted": True,
                "fact_checking_error": str(e)
            })
        
        return result
    
    def extract_with_comprehensive_analysis(self, 
                                          text: str, 
                                          source: str = "unknown",
                                          fact_config: Optional[FactCheckConfig] = None) -> ExtractionResult:
        """
        Extract claims with comprehensive analysis: filtering, selective fact-checking, fallacy detection, and scoring.
        
        Args:
            text: Raw debate transcript text
            source: Source identifier for metadata
            fact_config: Fact-checking configuration
            
        Returns:
            ExtractionResult with full analysis
        """
        try:
            logger.info(f"Starting comprehensive enhanced analysis for source: {source}")
            
            # Step 1-4: Enhanced claim extraction with filtering
            result = self.extract(text, source)
            
            if not result.claims:
                logger.info("No claims for comprehensive analysis")
                return result
            
            # Step 5: Fallacy Detection
            logger.debug("Step 5: Detecting fallacies")
            utterances = self.preprocessor.process(text)
            sentences = self.segmenter.segment(utterances)
            fallacies = self._run_fallacy_detection(result.claims, sentences)
            
            # Update result with fallacy data
            result.fallacy_detection_enabled = True
            result.fallacies = [f.to_dict() for f in fallacies]
            result.fallacy_summary = FallacyDetectionSummary.from_fallacies(fallacies).to_dict()
            result.meta["fallacies_detected"] = len(fallacies)
            
            # Step 6: Selective Fact-checking
            if fact_config and fact_config.enabled:
                claims_to_check = [c for c in result.claims if getattr(c, 'should_fact_check', True)]
                claims_skipped = len(result.claims) - len(claims_to_check)
                
                logger.info(f"Fact-checking {len(claims_to_check)} claims, skipping {claims_skipped} claims")
                
                if claims_to_check:
                    fact_results = self._run_fact_checking_sync(claims_to_check, fact_config)
                    result.fact_checking_enabled = True
                    result.fact_check_results = [fr.model_dump() for fr in fact_results]
                else:
                    result.fact_checking_enabled = True
                    result.fact_check_results = []
            else:
                logger.info("Fact-checking disabled or no config provided")
                result.fact_checking_enabled = False
                result.fact_check_results = []
            
            # Step 7: Scoring
            logger.debug("Step 7: Generating comprehensive scores")
            self._run_scoring(result, source)
            
            # Update comprehensive metadata
            fact_checked_count = len(claims_to_check) if fact_config and fact_config.enabled and claims_to_check else 0
            fact_skipped_count = claims_skipped if fact_config and fact_config.enabled else 0
            
            result.meta.update({
                "comprehensive_analysis": True,
                "fact_checked_claims": fact_checked_count,
                "fact_checking_skipped": fact_skipped_count,
                "fallacies_detected": len(fallacies),
                "selective_fact_checking": fact_config.enabled if fact_config else False
            })
            
            logger.info(f"Comprehensive enhanced analysis complete: {len(result.claims)} claims processed")
            return result
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed for source {source}: {e}")
            logger.exception("Full traceback:")
            
            return ExtractionResult(
                claims=result.claims if 'result' in locals() else [],
                meta={
                    "source": source,
                    "error": str(e),
                    "comprehensive_analysis_failed": True
                }
            )
    
    async def _run_fact_checking(self, claims, fact_config):
        """Run fact-checking in async context"""
        if self.fact_pipeline is None:
            self.fact_pipeline = FactVerificationPipeline(fact_config)
        
        try:
            fact_results = await self.fact_pipeline.verify_claims(claims)
            return fact_results
        finally:
            if self.fact_pipeline:
                await self.fact_pipeline.close()
    
    def _run_fact_checking_sync(self, claims, fact_config):
        """Synchronous wrapper for fact-checking that handles existing event loops"""
        import concurrent.futures
        import threading
        
        def run_in_thread():
            # Create a new event loop in the thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._run_fact_checking(claims, fact_config))
            finally:
                loop.close()
        
        # Run fact-checking in a separate thread with its own event loop
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()
    
    def _run_fallacy_detection(self, claims, sentences):
        """Run fallacy detection on claims and sentences"""
        if self.fallacy_detector is None:
            self.fallacy_detector = DebateFallacyDetector()
        
        fallacies = self.fallacy_detector.detect_fallacies(claims, sentences)
        
        # Update claims with fallacy information
        for claim in claims:
            claim_fallacies = [f for f in fallacies if f.target_claim_id == claim.id]
            if claim_fallacies:
                claim.fallacies = [f.to_dict() for f in claim_fallacies]
                claim.fallacy_score = sum(f.confidence for f in claim_fallacies) / len(claim_fallacies)
        
        return fallacies
    
    def _run_scoring(self, result: ExtractionResult, source: str = "unknown"):
        """Run scoring on extraction result"""
        try:
            logger.info(f"Starting scoring analysis for {len(result.claims)} claims")
            
            if self.scoring_pipeline is None:
                self.scoring_pipeline = ScoringPipeline()
            
            scoring_result = self.scoring_pipeline.score_extraction_result(result, source=source)
            
            result.scoring_enabled = True
            result.scoring_result = scoring_result.model_dump()
            
            result.meta.update({
                "scoring_performed": scoring_result.scoring_performed,
                "scoring_time_seconds": scoring_result.processing_time_seconds
            })
            
            if scoring_result.scoring_error:
                result.meta["scoring_error"] = scoring_result.scoring_error
                logger.warning(f"Scoring completed with error: {scoring_result.scoring_error}")
            else:
                logger.info(f"Scoring complete: {scoring_result.debate_score.overall_score:.3f} overall score")
                
        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            logger.exception("Scoring traceback:")
            
            result.meta.update({
                "scoring_attempted": True,
                "scoring_error": str(e)
            })
    
    def _create_verification_summary(self, fact_check_results):
        """Create verification summary from fact-check results"""
        if not fact_check_results:
            return {}
        
        summary = {}
        for status in ["verified_true", "likely_true", "mixed", "likely_false", "verified_false", "unverified"]:
            summary[status] = len([fr for fr in fact_check_results if fr.get('overall_status') == status])
        
        return summary
