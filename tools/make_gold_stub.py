#!/usr/bin/env python3
"""Generate a Markdown skeleton of claims for manual gold-label editing."""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
import sys
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from debate_claim_extractor.core.pipeline import ClaimExtractionPipeline, ExtractionConfig


def _normalise(text: str) -> str:
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
    )


def build_stub(
    transcript_path: Path,
    *,
    include_narrative: bool,
    limit: int | None,
) -> str:
    text = transcript_path.read_text()

    pipeline = ClaimExtractionPipeline(
        ExtractionConfig(include_narrative=include_narrative)
    )
    result = pipeline.extract(text, debate_id=transcript_path.stem)

    seen: set[str] = set()
    selected: list = []

    for claim in result.claims:
        key = _normalise(claim.text)
        if not key or key in seen:
            continue
        seen.add(key)
        selected.append(claim)
        if limit is not None and len(selected) >= limit:
            break

    lines: list[str] = []
    lines.append(f"<!-- Auto-generated claim stub for {transcript_path.name} -->")
    lines.append("<!-- Review, edit, delete, or reorder claims as needed. -->")
    lines.append("")

    for idx, claim in enumerate(selected, 1):
        lines.append(f"* **Claim {idx}:** {claim.text.strip()}")
        meta = textwrap.dedent(
            f"""
              - speaker: {claim.speaker or 'UNKNOWN'}
              - confidence: {claim.confidence:.2f} (origin={claim.origin})
              - indices: utterance={claim.source_sentence.utterance_index}, sentence={claim.source_sentence.sentence_index}
            """
        ).strip()
        for meta_line in meta.splitlines():
            lines.append(meta_line)
        lines.append("")

    if not selected:
        lines.append("<!-- No claims detected; pipeline may have filtered everything. -->")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Transcript to analyse")
    parser.add_argument("output", type=Path, help="Destination Markdown file")
    parser.add_argument(
        "--include-narrative",
        action="store_true",
        help="Include narrative claims (default: empirical only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unique claims to emit",
    )
    args = parser.parse_args(argv)

    stub = build_stub(
        args.input,
        include_narrative=args.include_narrative,
        limit=args.limit,
    )
    args.output.write_text(stub)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
