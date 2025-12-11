"""Claim extraction methods."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..canonicalize import claim_dedup_key
from ..registry import method
from ..result import OperatorResult, OperatorStatus
from ..task import Task
from .base import BaseMethod

if TYPE_CHECKING:
    from ...state.discourse import DiscourseState


@method(name="ExtractClaimsFromSegment", task="EXTRACT_CLAIMS_FROM_SEGMENT", base_cost=5.0)
class ExtractClaimsFromSegment(BaseMethod):
    """Extract claims from a text segment using heuristics."""

    # Patterns that indicate factual claims
    CLAIM_INDICATORS = [
        r"\b\d+%",  # Percentages
        r"\b\d{4}\b",  # Years
        r"\b\d+\s*(milliseconds?|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",  # Quantities with units
        r"\b\d+\s*(percent|million|billion|thousand)\b",  # Numeric quantities
        r"\bstud(?:y|ies)\b",  # Studies
        r"\bresearch\b",
        r"\bdata\b",
        r"\bevidence\b",
        r"\bshows?\b",
        r"\bproves?\b",
        r"\bdemonstrates?\b",
        r"\bfound\b",
        r"\bmeasured?\b",
        r"\bprecedes?\b",  # Temporal relationships (common in empirical claims)
        r"\bcauses?\b",  # Causal relationships
        r"\baffects?\b",  # Effects
    ]

    # Sentence boundary pattern
    SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        text = task.params.get("text", "")
        return len(text.strip()) > 10

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        """Split segment into sentences and create extraction tasks."""
        text = task.params["text"]
        speaker = task.params.get("speaker", "UNKNOWN")
        use_llm = task.params.get("use_llm", False)
        base_offset = task.span[0]

        # Split into sentences
        sentences = self._split_sentences(text)

        subtasks = []
        current_pos = 0

        for sentence in sentences:
            # Find sentence position in original text
            sent_start = text.find(sentence, current_pos)
            if sent_start == -1:
                sent_start = current_pos

            sent_end = sent_start + len(sentence)
            current_pos = sent_end

            # Calculate absolute span
            abs_start = base_offset + sent_start
            abs_end = base_offset + sent_end

            # Check if this sentence likely contains a claim
            if self._looks_like_claim(sentence):
                subtasks.append(
                    Task.create(
                        task_type="EXTRACT_ATOMIC_CLAIM",
                        params={
                            "text": sentence.strip(),
                            "speaker": speaker,
                            "use_llm": use_llm,
                        },
                        span=(abs_start, abs_end),
                        parent=task,
                    )
                )

        return subtasks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        sentences = self.SENTENCE_SPLIT.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _looks_like_claim(self, text: str) -> bool:
        """Check if text looks like it contains a factual claim."""
        text_lower = text.lower()

        # Check for claim indicators
        for pattern in self.CLAIM_INDICATORS:
            if re.search(pattern, text_lower):
                return True

        # Minimum length check
        words = text.split()
        if len(words) < 5:
            return False

        # Check for declarative structure (contains common claim verbs)
        claim_verbs = ["is", "are", "was", "were", "has", "have", "shows", "proves"]
        for verb in claim_verbs:
            if f" {verb} " in text_lower:
                return True

        return False


@method(name="ExtractAtomicClaim", task="EXTRACT_ATOMIC_CLAIM", base_cost=3.0)
class ExtractAtomicClaim(BaseMethod):
    """Primitive: extract a single atomic claim."""

    def preconditions(self, state: "DiscourseState", task: Task) -> bool:
        text = task.params.get("text", "")
        return len(text.strip()) > 5

    def decompose(self, state: "DiscourseState", task: Task) -> list[Task]:
        return []  # Primitive

    def execute(self, state: "DiscourseState", task: Task) -> OperatorResult:
        from ...artifacts.claim import AtomicClaim, ClaimType
        from ...state.entity import Entity

        text = task.params["text"].strip()
        speaker = task.params.get("speaker")
        use_llm = task.params.get("use_llm", False)

        # Classify claim type (heuristic first)
        claim_type, confidence, reasons = self._classify_claim(text)

        # Try LLM classification if available, enabled, and within budget
        llm_used = False
        llm_budget_ok = (
            not hasattr(state, 'llm_budget') or
            state.llm_calls < state.llm_budget
        )
        if use_llm and state.llm_client is not None and llm_budget_ok:
            try:
                llm_result = state.llm_client.classify_claim(text)
                state.llm_calls += 1
                if llm_result and "claim_type" in llm_result:
                    type_str = llm_result["claim_type"].upper()
                    try:
                        claim_type = ClaimType[type_str]
                        confidence = llm_result.get("confidence", 0.85)
                        reasons = [f"LLM classification: {llm_result.get('reasoning', 'no reason')}"]
                        llm_used = True
                    except KeyError:
                        pass  # Unknown type, keep heuristic result
            except Exception:
                pass  # LLM failed, keep heuristic result

        # Create claim artifact
        claim = AtomicClaim(
            artifact_id=f"claim_{claim_dedup_key(text, task.span)}",
            text=text,
            claim_type=claim_type,
            confidence=confidence,
            confidence_reasons=reasons,
            method_path=state.get_method_path(task.task_id),
            speaker=speaker,
            scope_id=state.current_scope_id,
            span=task.span,
            parent_artifact_id=task.params.get("parent_artifact_id"),
            created_by_task=task.task_id,
            created_by_method=self._method_name,
        )

        # Emit artifact
        state.emit_artifact(claim)

        # Link claim to current frame (if any)
        frame_id = getattr(state, "_current_frame_id", None)
        if frame_id:
            from ...artifacts.frame import ArgumentFrame
            frame = state.get_artifact(frame_id)
            if frame and isinstance(frame, ArgumentFrame):
                if claim.artifact_id not in frame.child_claim_ids:
                    frame.child_claim_ids.append(claim.artifact_id)

        # Register claim as entity for demonstrative resolution ("this", "that")
        # Use the claim text (truncated) as the canonical name
        canonical = text[:50] + "..." if len(text) > 50 else text
        claim_entity = Entity(
            entity_id="",
            canonical=canonical,
            aliases=set(),
            entity_type="CLAIM",
            first_mention_span=task.span,
            introducing_speaker=speaker,
            mention_spans=[task.span],
        )
        entity_id = state.register_entity(claim_entity)
        state.boost_salience(entity_id)

        mutations = [f"Emitted claim: {text[:50]}...", f"Registered as entity {entity_id}"]
        if frame_id:
            mutations.append(f"Linked to frame {frame_id}")

        return OperatorResult(
            status=OperatorStatus.SUCCESS,
            artifacts_emitted=[claim.artifact_id],
            state_mutations=mutations,
        )

    def _classify_claim(
        self, text: str
    ) -> tuple["ClaimType", float, list[str]]:
        """Classify claim type based on content."""
        from ...artifacts.claim import ClaimType

        text_lower = text.lower()
        reasons = []

        # Check for statistical claims
        if re.search(r"\b\d+%|\b\d+\s*(percent|million|billion|thousand)", text_lower):
            reasons.append("contains numeric/statistical data")
            return ClaimType.EMPIRICAL, 0.85, reasons

        # Check for methodological claims
        if any(
            word in text_lower
            for word in ["methodology", "sample", "controlled", "experiment", "study design"]
        ):
            reasons.append("contains methodology keywords")
            return ClaimType.METHODOLOGICAL, 0.8, reasons

        # Check for empirical claims
        if any(
            word in text_lower
            for word in ["study", "research", "data", "evidence", "found", "measured"]
        ):
            reasons.append("contains empirical keywords")
            return ClaimType.EMPIRICAL, 0.75, reasons

        # Check for normative claims
        if any(word in text_lower for word in ["should", "ought", "must", "wrong", "right"]):
            reasons.append("contains normative language")
            return ClaimType.NORMATIVE, 0.8, reasons

        # Check for philosophical claims
        if any(
            word in text_lower
            for word in ["free will", "consciousness", "determinism", "existence", "meaning"]
        ):
            reasons.append("contains philosophical keywords")
            return ClaimType.PHILOSOPHICAL, 0.85, reasons

        # Check for introspective claims
        if re.search(r"^i (think|believe|feel|know)", text_lower):
            reasons.append("first-person mental state")
            return ClaimType.INTROSPECTIVE, 0.9, reasons

        # Check for predictive claims
        if any(word in text_lower for word in ["will", "going to", "might", "probably"]):
            reasons.append("contains predictive language")
            return ClaimType.PREDICTIVE, 0.7, reasons

        # Default to unclassified
        reasons.append("no strong pattern match")
        return ClaimType.UNCLASSIFIED, 0.3, reasons
