#!/usr/bin/env python3
"""Compare extracted claim JSON against gold-standard claims."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Sequence, Tuple

THRESHOLD = 0.6


def _normalise(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(cleaned.split())


def load_predicted(path: Path) -> List[str]:
    data = json.loads(path.read_text())
    claims = data.get("claims", [])
    if not isinstance(claims, list):
        raise ValueError("Predicted JSON must contain a 'claims' list")
    texts = []
    for entry in claims:
        if isinstance(entry, dict) and "text" in entry:
            texts.append(str(entry["text"]))
    return texts


def load_gold(path: Path) -> List[str]:
    claims: List[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("* **Claim"):
            continue
        start = line.find("**Claim")
        colon = line.find(":", start)
        if colon == -1:
            continue
        claim = line[colon + 1 :].strip()
        if claim.startswith("**"):
            claim = claim[2:].strip()
        claims.append(claim)
    return claims


@dataclass
class MatchResult:
    predicted_index: int
    gold_index: int
    ratio: float
    predicted_text: str
    gold_text: str


@dataclass
class Comparison:
    matches: List[MatchResult]
    unmatched_predictions: List[Tuple[int, str]]
    unmatched_gold: List[Tuple[int, str]]


def compare(predicted: Sequence[str], gold: Sequence[str], threshold: float) -> Comparison:
    norm_pred = [_normalise(text) for text in predicted]
    norm_gold = [_normalise(text) for text in gold]

    matched_gold: set[int] = set()
    matches: List[MatchResult] = []

    for pred_idx, pred_text in enumerate(norm_pred):
        best_ratio = 0.0
        best_gold_idx = -1
        for gold_idx, gold_text in enumerate(norm_gold):
            if gold_idx in matched_gold:
                continue
            ratio = SequenceMatcher(None, pred_text, gold_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_gold_idx = gold_idx
        if best_gold_idx != -1 and best_ratio >= threshold:
            matched_gold.add(best_gold_idx)
            matches.append(
                MatchResult(
                    predicted_index=pred_idx,
                    gold_index=best_gold_idx,
                    ratio=best_ratio,
                    predicted_text=predicted[pred_idx],
                    gold_text=gold[best_gold_idx],
                )
            )

    unmatched_predictions = [
        (idx, predicted[idx])
        for idx in range(len(predicted))
        if idx not in {match.predicted_index for match in matches}
    ]
    unmatched_gold = [
        (idx, gold[idx])
        for idx in range(len(gold))
        if idx not in matched_gold
    ]
    return Comparison(matches=matches, unmatched_predictions=unmatched_predictions, unmatched_gold=unmatched_gold)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predicted", type=Path, help="Path to pipeline JSON output")
    parser.add_argument("gold", type=Path, help="Path to gold claim text file")
    parser.add_argument("--threshold", type=float, default=THRESHOLD, help="Similarity threshold (default: %(default)s)")
    args = parser.parse_args(argv)

    try:
        predicted = load_predicted(args.predicted)
        gold = load_gold(args.gold)
    except Exception as exc:  # pragma: no cover - CLI feedback
        parser.error(str(exc))

    comparison = compare(predicted, gold, args.threshold)

    matched = len(comparison.matches)
    precision = matched / len(predicted) if predicted else 0.0
    recall = matched / len(gold) if gold else 0.0

    print(f"Predicted claims: {len(predicted)}")
    print(f"Gold claims:      {len(gold)}")
    print(f"Matches:          {matched}")
    print(f"Precision:        {precision:.3f}")
    print(f"Recall:           {recall:.3f}")
    print(f"Threshold:        {args.threshold:.2f}\n")

    if comparison.matches:
        print("Matched claims:")
        for match in sorted(comparison.matches, key=lambda m: m.ratio, reverse=True):
            print(
                f"  pred#{match.predicted_index + 1:02d} ↔ gold#{match.gold_index + 1:02d} "
                f"(ratio={match.ratio:.2f})\n    P: {match.predicted_text}\n    G: {match.gold_text}\n"
            )
    else:
        print("No matches found.")

    if comparison.unmatched_predictions:
        print("Spurious predictions:")
        for idx, text in comparison.unmatched_predictions:
            print(f"  pred#{idx + 1:02d}: {text}")
        print()

    if comparison.unmatched_gold:
        print("Missed gold claims:")
        for idx, text in comparison.unmatched_gold:
            print(f"  gold#{idx + 1:02d}: {text}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
