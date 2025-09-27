"""Lightweight heuristic claim detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_NUMBER_RE = re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b")
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?%\b")
_YEAR_RE = re.compile(r"\b(18|19|20|21)\d{2}\b")
_COMPARATIVE_TERMS = (
    " more than ",
    " less than ",
    " better than ",
    " worse than ",
    " higher than ",
    " lower than ",
    " greater than ",
    " smaller than ",
    " compared to ",
    " compared with ",
)
_CAUSAL_TERMS = (
    " because ",
    " due to ",
    " leads to ",
    " results in ",
    " caused by ",
    " as a result ",
)

_FILLER_LEADS = {
    "uh",
    "um",
    "well",
    "so",
    "like",
    "anyway",
    "okay",
    "alright",
    "hmm",
    "hm",
    "yeah",
}

_DISCOURSE_STOPWORDS = {
    "just",
    "really",
    "kind",
    "sort",
    "maybe",
    "actually",
    "literally",
    "stuff",
    "things",
    "thing",
    "people",
    "right",
    "left",
    "like",
    "you",
    "know",
}

_CLAIM_VERBS = {
    "is",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "does",
    "do",
    "did",
    "can",
    "cannot",
    "will",
    "should",
    "must",
    "provides",
    "shows",
    "reports",
    "claims",
    "says",
    "states",
    "contains",
    "creates",
    "reduces",
    "increases",
    "decreases",
    "leads",
    "causes",
}


@dataclass(slots=True)
class HeuristicClaim:
    text: str
    claim_type: str
    confidence: float
    rationale: str


def sentence_tokenise(text: str) -> List[tuple[str, int, int]]:
    """Split text into sentences and return (sentence, start, end)."""

    spans: List[tuple[str, int, int]] = []
    start = 0
    for match in _SENTENCE_BOUNDARY_RE.finditer(text):
        end = match.start()
        segment = text[start:end].strip()
        if segment:
            spans.append((segment, start, end))
        start = match.end()
    tail = text[start:].strip()
    if tail:
        spans.append((tail, start, len(text)))
    return spans


def detect_claim(sentence: str) -> Optional[HeuristicClaim]:
    """Return a heuristic claim classification for a sentence."""

    cleaned = sentence.strip()
    if not cleaned:
        return None

    if cleaned.endswith("?"):
        return None

    lowered = f" {cleaned.lower()} "
    word_count = len(cleaned.split())

    if word_count < 5 and not _NUMBER_RE.search(cleaned):
        return None

    tokens = re.findall(r"[A-Za-z']+", cleaned.lower())
    if not tokens:
        return None

    if tokens[0] in _FILLER_LEADS and len(tokens) < 12:
        return None

    content = [tok for tok in tokens if len(tok) > 4 and tok not in _DISCOURSE_STOPWORDS]
    if len(content) < 2 and not (_NUMBER_RE.search(cleaned) or _PERCENT_RE.search(cleaned) or _YEAR_RE.search(cleaned)):
        return None

    if _PERCENT_RE.search(cleaned) or _NUMBER_RE.search(cleaned):
        return HeuristicClaim(cleaned, "statistical", 0.85, "numeric evidence detected")

    if any(term in lowered for term in _COMPARATIVE_TERMS):
        return HeuristicClaim(cleaned, "comparative", 0.8, "comparative phrase detected")

    if any(term in lowered for term in _CAUSAL_TERMS):
        return HeuristicClaim(cleaned, "causal", 0.75, "causal connective detected")

    if _YEAR_RE.search(cleaned):
        return HeuristicClaim(cleaned, "historical", 0.7, "year reference detected")

    if word_count >= 7 and any(tok in _CLAIM_VERBS for tok in tokens):
        return HeuristicClaim(cleaned, "factual", 0.6, "default factual statement")

    return None


def heuristically_extract_claims(sentences: Iterable[str]) -> List[HeuristicClaim]:
    claims: List[HeuristicClaim] = []
    for sentence in sentences:
        claim = detect_claim(sentence)
        if claim:
            claims.append(claim)
    return claims
