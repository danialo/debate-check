"""
Audio extraction utilities (YouTube, local files).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


def _get_ytdlp_path() -> str:
    """Get path to yt-dlp, preferring venv version."""
    # Check venv bin directory first
    venv_ytdlp = Path(sys.executable).parent / "yt-dlp"
    if venv_ytdlp.exists():
        return str(venv_ytdlp)

    # Fall back to system PATH
    system_ytdlp = shutil.which("yt-dlp")
    if system_ytdlp:
        return system_ytdlp

    raise FileNotFoundError(
        "yt-dlp not found. Install with: pip install yt-dlp"
    )


def extract_youtube_audio(
    url: str,
    output_path: Optional[str] = None,
    format: str = "mp3",
    verbose: bool = False
) -> str:
    """
    Extract audio from YouTube video using yt-dlp.

    Args:
        url: YouTube URL
        output_path: Output file path (auto-generated if None)
        format: Audio format (mp3, m4a, wav)
        verbose: Print progress

    Returns:
        Path to extracted audio file
    """
    if output_path is None:
        # Create temp file
        fd, output_path = tempfile.mkstemp(suffix=f".{format}")
        os.close(fd)

    # yt-dlp command
    cmd = [
        _get_ytdlp_path(),
        "-x",  # Extract audio
        "--audio-format", format,
        "--audio-quality", "0",  # Best quality
        "-o", output_path,
        "--no-playlist",  # Single video only
    ]

    if not verbose:
        cmd.append("--quiet")

    cmd.append(url)

    if verbose:
        print(f"Extracting audio from: {url}")
        print(f"Output: {output_path}")

    result = subprocess.run(cmd, capture_output=not verbose, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed: {result.stderr if not verbose else 'see output above'}"
        )

    # yt-dlp may add extension, find the actual file
    base = Path(output_path).stem
    parent = Path(output_path).parent
    for ext in [format, "mp3", "m4a", "webm", "opus"]:
        candidate = parent / f"{base}.{ext}"
        if candidate.exists():
            return str(candidate)

    # Fallback: return original path
    if Path(output_path).exists():
        return output_path

    raise FileNotFoundError(f"Could not find extracted audio file: {output_path}")


def get_audio_duration(file_path: str) -> float:
    """
    Get audio duration in seconds using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    return float(result.stdout.strip())


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL."""
    youtube_patterns = [
        "youtube.com/watch",
        "youtu.be/",
        "youtube.com/v/",
        "youtube.com/embed/",
    ]
    return any(p in url for p in youtube_patterns)
