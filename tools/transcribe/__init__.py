"""
Debate transcription tool with speaker diarization.

Uses AssemblyAI API for transcription and speaker diarization.
"""

from .diarize import transcribe_audio, transcribe_url
from .output import to_labeled_text, to_json, to_utterances

__all__ = [
    "transcribe_audio",
    "transcribe_url",
    "to_labeled_text",
    "to_json",
    "to_utterances",
]
