"""
Smart transcript chunking for YouTube-style long transcripts
Breaks down long continuous transcripts into logical segments for better claim extraction
"""

import re
import logging
from typing import List, Tuple, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TranscriptChunk:
    """A logical chunk of transcript with metadata"""
    text: str
    start_char: int
    end_char: int
    chunk_id: int
    estimated_speaker: str = "UNKNOWN"
    confidence: float = 0.0
    context_before: str = ""
    context_after: str = ""


class SmartTranscriptChunker:
    """
    Intelligently chunks long YouTube-style transcripts for better processing
    """
    
    def __init__(self, 
                 target_chunk_size: int = 1000,
                 max_chunk_size: int = 2000,
                 overlap_size: int = 100):
        """
        Args:
            target_chunk_size: Ideal chunk size in characters
            max_chunk_size: Maximum chunk size before forced split
            overlap_size: Character overlap between chunks for context
        """
        self.target_chunk_size = target_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        
        # Patterns that suggest speaker changes or topic transitions
        self.speaker_indicators = [
            r'\b(Neil|Charles|Chuck|Dr\.|Professor)\b',  # Name mentions
            r'\b(I think|In my opinion|My view is|I believe)\b',  # Opinion markers
            r'\b(But|However|On the other hand|Actually)\b',  # Contrast markers
            r'\b(Let me|Can I|So)\b',  # Turn-taking markers
            r'\b(Yeah|Right|Exactly|Absolutely)\b',  # Agreement/response markers
        ]
        
        # Strong sentence boundaries for chunking
        self.strong_boundaries = [
            r'[.!?]+\s+[A-Z]',  # Sentence ending + capital letter
            r'[.!?]+\s*\b(So|Now|But|However|Actually|Let me|Can I)\b',  # Transition words
            r'\b(okay|alright|right)\b[.!?]*\s+',  # Conversational markers
        ]
    
    def chunk_transcript(self, text: str) -> List[TranscriptChunk]:
        """
        Chunk a long transcript into logical segments
        
        Args:
            text: Long transcript text
            
        Returns:
            List of TranscriptChunk objects
        """
        if len(text) <= self.target_chunk_size:
            # Short enough, return as single chunk
            return [TranscriptChunk(
                text=text,
                start_char=0,
                end_char=len(text),
                chunk_id=0
            )]
        
        logger.info(f"Chunking transcript of {len(text)} characters")
        
        # Find potential chunk boundaries
        boundaries = self._find_chunk_boundaries(text)
        
        # Create chunks based on boundaries
        chunks = self._create_chunks(text, boundaries)
        
        # Add context and speaker inference
        chunks = self._enhance_chunks(chunks, text)
        
        logger.info(f"Created {len(chunks)} chunks (avg size: {sum(len(c.text) for c in chunks) // len(chunks)} chars)")
        
        return chunks
    
    def _find_chunk_boundaries(self, text: str) -> List[int]:
        """Find good places to split the transcript"""
        boundaries = [0]  # Always start at beginning
        
        # Look for strong sentence boundaries within target ranges
        pos = 0
        while pos < len(text):
            # Look for next boundary after target size
            search_start = pos + self.target_chunk_size
            search_end = min(pos + self.max_chunk_size, len(text))
            
            if search_start >= len(text):
                break
            
            # Find the best boundary in this range
            best_boundary = self._find_best_boundary(text, search_start, search_end)
            
            if best_boundary == -1:
                # No good boundary found, force split at max size
                best_boundary = search_end
            
            boundaries.append(best_boundary)
            pos = best_boundary
        
        # Always end at the end
        if boundaries[-1] != len(text):
            boundaries.append(len(text))
        
        return boundaries
    
    def _find_best_boundary(self, text: str, start: int, end: int) -> int:
        """Find the best boundary within a range"""
        best_pos = -1
        best_score = -1
        
        # Score each potential boundary position
        for pattern in self.strong_boundaries:
            for match in re.finditer(pattern, text[start:end]):
                pos = start + match.end()
                score = self._score_boundary(text, pos)
                
                if score > best_score:
                    best_score = score
                    best_pos = pos
        
        return best_pos
    
    def _score_boundary(self, text: str, pos: int) -> float:
        """Score how good a boundary position is"""
        score = 0.0
        
        # Prefer positions closer to target size
        distance_from_target = abs(pos % self.target_chunk_size - self.target_chunk_size)
        score += (self.target_chunk_size - distance_from_target) / self.target_chunk_size
        
        # Check for speaker indicators around this position
        context = text[max(0, pos-50):pos+50]
        for pattern in self.speaker_indicators:
            if re.search(pattern, context, re.IGNORECASE):
                score += 0.5
        
        # Prefer complete sentences
        if pos < len(text) and text[pos-1] in '.!?':
            score += 0.3
        
        return score
    
    def _create_chunks(self, text: str, boundaries: List[int]) -> List[TranscriptChunk]:
        """Create chunk objects from boundary positions"""
        chunks = []
        
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            
            chunk_text = text[start:end].strip()
            if chunk_text:  # Skip empty chunks
                chunks.append(TranscriptChunk(
                    text=chunk_text,
                    start_char=start,
                    end_char=end,
                    chunk_id=i
                ))
        
        return chunks
    
    def _enhance_chunks(self, chunks: List[TranscriptChunk], full_text: str) -> List[TranscriptChunk]:
        """Add context and speaker inference to chunks"""
        for i, chunk in enumerate(chunks):
            # Add context from adjacent chunks
            if i > 0:
                prev_chunk = chunks[i-1]
                context_start = max(0, len(prev_chunk.text) - self.overlap_size)
                chunk.context_before = prev_chunk.text[context_start:]
            
            if i < len(chunks) - 1:
                next_chunk = chunks[i+1]
                chunk.context_after = next_chunk.text[:self.overlap_size]
            
            # Infer likely speaker for this chunk
            chunk.estimated_speaker, chunk.confidence = self._infer_speaker(chunk, i)
        
        return chunks
    
    def _infer_speaker(self, chunk: TranscriptChunk, chunk_index: int) -> Tuple[str, float]:
        """
        Attempt to infer the speaker for this chunk based on context clues
        """
        text = chunk.text.lower()
        confidence = 0.1  # Base confidence for unknown
        
        # Look for explicit name mentions
        if 'neil' in text or 'tyson' in text:
            if 'neil' in text and len(text) < 500:  # Short chunks mentioning Neil likely from someone else
                return "OTHER", 0.6
            else:
                return "NEIL", 0.7
        
        if 'charles' in text or 'chuck' in text:
            if ('charles' in text or 'chuck' in text) and len(text) < 500:
                return "OTHER", 0.6
            else:
                return "CHARLES", 0.7
        
        # Look for first-person indicators
        first_person_count = len(re.findall(r'\bi\s+(?:think|believe|feel|am|was|have|had)\b', text))
        if first_person_count > 2:
            confidence += 0.3
        
        # Look for response patterns
        if text.startswith(('yeah', 'right', 'exactly', 'but', 'however')):
            confidence += 0.2
        
        # Alternate speakers based on chunk position (simple heuristic)
        if chunk_index % 2 == 0:
            speaker = "SPEAKER_A"
        else:
            speaker = "SPEAKER_B"
        
        return speaker, confidence
