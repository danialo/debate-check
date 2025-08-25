#!/usr/bin/env python3
"""
YouTube Video to Debate Claims Pipeline
Phase 2 Enhancement: Audio-based speaker diarization
"""

import subprocess
import tempfile
import json
from pathlib import Path


def download_youtube_audio(url: str, output_path: str) -> bool:
    """Download audio from YouTube video"""
    try:
        cmd = [
            "yt-dlp", 
            url,
            "-x",  # Extract audio only
            "--audio-format", "wav",
            "-o", output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to download audio: {e}")
        return False


def process_youtube_video(url: str) -> dict:
    """
    Complete pipeline: YouTube URL -> Claims
    
    Future implementation will use:
    1. yt-dlp for audio extraction
    2. whisperx for transcription + speaker diarization
    3. Our existing claim extraction pipeline
    """
    
    # Step 1: Download audio (working now)
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_path = Path(temp_dir) / "audio.%(ext)s"
        
        print(f"Downloading audio from: {url}")
        if not download_youtube_audio(url, str(audio_path)):
            return {"error": "Failed to download audio"}
        
        # Step 2: Transcribe + Diarize (needs whisperx)
        print("Audio downloaded successfully!")
        print("Next step: Install whisperx for transcription + speaker diarization")
        
        return {
            "status": "audio_downloaded",
            "next_steps": [
                "pip install whisperx",
                "Add transcription with speaker timestamps",
                "Feed to existing claim extraction pipeline"
            ]
        }


def install_whisperx():
    """Install WhisperX for transcription + diarization"""
    print("To enable YouTube video processing, run:")
    print()
    print("# Install WhisperX")
    print("pip install whisperx")
    print()
    print("# Then process any YouTube debate:")
    print("python youtube_processor.py 'https://youtube.com/watch?v=VIDEO_ID'")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python youtube_processor.py 'YOUTUBE_URL'")
        install_whisperx()
        sys.exit(1)
    
    url = sys.argv[1]
    result = process_youtube_video(url)
    print(json.dumps(result, indent=2))
