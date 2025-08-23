"""
Hierarchical chunking: Speaker Turn → Paragraph → Sentence
Groups consecutive utterances from the same speaker into logical paragraphs
"""

import re
import logging
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Paragraph:
    """A logical paragraph (speaker turn) with metadata"""
    text: str
    speaker: str
    start_char: int
    end_char: int
    paragraph_id: int
    utterance_count: int
    line_numbers: List[int]
    
    
@dataclass 
class SentenceRepairTrigger:
    """Conditions that trigger LLM/SLM assistance for sentence repair"""
    long_no_punct: bool = False      # 220+ chars with no .?!;
    high_filler_ratio: bool = False  # >35% filler words
    conj_start_short: bool = False   # starts with conj + <7 tokens
    asr_artifacts: bool = False      # repeated words, URLs, etc.
    
    def needs_repair(self) -> bool:
        return any([self.long_no_punct, self.high_filler_ratio, 
                   self.conj_start_short, self.asr_artifacts])


class ParagraphChunker:
    """
    Groups consecutive lines from same speaker into logical paragraphs.
    Respects blank lines and obvious scene breaks.
    """
    
    def __init__(self, 
                 max_paragraph_gap: int = 2,    # max lines between utterances to group
                 min_paragraph_length: int = 10, # min chars for viable paragraph
                 filler_threshold: float = 0.35): # filler ratio trigger
        self.max_paragraph_gap = max_paragraph_gap
        self.min_paragraph_length = min_paragraph_length
        self.filler_threshold = filler_threshold
        
        # Scene break indicators
        self.scene_breaks = [
            r'^\s*\[.*\]\s*$',           # [BREAK], [COMMERCIAL], etc.
            r'^\s*\-{3,}\s*$',           # --- dividers
            r'^\s*={3,}\s*$',            # === dividers
            r'^\s*\*{3,}\s*$',           # *** dividers
        ]
        
        # Filler words for ratio calculation
        self.filler_words = {
            'uh', 'um', 'erm', 'ah', 'like', 'you know', 'i mean', 
            'right', 'well', 'so', 'okay', 'yeah', 'yes', 'no'
        }
        
        # ASR artifacts patterns
        self.asr_artifacts = [
            r'\b(\w+)\s+\1\b',      # repeated words: "the the"
            r'https?://\S+',           # URLs
            r'\b\w*\.(?:com|org|net)\b', # domains
            r'\buse\s+code\s+\w+',   # promo codes
        ]
    
    def chunk_by_paragraphs(self, utterances: List[Tuple[str, str, int]]) -> List[Paragraph]:
        """
        Group utterances into logical paragraphs by speaker turns.
        
        Args:
            utterances: List of (speaker, text, line_number) from DebatePreprocessor
            
        Returns:
            List of Paragraph objects
        """
        if not utterances:
            return []
        
        logger.info(f"Chunking {len(utterances)} utterances into paragraphs")
        
        paragraphs = []
        current_group = []
        current_speaker = None
        char_offset = 0
        paragraph_id = 0
        
        for i, (speaker, text, line_num) in enumerate(utterances):
            # Check for scene breaks
            if self._is_scene_break(text):
                if current_group:
                    # Finalize current paragraph
                    para = self._create_paragraph(current_group, char_offset, paragraph_id)
                    if para:
                        paragraphs.append(para)
                        char_offset += len(para.text) + 1
                        paragraph_id += 1
                    current_group = []
                    current_speaker = None
                continue
            
            # Check if we should start a new paragraph
            should_break = False
            
            if current_speaker is None:
                # First utterance
                should_break = False
            elif speaker != current_speaker:
                # Speaker change
                should_break = True
            elif self._has_topic_shift(text, current_group):
                # Same speaker but topic shift
                should_break = True
            elif len(current_group) > 0 and i > 0:
                # Check line gap
                last_line = current_group[-1][2]
                if line_num - last_line > self.max_paragraph_gap:
                    should_break = True
            
            if should_break and current_group:
                # Finalize current paragraph
                para = self._create_paragraph(current_group, char_offset, paragraph_id)
                if para:
                    paragraphs.append(para)
                    char_offset += len(para.text) + 1
                    paragraph_id += 1
                current_group = []
            
            # Add to current group
            current_group.append((speaker, text, line_num))
            current_speaker = speaker
        
        # Finalize last paragraph
        if current_group:
            para = self._create_paragraph(current_group, char_offset, paragraph_id)
            if para:
                paragraphs.append(para)
        
        logger.info(f"Created {len(paragraphs)} paragraphs (avg {len(utterances)/len(paragraphs):.1f} utterances/paragraph)")
        return paragraphs
    
    def _is_scene_break(self, text: str) -> bool:
        """Check if text indicates a scene break"""
        for pattern in self.scene_breaks:
            if re.match(pattern, text.strip()):
                return True
        return False
    
    def _has_topic_shift(self, text: str, current_group: List[Tuple[str, str, int]]) -> bool:
        """
        Detect if this utterance represents a topic shift from current paragraph.
        Simple heuristics for now.
        """
        if len(current_group) < 2:
            return False
        
        # Strong transition indicators
        transition_markers = [
            r'^(but|however|anyway|meanwhile|now|so|well|actually)\b',
            r'^(let me|can i|i want to)\b',
            r'^(by the way|speaking of|that reminds me)\b'
        ]
        
        text_lower = text.lower().strip()
        for pattern in transition_markers:
            if re.match(pattern, text_lower):
                return True
        
        return False
    
    def _create_paragraph(self, 
                         utterance_group: List[Tuple[str, str, int]], 
                         start_char: int, 
                         paragraph_id: int) -> Optional[Paragraph]:
        """Create a Paragraph object from a group of utterances"""
        if not utterance_group:
            return None
        
        # Combine utterances into paragraph text
        texts = []
        speakers = set()
        line_numbers = []
        
        for speaker, text, line_num in utterance_group:
            texts.append(text.strip())
            speakers.add(speaker)
            line_numbers.append(line_num)
        
        paragraph_text = ' '.join(texts)
        
        # Skip very short paragraphs
        if len(paragraph_text) < self.min_paragraph_length:
            return None
        
        # Use majority speaker (should be consistent in a proper paragraph)
        speaker_counts = {}
        for speaker, _, _ in utterance_group:
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
        primary_speaker = max(speaker_counts.items(), key=lambda x: x[1])[0]
        
        return Paragraph(
            text=paragraph_text,
            speaker=primary_speaker,
            start_char=start_char,
            end_char=start_char + len(paragraph_text),
            paragraph_id=paragraph_id,
            utterance_count=len(utterance_group),
            line_numbers=line_numbers
        )
    
    def analyze_repair_needs(self, text: str) -> SentenceRepairTrigger:
        """
        Analyze if a sentence/paragraph needs LLM repair.
        
        Triggers:
        - 220+ chars with no .?!; → likely run-on
        - filler ratio > 35% (uh, um, like, you know, right, well)  
        - starts with conjunction and length < 7 tokens
        - ASR artifacts (repeated words, sponsor URL inside)
        """
        trigger = SentenceRepairTrigger()
        
        # Long text with no punctuation
        if len(text) >= 220 and not re.search(r'[.!?;]', text):
            trigger.long_no_punct = True
        
        # High filler ratio
        words = text.lower().split()
        if len(words) > 3:
            filler_count = sum(1 for word in words if word in self.filler_words)
            filler_ratio = filler_count / len(words)
            if filler_ratio > self.filler_threshold:
                trigger.high_filler_ratio = True
        
        # Conjunction start + short
        conj_start = re.match(r'^\s*(and|but|so|or|because)\b', text.lower())
        if conj_start and len(words) < 7:
            trigger.conj_start_short = True
        
        # ASR artifacts
        for pattern in self.asr_artifacts:
            if re.search(pattern, text, re.IGNORECASE):
                trigger.asr_artifacts = True
                break
        
        return trigger


class HierarchicalChunker:
    """
    Main orchestrator for hierarchical chunking:
    Speaker Turn → Paragraph → Sentence
    """
    
    def __init__(self, 
                 paragraph_chunker: Optional[ParagraphChunker] = None,
                 use_repair: bool = False):
        self.paragraph_chunker = paragraph_chunker or ParagraphChunker()
        self.use_repair = use_repair
        
    def chunk_transcript(self, utterances: List[Tuple[str, str, int]]) -> Tuple[List[Paragraph], Dict[str, int]]:
        """
        Hierarchically chunk transcript into paragraphs.
        
        Returns:
            Tuple of (paragraphs, stats)
        """
        paragraphs = self.paragraph_chunker.chunk_by_paragraphs(utterances)
        
        # Collect statistics
        stats = {
            'total_paragraphs': len(paragraphs),
            'total_utterances': len(utterances),
            'avg_utterances_per_paragraph': len(utterances) / max(len(paragraphs), 1),
            'speakers': len(set(p.speaker for p in paragraphs)),
            'repair_candidates': 0
        }
        
        if self.use_repair:
            # Analyze repair needs
            for paragraph in paragraphs:
                trigger = self.paragraph_chunker.analyze_repair_needs(paragraph.text)
                if trigger.needs_repair():
                    stats['repair_candidates'] += 1
        
        logger.info(f"Hierarchical chunking stats: {stats}")
        
        return paragraphs, stats
