"""
Enhanced pipeline for YouTube-style transcript processing
Integrates smart chunking, claim clustering, and speaker inference
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from .pipeline import ClaimExtractionPipeline
from .transcript_chunker import SmartTranscriptChunker, TranscriptChunk
from .claim_clusterer import ClaimClusterer, ClaimCluster
from .models import ExtractionResult, Claim
from ..fallacy_detection import DebateFallacyDetector, FallacyDetectionSummary

logger = logging.getLogger(__name__)


class YouTubePipeline(ClaimExtractionPipeline):
    """
    Enhanced pipeline specifically for YouTube-style long transcripts
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the YouTube-optimized pipeline"""
        super().__init__(config_path)
        
        # Add YouTube-specific components
        self.chunker = SmartTranscriptChunker()
        self.clusterer = ClaimClusterer(similarity_threshold=0.4)  # Lower threshold for YouTube
        
        logger.info("Initialized YouTube-optimized pipeline")
    
    def extract(self, text: str, source: str = "unknown") -> Dict[str, Any]:
        """
        Enhanced extraction for YouTube-style transcripts
        
        Args:
            text: Raw transcript text (possibly very long)
            source: Source identifier
            
        Returns:
            Enhanced results with chunking and clustering information
        """
        logger.info(f"Starting YouTube pipeline for source: {source}")
        logger.info(f"Input length: {len(text)} characters")
        
        try:
            # Step 1: Smart chunking for long transcripts
            if len(text) > 2000:  # Use chunking for long transcripts
                return self._process_long_transcript(text, source)
            else:
                # Use regular pipeline for short transcripts
                regular_result = super().extract(text, source)
                return self._enhance_regular_result(regular_result)
        
        except Exception as e:
            logger.error(f"YouTube pipeline failed: {e}")
            return {
                "error": str(e),
                "fallback_used": True,
                "source": source
            }
    
    def extract_with_fact_checking(self, 
                                  text: str, 
                                  source: str = "unknown",
                                  fact_config: Optional[Any] = None) -> Dict[str, Any]:
        """
        Enhanced extraction with fact-checking for YouTube-style transcripts
        
        Args:
            text: Raw transcript text
            source: Source identifier
            fact_config: Fact-checking configuration
            
        Returns:
            Enhanced results with fact-checking data
        """
        # First extract normally
        result = self.extract(text, source)
        
        if "error" in result:
            return result
        
        # Get claims from result
        claims = result.get("claims", [])
        if not claims:
            logger.info("No claims to fact-check in YouTube pipeline")
            return result
        
        # Convert dict claims to Claim objects if needed
        from .models import Claim, ClaimType
        claim_objects = []
        for claim_data in claims:
            if isinstance(claim_data, dict):
                claim_obj = Claim(
                    id=claim_data["id"],
                    type=ClaimType(claim_data["type"]),
                    text=claim_data["text"],
                    speaker=claim_data["speaker"],
                    sentence_id=claim_data["sentence_id"],
                    turn_id=claim_data["turn_id"],
                    char_start=claim_data["char_start"],
                    char_end=claim_data["char_end"],
                    context=claim_data.get("context"),
                    confidence=claim_data["confidence"],
                    timestamp=claim_data.get("timestamp")
                )
                claim_objects.append(claim_obj)
            else:
                claim_objects.append(claim_data)  # Already a Claim object
        
        try:
            logger.info(f"Starting fact-checking for {len(claim_objects)} claims in YouTube pipeline")
            
            # Run fact-checking using parent pipeline infrastructure
            import asyncio
            fact_results = asyncio.run(self._run_fact_checking(claim_objects, fact_config))
            
            # Add fact-checking data to result
            result["fact_checking_enabled"] = True
            result["fact_check_results"] = [fr.model_dump() for fr in fact_results]
            
            # Update metadata
            if "meta" not in result:
                result["meta"] = {}
            
            result["meta"].update({
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
            
            logger.info(f"YouTube fact-checking complete for {len(fact_results)} claims")
            
        except Exception as e:
            logger.error(f"YouTube pipeline fact-checking failed: {e}")
            logger.exception("YouTube fact-checking traceback:")
            
            if "meta" not in result:
                result["meta"] = {}
            
            result["meta"].update({
                "fact_checking_attempted": True,
                "fact_checking_error": str(e)
            })
        
        return result
    
    def _process_long_transcript(self, text: str, source: str) -> Dict[str, Any]:
        """Process long YouTube transcript with chunking and clustering"""
        
        # Step 1: Chunk the transcript
        logger.debug("Chunking long transcript")
        chunks = self.chunker.chunk_transcript(text)
        
        # Step 2: Process each chunk through the regular pipeline
        logger.debug(f"Processing {len(chunks)} chunks")
        all_claims = []
        chunk_results = []
        
        for chunk in chunks:
            # Create mock utterances for the preprocessor
            mock_utterances = [(chunk.estimated_speaker, chunk.text, 0)]
            
            # Process through segmentation
            sentences = self.segmenter.segment(mock_utterances)
            
            # Update character positions to be absolute
            for sentence in sentences:
                sentence.char_start += chunk.start_char
                sentence.char_end += chunk.start_char
            
            # Detect claims
            chunk_claims = self.claim_detector.detect_claims(sentences)
            
            # Post-process claims within chunk
            processed_claims = self.postprocessor.process(chunk_claims, sentences)
            
            all_claims.extend(processed_claims)
            
            chunk_results.append({
                "chunk_id": chunk.chunk_id,
                "estimated_speaker": chunk.estimated_speaker,
                "speaker_confidence": chunk.confidence,
                "claims_found": len(processed_claims),
                "char_range": [chunk.start_char, chunk.end_char]
            })
        
        logger.info(f"Extracted {len(all_claims)} claims from {len(chunks)} chunks")
        
        # Step 3: Cluster related claims across chunks
        logger.debug("Clustering claims across chunks")
        clusters = self.clusterer.cluster_claims(all_claims)
        
        # Step 4: Build enhanced results
        result = self._build_youtube_result(
            claims=all_claims,
            clusters=clusters,
            chunks=chunks,
            chunk_results=chunk_results,
            source=source
        )
        
        return result
    
    def extract_with_fallacy_detection(self, text: str, source: str = "unknown") -> Dict[str, Any]:
        """
        Enhanced extraction with fallacy detection for YouTube-style transcripts
        
        Args:
            text: Raw transcript text
            source: Source identifier
            
        Returns:
            Enhanced results with fallacy detection data
        """
        logger.info(f"Starting YouTube pipeline with fallacy detection for source: {source}")
        logger.info(f"Input length: {len(text)} characters")
        
        try:
            # Step 1: Smart chunking for long transcripts
            if len(text) > 2000:  # Use chunking for long transcripts
                return self._process_long_transcript_with_fallacies(text, source)
            else:
                # Use regular pipeline for short transcripts with fallacy detection
                regular_result = super().extract_with_fallacy_detection(text, source)
                return self._enhance_regular_result(regular_result, include_fallacies=True)
        
        except Exception as e:
            logger.error(f"YouTube pipeline with fallacy detection failed: {e}")
            return {
                "error": str(e),
                "fallback_used": True,
                "source": source
            }
    
    def extract_with_all_analysis(self, 
                                text: str, 
                                source: str = "unknown",
                                fact_config: Optional[Any] = None) -> Dict[str, Any]:
        """
        Enhanced extraction with both fact-checking and fallacy detection for YouTube-style transcripts
        
        Args:
            text: Raw transcript text
            source: Source identifier
            fact_config: Fact-checking configuration
            
        Returns:
            Enhanced results with fact-checking and fallacy detection data
        """
        # First run with fallacy detection
        result = self.extract_with_fallacy_detection(text, source)
        
        if "error" in result:
            return result
        
        # Get claims from result and add fact-checking
        claims = result.get("claims", [])
        if not claims:
            logger.info("No claims to fact-check in YouTube pipeline")
            return result
        
        # Convert dict claims to Claim objects if needed
        from .models import Claim, ClaimType
        claim_objects = []
        for claim_data in claims:
            if isinstance(claim_data, dict):
                claim_obj = Claim(
                    id=claim_data["id"],
                    type=ClaimType(claim_data["type"]),
                    text=claim_data["text"],
                    speaker=claim_data["speaker"],
                    sentence_id=claim_data["sentence_id"],
                    turn_id=claim_data["turn_id"],
                    char_start=claim_data["char_start"],
                    char_end=claim_data["char_end"],
                    context=claim_data.get("context"),
                    confidence=claim_data["confidence"],
                    timestamp=claim_data.get("timestamp")
                )
                claim_objects.append(claim_obj)
            else:
                claim_objects.append(claim_data)  # Already a Claim object
        
        try:
            logger.info(f"Starting fact-checking for {len(claim_objects)} claims in YouTube pipeline")
            
            # Run fact-checking using parent pipeline infrastructure
            import asyncio
            fact_results = asyncio.run(self._run_fact_checking(claim_objects, fact_config))
            
            # Add fact-checking data to result
            result["fact_checking_enabled"] = True
            result["fact_check_results"] = [fr.model_dump() for fr in fact_results]
            
            # Update metadata
            if "meta" not in result:
                result["meta"] = {}
            
            result["meta"].update({
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
            
            logger.info(f"YouTube fact-checking complete for {len(fact_results)} claims")
            
        except Exception as e:
            logger.error(f"YouTube pipeline fact-checking failed: {e}")
            logger.exception("YouTube fact-checking traceback:")
            
            if "meta" not in result:
                result["meta"] = {}
            
            result["meta"].update({
                "fact_checking_attempted": True,
                "fact_checking_error": str(e)
            })
        
        return result
    
    def _process_long_transcript_with_fallacies(self, text: str, source: str) -> Dict[str, Any]:
        """Process long YouTube transcript with chunking, clustering, and fallacy detection"""
        
        # Step 1: Chunk the transcript
        logger.debug("Chunking long transcript")
        chunks = self.chunker.chunk_transcript(text)
        
        # Step 2: Process each chunk through the regular pipeline
        logger.debug(f"Processing {len(chunks)} chunks")
        all_claims = []
        all_sentences = []
        chunk_results = []
        
        for chunk in chunks:
            # Create mock utterances for the preprocessor
            mock_utterances = [(chunk.estimated_speaker, chunk.text, 0)]
            
            # Process through segmentation
            sentences = self.segmenter.segment(mock_utterances)
            
            # Update character positions to be absolute
            for sentence in sentences:
                sentence.char_start += chunk.start_char
                sentence.char_end += chunk.start_char
            
            all_sentences.extend(sentences)
            
            # Detect claims
            chunk_claims = self.claim_detector.detect_claims(sentences)
            
            # Post-process claims within chunk
            processed_claims = self.postprocessor.process(chunk_claims, sentences)
            
            all_claims.extend(processed_claims)
            
            chunk_results.append({
                "chunk_id": chunk.chunk_id,
                "estimated_speaker": chunk.estimated_speaker,
                "speaker_confidence": chunk.confidence,
                "claims_found": len(processed_claims),
                "char_range": [chunk.start_char, chunk.end_char]
            })
        
        logger.info(f"Extracted {len(all_claims)} claims from {len(chunks)} chunks")
        
        # Step 3: Fallacy Detection across all claims and sentences
        logger.debug("Detecting fallacies across chunks")
        fallacies = self._run_fallacy_detection(all_claims, all_sentences)
        logger.info(f"YouTube fallacy detection complete for {len(all_claims)} claims")
        
        # Step 4: Cluster related claims across chunks
        logger.debug("Clustering claims across chunks")
        clusters = self.clusterer.cluster_claims(all_claims)
        
        # Step 5: Build enhanced results with fallacy data
        result = self._build_youtube_result_with_fallacies(
            claims=all_claims,
            clusters=clusters,
            chunks=chunks,
            chunk_results=chunk_results,
            fallacies=fallacies,
            source=source
        )
        
        return result
    
    def _enhance_regular_result(self, result, include_fallacies=False) -> Dict[str, Any]:
        """Enhance regular pipeline results with clustering"""
        # Add clustering even for regular results
        clusters = self.clusterer.cluster_claims(result.claims)
        
        enhanced = result.model_dump()
        enhanced.update({
            "youtube_enhanced": True,
            "chunks_used": False,
            "clusters": self._serialize_clusters(clusters)
        })
        
        return enhanced
    
    def _build_youtube_result(self, 
                            claims: list[Claim], 
                            clusters: list[ClaimCluster],
                            chunks: list[TranscriptChunk],
                            chunk_results: list[Dict],
                            source: str) -> Dict[str, Any]:
        """Build comprehensive YouTube processing results"""
        
        # Create base result
        base_result = ExtractionResult(claims=claims)
        base_result.meta.update({
            "source": source,
            "processing_method": "youtube_chunked",
            "chunks_processed": len(chunks),
            "clusters_found": len(clusters)
        })
        
        # Enhanced result with YouTube-specific data
        result = base_result.model_dump()
        result.update({
            "youtube_enhanced": True,
            "chunks_used": True,
            "chunk_analysis": {
                "total_chunks": len(chunks),
                "avg_chunk_size": sum(len(c.text) for c in chunks) // len(chunks) if chunks else 0,
                "speaker_inference": {
                    speaker: len([c for c in chunks if c.estimated_speaker == speaker])
                    for speaker in set(c.estimated_speaker for c in chunks)
                }
            },
            "chunk_details": chunk_results,
            "clusters": self._serialize_clusters(clusters),
            "cluster_analysis": {
                "total_clusters": len(clusters),
                "avg_claims_per_cluster": sum(len(c.claims) for c in clusters) // len(clusters) if clusters else 0,
                "topics_identified": list(set().union(*[c.topics for c in clusters])),
                "stance_distribution": {
                    stance: len([c for c in clusters if c.stance == stance])
                    for stance in ["pro", "con", "neutral"]
                }
            }
        })
        
        return result
    
    def _serialize_clusters(self, clusters: list[ClaimCluster]) -> list[Dict[str, Any]]:
        """Serialize cluster objects for JSON output"""
        serialized = []
        
        for cluster in clusters:
            cluster_data = {
                "id": cluster.id,
                "type": cluster.cluster_type.value,
                "stance": cluster.stance,
                "confidence": cluster.confidence,
                "topics": list(cluster.topics),
                "claims_count": len(cluster.claims),
                "primary_claim": {
                    "id": cluster.primary_claim.id,
                    "text": cluster.primary_claim.text,
                    "speaker": cluster.primary_claim.speaker,
                    "confidence": cluster.primary_claim.confidence
                },
                "all_claim_ids": [claim.id for claim in cluster.claims]
            }
            serialized.append(cluster_data)
        
        return serialized
    
    def _build_youtube_result_with_fallacies(self, 
                                           claims: list[Claim], 
                                           clusters: list[ClaimCluster],
                                           chunks: list[TranscriptChunk],
                                           chunk_results: list[Dict],
                                           fallacies: list,
                                           source: str) -> Dict[str, Any]:
        """Build comprehensive YouTube processing results with fallacy data"""
        
        # Start with regular YouTube result
        result = self._build_youtube_result(claims, clusters, chunks, chunk_results, source)
        
        # Add fallacy detection data
        result["fallacy_detection_enabled"] = True
        result["fallacies"] = [f.to_dict() for f in fallacies]
        result["fallacy_summary"] = FallacyDetectionSummary.from_fallacies(fallacies).to_dict()
        
        # Update metadata
        result["meta"].update({
            "fallacy_detection_performed": True,
            "fallacies_detected": len(fallacies)
        })
        
        return result
