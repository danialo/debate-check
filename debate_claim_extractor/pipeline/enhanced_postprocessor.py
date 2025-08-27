"""
Enhanced post-processing with claim filtering and classification
"""

import logging
from typing import List, Dict, Set
from collections import defaultdict

from .models import Claim, Sentence, ClaimType
from .claim_filters import ImprovedClaimFilteringSystem
from .postprocessor import ClaimPostprocessor

logger = logging.getLogger(__name__)


class EnhancedClaimPostprocessor(ClaimPostprocessor):
    """
    Enhanced post-processor that includes intelligent claim filtering and classification.
    
    Process order:
    1. Filter out non-claims (conversational fillers, questions, etc.)
    2. Classify remaining claims (factual vs normative/philosophical)
    3. Standard deduplication and merging
    4. Add context
    """
    
    def __init__(self, context_window: int = 1, enable_filtering: bool = True):
        """
        Args:
            context_window: Number of sentences before/after to include as context
            enable_filtering: Whether to enable the claim filtering system
        """
        super().__init__(context_window)
        self.enable_filtering = enable_filtering
        self.filtering_system = ImprovedClaimFilteringSystem() if enable_filtering else None
    
    def process(self, claims: List[Claim], sentences: List[Sentence]) -> List[Claim]:
        """
        Enhanced post-processing with filtering and classification.
        
        Args:
            claims: Raw claims from detectors
            sentences: Original sentences for context lookup
            
        Returns:
            Processed, filtered, and classified claims
        """
        logger.debug(f"Enhanced post-processing {len(claims)} raw claims")
        
        # Step 1: Build transient context for filters (same-turn, same-speaker)
        context_map = self._build_filter_context(claims, sentences, max_context_chars=300)

        # Step 2: Filter out non-claims and classify remaining claims
        if self.enable_filtering and self.filtering_system:
            filtered_claims = self.filtering_system.filter_and_classify_claims(claims, context_map=context_map)
            logger.info(f"After filtering: {len(filtered_claims)} valid claims")
        else:
            filtered_claims = claims
            logger.info(f"Filtering disabled, proceeding with {len(filtered_claims)} claims")
        
        # Step 2: Continue with standard postprocessing
        if not filtered_claims:
            logger.info("No claims remaining after filtering")
            return []
        
        # Create sentence lookup for context building
        sentence_lookup = {sent.id: sent for sent in sentences}
        
        # Step 3: Remove exact duplicates
        deduped_claims = self._remove_duplicates(filtered_claims)
        logger.debug(f"After deduplication: {len(deduped_claims)} claims")
        
        # Step 4: Merge overlapping claims of the same type
        merged_claims = self._merge_overlapping_claims(deduped_claims)
        logger.debug(f"After merging: {len(merged_claims)} claims")
        
        # Step 5: Add context to claims
        contextualized_claims = self._add_context_enhanced(merged_claims, sentences)
        logger.debug(f"Added context to {len(contextualized_claims)} claims")
        
        # Step 6: Sort by confidence (highest first)
        final_claims = sorted(contextualized_claims, key=lambda c: c.confidence, reverse=True)
        
        logger.info(f"Enhanced post-processing complete: {len(final_claims)} final claims")
        
        # Log claim type distribution
        claim_types = defaultdict(int)
        fact_check_counts = defaultdict(int)
        
        for claim in final_claims:
            claim_types[claim.type.value] += 1
            if hasattr(claim, 'should_fact_check') and claim.should_fact_check is not None:
                fact_check_counts['should_fact_check' if claim.should_fact_check else 'skip_fact_check'] += 1
        
        logger.info(f"Final claim type distribution: {dict(claim_types)}")
        logger.info(f"Fact-checking distribution: {dict(fact_check_counts)}")
        
        return final_claims
    
    def _build_filter_context(self,
                               claims: List[Claim],
                               sentences: List[Sentence],
                               *,
                               context_window: int | None = None,
                               max_context_chars: int = 300) -> dict:
        """
        Attach lightweight, same-turn/same-speaker context for filtering.
        Produces a mapping claim_id -> {'before': str, 'after': str}
        """
        from collections import defaultdict

        cw = self.context_window if context_window is None else context_window
        if cw is None:
            cw = 2

        # Prefer composite turn key to avoid collisions across chunks
        def turn_key(s: Sentence) -> tuple:
            return (getattr(s, 'chunk_id', None), s.turn_id)

        sents_by_turn: dict[tuple, list[Sentence]] = defaultdict(list)
        for s in sentences:
            sents_by_turn[turn_key(s)].append(s)

        # Sort per turn and build id->index maps
        idx_by_turn: dict[tuple, dict[str, int]] = {}
        for k, lst in sents_by_turn.items():
            lst.sort(key=lambda s: s.sentence_index)
            idx_by_turn[k] = {s.id: i for i, s in enumerate(lst)}

        # Helper to join with a char budget
        def _join_with_char_budget(items: list[str], budget: int, reverse: bool = False) -> str:
            acc, used = [], 0
            it = reversed(items) if reverse else items
            for t in it:
                t = " ".join(t.split())
                if not t:
                    continue
                add = (len(t) + (1 if used else 0))
                if used + add > budget:
                    break
                acc.append(t)
                used += add
            if reverse:
                acc.reverse()
            return " ".join(acc)

        context_map: dict[str, dict[str, str]] = {}
        # Build per-claim contexts
        for c in claims:
            sid = getattr(c, 'sentence_id', None)
            if not sid:
                continue
            # find which turn contains this sentence
            found = None
            for k, id_index in idx_by_turn.items():
                if sid in id_index:
                    found = (k, id_index[sid])
                    break
            if not found:
                continue
            k, idx = found
            turn_list = sents_by_turn[k]
            focus_sent = turn_list[idx]
            spk = focus_sent.speaker

            # window bounds
            start = max(0, idx - cw)
            end = min(len(turn_list), idx + cw + 1)

            # collect same-speaker contexts only
            before_texts = [ss.text for ss in turn_list[start:idx] if ss.speaker == spk]
            after_texts  = [ss.text for ss in turn_list[idx+1:end] if ss.speaker == spk]

            context_before = _join_with_char_budget(before_texts, max_context_chars, reverse=True)
            context_after  = _join_with_char_budget(after_texts,  max_context_chars, reverse=False)

            context_map[c.id] = {"before": context_before, "after": context_after}

        return context_map

    def _add_context_enhanced(self, claims: List[Claim], sentences: List[Sentence]) -> List[Claim]:
        """Enhanced context addition that preserves new claim metadata."""
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
            
            # Create new claim with context, preserving all metadata
            claim_dict = claim.model_dump()
            claim_dict['context'] = context_text
            
            claim_with_context = Claim(**claim_dict)
            contextualized_claims.append(claim_with_context)
        
        return contextualized_claims
    
    def _merge_claim_group_enhanced(self, claims: List[Claim]) -> Claim:
        """Enhanced claim merging that preserves new metadata."""
        # Use the claim with the highest confidence as the base
        base_claim = max(claims, key=lambda c: c.confidence)
        
        # Extend the text span to cover all claims if needed
        min_start = min(c.char_start for c in claims)
        max_end = max(c.char_end for c in claims)
        
        # Choose the most specific claim type (normative > statistical > causal > comparative > historical > factual)
        type_priority = {
            ClaimType.NORMATIVE: 6,
            ClaimType.STATISTICAL: 5,
            ClaimType.CAUSAL: 4,
            ClaimType.COMPARATIVE: 3,
            ClaimType.HISTORICAL: 2,
            ClaimType.FACTUAL: 1
        }
        
        best_claim = max(claims, key=lambda c: type_priority.get(c.type, 0))
        best_type = best_claim.type
        
        # Average the confidence scores
        avg_confidence = sum(c.confidence for c in claims) / len(claims)
        
        # Preserve metadata from the highest-priority claim
        merged_dict = base_claim.model_dump()
        merged_dict.update({
            'type': best_type,
            'char_start': min_start,
            'char_end': max_end,
            'confidence': avg_confidence,
            'should_fact_check': getattr(best_claim, 'should_fact_check', None),
            'classification_reason': getattr(best_claim, 'classification_reason', None)
        })
        
        return Claim(**merged_dict)
