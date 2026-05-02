#!/usr/bin/env python3
"""Automatically generate a filtered gold-claim file for a transcript."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from debate_claim_extractor.core.pipeline import ClaimExtractionPipeline, ExtractionConfig
from debate_claim_extractor.core import heuristics

BANNED_SUBSTRINGS = {
    "promo code",
    "promocode",
    "pharmacy",
    "check them out",
    "allfamilyfarm",
    "kirk10",
    "10% off",
    "ivormectin",
    "hydroxychloricquin",
    "methyline blue",
    "use promo",
    "sponsor",
    "advertise",
    "subscribe",
    "like and subscribe",
}


def should_keep(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    lowered = stripped.lower()

    if any(bad in lowered for bad in heuristics._BANNED_PHRASES):
        return False
    if any(bad in lowered for bad in BANNED_SUBSTRINGS):
        return False

    claim = heuristics.detect_claim(stripped)
    if not claim:
        return False

    words = stripped.split()
    if len(words) < 2 and stripped.lower() not in heuristics._SHORT_ASSERTIONS:
        return False

    return True


def build(transcript_path: Path, *, include_narrative: bool, limit: int | None) -> list:
    text = transcript_path.read_text()
    pipeline = ClaimExtractionPipeline(ExtractionConfig(include_narrative=include_narrative))
    result = pipeline.extract(text, debate_id=transcript_path.stem)

    seen: set[str] = set()
    kept = []
    for claim in result.claims:
        clean_text = claim.text.strip()
        key = heuristics._SHORT_NORMALISE_RE.sub(" ", clean_text.lower()).strip()
        if key in seen:
            continue
        if not should_keep(clean_text):
            continue
        seen.add(key)
        kept.append(claim)
        if limit is not None and len(kept) >= limit:
            break
    kept.sort(key=lambda c: (c.source_sentence.utterance_index, c.source_sentence.sentence_index))
    return kept


def write_gold(claims: list, destination: Path) -> None:
    lines = []
    lines.append(f"# Auto-generated gold claims for {destination.stem}")
    lines.append("")
    for idx, claim in enumerate(claims, 1):
        lines.append(f"* **Claim {idx}:** {claim.text.strip()}")
    destination.write_text("\n".join(lines) + "\n")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Transcript to process")
    parser.add_argument("output", type=Path, help="Gold file destination")
    parser.add_argument("--include-narrative", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    claims = build(
        args.input,
        include_narrative=args.include_narrative,
        limit=args.limit,
    )
    write_gold(claims, args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
