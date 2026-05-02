from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

from debate_claim_extractor import ClaimExtractionPipeline, ExtractionConfig


def _normalise(text: str) -> str:
    return " ".join(
        "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text).split()
    )


def _load_gold_claims(path: Path) -> list[str]:
    claims: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("* **Claim"):
            continue
        colon = line.find(":")
        if colon == -1:
            continue
        claims.append(line[colon + 1 :].strip(" *"))
    return claims


def _count_matches(predicted: list[str], gold: list[str], threshold: float) -> tuple[int, int, int]:
    norm_pred = [_normalise(text) for text in predicted]
    norm_gold = [_normalise(text) for text in gold]

    matched_gold: set[int] = set()
    matches = 0
    for pred_text in norm_pred:
        best_ratio = 0.0
        best_idx = -1
        for idx, gold_text in enumerate(norm_gold):
            if idx in matched_gold:
                continue
            ratio = SequenceMatcher(None, pred_text, gold_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = idx
        if best_idx != -1 and best_ratio >= threshold:
            matched_gold.add(best_idx)
            matches += 1

    return matches, len(predicted), len(gold)


def test_transcript_two_alignment():
    pipeline = ClaimExtractionPipeline(ExtractionConfig(include_narrative=True))
    transcript = Path("tests/transcripts/2.txt").read_text()
    result = pipeline.extract(transcript)
    predicted = [claim.text for claim in result.claims]

    gold = _load_gold_claims(Path("tests/transcripts/2-gold.txt"))
    matches, total_predictions, total_gold = _count_matches(predicted, gold, threshold=0.35)

    precision = matches / total_predictions if total_predictions else 0.0
    recall = matches / total_gold if total_gold else 0.0

    # Allow for some paraphrasing differences but ensure we are very close to gold.
    assert recall >= 0.95, f"Recall too low: {recall:.3f}"
    assert precision >= 0.25, f"Precision too low: {precision:.3f}"
