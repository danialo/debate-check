"""
Enhanced claim extraction pipeline with hierarchical chunking
Integrates: Speaker Turn → Paragraph → Sentence → Claim pipeline
Production-ready with robust error handling and performance optimizations.
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Tuple
from uuid import uuid4
from collections import Counter

from .models import ExtractionResult, Claim, Sentence
from .preprocessor import DebatePreprocessor
from .paragraph_chunker import HierarchicalChunker, ParagraphChunker, Paragraph
from .enhanced_segmenter import ParagraphAwareSegmenter, ClaimGatingFilter, ClassifiedSentence
from .claim_detector import DebateClaimDetector
from .postprocessor import ClaimPostprocessor
from .claim_filters import ImprovedClaimFilteringSystem
from ..fact_checking import FactVerificationPipeline, FactCheckConfig
from ..fallacy_detection import DebateFallacyDetector, FallacyDetectionSummary
from ..scoring import ScoringPipeline

logger = logging.getLogger(__name__)


class HierarchicalClaimExtractionPipeline:
    """
    Production-ready pipeline with hierarchical chunking and comprehensive filtering.
    
    Pipeline flow:
    1. Preprocessing: Clean text and identify speakers → (speaker, utterance, line) tuples
    2. Hierarchical Chunking: Group by speaker turns → Paragraph objects  
    3. Enhanced Segmentation: Segment with classification → ClassifiedSentence objects
    4. Claim Gating: Filter for claimable sentences → Valid sentences
    5. Claim Detection: Apply detectors → Raw claims
    6. Claim Filtering: Advanced filtering system → Filtered claims
    7. Post-processing: Context and deduplication → Final claims
    """
    
    def __init__(self, 
                 config_path: Optional[Path] = None,
                 use_enhanced_filtering: bool = True,
                 context_window: int = 2,
                 allow_questions: bool = False,
                 allow_imperatives: bool = True,
                 max_paragraph_chars: int = 10000,
                 min_tokens_no_anchor: int = 7,
                 allow_assertive_questions: bool = True,
                 context_sentences: int = 2,
                 max_meta_examples: int = 3):
        """
        Initialize the enhanced pipeline.
        
        Args:
            config_path: Path to YAML configuration file (future enhancement)
            use_enhanced_filtering: Enable advanced claim filtering system
            context_window: Number of paragraphs of context for sentences
            allow_questions: Allow questions through claim gating
            allow_imperatives: Allow imperatives through claim gating
            max_paragraph_chars: Max chars per paragraph before failsafe splitting
            min_tokens_no_anchor: Min tokens required when no anchors present
            allow_assertive_questions: Allow questions with years/numbers + copula/modal
            context_sentences: Number of sentences for post-processing display context
            max_meta_examples: Maximum examples to include in gating metadata
        """
        self.config_path = config_path
        self.use_enhanced_filtering = use_enhanced_filtering
        self.max_paragraph_chars = max_paragraph_chars
        self.min_tokens_no_anchor = min_tokens_no_anchor
        self.allow_assertive_questions = allow_assertive_questions
        self.context_sentences = context_sentences
        self.max_meta_examples = max_meta_examples
        
        # Initialize components
        logger.info("Initializing hierarchical claim extraction pipeline")
        
        # Stage 1: Preprocessing (unchanged)
        self.preprocessor = DebatePreprocessor()
        
        # Stage 2: Hierarchical chunking (NEW)
        shared_state = {"in_sponsor": False}  # For stateful sponsor filtering
        self.paragraph_chunker = ParagraphChunker()
        self.hierarchical_chunker = HierarchicalChunker(
            paragraph_chunker=self.paragraph_chunker,
            use_repair=False  # Can enable LLM repair later
        )
        
        # Stage 3: Enhanced segmentation with classification (NEW)
        self.segmenter = ParagraphAwareSegmenter(
            use_spacy=True, 
            context_window=context_window
        )
        
        # Stage 4: Claim gating filter (NEW)
        self.claim_gating_filter = ClaimGatingFilter(
            allow_questions=allow_questions,
            allow_imperatives=allow_imperatives
        )
        
        # Stage 5: Claim detection (enhanced)
        self.claim_detector = DebateClaimDetector()
        
        # Stage 6: Advanced claim filtering (NEW) - thread config through
        if self.use_enhanced_filtering:
            self.claim_filtering_system = ImprovedClaimFilteringSystem(
                shared_state=shared_state,
                min_tokens_no_anchor=self.min_tokens_no_anchor
            )
        else:
            self.claim_filtering_system = None
        
        # Stage 7: Post-processing (enhanced)
        self.postprocessor = ClaimPostprocessor()
        
        # Optional components (initialized on-demand)
        self.fact_pipeline = None
        self.fallacy_detector = None
        self.scoring_pipeline = None
        
        logger.info("Hierarchical pipeline initialization complete")
    
    def extract(self, text: str, source: str = "unknown") -> Tuple[ExtractionResult, List[Sentence]]:
        """
        Extract claims using hierarchical chunking and enhanced filtering.
        
        Args:
            text: Raw debate transcript text
            source: Source identifier for metadata
            
        Returns:
            Tuple of (ExtractionResult with claims and metadata, sentence_objects for reuse)
        """
        try:
            logger.info(f"Starting hierarchical extraction for source: {source}")
            
            # Stage 1: Preprocessing
            logger.debug("Stage 1: Preprocessing text")
            utterances = self.preprocessor.process(text)
            
            if not utterances:
                logger.warning("No utterances found after preprocessing")
                return ExtractionResult(
                    claims=[],
                    meta={"source": source, "error": "No utterances found"}
                ), []
            
            # Stage 2: Hierarchical chunking
            logger.debug("Stage 2: Hierarchical chunking into paragraphs")
            paragraphs, chunk_stats = self.hierarchical_chunker.chunk_transcript(utterances)
            
            if not paragraphs:
                logger.warning("No paragraphs found after chunking")
                return ExtractionResult(
                    claims=[],
                    meta={"source": source, "error": "No paragraphs found"}
                ), []
            
            # Apply rogue paragraph failsafe
            paragraphs = self._apply_paragraph_failsafe(paragraphs)
            
            # Stage 3: Enhanced segmentation with validation
            logger.debug("Stage 3: Enhanced segmentation with classification")
            classified_sentences = self.segmenter.segment_paragraphs(paragraphs)
            
            if not classified_sentences:
                logger.warning("No sentences found after segmentation")
                return ExtractionResult(
                    claims=[],
                    meta={"source": source, "error": "No sentences found"}
                ), []
            
            # Convert to base Sentence objects early (single canonical conversion)
            sentence_objects = [self._convert_to_sentence(cs) for cs in classified_sentences]
            
            # Validate spans (production-safe, no asserts)
            self._validate_sentence_spans(paragraphs, classified_sentences)
            
            # Stage 4: Claim gating with detailed diagnostics
            logger.debug("Stage 4: Filtering sentences for claim processing")
            valid_classified_sentences, gating_stats = self.claim_gating_filter.filter_sentences(classified_sentences)
            
            # Ensure gating_stats has all required keys (Fix #4)
            gating_stats = gating_stats or {}
            
            if not valid_classified_sentences:
                logger.warning("No valid sentences for claim processing after gating")
                empty_result = self._create_empty_result(source, utterances, paragraphs, classified_sentences, chunk_stats, gating_stats)
                return empty_result, sentence_objects
            
            # Map valid classified sentences to base Sentence objects
            valid_keys = {(cs.turn_id, cs.sentence_index) for cs in valid_classified_sentences}
            valid_base_sentences = [s for s in sentence_objects if (s.turn_id, s.sentence_index) in valid_keys]
            
            # Stage 5: Claim detection (operates on base Sentence objects only)
            logger.debug("Stage 5: Detecting claims from valid sentences")
            raw_claims = self.claim_detector.detect_claims(valid_base_sentences)
            
            # Ensure all claims have IDs and proper turn_id/sentence_index (Fix #5)
            for c in raw_claims:
                if not getattr(c, "id", None):
                    c.id = f"claim_{uuid4().hex}"
                # Fix #5: treat falsy turn_id as missing
                if not getattr(c, "turn_id", None) or not hasattr(c, "sentence_index"):
                    match = next((s for s in sentence_objects 
                                if s.char_start == c.char_start and s.char_end == c.char_end), None)
                    if match:
                        c.turn_id = match.turn_id
                        if not hasattr(c, "sentence_index"):
                            c.sentence_index = match.sentence_index
            
            # Sort for determinism with type safety (Fix #1)
            raw_claims.sort(key=lambda c: (
                str(getattr(c, 'turn_id', '')),
                int(getattr(c, 'sentence_index', 0) or 0),
                int(getattr(c, 'char_start', 0) or 0),
            ))
            
            if not raw_claims:
                logger.info("No claims detected")
                empty_result = self._create_empty_result(source, utterances, paragraphs, classified_sentences, chunk_stats, gating_stats)
                return empty_result, sentence_objects
            
            # Stage 6: Advanced claim filtering
            if self.use_enhanced_filtering and self.claim_filtering_system:
                logger.debug("Stage 6: Advanced claim filtering")
                filtered_claims = self.claim_filtering_system.filter_and_classify_claims(raw_claims)
            else:
                logger.debug("Stage 6: Skipping advanced filtering (disabled)")
                filtered_claims = raw_claims
            
            if not filtered_claims:
                logger.info("No claims remaining after filtering")
                empty_result = self._create_empty_result(source, utterances, paragraphs, classified_sentences, chunk_stats, gating_stats)
                return empty_result, sentence_objects
            
            # Stage 7: Post-processing (uses sentence_objects)
            logger.debug("Stage 7: Post-processing claims")
            final_claims = self.postprocessor.process(filtered_claims, sentence_objects)
            
            # Create comprehensive result with performance optimizations
            result = ExtractionResult(claims=final_claims)
            
            # Optimize sentence type counting (single pass)
            stype_counts = Counter(s.sentence_type.value for s in classified_sentences)
            repair_count = sum(1 for s in classified_sentences if s.needs_repair)
            
            # Stable sentence_types keys (include zeros)
            for k in ["statement", "question", "imperative", "exclamation", "fragment"]:
                stype_counts.setdefault(k, 0)
            
            # Guard gating_examples size (Fix #6)
            examples = gating_stats.get("examples", {})
            for reason, lst in list(examples.items()):
                examples[reason] = [t[:300] for t in (lst or [])[:self.max_meta_examples]]
            
            result.meta.update({
                "source": source,
                "pipeline_type": "hierarchical",
                
                # Stage statistics (ensure JSON-safe integers)
                "utterances_processed": int(len(utterances)),
                "paragraphs_created": int(len(paragraphs)),
                "sentences_classified": int(len(classified_sentences)),
                "valid_sentences": int(len(valid_classified_sentences)),
                "raw_claims_detected": int(len(raw_claims)),
                "filtered_claims": int(len(filtered_claims)),
                "final_claims": int(len(final_claims)),
                
                # Detailed stats
                "chunking_stats": chunk_stats,
                "gating_stats": gating_stats,
                
                # Bounded gating examples for tuning
                "gating_examples": examples,
                
                # Optimized sentence type distribution
                "sentence_types": {k: int(v) for k, v in stype_counts.items()},
                
                # Repair candidates (if enabled)
                "repair_needed": int(repair_count),
                
                # Drop ledger for UI insights
                "drop_ledger": {
                    "gated_fragments": int(gating_stats.get("filtered_fragment", 0)),
                    "gated_questions": int(gating_stats.get("filtered_question", 0)),
                    "gated_imperatives": int(gating_stats.get("filtered_imperative", 0)),
                    "filtered_after_detectors": int(len(raw_claims) - len(filtered_claims)),
                },
                
                # Store sentence index map for fallacy detection reuse
                "sentence_index_map": [(s.id, s.turn_id, s.sentence_index) for s in sentence_objects],
                
                # Claim→sentence mapping for UI highlighting
                "claim_sentence_map": [(c.id, getattr(c, 'turn_id', ''), getattr(c, 'sentence_index', 0)) for c in final_claims]
            })
            
            logger.info(f"Hierarchical extraction complete: {len(final_claims)} final claims from {source}")
            return result, sentence_objects
            
        except Exception as e:
            logger.error(f"Hierarchical pipeline failed for source {source}: {e}")
            logger.exception("Full traceback:")
            
            return ExtractionResult(
                claims=[],
                meta={
                    "source": source,
                    "error": str(e),
                    "pipeline_failed": True,
                    "pipeline_type": "hierarchical"
                }
            ), []
    
    def extract_simple(self, text: str, source: str = "unknown") -> ExtractionResult:
        """Simple extract method that returns just the result (backward compatibility)"""
        result, _ = self.extract(text, source)
        return result
    
    def _apply_paragraph_failsafe(self, paragraphs):
        """Apply failsafe splitting for rogue paragraphs"""
        safe_paragraphs = []
        
        for para in paragraphs:
            # Check both length and lack of end punctuation
            needs_split = (len(para.text) > self.max_paragraph_chars or 
                          (len(para.text.split()) > 100 and not para.text.strip().endswith(('.', '!', '?'))))
            
            if needs_split:
                logger.debug(f"Applying failsafe split to {len(para.text)}-char paragraph")
                split_paras = self._split_rogue_paragraph(para)
                safe_paragraphs.extend(split_paras)
            else:
                safe_paragraphs.append(para)
        
        return safe_paragraphs
    
    def _split_rogue_paragraph(self, paragraph):
        """Split a rogue paragraph on punctuation with exact offset tracking"""
        text = paragraph.text
        split_chars = ['; ', ' — ', ' – ', ', ']
        
        # Try smart separators first
        for sep in split_chars:
            if sep in text:
                parts = text.split(sep)
                if len(parts) > 1 and all(len(p.split()) > 5 for p in parts):
                    result = []
                    # Walk the original text using index searches to keep offsets exact
                    start = 0
                    for i, p in enumerate(parts):
                        if not p.strip():
                            # Advance past empty part + separator
                            start = text.find(sep, start)
                            if start != -1:
                                start += len(sep)
                            continue
                        
                        end = start + len(p)
                        # Slice exactly without re-inserting separator
                        segment = text[start:end]
                        
                        if segment.strip():
                            # Fix #3: prevent ID collisions with unique counter and uid
                            result.append(Paragraph(
                                text=segment.strip(),
                                speaker=paragraph.speaker,
                                start_char=paragraph.start_char + start,
                                end_char=paragraph.start_char + end,
                                paragraph_id=f"{paragraph.paragraph_id}_{sep.strip()}_{i:03d}_{uuid4().hex[:6]}",
                                utterance_count=paragraph.utterance_count,
                                line_numbers=paragraph.line_numbers
                            ))
                        
                        # Move past this part + separator (if any)
                        next_idx = text.find(sep, end)
                        start = (next_idx + len(sep)) if next_idx != -1 else end
                    
                    return result if result else [paragraph]
        
        # Fallback: token-budget split for massive run-ons (Fix #9 & #6)
        TOK_LIMIT = 120
        toks = text.split()
        if len(toks) <= TOK_LIMIT:
            return [paragraph]
        
        result, cursor = [], 0
        for i in range(0, len(toks), TOK_LIMIT):
            part = " ".join(toks[i:i+TOK_LIMIT])
            # Find substring position robustly
            pos = text.find(part, cursor)
            if pos == -1:
                # Fix #6: log warning for offset misalignment
                logger.warning("Token split mismatch; using conservative offsets for %s", paragraph.paragraph_id)
                pos = cursor  # best-effort, but expect span validator warnings
            
            segment = part
            result.append(Paragraph(
                text=segment,
                speaker=paragraph.speaker,
                start_char=paragraph.start_char + pos,
                end_char=paragraph.start_char + pos + len(segment),
                paragraph_id=f"{paragraph.paragraph_id}_tok{i:03d}_{uuid4().hex[:6]}",
                utterance_count=paragraph.utterance_count,
                line_numbers=paragraph.line_numbers
            ))
            cursor = pos + len(segment)
        
        return result if result else [paragraph]
    
    def _validate_sentence_spans(self, paragraphs, classified_sentences):
        """Validate spans with production-safe soft checks"""
        para_map = {para.paragraph_id: para for para in paragraphs}
        
        for sentence in classified_sentences:
            if sentence.turn_id in para_map:
                para = para_map[sentence.turn_id]
                relative_start = sentence.char_start - para.start_char
                relative_end = sentence.char_end - para.start_char
                
                if 0 <= relative_start <= relative_end <= len(para.text):
                    extracted = para.text[relative_start:relative_end]
                    
                    # Soft validation - log warnings with context
                    if extracted.strip() != sentence.text.strip():
                        logger.warning("Span mismatch (para_id=%s, turn_id=%s, idx=%s): %r != %r",
                                     para.paragraph_id, sentence.turn_id, sentence.sentence_index,
                                     extracted, sentence.text)
                    
                    if extracted.endswith((" ", "-", "—")):
                        logger.warning("Sentence ends mid-token (para_id=%s, turn_id=%s, idx=%s): %r",
                                     para.paragraph_id, sentence.turn_id, sentence.sentence_index,
                                     extracted)
                else:
                    logger.warning("Invalid span range (para_id=%s, turn_id=%s, idx=%s): %d-%d not in [0, %d]",
                                 para.paragraph_id, sentence.turn_id, sentence.sentence_index,
                                 relative_start, relative_end, len(para.text))
    
    def _create_empty_result(self, source: str, utterances, paragraphs, sentences, chunk_stats, gating_stats) -> ExtractionResult:
        """Create an empty result with comprehensive metadata"""
        # Optimize type counting
        stype_counts = Counter(s.sentence_type.value for s in sentences)
        repair_count = sum(1 for s in sentences if s.needs_repair)
        
        # Include zeros for missing types
        for k in ["statement", "question", "imperative", "exclamation", "fragment"]:
            stype_counts.setdefault(k, 0)
        
        # Guard gating_stats access (Fix #4)
        gating_stats = gating_stats or {}
        
        # Guard gating_examples size (Fix #6)
        examples = gating_stats.get("examples", {})
        for reason, lst in list(examples.items()):
            examples[reason] = [t[:300] for t in (lst or [])[:self.max_meta_examples]]
        
        return ExtractionResult(
            claims=[],
            meta={
                "source": source,
                "pipeline_type": "hierarchical",
                "utterances_processed": int(len(utterances)),
                "paragraphs_created": int(len(paragraphs)),
                "sentences_classified": int(len(sentences)),
                "chunking_stats": chunk_stats,
                "gating_stats": gating_stats,
                "gating_examples": examples,
                "sentence_types": {k: int(v) for k, v in stype_counts.items()},
                "repair_needed": int(repair_count),
                # Include zeros for drop ledger on early exits
                "drop_ledger": {
                    "gated_fragments": int(gating_stats.get("filtered_fragment", 0)),
                    "gated_questions": int(gating_stats.get("filtered_question", 0)),
                    "gated_imperatives": int(gating_stats.get("filtered_imperative", 0)),
                    "filtered_after_detectors": 0,
                }
            }
        )
    
    def _convert_to_sentence(self, classified_sentence: ClassifiedSentence) -> Sentence:
        """Convert ClassifiedSentence to regular Sentence for compatibility"""
        # Ensure ID exists (prevent None serialization)
        sid = getattr(classified_sentence, "id", None) or f"sent_{uuid4().hex}"
        
        return Sentence(
            id=sid,
            text=classified_sentence.text,
            speaker=classified_sentence.speaker,
            turn_id=classified_sentence.turn_id,
            sentence_index=classified_sentence.sentence_index,
            char_start=classified_sentence.char_start,
            char_end=classified_sentence.char_end,
            line_number=classified_sentence.line_number
        )
    
    # Async-safe fact-checking methods
    async def _afact_check(self, claims, fact_config):
        """Async fact-checking implementation"""
        if self.fact_pipeline is None:
            self.fact_pipeline = FactVerificationPipeline(fact_config)
        
        try:
            return await self.fact_pipeline.verify_claims(claims)
        finally:
            if self.fact_pipeline:
                await self.fact_pipeline.close()
                self.fact_pipeline = None  # Fix #2: critical - reset after close
    
    def _sfact_check(self, claims, fact_config):
        """Sync fact-checking wrapper (handles event loop detection)"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - schedule and block until done
                future = asyncio.run_coroutine_threadsafe(self._afact_check(claims, fact_config), loop)
                return future.result()
            else:
                # No running loop - use asyncio.run
                return asyncio.run(self._afact_check(claims, fact_config))
        except RuntimeError:
            # No event loop - use asyncio.run
            return asyncio.run(self._afact_check(claims, fact_config))
    
    # Enhanced analysis methods
    def extract_with_fact_checking(self, 
                                  text: str, 
                                  source: str = "unknown",
                                  fact_config: Optional[FactCheckConfig] = None) -> ExtractionResult:
        """Extract claims with fact-checking using hierarchical pipeline"""
        result, sentence_objects = self.extract(text, source)
        
        if not result.claims:
            logger.info("No claims to fact-check")
            return result
        
        try:
            logger.info(f"Starting fact-checking for {len(result.claims)} claims")
            fact_results = self._sfact_check(result.claims, fact_config)
            
            result.fact_checking_enabled = True
            result.fact_check_results = [fr.model_dump() for fr in fact_results]
            
            # Optimize verification summary counting
            status_counts = Counter(fr.overall_status for fr in fact_results)
            
            result.meta.update({
                "fact_checking_performed": True,
                "fact_checked_claims": int(len(fact_results)),
                "fact_checking_services": list(set(
                    service for fr in fact_results for service in fr.services_used
                )),
                "verification_summary": {k: int(v) for k, v in status_counts.items()}
            })
            
            logger.info(f"Hierarchical fact-checking complete for {len(fact_results)} claims")
            
        except Exception as e:
            logger.error(f"Hierarchical fact-checking failed: {e}")
            logger.exception("Fact-checking traceback:")
            result.meta.update({
                "fact_checking_attempted": True,
                "fact_checking_error": str(e)
            })
        
        return result
    
    def extract_with_fallacy_detection(self, text: str, source: str = "unknown") -> ExtractionResult:
        """Extract claims with fallacy detection using hierarchical pipeline (reuses sentences)"""
        try:
            logger.info(f"Starting hierarchical extraction with fallacy detection for source: {source}")
            
            # Run normal extraction to get claims and sentence objects
            result, sentence_objects = self.extract(text, source)
            
            if not result.claims:
                logger.info("No claims for fallacy detection")
                return result
            
            # Run fallacy detection using the same sentence objects
            logger.debug("Running fallacy detection")
            fallacies = self._run_fallacy_detection(result.claims, sentence_objects)
            
            # Update result with fallacy data
            result.fallacy_detection_enabled = True
            result.fallacies = [f.to_dict() for f in fallacies]
            result.fallacy_summary = FallacyDetectionSummary.from_fallacies(fallacies).to_dict()
            
            result.meta.update({
                "fallacy_detection_performed": True,
                "fallacies_detected": int(len(fallacies))
            })
            
            logger.info(f"Hierarchical fallacy detection complete: {len(result.claims)} claims, {len(fallacies)} fallacies")
            return result
            
        except Exception as e:
            logger.error(f"Hierarchical fallacy detection failed: {e}")
            logger.exception("Full traceback:")
            
            return ExtractionResult(
                claims=[],
                meta={
                    "source": source,
                    "error": str(e),
                    "pipeline_failed": True,
                    "pipeline_type": "hierarchical"
                }
            )
    
    def _run_fallacy_detection(self, claims, sentences):
        """Run fallacy detection on claims and sentences"""
        if self.fallacy_detector is None:
            self.fallacy_detector = DebateFallacyDetector()
        
        fallacies = self.fallacy_detector.detect_fallacies(claims, sentences)
        
        # Update claims with fallacy information
        for claim in claims:
            claim_fallacies = [f for f in fallacies if f.target_claim_id == claim.id]
            if claim_fallacies:
                claim.fallacies = [f.to_dict() for f in claim_fallacies]
                claim.fallacy_score = sum(f.confidence for f in claim_fallacies) / len(claim_fallacies)
        
        return fallacies
    
    def _run_scoring(self, result: ExtractionResult, source: str = "unknown"):
        """Run scoring on extraction result"""
        try:
            logger.info(f"Starting scoring analysis for {len(result.claims)} claims")
            
            if self.scoring_pipeline is None:
                self.scoring_pipeline = ScoringPipeline()
            
            scoring_result = self.scoring_pipeline.score_extraction_result(result, source=source)
            
            result.scoring_enabled = True
            result.scoring_result = scoring_result.model_dump()
            
            result.meta.update({
                "scoring_performed": scoring_result.scoring_performed,
                "scoring_time_seconds": scoring_result.processing_time_seconds
            })
            
            if scoring_result.scoring_error:
                result.meta["scoring_error"] = scoring_result.scoring_error
                logger.warning(f"Scoring completed with error: {scoring_result.scoring_error}")
            else:
                logger.info(f"Scoring complete: {scoring_result.debate_score.overall_score:.3f} overall score")
                
        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            logger.exception("Scoring traceback:")
            
            result.meta.update({
                "scoring_attempted": True,
                "scoring_error": str(e)
            })
    
    def extract_with_comprehensive_analysis(self, 
                                          text: str, 
                                          source: str = "unknown",
                                          fact_config: Optional[FactCheckConfig] = None) -> ExtractionResult:
        """Extract claims with fact-checking, fallacy detection, and scoring"""
        # Start with fallacy detection (reuses sentence objects efficiently)
        result = self.extract_with_fallacy_detection(text, source)
        
        if not result.claims:
            logger.info("No claims for comprehensive analysis")
            return result
        
        # Add fact-checking if not already performed
        if not result.meta.get("fact_checking_performed"):
            try:
                logger.info(f"Adding fact-checking to {len(result.claims)} claims")
                fact_results = self._sfact_check(result.claims, fact_config)
                
                result.fact_checking_enabled = True
                result.fact_check_results = [fr.model_dump() for fr in fact_results]
                
                status_counts = Counter(fr.overall_status for fr in fact_results)
                
                result.meta.update({
                    "fact_checking_performed": True,
                    "fact_checked_claims": int(len(fact_results)),
                    "verification_summary": {k: int(v) for k, v in status_counts.items()}
                })
                
            except Exception as e:
                logger.error(f"Fact-checking in comprehensive analysis failed: {e}")
                result.meta.update({
                    "fact_checking_attempted": True,
                    "fact_checking_error": str(e)
                })
        
        # Add scoring
        self._run_scoring(result, source)
        
        return result
    
    def close(self):
        """Explicit cleanup method for production environments"""
        if self.fact_pipeline:
            try:
                asyncio.run(self.fact_pipeline.close())
            except:
                pass  # Already closed or no event loop
        
        # Clear component references
        self.fact_pipeline = None
        self.fallacy_detector = None
        self.scoring_pipeline = None
