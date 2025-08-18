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
    
    def _enhance_regular_result(self, result: ExtractionResult) -> Dict[str, Any]:
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
