"""Command line entry-point for debate claim extraction using HTN planner."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Optional, TextIO

import click

from .htn import HTNPlanner, Task
from .htn.planner import PlannerConfig
from .state import DiscourseState, SpeakerTurn
from .core.preprocess import parse_transcript
from .artifacts import AtomicClaim, ArgumentFrame, FactCheckResult

logger = logging.getLogger("debate_claim_extractor.cli")


def _parse_transcript_to_turns(text: str) -> list[SpeakerTurn]:
    """Parse raw transcript text into speaker turns."""
    # Try to parse structured transcript
    utterances = parse_transcript(text)

    if utterances:
        turns = []
        offset = 0
        for i, utt in enumerate(utterances):
            turn = SpeakerTurn(
                speaker=utt.speaker,
                text=utt.text,
                span=(offset, offset + len(utt.text)),
                turn_index=i,
            )
            turns.append(turn)
            offset += len(utt.text) + 2  # Account for newlines
        return turns

    # Fallback: treat entire text as single turn
    return [
        SpeakerTurn(
            speaker="UNKNOWN",
            text=text.strip(),
            span=(0, len(text.strip())),
            turn_index=0,
        )
    ]


def _format_output(result, state: DiscourseState) -> dict:
    """Format planner result for JSON output."""
    # Extract claims
    claims = []
    for claim in result.claims:
        claims.append({
            "id": claim.artifact_id,
            "text": claim.text,
            "claim_type": claim.claim_type.value if hasattr(claim.claim_type, 'value') else str(claim.claim_type),
            "speaker": claim.speaker,
            "confidence": claim.confidence,
            "span": list(claim.span) if claim.span else None,
        })

    # Extract frames
    frames = []
    for frame in result.frames:
        frames.append({
            "id": frame.artifact_id,
            "frame_type": frame.frame_type,
            "speaker": frame.speaker,
            "summary": frame.summary,
            "child_claims": frame.child_claim_ids,
            "parent_frame": frame.parent_frame_id,
        })

    # Extract fact-checks
    fact_checks = []
    for artifact in result.artifacts:
        if isinstance(artifact, FactCheckResult):
            fact_checks.append({
                "claim_id": artifact.claim_id,
                "status": artifact.status.value if hasattr(artifact.status, 'value') else str(artifact.status),
                "confidence": artifact.confidence,
                "summary": artifact.summary,
                "sources": artifact.sources,
            })

    # Stats
    stats = {
        "tasks_executed": result.stats.tasks_executed,
        "elapsed_ms": result.stats.elapsed_ms,
        "claims_count": len(claims),
        "frames_count": len(frames),
        "fact_checks_count": len(fact_checks),
    }

    if result.stats.llm_calls > 0:
        stats["llm_calls"] = result.stats.llm_calls

    return {
        "claims": claims,
        "frames": frames,
        "fact_checks": fact_checks,
        "stats": stats,
    }


@click.command()
@click.option("--input", "-i", type=click.File("r"), default="-", help="Transcript file path (defaults to stdin)")
@click.option("--output", "-o", type=click.File("w"), default="-", help="Output destination (defaults to stdout)")
@click.option("--fact-check", is_flag=True, help="Enable fact-checking for empirical claims")
@click.option("--use-llm", is_flag=True, help="Enable LLM-assisted claim classification")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(
    input: TextIO,
    output: TextIO,
    fact_check: bool,
    use_llm: bool,
    verbose: bool,
) -> None:
    """Extract claims from a debate transcript using HTN planning."""

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    transcript = input.read()
    if not transcript.strip():
        raise click.ClickException("No transcript text supplied")

    # Parse transcript into turns
    turns = _parse_transcript_to_turns(transcript)

    if verbose:
        logger.info(f"Parsed {len(turns)} speaker turns")

    # Create discourse state
    state = DiscourseState.from_transcript(
        transcript_id="cli_extraction",
        transcript_text=transcript,
        turns=turns,
    )

    # Configure and run planner
    planner = HTNPlanner()

    # Create root task with options
    root_task = Task.create(
        task_type="DECOMPOSE_TRANSCRIPT",
        params={
            "use_llm": use_llm,
            "fact_check": fact_check,
        },
        span=(0, len(transcript)),
    )

    result = planner.run(root_task, state)

    if verbose:
        logger.info(f"Extracted {len(result.claims)} claims in {result.stats.elapsed_ms}ms")

    # Format and output
    output_data = _format_output(result, state)
    json.dump(output_data, output, indent=2)
    output.write("\n")


if __name__ == "__main__":  # pragma: no cover
    main()
