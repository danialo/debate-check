"""
Post-processing for claim deduplication and context enrichment
"""

import logging
from typing import List, Dict, Set
from collections import defaultdict

from .models import Claim, Sentence, ClaimType
from .claim_filters import ImprovedClaimFilteringSystem

logger = logging.getLogger(__name__)


class ClaimPostprocessor:
    """
    Post-processes detected claims by:
    1. Removing duplicates
    2. Merging overlapping spans
    3. Adding context sentences
    4. Ranking by confidence
    """
    
    def __init__(self, context_window: int = 1):
        """
        Args:
            context_window: Number of sentences before/after to include as context
        """
        self.context_window = context_window
    
    def process(self, claims: List[Claim], sentences: List[Sentence]) -> List[Claim]:
        """
        Post-process the detected claims.
        
        Args:
            claims: Raw claims from detectors
            sentences: Original sentences for context lookup
            
        Returns:
            Processed and deduplicated claims
        """
        logger.debug(f"Post-processing {len(claims)} raw claims")
        
        # Create sentence lookup for context building
        sentence_lookup = {sent.id: sent for sent in sentences}
        
        # Step 1: Remove exact duplicates
        deduped_claims = self._remove_duplicates(claims)
        logger.debug(f"After deduplication: {len(deduped_claims)} claims")
        
        # Step 2: Merge overlapping claims of the same type
        merged_claims = self._merge_overlapping_claims(deduped_claims)
        logger.debug(f"After merging: {len(merged_claims)} claims")
        
        # Step 3: Add context to claims
        contextualized_claims = self._add_context(merged_claims, sentences)
        logger.debug(f"Added context to {len(contextualized_claims)} claims")
        
        # Step 4: Sort by confidence (highest first)
        final_claims = sorted(contextualized_claims, key=lambda c: c.confidence, reverse=True)
        
        logger.info(f"Post-processing complete: {len(final_claims)} final claims")
        return final_claims
    
    def _remove_duplicates(self, claims: List[Claim]) -> List[Claim]:
        """Remove claims with identical text, speaker, and sentence."""
        seen = set()
        unique_claims = []
        
        for claim in claims:
            # Create a key based on normalized text, speaker, and sentence
            key = (
                claim.text.strip().lower(),
                claim.speaker,
                claim.sentence_id,
                claim.type
            )
            
            if key not in seen:
                seen.add(key)
                unique_claims.append(claim)
        
        return unique_claims
    
    def _merge_overlapping_claims(self, claims: List[Claim]) -> List[Claim]:
        """
        Merge claims that overlap significantly in the same sentence.
        This helps when multiple detectors find similar claims.
        """
        # Group claims by sentence and speaker
        grouped = defaultdict(list)
        for claim in claims:
            key = (claim.sentence_id, claim.speaker)
            grouped[key].append(claim)
        
        merged_claims = []
        
        for (sentence_id, speaker), sentence_claims in grouped.items():
            if len(sentence_claims) <= 1:
                merged_claims.extend(sentence_claims)
                continue
            
            # Sort by start position
            sentence_claims.sort(key=lambda c: c.char_start)
            
            # Group overlapping claims
            groups = []
            current_group = [sentence_claims[0]]
            
            for claim in sentence_claims[1:]:
                # Check if this claim overlaps significantly with the current group
                current_end = max(c.char_end for c in current_group)
                
                # If claims overlap by more than 50% of either claim, group them
                overlap_start = max(claim.char_start, min(c.char_start for c in current_group))
                overlap_end = min(claim.char_end, current_end)
                
                if overlap_start < overlap_end:
                    overlap_length = overlap_end - overlap_start
                    claim_length = claim.char_end - claim.char_start
                    group_length = current_end - min(c.char_start for c in current_group)
                    
                    if (overlap_length / claim_length > 0.5 or 
                        overlap_length / group_length > 0.5):
                        current_group.append(claim)
                    else:
                        groups.append(current_group)
                        current_group = [claim]
                else:
                    groups.append(current_group)
                    current_group = [claim]
            
            groups.append(current_group)
            
            # Merge each group into a single claim
            for group in groups:
                if len(group) == 1:
                    merged_claims.append(group[0])
                else:
                    merged_claim = self._merge_claim_group(group)
                    merged_claims.append(merged_claim)
        
        return merged_claims
    
    def _merge_claim_group(self, claims: List[Claim]) -> Claim:
        """Merge a group of overlapping claims into a single claim."""
        # Use the claim with the highest confidence as the base
        base_claim = max(claims, key=lambda c: c.confidence)
        
        # Extend the text span to cover all claims if needed
        min_start = min(c.char_start for c in claims)
        max_end = max(c.char_end for c in claims)
        
        # Choose the most specific claim type (statistical > causal > comparative > historical > factual)
        type_priority = {
            ClaimType.STATISTICAL: 5,
            ClaimType.CAUSAL: 4,
            ClaimType.COMPARATIVE: 3,
            ClaimType.HISTORICAL: 2,
            ClaimType.FACTUAL: 1
        }
        
        best_type = max(claims, key=lambda c: type_priority.get(c.type, 0)).type
        
        # Average the confidence scores
        avg_confidence = sum(c.confidence for c in claims) / len(claims)
        
        merged_claim = Claim(
            type=best_type,
            text=base_claim.text,  # Keep the original text from the highest confidence claim
            speaker=base_claim.speaker,
            sentence_id=base_claim.sentence_id,
            turn_id=base_claim.turn_id,
            char_start=min_start,
            char_end=max_end,
            confidence=avg_confidence,
            context=base_claim.context  # Will be updated in next step
        )
        
        return merged_claim
    
    def _add_context(self, claims: List[Claim], sentences: List[Sentence]) -> List[Claim]:
        """Add surrounding sentences as context for each claim."""
        # Create mappings for efficient lookup
        sentence_by_id = {sent.id: sent for sent in sentences}
        sentences_by_turn = defaultdict(list)
        
        for sent in sentences:
            sentences_by_turn[sent.turn_id].append(sent)
        
        # Sort sentences within each turn
        for turn_sentences in sentences_by_turn.values():
            turn_sentences.sort(key=lambda s: s.sentence_index)
        
        contextualized_claims = []
        
        for claim in claims:
            # Find the sentence containing this claim
            claim_sentence = sentence_by_id.get(claim.sentence_id)
            if not claim_sentence:
                logger.warning(f"Could not find sentence {claim.sentence_id} for claim")
                contextualized_claims.append(claim)
                continue
            
            # Get surrounding sentences from the same turn
            turn_sentences = sentences_by_turn[claim_sentence.turn_id]
            claim_sent_idx = next((i for i, s in enumerate(turn_sentences) 
                                 if s.id == claim.sentence_id), None)
            
            if claim_sent_idx is None:
                logger.warning(f"Could not find sentence index for claim")
                contextualized_claims.append(claim)
                continue
            
            # Build context window
            start_idx = max(0, claim_sent_idx - self.context_window)
            end_idx = min(len(turn_sentences), claim_sent_idx + self.context_window + 1)
            
            context_sentences = turn_sentences[start_idx:end_idx]
            context_text = ' '.join(sent.text for sent in context_sentences)
            
            # Create new claim with context
            claim_with_context = Claim(
                id=claim.id,
                type=claim.type,
                text=claim.text,
                speaker=claim.speaker,
                sentence_id=claim.sentence_id,
                turn_id=claim.turn_id,
                char_start=claim.char_start,
                char_end=claim.char_end,
                confidence=claim.confidence,
                context=context_text,
                timestamp=claim.timestamp
            )
            
            contextualized_claims.append(claim_with_context)
        
        return contextualized_claims
