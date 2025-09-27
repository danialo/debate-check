"""Transcript preprocessing utilities."""

from __future__ import annotations

import re
from typing import Iterable, List

from .models import Utterance

_SPEAKER_LINE_RE = re.compile(r"^\s*([A-Z][A-Z0-9 .'-]{0,40})[:\-]\s*(.*)$")
_STAGE_DIRECTION_RE = re.compile(r"\s*[\[(][^\]\)]*[\])]")
_MULTISPACE_RE = re.compile(r"\s{2,}")

_TITLE_PREFIXES = {
    "MR",
    "MRS",
    "MS",
    "DR",
    "PROF",
    "SEN",
    "REP",
    "PRES",
    "GOV",
    "GOVERNOR",
    "SPEAKER",
    "CHAIR",
}

_LEADING_TITLES = {
    "CANDIDATE",
    "SPEAKER",
    "PARTICIPANT",
    "DEBATER",
    "SENATOR",
    "GOVERNOR",
    "CONGRESSMAN",
    "CONGRESSWOMAN",
    "MINISTER",
}


def _strip_stage_directions(text: str) -> str:
    return _STAGE_DIRECTION_RE.sub(" ", text)


def _collapse_whitespace(text: str) -> str:
    return _MULTISPACE_RE.sub(" ", text).strip()


def normalize_speaker(raw: str) -> str:
    """Normalise raw speaker labels to short, comparable identifiers."""

    label = raw.strip().upper()
    if not label:
        return "UNKNOWN"

    parts = [part for part in re.split(r"\s+", label) if part]
    filtered: List[str] = []
    for part in parts:
        normalized = part.rstrip('.')
        if normalized in _TITLE_PREFIXES:
            continue
        filtered.append(normalized)

    if not filtered:
        filtered = parts

    # Collapse patterns like "CANDIDATE A" → "A"
    if filtered[0] in _LEADING_TITLES and len(filtered) >= 2:
        return filtered[-1]

    if len(filtered) > 2:
        return filtered[-1]

    if len(filtered) == 2 and filtered[0] == filtered[1]:
        return filtered[0]

    return " ".join(filtered)


def parse_transcript(text: str) -> List[Utterance]:
    """Parse a raw transcript into speaker utterances."""

    lines = text.splitlines()
    has_labels = any(
        _SPEAKER_LINE_RE.match(line.strip())
        for line in lines
        if line.strip()
    )

    if not has_labels:
        return _fallback_utterances(lines)

    utterances: List[Utterance] = []
    current_speaker = "UNKNOWN"

    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        match = _SPEAKER_LINE_RE.match(stripped)
        if match:
            current_speaker = normalize_speaker(match.group(1))
            remainder = _collapse_whitespace(_strip_stage_directions(match.group(2)))
            if remainder:
                utterances.append(Utterance(current_speaker, remainder, line_number))
            continue

        cleaned = _collapse_whitespace(_strip_stage_directions(stripped))
        if not cleaned:
            continue

        if utterances and utterances[-1].speaker == current_speaker:
            utterances[-1].text = f"{utterances[-1].text} {cleaned}".strip()
        else:
            utterances.append(Utterance(current_speaker, cleaned, line_number))

    return utterances


def iter_utterance_text(utterances: Iterable[Utterance]) -> Iterable[str]:
    for utt in utterances:
        yield utt.text


def _fallback_utterances(lines: List[str]) -> List[Utterance]:
    """Build utterances when no explicit speaker labels are present."""

    utterances: List[Utterance] = []
    buffer: List[str] = []
    start_line = 1

    def flush(current_line: int) -> None:
        if not buffer:
            return
        paragraph = " ".join(buffer)
        cleaned = _collapse_whitespace(_strip_stage_directions(paragraph))
        if cleaned:
            utterances.append(Utterance("UNKNOWN", cleaned, start_line))
        buffer.clear()

    for idx, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            flush(idx)
            start_line = idx + 1
            continue
        buffer.append(raw_line.strip())

    flush(len(lines) + 1)

    return utterances
