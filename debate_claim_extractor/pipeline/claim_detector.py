"""
Rule-based claim detection for extracting factual claims from debate sentences
"""

import re
import logging
from typing import List, Dict, Set, Optional
from abc import ABC, abstractmethod

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from .models import Claim, ClaimType, Sentence

logger = logging.getLogger(__name__)


class ClaimDetector(ABC):
    """Abstract base class for claim detectors"""
    
    @abstractmethod
    def detect(self, sentence: Sentence) -> List[Claim]:
        """Detect claims in a sentence"""
        pass
    
    @abstractmethod
    def get_claim_type(self) -> ClaimType:
        """Return the type of claims this detector finds"""
        pass


class StatisticalClaimDetector(ClaimDetector):
    """Detects statistical claims with numbers and percentages"""
    
    def __init__(self):
        # Patterns for statistical claims
        self.statistical_patterns = [
            # Percentages: "50%", "3.5 percent"
            r'\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*percent\b',
            # Large numbers: "2 million", "5 billion", "1,500"
            r'\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|thousand)\b',
            r'\b\d{1,3}(?:,\d{3})+\b',  # Comma-separated numbers
            # Ratios: "3 in 4", "1 out of 5"  
            r'\b\d+\s+(?:in|out\s+of)\s+\d+\b',
            # Rates: "per capita", "per year"
            r'\b\d+(?:\.\d+)?\s+per\s+\w+\b',
        ]
        
        # Statistical keywords that strengthen the claim
        self.stat_keywords = [
            'data', 'statistics', 'survey', 'poll', 'study', 'research',
            'analysis', 'report', 'findings', 'rate', 'level', 'average',
            'median', 'mean', 'increase', 'decrease', 'growth', 'decline'
        ]
    
    def detect(self, sentence: Sentence) -> List[Claim]:
        claims = []
        text = sentence.text.lower()
        
        # Check for statistical patterns
        has_stats = any(re.search(pattern, text, re.IGNORECASE) for pattern in self.statistical_patterns)
        
        if has_stats:
            # Boost confidence if statistical keywords are present
            confidence = 0.6
            if any(keyword in text for keyword in self.stat_keywords):
                confidence += 0.2
            
            # Look for the specific statistical claim within the sentence
            claim_text = self._extract_statistical_claim(sentence.text)
            
            claim = Claim(
                type=ClaimType.STATISTICAL,
                text=claim_text,
                speaker=sentence.speaker,
                sentence_id=sentence.id,
                turn_id=sentence.turn_id,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                confidence=min(confidence, 1.0)
            )
            claims.append(claim)
        
        return claims
    
    def _extract_statistical_claim(self, text: str) -> str:
        """Extract the most relevant statistical portion of the sentence"""
        # For now, return the full sentence, but this could be refined
        # to extract just the statistical assertion
        return text.strip()
    
    def get_claim_type(self) -> ClaimType:
        return ClaimType.STATISTICAL


class CausalClaimDetector(ClaimDetector):
    """Detects causal claims expressing cause-and-effect relationships"""
    
    def __init__(self):
        # Causal keywords and phrases
        self.causal_keywords = [
            'because', 'due to', 'caused by', 'leads to', 'results in',
            'brings about', 'produces', 'creates', 'generates', 'triggers',
            'stems from', 'originates from', 'responsible for', 'blamed on',
            'thanks to', 'owing to', 'as a result of', 'consequently'
        ]
        
        # Stronger causal indicators
        self.strong_causal = [
            'directly caused', 'primarily due to', 'main reason',
            'root cause', 'primary cause', 'leading cause'
        ]
    
    def detect(self, sentence: Sentence) -> List[Claim]:
        claims = []
        text = sentence.text.lower()
        
        # Check for causal language
        causal_matches = sum(1 for keyword in self.causal_keywords if keyword in text)
        strong_matches = sum(1 for keyword in self.strong_causal if keyword in text)
        
        if causal_matches > 0 or strong_matches > 0:
            confidence = 0.5 + (causal_matches * 0.1) + (strong_matches * 0.2)
            confidence = min(confidence, 1.0)
            
            claim = Claim(
                type=ClaimType.CAUSAL,
                text=sentence.text.strip(),
                speaker=sentence.speaker,
                sentence_id=sentence.id,
                turn_id=sentence.turn_id,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                confidence=confidence
            )
            claims.append(claim)
        
        return claims
    
    def get_claim_type(self) -> ClaimType:
        return ClaimType.CAUSAL


class ComparativeClaimDetector(ClaimDetector):
    """Detects comparative claims"""
    
    def __init__(self):
        # Comparative indicators
        self.comparative_patterns = [
            r'\b(?:more|less|better|worse|higher|lower|greater|smaller)\s+than\b',
            r'\b(?:most|least|best|worst|highest|lowest|greatest|smallest)\b',
            r'\b(?:superior|inferior)\s+to\b',
            r'\b(?:exceeds|surpasses|outperforms)\b',
            r'\bcompared\s+(?:to|with)\b',
            r'\b(?:versus|vs\.?)\b',
        ]
    
    def detect(self, sentence: Sentence) -> List[Claim]:
        claims = []
        text = sentence.text.lower()
        
        # Check for comparative patterns
        comparative_matches = sum(1 for pattern in self.comparative_patterns 
                                if re.search(pattern, text))
        
        if comparative_matches > 0:
            confidence = 0.5 + (comparative_matches * 0.15)
            confidence = min(confidence, 1.0)
            
            claim = Claim(
                type=ClaimType.COMPARATIVE,
                text=sentence.text.strip(),
                speaker=sentence.speaker,
                sentence_id=sentence.id,
                turn_id=sentence.turn_id,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                confidence=confidence
            )
            claims.append(claim)
        
        return claims
    
    def get_claim_type(self) -> ClaimType:
        return ClaimType.COMPARATIVE


class HistoricalClaimDetector(ClaimDetector):
    """Detects historical claims referencing past events or time periods"""
    
    def __init__(self):
        # Historical time references
        self.time_patterns = [
            r'\b(?:in|during|since|from|until|by)\s+\d{4}\b',  # "in 1995"
            r'\b\d{4}(?:-\d{4})?\b',  # "1995" or "1995-2000"
            r'\b(?:last|past|previous)\s+(?:year|decade|century|month)\b',
            r'\b(?:decades?|centuries?)\s+ago\b',
            r'\b(?:historically|traditionally|previously|formerly)\b',
            r'\b(?:used to|had been|were|was)\b.*\b(?:ago|back then|at that time)\b',
        ]
        
        # Past tense verbs that indicate historical statements
        self.past_indicators = [
            'happened', 'occurred', 'took place', 'began', 'started',
            'ended', 'concluded', 'established', 'founded', 'created',
            'implemented', 'introduced', 'adopted'
        ]
    
    def detect(self, sentence: Sentence) -> List[Claim]:
        claims = []
        text = sentence.text.lower()
        
        # Check for historical time references
        time_matches = sum(1 for pattern in self.time_patterns 
                          if re.search(pattern, text))
        
        # Check for past tense indicators
        past_matches = sum(1 for indicator in self.past_indicators 
                          if indicator in text)
        
        if time_matches > 0 or past_matches > 1:  # Need more past indicators for confidence
            confidence = 0.4 + (time_matches * 0.2) + (past_matches * 0.1)
            confidence = min(confidence, 1.0)
            
            claim = Claim(
                type=ClaimType.HISTORICAL,
                text=sentence.text.strip(),
                speaker=sentence.speaker,
                sentence_id=sentence.id,
                turn_id=sentence.turn_id,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                confidence=confidence
            )
            claims.append(claim)
        
        return claims
    
    def get_claim_type(self) -> ClaimType:
        return ClaimType.HISTORICAL


class FactualClaimDetector(ClaimDetector):
    """Detects general factual claims using linguistic patterns"""
    
    def __init__(self):
        self.use_spacy = SPACY_AVAILABLE
        self.nlp = None
        
        if self.use_spacy:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not available for factual claim detection")
                self.use_spacy = False
        
        # Modal words that indicate uncertainty (reduce confidence)
        self.uncertainty_words = [
            'might', 'may', 'could', 'would', 'should', 'possibly',
            'probably', 'likely', 'perhaps', 'maybe', 'seems', 'appears',
            'believes', 'thinks', 'feels', 'opinions', 'suggests'
        ]
        
        # Words that indicate certainty (increase confidence)
        self.certainty_words = [
            'is', 'are', 'was', 'were', 'has', 'have', 'will',
            'does', 'did', 'facts', 'evidence', 'proof', 'confirmed'
        ]
    
    def detect(self, sentence: Sentence) -> List[Claim]:
        claims = []
        text = sentence.text.lower()
        
        # Start with base confidence
        confidence = 0.4
        
        # Check for uncertainty markers (reduce confidence)
        uncertainty_count = sum(1 for word in self.uncertainty_words if word in text)
        confidence -= uncertainty_count * 0.1
        
        # Check for certainty markers (increase confidence)  
        certainty_count = sum(1 for word in self.certainty_words if word in text)
        confidence += certainty_count * 0.05
        
        # Use spaCy if available for more sophisticated analysis
        if self.use_spacy:
            confidence = self._analyze_with_spacy(sentence.text, confidence)
        
        # Only create claim if confidence is reasonable
        if confidence > 0.3:
            confidence = max(0.0, min(confidence, 1.0))
            
            claim = Claim(
                type=ClaimType.FACTUAL,
                text=sentence.text.strip(),
                speaker=sentence.speaker,
                sentence_id=sentence.id,
                turn_id=sentence.turn_id,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                confidence=confidence
            )
            claims.append(claim)
        
        return claims
    
    def _analyze_with_spacy(self, text: str, base_confidence: float) -> float:
        """Use spaCy to analyze grammatical structure for factual content"""
        doc = self.nlp(text)
        confidence = base_confidence
        
        # Look for declarative sentence structure
        has_subject = any(token.dep_ in ['nsubj', 'nsubjpass'] for token in doc)
        has_verb = any(token.pos_ == 'VERB' for token in doc)
        
        if has_subject and has_verb:
            confidence += 0.1
        
        # Boost confidence for third-person statements
        third_person_pronouns = ['he', 'she', 'it', 'they', 'this', 'that']
        if any(token.text.lower() in third_person_pronouns for token in doc):
            confidence += 0.05
        
        return confidence
    
    def get_claim_type(self) -> ClaimType:
        return ClaimType.FACTUAL


class DebateClaimDetector:
    """Main claim detection engine that coordinates multiple detectors"""
    
    def __init__(self):
        self.detectors = [
            StatisticalClaimDetector(),
            CausalClaimDetector(),
            ComparativeClaimDetector(),
            HistoricalClaimDetector(),
            FactualClaimDetector(),  # Run this last as it's most general
        ]
        
        logger.info(f"Initialized {len(self.detectors)} claim detectors")
    
    def detect_claims(self, sentences: List[Sentence]) -> List[Claim]:
        """
        Detect claims across all sentences using all available detectors.
        
        Args:
            sentences: List of segmented sentences
            
        Returns:
            List of detected claims
        """
        all_claims = []
        
        for sentence in sentences:
            sentence_claims = []
            
            # Run each detector on the sentence
            for detector in self.detectors:
                try:
                    claims = detector.detect(sentence)
                    sentence_claims.extend(claims)
                except Exception as e:
                    logger.warning(f"Detector {detector.__class__.__name__} failed on sentence: {e}")
            
            # For now, keep all claims. Post-processing will handle deduplication
            all_claims.extend(sentence_claims)
        
        logger.info(f"Detected {len(all_claims)} total claims across {len(sentences)} sentences")
        
        # Log claim type distribution
        claim_types = {}
        for claim in all_claims:
            claim_types[claim.type.value] = claim_types.get(claim.type.value, 0) + 1
        
        for claim_type, count in claim_types.items():
            logger.info(f"  {claim_type}: {count}")
        
        return all_claims
