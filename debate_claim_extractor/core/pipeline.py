"""New claim extraction pipeline with optional LLM assistance."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from uuid import uuid4

from . import heuristics
from .llm import LLMClient, LLMClaim
from .models import Claim, ClaimCategory, ClaimType, ExtractionResult, Sentence, Utterance
from .preprocess import parse_transcript


@dataclass(slots=True)
class ExtractionConfig:
    use_llm: bool = False
    llm_client: Optional[LLMClient] = None
    llm_context_window: int = 3  # sentences per prompt
    include_narrative: bool = False


class ClaimExtractionPipeline:
    """High-level orchestrator for transcript -> claims."""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()

    def extract(self, text: str, *, debate_id: Optional[str] = None) -> ExtractionResult:
        utterances = parse_transcript(text)
        sentences = self._build_sentences(utterances)

        heuristic_claims = self._run_heuristics(sentences)
        llm_claims: List[Claim] = []
        if self.config.use_llm and self.config.llm_client:
            llm_claims = self._run_llm(utterances, sentences)

        combined = self._dedupe_claims(heuristic_claims + llm_claims)
        combined.sort(key=lambda claim: claim.confidence, reverse=True)

        diagnostics = {
            "utterances": len(utterances),
            "sentences": len(sentences),
            "heuristic_candidates": len(heuristic_claims),
            "llm_candidates": len(llm_claims),
            "debate_id": debate_id,
        }

        return ExtractionResult(combined, transcript_characters=len(text), diagnostics=diagnostics)

    # ------------------------------------------------------------------
    # Internal helpers

    def _build_sentences(self, utterances: List[Utterance]) -> List[Sentence]:
        sentences: List[Sentence] = []
        for utter_idx, utterance in enumerate(utterances):
            speech_id = str(uuid4())
            for sent_idx, (sentence_text, start, end) in enumerate(heuristics.sentence_tokenise(utterance.text)):
                sentences.append(
                    Sentence(
                        speech_id=speech_id,
                        speaker=utterance.speaker,
                        text=sentence_text,
                        utterance_index=utter_idx,
                        sentence_index=sent_idx,
                        start_char=start,
                        end_char=end,
                    )
                )
        return sentences

    def _run_heuristics(self, sentences: List[Sentence]) -> List[Claim]:
        claims: List[Claim] = []
        for sentence in sentences:
            heuristic_claim = heuristics.detect_claim(sentence.text)
            if not heuristic_claim:
                continue
            metadata = {"rationale": heuristic_claim.rationale}
            category = _classify_heuristic_category(heuristic_claim)
            if category is ClaimCategory.NARRATIVE:
                metadata["anchor_level"] = "soft"
            if not self.config.include_narrative and category is not ClaimCategory.EMPIRICAL:
                continue
            claims.append(
                Claim(
                    text=heuristic_claim.text,
                    speaker=sentence.speaker,
                    claim_type=ClaimType(heuristic_claim.claim_type),
                    category=category,
                    confidence=heuristic_claim.confidence,
                    source_sentence=sentence,
                    origin="heuristic",
                    metadata=metadata,
                )
            )
        return claims

    def _run_llm(self, utterances: List[Utterance], sentences: List[Sentence]) -> List[Claim]:
        claims: List[Claim] = []
        sentences_by_utterance: Dict[int, List[Sentence]] = {}
        for sentence in sentences:
            sentences_by_utterance.setdefault(sentence.utterance_index, []).append(sentence)

        for utter_idx, utterance in enumerate(utterances):
            candidate_sentences = [
                sentence
                for sentence in sentences_by_utterance.get(utter_idx, [])
                if heuristics.detect_claim(sentence.text)
            ]
            if not candidate_sentences:
                continue

            enumerated = "\n".join(
                f"{idx + 1}. {sentence.text.strip()}"
                for idx, sentence in enumerate(candidate_sentences)
            )

            response_claims = self.config.llm_client.extract_claims(
                enumerated,
                utterance.speaker,
                context={"utterance_index": str(utter_idx)}
            )
            if not response_claims:
                continue
            for idx, llm_claim in enumerate(response_claims):
                text = llm_claim.text.strip()
                if not text:
                    continue
                if llm_claim.claim_type is None:
                    claim_type_enum = self._infer_type(text)
                else:
                    try:
                        claim_type_enum = ClaimType(llm_claim.claim_type)
                    except ValueError:
                        claim_type_enum = self._infer_type(text)
                metadata = dict(llm_claim.metadata or {})
                soft = False
                evidence = metadata.get("evidence", "")
                anchors = _has_anchors(text, evidence)
                if claim_type_enum is ClaimType.FACTUAL and not anchors:
                    metadata["anchor_level"] = "soft"
                    soft = True
                category = ClaimCategory.EMPIRICAL if claim_type_enum is not ClaimType.FACTUAL or anchors else ClaimCategory.NARRATIVE
                if not self.config.include_narrative and category is not ClaimCategory.EMPIRICAL:
                    continue
                target_sentence = self._locate_sentence(text, candidate_sentences)
                if not target_sentence:
                    target_sentence = Sentence(
                        speech_id=str(uuid4()),
                        speaker=llm_claim.speaker or utterance.speaker,
                        text=text,
                        utterance_index=utter_idx,
                        sentence_index=0,
                        start_char=0,
                        end_char=len(text),
                    )
                claims.append(
                    Claim(
                        text=text,
                        speaker=llm_claim.speaker or utterance.speaker,
                        claim_type=claim_type_enum,
                        category=category,
                        confidence=min(max(llm_claim.confidence, 0.0), 1.0),
                        source_sentence=target_sentence,
                        origin="llm",
                        metadata=metadata,
                    )
                )
        return claims

    def _locate_sentence(self, claim_text: str, sentences: List[Sentence]) -> Optional[Sentence]:
        lowered = claim_text.lower()
        for sentence in sentences:
            if lowered in sentence.text.lower():
                return sentence
        return sentences[0] if sentences else None

    def _infer_type(self, text: str) -> ClaimType:
        detected = heuristics.detect_claim(text)
        if detected:
            return ClaimType(detected.claim_type)
        return ClaimType.FACTUAL

    def _dedupe_claims(self, claims: List[Claim]) -> List[Claim]:
        deduped: Dict[str, Claim] = {}
        for claim in claims:
            key = _normalise_claim(claim.text)
            if not key:
                continue
            existing = deduped.get(key)
            if not existing or claim.confidence > existing.confidence:
                deduped[key] = claim
        return list(deduped.values())


def _normalise_claim(text: str) -> str:
    collapsed = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(collapsed.split())


def _has_anchors(text: str, evidence: str) -> bool:
    combined = f"{text} {evidence}".lower()
    if heuristics._NUMBER_RE.search(combined):  # type: ignore[attr-defined]
        return True
    if heuristics._PERCENT_RE.search(combined):  # type: ignore[attr-defined]
        return True
    if heuristics._YEAR_RE.search(combined):  # type: ignore[attr-defined]
        return True
    keywords = {
        "percent",
        "percentage",
        "million",
        "billion",
        "increase",
        "decrease",
        "rate",
        "poll",
        "cost",
        "costs",
        "tax",
        "taxes",
    }
    if any(word in combined for word in keywords):
        return True
    return False


def _classify_heuristic_category(heuristic_claim: heuristics.HeuristicClaim) -> ClaimCategory:
    claim_type = heuristic_claim.claim_type
    if claim_type != "factual":
        return ClaimCategory.EMPIRICAL
    if heuristic_claim.rationale == "numeric evidence detected":
        return ClaimCategory.EMPIRICAL
    return ClaimCategory.NARRATIVE
