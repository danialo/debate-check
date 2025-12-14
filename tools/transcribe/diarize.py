"""
AssemblyAI transcription with speaker diarization.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List, Optional

import requests


ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLYAI_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"


@dataclass
class SpeakerTurn:
    """A speaker turn from diarized transcript."""
    speaker: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float = 1.0
    words: List[dict] = None

    def __post_init__(self):
        if self.words is None:
            self.words = []


@dataclass
class TranscriptResult:
    """Full transcript result with diarization."""
    utterances: List[SpeakerTurn]
    full_text: str
    audio_duration_ms: int
    speaker_count: int
    language: str = "en"
    raw_response: dict = None


def _get_headers() -> dict:
    """Get API headers."""
    if not ASSEMBLYAI_API_KEY:
        raise ValueError(
            "ASSEMBLYAI_API_KEY environment variable not set. "
            "Add it to ~/.bashrc: export ASSEMBLYAI_API_KEY='your-key'"
        )
    return {"authorization": ASSEMBLYAI_API_KEY}


def _upload_audio(file_path: str) -> str:
    """Upload audio file to AssemblyAI, return upload URL."""
    headers = _get_headers()

    with open(file_path, "rb") as f:
        response = requests.post(
            ASSEMBLYAI_UPLOAD_URL,
            headers=headers,
            data=f
        )
    response.raise_for_status()
    return response.json()["upload_url"]


def _request_transcription(audio_url: str, speaker_labels: bool = True) -> str:
    """Request transcription, return transcript ID."""
    headers = _get_headers()
    headers["content-type"] = "application/json"

    payload = {
        "audio_url": audio_url,
        "speaker_labels": speaker_labels,
    }

    response = requests.post(
        ASSEMBLYAI_TRANSCRIPT_URL,
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    return response.json()["id"]


def _poll_transcript(transcript_id: str, poll_interval: float = 3.0) -> dict:
    """Poll for transcript completion."""
    headers = _get_headers()
    url = f"{ASSEMBLYAI_TRANSCRIPT_URL}/{transcript_id}"

    while True:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()

        status = result["status"]
        if status == "completed":
            return result
        elif status == "error":
            raise RuntimeError(f"Transcription failed: {result.get('error', 'Unknown error')}")

        # Still processing
        time.sleep(poll_interval)


def _parse_result(result: dict) -> TranscriptResult:
    """Parse AssemblyAI response into TranscriptResult."""
    utterances = []

    # AssemblyAI returns utterances with speaker labels
    for utt in result.get("utterances", []):
        utterances.append(SpeakerTurn(
            speaker=f"SPEAKER_{utt['speaker']}",
            text=utt["text"],
            start_ms=utt["start"],
            end_ms=utt["end"],
            confidence=utt.get("confidence", 1.0),
            words=utt.get("words", []),
        ))

    # Count unique speakers
    speakers = set(u.speaker for u in utterances)

    return TranscriptResult(
        utterances=utterances,
        full_text=result.get("text", ""),
        audio_duration_ms=result.get("audio_duration", 0) * 1000,
        speaker_count=len(speakers),
        language=result.get("language_code", "en"),
        raw_response=result,
    )


def transcribe_audio(
    file_path: str,
    speaker_labels: bool = True,
    verbose: bool = False
) -> TranscriptResult:
    """
    Transcribe a local audio file with speaker diarization.

    Args:
        file_path: Path to audio file (mp3, wav, m4a, etc.)
        speaker_labels: Enable speaker diarization
        verbose: Print progress

    Returns:
        TranscriptResult with diarized utterances
    """
    if verbose:
        print(f"Uploading {file_path}...")

    upload_url = _upload_audio(file_path)

    if verbose:
        print("Requesting transcription...")

    transcript_id = _request_transcription(upload_url, speaker_labels)

    if verbose:
        print(f"Transcription ID: {transcript_id}")
        print("Waiting for completion...")

    result = _poll_transcript(transcript_id)

    if verbose:
        print("Done!")

    return _parse_result(result)


def transcribe_url(
    audio_url: str,
    speaker_labels: bool = True,
    verbose: bool = False
) -> TranscriptResult:
    """
    Transcribe audio from a URL with speaker diarization.

    Args:
        audio_url: Direct URL to audio file
        speaker_labels: Enable speaker diarization
        verbose: Print progress

    Returns:
        TranscriptResult with diarized utterances
    """
    if verbose:
        print("Requesting transcription...")

    transcript_id = _request_transcription(audio_url, speaker_labels)

    if verbose:
        print(f"Transcription ID: {transcript_id}")
        print("Waiting for completion...")

    result = _poll_transcript(transcript_id)

    if verbose:
        print("Done!")

    return _parse_result(result)
