"""
Core fallacy detection classes for identifying logical fallacies in debate transcripts.
"""

import re
import logging
from typing import List, Dict, Optional, Pattern
from abc import ABC, abstractmethod

from .fallacy_models import FallacyType, FallacyResult, FallacySeverity, get_fallacy_explanation
from ..pipeline.models import Sentence, Claim

logger = logging.getLogger(__name__)


class FallacyDetector(ABC):
    """Abstract base class for fallacy detectors"""
    
    @abstractmethod
    def detect(self, text: str, context: Optional[Dict] = None) -> List[FallacyResult]:
        """Detect fallacies in the given text"""
        pass
    
    @abstractmethod
    def get_fallacy_type(self) -> FallacyType:
        """Return the type of fallacy this detector finds"""
        pass


class AdHominemDetector(FallacyDetector):
    """Detects ad hominem attacks - personal attacks instead of addressing arguments"""
    
    def __init__(self):
        # Personal attack patterns
        self.attack_patterns = [
            r'\b(?:you|he|she|they)\s+(?:are|is)\s+(?:a|an|just|nothing but|always)\s+(?:corrupt|dishonest|liar|fraud|hypocrite|fool|idiot)\b',
            r'\btypical\s+(?:liberal|conservative|democrat|republican|politician)\s+(?:response|answer|behavior|nonsense)\b',
            r'\bcoming from (?:you|him|her|them|someone who)\b',
            r'\b(?:hypocrite|liar|fraud|corrupt|dishonest)\b',
            r'\bwhat (?:do you|does he|does she) know about\b',
            r'\byou\'re (?:just|nothing but|always) (?:a|an)\s+\w+\b',
            r'\bthat\'s what (?:a|an) \w+ would say\b',
            r'\byou (?:can\'t be trusted|have no credibility|lack experience)\b'
        ]
        
        # Character dismissal phrases
        self.dismissal_patterns = [
            r'\b(?:ignore|dismiss) (?:him|her|them) because\b',
            r'\bdon\'t listen to (?:someone who|a person who)\b',
            r'\bthis coming from (?:a|an|someone)\b'
        ]
        
        # Compile patterns for efficiency
        self.compiled_attack_patterns = [re.compile(p, re.IGNORECASE) for p in self.attack_patterns]
        self.compiled_dismissal_patterns = [re.compile(p, re.IGNORECASE) for p in self.dismissal_patterns]
    
    def detect(self, text: str, context: Optional[Dict] = None) -> List[FallacyResult]:
        fallacies = []
        text_lower = text.lower()
        
        # Check for personal attack patterns
        attack_matches = []
        for pattern in self.compiled_attack_patterns:
            matches = pattern.finditer(text)
            attack_matches.extend([m.group() for m in matches])
        
        # Check for dismissal patterns  
        dismissal_matches = []
        for pattern in self.compiled_dismissal_patterns:
            matches = pattern.finditer(text)
            dismissal_matches.extend([m.group() for m in matches])
        
        if attack_matches or dismissal_matches:
            # Calculate confidence based on pattern strength
            confidence = 0.5
            patterns_found = []
            
            if attack_matches:
                confidence += len(attack_matches) * 0.2
                patterns_found.extend(['personal_attack'] * len(attack_matches))
            
            if dismissal_matches:
                confidence += len(dismissal_matches) * 0.15
                patterns_found.extend(['character_dismissal'] * len(dismissal_matches))
            
            # Cap confidence at 1.0
            confidence = min(confidence, 1.0)
            
            # Determine severity
            severity = FallacySeverity.HIGH if confidence > 0.8 else (
                FallacySeverity.MEDIUM if confidence > 0.5 else FallacySeverity.LOW
            )
            
            explanation = get_fallacy_explanation(FallacyType.AD_HOMINEM)
            
            fallacy = FallacyResult(
                id=None,  # Will be auto-generated
                type=FallacyType.AD_HOMINEM,
                text=text.strip(),
                speaker=context.get('speaker') if context else None,
                target_claim_id=context.get('claim_id') if context else None,
                sentence_id=context.get('sentence_id') if context else None,
                turn_id=context.get('turn_id') if context else None,
                char_start=context.get('char_start') if context else None,
                char_end=context.get('char_end') if context else None,
                context=context.get('context_text') if context else None,
                confidence=confidence,
                patterns_matched=patterns_found,
                explanation=f"{explanation['description']} {explanation['why_problematic']}",
                severity=severity
            )
            
            fallacies.append(fallacy)
        
        return fallacies
    
    def get_fallacy_type(self) -> FallacyType:
        return FallacyType.AD_HOMINEM


class StrawManDetector(FallacyDetector):
    """Detects straw man fallacies - misrepresenting opponent's arguments"""
    
    def __init__(self):
        self.straw_man_patterns = [
            r'\bso (?:you\'re|he\'s|she\'s|they\'re) saying\s+.{10,}\b',
            r'\bwhat (?:you|he|she|they) (?:want|believe|think) is\s+.{10,}\b',
            r'\b(?:you|he|she|they) (?:want to|would) (?:destroy|eliminate|ban|get rid of)\s+.{5,}\b',
            r'\baccording to (?:you|him|her|them), (?:we should|everyone should)\s+.{10,}\b',
            r'\byour position is that\s+.{10,}\b',
            r'\byou\'re essentially saying\s+.{10,}\b',
            r'\bif (?:I understand|I hear) (?:you|him|her) correctly\s+.{10,}\b'
        ]
        
        # Extreme characterizations
        self.extreme_patterns = [
            r'\b(?:all|every|never|always|completely|totally|absolutely) (?:destroy|eliminate|ban|remove)\b',
            r'\b(?:open all|close all|destroy all|eliminate all)\b',
            r'\b(?:socialism|communism|fascism|dictatorship|anarchy)\b(?!.*(?:aspects of|elements of|like))'
        ]
        
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.straw_man_patterns]
        self.compiled_extreme = [re.compile(p, re.IGNORECASE) for p in self.extreme_patterns]
    
    def detect(self, text: str, context: Optional[Dict] = None) -> List[FallacyResult]:
        fallacies = []
        
        # Look for straw man construction patterns
        construction_matches = []
        for pattern in self.compiled_patterns:
            matches = pattern.finditer(text)
            construction_matches.extend([m.group() for m in matches])
        
        # Look for extreme characterizations
        extreme_matches = []
        for pattern in self.compiled_extreme:
            matches = pattern.finditer(text)  
            extreme_matches.extend([m.group() for m in matches])
        
        if construction_matches or extreme_matches:
            confidence = 0.4
            patterns_found = []
            
            if construction_matches:
                confidence += len(construction_matches) * 0.25
                patterns_found.extend(['misrepresentation'] * len(construction_matches))
            
            if extreme_matches:
                confidence += len(extreme_matches) * 0.15
                patterns_found.extend(['extreme_characterization'] * len(extreme_matches))
            
            confidence = min(confidence, 1.0)
            
            severity = FallacySeverity.HIGH if confidence > 0.8 else (
                FallacySeverity.MEDIUM if confidence > 0.5 else FallacySeverity.LOW
            )
            
            explanation = get_fallacy_explanation(FallacyType.STRAW_MAN)
            
            fallacy = FallacyResult(
                id=None,
                type=FallacyType.STRAW_MAN,
                text=text.strip(),
                speaker=context.get('speaker') if context else None,
                target_claim_id=context.get('claim_id') if context else None,
                sentence_id=context.get('sentence_id') if context else None,
                turn_id=context.get('turn_id') if context else None,
                char_start=context.get('char_start') if context else None,
                char_end=context.get('char_end') if context else None,
                context=context.get('context_text') if context else None,
                confidence=confidence,
                patterns_matched=patterns_found,
                explanation=f"{explanation['description']} {explanation['why_problematic']}",
                severity=severity
            )
            
            fallacies.append(fallacy)
        
        return fallacies
    
    def get_fallacy_type(self) -> FallacyType:
        return FallacyType.STRAW_MAN


class FalseDilemmaDetector(FallacyDetector):
    """Detects false dilemma fallacies - presenting only two options when more exist"""
    
    def __init__(self):
        self.dilemma_patterns = [
            r'\beither\s+.{5,}\s+or\s+.{5,}\b',
            r'\bonly (?:two|2) (?:choices|options|ways|possibilities)\b',
            r'\b(?:you\'re|it\'s|we\'re) either\s+.{5,}\s+or\s+.{5,}\b',
            r'\bthere are (?:only )?(?:two|2) (?:options|choices|possibilities)\b',
            r'\bif (?:you\'re not|we don\'t|you don\'t).{5,}then (?:you\'re|we\'re|you must be).{5,}\b',
            r'\byou (?:can\'t|cannot) have it both ways\b',
            r'\byou (?:must|have to) choose (?:between|one or the other)\b'
        ]
        
        # Binary thinking indicators
        self.binary_patterns = [
            r'\bwith us or against us\b',
            r'\bpart of the solution or part of the problem\b',
            r'\byou\'re (?:for|against) (?:America|democracy|freedom|justice)\b'
        ]
        
        self.compiled_dilemma = [re.compile(p, re.IGNORECASE) for p in self.dilemma_patterns]
        self.compiled_binary = [re.compile(p, re.IGNORECASE) for p in self.binary_patterns]
    
    def detect(self, text: str, context: Optional[Dict] = None) -> List[FallacyResult]:
        fallacies = []
        
        # Check for dilemma constructions
        dilemma_matches = []
        for pattern in self.compiled_dilemma:
            matches = pattern.finditer(text)
            dilemma_matches.extend([m.group() for m in matches])
        
        # Check for binary thinking
        binary_matches = []
        for pattern in self.compiled_binary:
            matches = pattern.finditer(text)
            binary_matches.extend([m.group() for m in matches])
        
        if dilemma_matches or binary_matches:
            confidence = 0.5
            patterns_found = []
            
            if dilemma_matches:
                confidence += len(dilemma_matches) * 0.3
                patterns_found.extend(['false_dilemma'] * len(dilemma_matches))
            
            if binary_matches:
                confidence += len(binary_matches) * 0.25
                patterns_found.extend(['binary_thinking'] * len(binary_matches))
            
            confidence = min(confidence, 1.0)
            
            severity = FallacySeverity.HIGH if confidence > 0.8 else (
                FallacySeverity.MEDIUM if confidence > 0.5 else FallacySeverity.LOW
            )
            
            explanation = get_fallacy_explanation(FallacyType.FALSE_DILEMMA)
            
            fallacy = FallacyResult(
                id=None,
                type=FallacyType.FALSE_DILEMMA,
                text=text.strip(),
                speaker=context.get('speaker') if context else None,
                target_claim_id=context.get('claim_id') if context else None,
                sentence_id=context.get('sentence_id') if context else None,
                turn_id=context.get('turn_id') if context else None,
                char_start=context.get('char_start') if context else None,
                char_end=context.get('char_end') if context else None,
                context=context.get('context_text') if context else None,
                confidence=confidence,
                patterns_matched=patterns_found,
                explanation=f"{explanation['description']} {explanation['why_problematic']}",
                severity=severity
            )
            
            fallacies.append(fallacy)
        
        return fallacies
    
    def get_fallacy_type(self) -> FallacyType:
        return FallacyType.FALSE_DILEMMA


class AppealToAuthorityDetector(FallacyDetector):
    """Detects inappropriate appeals to authority"""
    
    def __init__(self):
        self.vague_authority_patterns = [
            r'\baccording to (?:many|most|all|some) (?:experts|scientists|doctors|studies|reports)\b',
            r'\b(?:everyone|everybody) (?:knows|agrees|says)\b',
            r'\ba (?:famous|well-known|prominent|leading) \w+ said\b',
            r'\bstudies show\b(?!\s+(?:that\s+)?(?:specific|clear|detailed|the\s+\w+\s+study))',
            r'\bit\'s (?:common knowledge|widely known|obvious|well known) that\b',
            r'\bpeople say\b',
            r'\bthey say\b'
        ]
        
        # Celebrity/irrelevant authority
        self.celebrity_patterns = [
            r'\b(?:hollywood|celebrity|actor|actress)\s+\w+\s+(?:said|believes|thinks)\b',
            r'\ba (?:businessman|ceo|billionaire)\s+(?:said|believes|thinks)\b(?!.*(?:about business|about the economy))'
        ]
        
        self.compiled_vague = [re.compile(p, re.IGNORECASE) for p in self.vague_authority_patterns]
        self.compiled_celebrity = [re.compile(p, re.IGNORECASE) for p in self.celebrity_patterns]
    
    def detect(self, text: str, context: Optional[Dict] = None) -> List[FallacyResult]:
        fallacies = []
        
        # Check for vague authority appeals
        vague_matches = []
        for pattern in self.compiled_vague:
            matches = pattern.finditer(text)
            vague_matches.extend([m.group() for m in matches])
        
        # Check for celebrity/irrelevant authority
        celebrity_matches = []
        for pattern in self.compiled_celebrity:
            matches = pattern.finditer(text)
            celebrity_matches.extend([m.group() for m in matches])
        
        if vague_matches or celebrity_matches:
            confidence = 0.4
            patterns_found = []
            
            if vague_matches:
                confidence += len(vague_matches) * 0.2
                patterns_found.extend(['vague_authority'] * len(vague_matches))
            
            if celebrity_matches:
                confidence += len(celebrity_matches) * 0.25
                patterns_found.extend(['irrelevant_authority'] * len(celebrity_matches))
            
            confidence = min(confidence, 1.0)
            
            severity = FallacySeverity.MEDIUM if confidence > 0.6 else FallacySeverity.LOW
            
            explanation = get_fallacy_explanation(FallacyType.APPEAL_TO_AUTHORITY)
            
            fallacy = FallacyResult(
                id=None,
                type=FallacyType.APPEAL_TO_AUTHORITY,
                text=text.strip(),
                speaker=context.get('speaker') if context else None,
                target_claim_id=context.get('claim_id') if context else None,
                sentence_id=context.get('sentence_id') if context else None,
                turn_id=context.get('turn_id') if context else None,
                char_start=context.get('char_start') if context else None,
                char_end=context.get('char_end') if context else None,
                context=context.get('context_text') if context else None,
                confidence=confidence,
                patterns_matched=patterns_found,
                explanation=f"{explanation['description']} {explanation['why_problematic']}",
                severity=severity
            )
            
            fallacies.append(fallacy)
        
        return fallacies
    
    def get_fallacy_type(self) -> FallacyType:
        return FallacyType.APPEAL_TO_AUTHORITY


class SlipperySlopeDetector(FallacyDetector):
    """Detects slippery slope fallacies - arguing that one event leads to extreme consequences"""
    
    def __init__(self):
        self.slope_patterns = [
            r'\bif we (?:allow|permit|do|start) this.+(?:then|next).+(?:will|would|they\'ll)',
            r'\bthis (?:will|would) (?:lead to|result in|cause).{10,}(?:destruction|collapse|end|disaster)\b',
            r'\b(?:before you know it|next thing you know|soon).+(?:will|would|they\'ll)',
            r'\bonce we start.{5,}(?:where does it end|there\'s no stopping|can\'t stop)\b',
            r'\bthis is (?:just the beginning|the first step) (?:of|to|toward).{5,}\b',
            r'\bif we give (?:them|him|her) an inch.{5,}(?:mile|everything)\b'
        ]
        
        # Extreme consequence words
        self.extreme_consequences = [
            r'\b(?:complete|total|absolute) (?:destruction|collapse|chaos|anarchy|tyranny)\b',
            r'\b(?:end of|death of|destruction of) (?:democracy|freedom|america|civilization)\b',
            r'\b(?:slippery slope|domino effect|snowball effect)\b'
        ]
        
        self.compiled_slope = [re.compile(p, re.IGNORECASE) for p in self.slope_patterns]
        self.compiled_extreme = [re.compile(p, re.IGNORECASE) for p in self.extreme_consequences]
    
    def detect(self, text: str, context: Optional[Dict] = None) -> List[FallacyResult]:
        fallacies = []
        
        # Check for slippery slope construction
        slope_matches = []
        for pattern in self.compiled_slope:
            matches = pattern.finditer(text)
            slope_matches.extend([m.group() for m in matches])
        
        # Check for extreme consequences
        extreme_matches = []
        for pattern in self.compiled_extreme:
            matches = pattern.finditer(text)
            extreme_matches.extend([m.group() for m in matches])
        
        if slope_matches or extreme_matches:
            confidence = 0.4
            patterns_found = []
            
            if slope_matches:
                confidence += len(slope_matches) * 0.3
                patterns_found.extend(['chain_reaction'] * len(slope_matches))
            
            if extreme_matches:
                confidence += len(extreme_matches) * 0.2
                patterns_found.extend(['extreme_consequences'] * len(extreme_matches))
            
            confidence = min(confidence, 1.0)
            
            severity = FallacySeverity.HIGH if confidence > 0.8 else (
                FallacySeverity.MEDIUM if confidence > 0.5 else FallacySeverity.LOW
            )
            
            explanation = get_fallacy_explanation(FallacyType.SLIPPERY_SLOPE)
            
            fallacy = FallacyResult(
                id=None,
                type=FallacyType.SLIPPERY_SLOPE,
                text=text.strip(),
                speaker=context.get('speaker') if context else None,
                target_claim_id=context.get('claim_id') if context else None,
                sentence_id=context.get('sentence_id') if context else None,
                turn_id=context.get('turn_id') if context else None,
                char_start=context.get('char_start') if context else None,
                char_end=context.get('char_end') if context else None,
                context=context.get('context_text') if context else None,
                confidence=confidence,
                patterns_matched=patterns_found,
                explanation=f"{explanation['description']} {explanation['why_problematic']}",
                severity=severity
            )
            
            fallacies.append(fallacy)
        
        return fallacies
    
    def get_fallacy_type(self) -> FallacyType:
        return FallacyType.SLIPPERY_SLOPE


class DebateFallacyDetector:
    """Main fallacy detection engine that coordinates multiple detectors"""
    
    def __init__(self):
        # Phase 1: Core detectors
        self.detectors = [
            AdHominemDetector(),
            StrawManDetector(), 
            FalseDilemmaDetector(),
            AppealToAuthorityDetector(),
            SlipperySlopeDetector()
        ]
        
        logger.info(f"Initialized {len(self.detectors)} fallacy detectors")
    
    def detect_fallacies(self, claims: List[Claim], sentences: Optional[List[Sentence]] = None) -> List[FallacyResult]:
        """
        Detect fallacies in claims and sentences.
        
        Args:
            claims: List of extracted claims to analyze
            sentences: Optional list of sentences for broader context analysis
            
        Returns:
            List of detected fallacies
        """
        all_fallacies = []
        
        # Detect fallacies in claims
        for claim in claims:
            context = {
                'speaker': claim.speaker,
                'claim_id': claim.id,
                'sentence_id': claim.sentence_id,
                'turn_id': claim.turn_id,
                'char_start': claim.char_start,
                'char_end': claim.char_end,
                'context_text': claim.context
            }
            
            claim_fallacies = self._detect_in_text(claim.text, context)
            all_fallacies.extend(claim_fallacies)
        
        # Optionally detect in sentences that didn't produce claims
        if sentences:
            claim_sentence_ids = {claim.sentence_id for claim in claims}
            non_claim_sentences = [s for s in sentences if s.id not in claim_sentence_ids]
            
            for sentence in non_claim_sentences:
                context = {
                    'speaker': sentence.speaker,
                    'sentence_id': sentence.id,
                    'turn_id': sentence.turn_id,
                    'char_start': sentence.char_start,
                    'char_end': sentence.char_end
                }
                
                sentence_fallacies = self._detect_in_text(sentence.text, context)
                all_fallacies.extend(sentence_fallacies)
        
        logger.info(f"Detected {len(all_fallacies)} total fallacies")
        
        # Log fallacy type distribution
        fallacy_types = {}
        for fallacy in all_fallacies:
            fallacy_type = fallacy.type.value
            fallacy_types[fallacy_type] = fallacy_types.get(fallacy_type, 0) + 1
        
        for fallacy_type, count in fallacy_types.items():
            logger.info(f"  {fallacy_type}: {count}")
        
        return all_fallacies
    
    def _detect_in_text(self, text: str, context: Dict) -> List[FallacyResult]:
        """Run all detectors on a single piece of text"""
        fallacies = []
        
        for detector in self.detectors:
            try:
                detected = detector.detect(text, context)
                fallacies.extend(detected)
            except Exception as e:
                logger.warning(f"Detector {detector.__class__.__name__} failed on text: {e}")
        
        return fallacies
