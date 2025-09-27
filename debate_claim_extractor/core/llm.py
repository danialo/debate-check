"""Interfaces for optional LLM-assisted extraction."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMClaim:
    text: str
    speaker: Optional[str] = None
    claim_type: Optional[str] = None
    confidence: float = 0.9
    metadata: Dict[str, str] = None

    def normalised_text(self) -> str:
        return " ".join(self.text.lower().split())


class LLMClient(Protocol):
    """Protocol for pluggable LLM backends."""

    def extract_claims(self, block: str, speaker: str, *, context: Optional[Dict[str, str]] = None) -> List[LLMClaim]:
        ...


class StaticLLMClient:
    """Simple in-memory implementation for tests and offline usage."""

    def __init__(self, responses: Dict[str, Iterable[LLMClaim]]):
        self._responses = responses

    def extract_claims(self, block: str, speaker: str, *, context: Optional[Dict[str, str]] = None) -> List[LLMClaim]:
        key = block.strip()
        if key in self._responses:
            return list(self._responses[key])
        for pattern, claims in self._responses.items():
            if pattern.lower() in key.lower():
                return list(claims)
        return []


def parse_json_claims(raw_response: str) -> List[LLMClaim]:
    """Parse a JSON array into :class:`LLMClaim` objects.

    Expected format:
        [
            {"text": "...", "type": "factual", "confidence": 0.9}
        ]
    """

    data = raw_response.strip()
    if data.startswith("```"):
        data = data.strip("`").lstrip("json").strip()

    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        start = data.find("[")
        end = data.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                payload = json.loads(data[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ValueError("LLM response is not valid JSON") from exc
        else:
            raise ValueError("LLM response is not valid JSON")

    if not isinstance(payload, list):
        raise ValueError("LLM response must be a list of claim objects")

    claims: List[LLMClaim] = []
    for item in payload:
        if not isinstance(item, dict) or "text" not in item:
            continue
        metadata = {
            key: (item[key] if key == "evidence" else str(item[key]))
            for key in item
            if key not in {"text", "speaker", "type", "confidence"}
        }
        claims.append(
            LLMClaim(
                text=str(item["text"]).strip(),
                speaker=item.get("speaker"),
                claim_type=item.get("type"),
                confidence=float(item.get("confidence", 0.9)),
                metadata=metadata,
            )
        )
    return claims


class OpenAILLMClient:
    """Routes claim extraction prompts to the OpenAI API."""

    def __init__(self, model: str = "gpt-4o-mini", *, api_key: Optional[str] = None, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self._client = self._build_client(api_key)

    def _build_client(self, api_key: Optional[str]):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Install the 'openai' package to enable OpenAI-backed extraction.") from exc
        return OpenAI(api_key=key)

    def extract_claims(self, block: str, speaker: str, *, context: Optional[Dict[str, str]] = None) -> List[LLMClaim]:
        prompt = _build_prompt(block, speaker)
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You convert debate speeches into fact-checkable claims. "
                        "Always respond with a JSON array.")
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content if response.choices else "[]"
        # Debug logging for inspection
        logger.debug("OpenAI response: %s", content)
        parsed = parse_json_claims(content or "[]")
        cleaned: List[LLMClaim] = []
        seen = set()
        for claim in parsed:
            normal = claim.normalised_text()
            if not normal or normal in seen:
                continue
            seen.add(normal)
            cleaned.append(claim)
        return cleaned


def _build_prompt(enumerated_sentences: str, speaker: str) -> str:
    return (
        "You are given numbered sentences from a speech. Identify the sentences that contain factual, statistical, causal, comparative, or historical claims suitable for fact-checking.\n"
        "Respond with a JSON array. Each element must include: 'text' (the claim as written), 'type' (factual, statistical, causal, comparative, historical), 'confidence' (0-1), and 'evidence' describing the specific words or numbers in the sentence that justify treating it as a claim.\n"
        "Ignore subjective opinions or vague statements that lack concrete evidence.\n"
        "Use only the content of the numbered sentences—do not invent new wording. If no sentences contain fact-checkable claims, return [].\n"
        f"Speaker: {speaker or 'UNKNOWN'}\n"
        "Sentences:\n"
        f"{enumerated_sentences}"
    )
