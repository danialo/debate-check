"""
Enhanced sentence segmentation that works with paragraph-level chunking
and includes sentence type classification (statement/question/imperative/fragment)
"""

import re
import logging
from typing import List, Tuple, Optional, Dict
from enum import Enum
from dataclasses import dataclass

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from .models import Sentence
from .paragraph_chunker import Paragraph

logger = logging.getLogger(__name__)


class SentenceType(Enum):
    """Types of sentences for claim gating"""
    STATEMENT = "statement"      # Declarative sentence - good for claims
    QUESTION = "question"        # Interrogative - usually not claimable  
    IMPERATIVE = "imperative"    # Command/request - sometimes claimable
    EXCLAMATION = "exclamation"  # Exclamatory - context dependent
    FRAGMENT = "fragment"        # Incomplete - needs repair or filtering


@dataclass
class ClassifiedSentence(Sentence):
    """Enhanced sentence with type classification and repair metadata"""
    sentence_type: SentenceType
    confidence: float = 0.0
    needs_repair: bool = False
    repair_reason: str = ""
    paragraph_context: str = ""  # Full paragraph for context
    

class SentenceClassifier:
    """Classifies sentence types using minimal regex/POS rules"""
    
    def __init__(self):
        # Question patterns
        self.question_patterns = [
            r'^(what|who|where|when|why|how|which|whose)\b',  # Wh-questions
            r'^(do|does|did|are|is|was|were|can|could|would|should|will)\b.*\?$',  # Yes/no questions
            r'^(isn\'t|aren\'t|wasn\'t|weren\'t|don\'t|doesn\'t|didn\'t)\b',  # Negative questions
        ]
        
        # Imperative patterns (commands/requests)
        self.imperative_patterns = [
            r'^(consider|imagine|think|look|listen|remember|note|see)\b',  # Mental commands
            r'^(let\'s|let us)\b',  # Suggestions
            r'^(don\'t|do not|never)\b',  # Negative imperatives
            r'^[A-Z][a-z]*\s+(?:this|that|it)\b',  # "Consider this", "Imagine that"
        ]
        
        # Fragment indicators (incomplete sentences)
        self.fragment_patterns = [
            r'^(because|since|although|while|if|when|after|before)\b.*[^.!?]$',  # Subordinate clauses
            r'^(and|but|or|so)\b.*[^.!?]$',  # Coordinating conjunctions without main clause
            r'^(the|a|an)\s+\w+\s*$',  # Just articles + noun
            r'[^.!?]\s*$',  # No sentence ending punctuation (but allow some short statements)
        ]
        
        # Finite verb patterns (for detecting complete predicates)
        self.finite_verbs = [
            r'\b(is|are|was|were|am)\b',  # Copula
            r'\b(has|have|had)\b',  # Auxiliary
            r'\b(does|do|did)\b',  # Auxiliary
            r'\b(can|could|will|would|shall|should|may|might|must)\b',  # Modals
            r'\b\w+ed\b',  # Past tense
            r'\b\w+s\b',  # Third person singular
        ]
    
    def classify_sentence(self, text: str, context: str = "") -> Tuple[SentenceType, float, bool, str]:
        """
        Classify sentence type and determine if repair is needed.
        
        Returns:
            (sentence_type, confidence, needs_repair, repair_reason)
        """
        text_clean = text.strip()
        text_lower = text_clean.lower()
        
        # Direct markers first
        if text_clean.endswith('?'):
            return SentenceType.QUESTION, 0.9, False, ""
        
        if text_clean.endswith('!'):
            return SentenceType.EXCLAMATION, 0.8, False, ""
        
        # Check for question patterns
        for pattern in self.question_patterns:
            if re.match(pattern, text_lower):
                return SentenceType.QUESTION, 0.8, False, ""
        
        # Check for imperative patterns
        for pattern in self.imperative_patterns:
            if re.match(pattern, text_lower):
                return SentenceType.IMPERATIVE, 0.7, False, ""
        
        # Check for fragments
        has_finite_verb = any(re.search(pattern, text_lower) for pattern in self.finite_verbs)
        
        for pattern in self.fragment_patterns:
            if re.match(pattern, text_lower):
                if not has_finite_verb and len(text_clean.split()) < 8:
                    return SentenceType.FRAGMENT, 0.8, True, "Subordinate clause or conjunction without main clause"
        
        # Check for fragments by lack of finite verb (but be conservative)
        if not has_finite_verb and len(text_clean.split()) > 2:
            # Could be a fragment, but check for noun phrases that might be legitimate
            if len(text_clean.split()) < 6:
                return SentenceType.FRAGMENT, 0.6, True, "No finite verb detected"
        
        # Default to statement
        confidence = 0.9 if has_finite_verb else 0.5
        return SentenceType.STATEMENT, confidence, False, ""


class ParagraphAwareSegmenter:
    """
    Enhanced segmenter that works with paragraphs and classifies sentences.
    Operates on Paragraph objects and produces ClassifiedSentence objects.
    """
    
    def __init__(self, use_spacy: bool = True, context_window: int = 2):
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.context_window = context_window  # paragraphs of context
        self.nlp = None
        self.classifier = SentenceClassifier()
        
        if self.use_spacy:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Using spaCy for enhanced sentence segmentation")
            except OSError:
                logger.warning("spaCy English model not found. Using rule-based segmentation")
                self.use_spacy = False
        else:
            logger.info("Using rule-based sentence segmentation with classification")
        
        # Enhanced no-split patterns
        self.no_split_patterns = [
            r'\b[A-Z]\.',  # Initials
            r'\b(?:[A-Z][a-z]*\.){2,}',  # Multiple initials: "J.R.R. Tolkien"
            r'\b(?:Mr|Ms|Mrs|Dr|Prof|Sen|Rep|Pres|Vice)\.',  # Titles
            r'\b(?:vs|etc|inc|corp|ltd|co|fig|vol|ch|pp)\.',  # Abbreviations
            r'\d+\.\d+',  # Numbers (3.14)
            r'\$\d+\.\d+',  # Currency ($12.34)
            r'\.\.\.|\u2026',  # Ellipsis
            r'\b[A-Z]\.\s*[A-Z]\.',  # "U.S.A.", "Ph.D."
        ]
    
    def segment_paragraphs(self, paragraphs: List[Paragraph]) -> List[ClassifiedSentence]:
        """
        Segment paragraphs into classified sentences with context.
        
        Args:
            paragraphs: List of Paragraph objects from ParagraphChunker
            
        Returns:
            List of ClassifiedSentence objects
        """
        sentences = []
        
        for para_idx, paragraph in enumerate(paragraphs):
            # Generate context from surrounding paragraphs
            context_before = self._get_context_before(paragraphs, para_idx)
            context_after = self._get_context_after(paragraphs, para_idx)
            full_context = f"{context_before} {paragraph.text} {context_after}".strip()
            
            # Segment this paragraph
            sent_spans = self._segment_text(paragraph.text)
            
            for sent_idx, (start, end) in enumerate(sent_spans):
                sentence_text = paragraph.text[start:end].strip()
                if not sentence_text:
                    continue
                
                # Classify sentence
                sent_type, confidence, needs_repair, repair_reason = self.classifier.classify_sentence(
                    sentence_text, full_context
                )
                
                # Create enhanced sentence object
                sentence = ClassifiedSentence(
                    text=sentence_text,
                    speaker=paragraph.speaker,
                    turn_id=paragraph.paragraph_id,
                    sentence_index=sent_idx,
                    char_start=paragraph.start_char + start,
                    char_end=paragraph.start_char + end,
                    line_number=paragraph.line_numbers[0] if paragraph.line_numbers else 0,
                    sentence_type=sent_type,
                    confidence=confidence,
                    needs_repair=needs_repair,
                    repair_reason=repair_reason,
                    paragraph_context=paragraph.text
                )
                
                sentences.append(sentence)
        
        logger.info(f"Segmented {len(paragraphs)} paragraphs into {len(sentences)} classified sentences")
        self._log_sentence_stats(sentences)
        
        return sentences
    
    def _get_context_before(self, paragraphs: List[Paragraph], current_idx: int) -> str:
        """Get context from previous paragraphs"""
        start_idx = max(0, current_idx - self.context_window)
        context_paras = paragraphs[start_idx:current_idx]
        return ' '.join(p.text for p in context_paras)
    
    def _get_context_after(self, paragraphs: List[Paragraph], current_idx: int) -> str:
        """Get context from following paragraphs"""
        end_idx = min(len(paragraphs), current_idx + self.context_window + 1)
        context_paras = paragraphs[current_idx + 1:end_idx]
        return ' '.join(p.text for p in context_paras)
    
    def _segment_text(self, text: str) -> List[Tuple[int, int]]:
        """Segment text into sentence spans"""
        if self.use_spacy:
            return self._spacy_segment(text)
        else:
            return self._rule_based_segment(text)
    
    def _spacy_segment(self, text: str) -> List[Tuple[int, int]]:
        """Use spaCy for sentence segmentation"""
        doc = self.nlp(text)
        spans = []
        
        for sent in doc.sents:
            start = sent.start_char
            end = sent.end_char
            spans.append((start, end))
        
        return spans
    
    def _rule_based_segment(self, text: str) -> List[Tuple[int, int]]:
        """Enhanced rule-based sentence segmentation"""
        if not text.strip():
            return []
        
        # Find potential sentence boundaries
        sentence_endings = [r'[.!?]+\s+', r'[.!?]+$']
        potential_splits = []
        
        for pattern in sentence_endings:
            for match in re.finditer(pattern, text):
                potential_splits.append(match.end())
        
        # Filter out false positives using enhanced patterns
        valid_splits = []
        for split_pos in sorted(set(potential_splits)):
            # Check preceding context for no-split patterns
            preceding_text = text[max(0, split_pos-30):split_pos]
            should_skip = False
            
            for no_split_pattern in self.no_split_patterns:
                if re.search(no_split_pattern + r'$', preceding_text):
                    should_skip = True
                    break
            
            if not should_skip:
                valid_splits.append(split_pos)
        
        # Convert to spans
        spans = []
        start = 0
        
        for split_pos in valid_splits:
            if start < split_pos:
                spans.append((start, split_pos))
                start = split_pos
        
        # Final span
        if start < len(text):
            spans.append((start, len(text)))
        
        # Fallback for no splits
        if not spans:
            spans = [(0, len(text))]
        
        return spans
    
    def _log_sentence_stats(self, sentences: List[ClassifiedSentence]) -> None:
        """Log statistics about sentence classification"""
        type_counts = {}
        repair_count = 0
        
        for sent in sentences:
            type_counts[sent.sentence_type] = type_counts.get(sent.sentence_type, 0) + 1
            if sent.needs_repair:
                repair_count += 1
        
        logger.info(f"Sentence classification stats:")
        for sent_type, count in type_counts.items():
            logger.info(f"  {sent_type.value}: {count}")
        logger.info(f"  needs_repair: {repair_count}")


class ClaimGatingFilter:
    """
    Filters sentences before passing to claim detectors.
    Only allows statement/question/imperative/exclamation through.
    Fragments get repaired or dropped.
    """
    
    def __init__(self, allow_questions: bool = False, allow_imperatives: bool = True):
        self.allow_questions = allow_questions
        self.allow_imperatives = allow_imperatives
    
    def should_process_for_claims(self, sentence: ClassifiedSentence) -> Tuple[bool, str]:
        """
        Determine if sentence should be processed for claim detection.
        
        Returns:
            (should_process, reason)
        """
        # Fragments need repair or should be dropped
        if sentence.sentence_type == SentenceType.FRAGMENT:
            if sentence.needs_repair:
                return False, f"Fragment requiring repair: {sentence.repair_reason}"
            else:
                return False, "Sentence fragment"
        
        # Questions usually don't contain claims
        if sentence.sentence_type == SentenceType.QUESTION and not self.allow_questions:
            return False, "Question (not typically claimable)"
        
        # Imperatives can sometimes contain claims
        if sentence.sentence_type == SentenceType.IMPERATIVE and not self.allow_imperatives:
            return False, "Imperative (command/request)"
        
        # Allow statements and exclamations, and conditionally questions/imperatives
        return True, ""
    
    def filter_sentences(self, sentences: List[ClassifiedSentence]) -> Tuple[List[ClassifiedSentence], Dict[str, int]]:
        """
        Filter sentences for claim processing.
        
        Returns:
            (valid_sentences, stats)
        """
        valid_sentences = []
        stats = {
            'total_input': len(sentences),
            'passed_filter': 0,
            'filtered_fragment': 0,
            'filtered_question': 0,
            'filtered_imperative': 0,
            'needs_repair': 0
        }
        
        for sentence in sentences:
            should_process, reason = self.should_process_for_claims(sentence)
            
            if should_process:
                valid_sentences.append(sentence)
                stats['passed_filter'] += 1
                if sentence.needs_repair:
                    stats['needs_repair'] += 1
            else:
                # Count rejection reasons
                if 'fragment' in reason.lower():
                    stats['filtered_fragment'] += 1
                elif 'question' in reason.lower():
                    stats['filtered_question'] += 1
                elif 'imperative' in reason.lower():
                    stats['filtered_imperative'] += 1
        
        logger.info(f"Claim gating filter stats: {stats}")
        return valid_sentences, stats
