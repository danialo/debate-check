"""
Output formatters for transcription results.
"""

from __future__ import annotations

import json
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .diarize import TranscriptResult, SpeakerTurn


def to_labeled_text(result: "TranscriptResult") -> str:
    """
    Convert to labeled text format (compatible with claim extractor).

    Output format:
        SPEAKER_A: First thing they said.
        SPEAKER_B: Response to that.
        SPEAKER_A: Follow up comment.
    """
    lines = []
    for utt in result.utterances:
        lines.append(f"{utt.speaker}: {utt.text}")
    return "\n\n".join(lines)


def to_json(result: "TranscriptResult", include_raw: bool = False) -> str:
    """
    Convert to JSON format with full metadata.

    Output includes:
        - utterances with speaker, text, timestamps
        - metadata (duration, speaker count, language)
    """
    data = {
        "metadata": {
            "audio_duration_ms": result.audio_duration_ms,
            "speaker_count": result.speaker_count,
            "language": result.language,
            "utterance_count": len(result.utterances),
        },
        "utterances": [
            {
                "speaker": utt.speaker,
                "text": utt.text,
                "start_ms": utt.start_ms,
                "end_ms": utt.end_ms,
                "confidence": utt.confidence,
            }
            for utt in result.utterances
        ],
        "full_text": result.full_text,
    }

    if include_raw:
        data["raw_response"] = result.raw_response

    return json.dumps(data, indent=2)


def to_utterances(result: "TranscriptResult") -> List[dict]:
    """
    Convert to list of utterance dicts (for programmatic use).
    """
    return [
        {
            "speaker": utt.speaker,
            "text": utt.text,
            "start_ms": utt.start_ms,
            "end_ms": utt.end_ms,
        }
        for utt in result.utterances
    ]


def to_srt(result: "TranscriptResult") -> str:
    """
    Convert to SRT subtitle format.
    """
    def ms_to_srt_time(ms: int) -> str:
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    lines = []
    for i, utt in enumerate(result.utterances, 1):
        lines.append(str(i))
        lines.append(f"{ms_to_srt_time(utt.start_ms)} --> {ms_to_srt_time(utt.end_ms)}")
        lines.append(f"[{utt.speaker}] {utt.text}")
        lines.append("")

    return "\n".join(lines)
