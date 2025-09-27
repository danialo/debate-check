"""Command line entry-point for the new claim extractor."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, TextIO

import click

from .core.llm import LLMClaim, OpenAILLMClient, StaticLLMClient
from .core.pipeline import ClaimExtractionPipeline, ExtractionConfig

logger = logging.getLogger("debate_claim_extractor.cli")


def _load_llm_client(mapping_path: Path) -> StaticLLMClient:
    data = json.loads(mapping_path.read_text())
    responses = {}
    for block, claim_list in data.items():
        items = []
        for entry in claim_list:
            if "text" not in entry:
                continue
            items.append(
                LLMClaim(
                    text=str(entry["text"]),
                    speaker=entry.get("speaker"),
                    claim_type=entry.get("type"),
                    confidence=float(entry.get("confidence", 0.9)),
                    metadata={k: str(v) for k, v in entry.items() if k not in {"text", "speaker", "type", "confidence"}},
                )
            )
        responses[block.strip()] = items
    return StaticLLMClient(responses)


@click.command()
@click.option("--input", "-i", type=click.File("r"), default="-", help="Transcript file path (defaults to stdin)")
@click.option("--output", "-o", type=click.File("w"), default="-", help="Output destination (defaults to stdout)")
@click.option("--use-llm", is_flag=True, help="Enable LLM-assisted claim extraction via OpenAI")
@click.option("--llm-json", type=click.Path(exists=True), help="If provided, use static JSON responses instead of calling an API")
@click.option("--llm-model", default="gpt-4o-mini", show_default=True, help="OpenAI model to use when --use-llm is enabled")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(input: TextIO, output: TextIO, use_llm: bool, llm_json: Optional[str], llm_model: str, verbose: bool) -> None:
    """Extract canonical claims from a debate transcript."""

    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    transcript = input.read()
    if not transcript.strip():
        raise click.ClickException("No transcript text supplied")

    config = ExtractionConfig()
    if use_llm:
        config.use_llm = True
        if llm_json:
            config.llm_client = _load_llm_client(Path(llm_json))
        else:
            try:
                config.llm_client = OpenAILLMClient(model=llm_model)
            except RuntimeError as exc:
                raise click.ClickException(str(exc)) from exc

    pipeline = ClaimExtractionPipeline(config)
    result = pipeline.extract(transcript)

    json.dump(result.summary(), output, indent=2)
    output.write("\n")


if __name__ == "__main__":  # pragma: no cover
    main()
