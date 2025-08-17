"""
Main claim extraction pipeline integrating all components
"""

import logging
from pathlib import Path
from typing import Optional

from .models import ExtractionResult
from .preprocessor import DebatePreprocessor
from .segmenter import DebateSegmenter
from .claim_detector import DebateClaimDetector
from .postprocessor import ClaimPostprocessor

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
