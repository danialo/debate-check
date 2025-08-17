"""
Sentence segmentation for debate transcripts with speaker tracking
"""

import re
import logging
from typing import List, Tuple

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from .models import Sentence

logger = logging.getLogger(__name__)


class DebateSegmenter:
    """
    Segments utterances into sentences while preserving speaker information
    and character positions for downstream processing.
    """
    
    def __init__(self, use_spacy: bool = True):
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.nlp = None
        
        if self.use_spacy:
            try:
                # Try to load English model
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Using spaCy for sentence segmentation")
            except OSError:
                logger.warning("spaCy English model not found. Install with: python -m spacy download en_core_web_sm")
                logger.info("Falling back to rule-based segmentation")
                self.use_spacy = False
        else:
            logger.info("Using rule-based sentence segmentation")
        
        # Fallback sentence boundary patterns
        self.sentence_endings = [
            r'[.!?]+\s+',  # Standard sentence endings
            r'[.!?]+$',    # End of string
        ]
        
        # Patterns that should NOT split sentences
        self.no_split_patterns = [
            r'\b[A-Z]\.',          # Initials (J. Smith)
            r'\b(?:Mr|Ms|Mrs|Dr|Prof|Sen|Rep)\.',  # Titles
            r'\b(?:vs|etc|inc|corp)\.',            # Abbreviations
            r'\d+\.\d+',           # Numbers (3.14)
            r'\.\.\.',             # Ellipsis
        ]
    
    def segment(self, utterances: List[Tuple[str, str, int]]) -> List[Sentence]:
        """
        Segment utterances into individual sentences.
        
        Args:
            utterances: List of (speaker, text, line_number) tuples from preprocessor
            
        Returns:
            List of Sentence objects with position tracking
        """
        sentences = []
        char_offset = 0
        
        for turn_id, (speaker, utterance_text, line_number) in enumerate(utterances):
            # Segment this utterance into sentences
            sent_spans = self._segment_utterance(utterance_text)
            
            for sent_idx, (start, end) in enumerate(sent_spans):
                sentence_text = utterance_text[start:end].strip()
                if sentence_text:  # Skip empty sentences
                    sentence = Sentence(
                        text=sentence_text,
                        speaker=speaker,
                        turn_id=turn_id,
                        sentence_index=sent_idx,
                        char_start=char_offset + start,
                        char_end=char_offset + end,
                        line_number=line_number
                    )
                    sentences.append(sentence)
            
            # Update character offset for next utterance
            char_offset += len(utterance_text) + 1  # +1 for implicit newline
        
        logger.info(f"Segmented {len(utterances)} utterances into {len(sentences)} sentences")
        return sentences
    
    def _segment_utterance(self, text: str) -> List[Tuple[int, int]]:
        """
        Segment a single utterance into sentence spans.
        
        Returns:
            List of (start_char, end_char) tuples for each sentence
        """
        if self.use_spacy:
            return self._spacy_segment(text)
        else:
            return self._rule_based_segment(text)
    
    def _spacy_segment(self, text: str) -> List[Tuple[int, int]]:
        """Use spaCy for sentence segmentation."""
        doc = self.nlp(text)
        spans = []
        
        for sent in doc.sents:
            # Get character positions
            start = sent.start_char
            end = sent.end_char
            spans.append((start, end))
        
        return spans
    
    def _rule_based_segment(self, text: str) -> List[Tuple[int, int]]:
        """
        Fallback rule-based sentence segmentation.
        This is simpler but should work for most debate transcripts.
        """
        if not text.strip():
            return []
        
        # Find potential sentence boundaries
        potential_splits = []
        
        for pattern in self.sentence_endings:
            for match in re.finditer(pattern, text):
                potential_splits.append(match.end())
        
        # Filter out false positives
        valid_splits = []
        for split_pos in sorted(set(potential_splits)):
            # Check if this split is preceded by a pattern we shouldn't split on
            preceding_text = text[max(0, split_pos-20):split_pos]
            should_skip = False
            
            for no_split_pattern in self.no_split_patterns:
                if re.search(no_split_pattern + r'$', preceding_text):
                    should_skip = True
                    break
            
            if not should_skip:
                valid_splits.append(split_pos)
        
        # Convert split positions to spans
        spans = []
        start = 0
        
        for split_pos in valid_splits:
            if start < split_pos:
                spans.append((start, split_pos))
                start = split_pos
        
        # Add final span if there's remaining text
        if start < len(text):
            spans.append((start, len(text)))
        
        # If no splits found, treat entire text as one sentence
        if not spans:
            spans = [(0, len(text))]
        
        return spans
