#!/usr/bin/env python3
"""
CLI for debate transcription with speaker diarization.

Usage:
    # From YouTube
    python -m tools.transcribe https://youtube.com/watch?v=xxx -o transcript.txt

    # From local audio
    python -m tools.transcribe audio.mp3 -o transcript.txt

    # JSON output with timestamps
    python -m tools.transcribe audio.mp3 --format json -o transcript.json
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio/video with speaker diarization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s https://youtube.com/watch?v=xxx -o debate.txt
    %(prog)s recording.mp3 -o transcript.json --format json
    %(prog)s video.mp4 --format srt -o subtitles.srt
        """
    )

    parser.add_argument(
        "source",
        help="YouTube URL or path to audio/video file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "srt"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--no-diarize",
        action="store_true",
        help="Disable speaker diarization"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep downloaded audio file (for YouTube)"
    )

    args = parser.parse_args()

    # Import here to avoid slow startup for --help
    from .audio import extract_youtube_audio, is_youtube_url
    from .diarize import transcribe_audio, transcribe_url
    from .output import to_labeled_text, to_json, to_srt

    source = args.source
    audio_file = None
    cleanup_audio = False

    try:
        # Handle YouTube URLs
        if is_youtube_url(source):
            if args.verbose:
                print(f"Detected YouTube URL: {source}", file=sys.stderr)

            audio_file = extract_youtube_audio(source, verbose=args.verbose)
            cleanup_audio = not args.keep_audio

            if args.verbose:
                print(f"Extracted audio: {audio_file}", file=sys.stderr)

        # Handle local files
        elif Path(source).exists():
            audio_file = source

        # Handle direct audio URLs
        elif source.startswith("http"):
            if args.verbose:
                print(f"Using direct URL: {source}", file=sys.stderr)

            result = transcribe_url(
                source,
                speaker_labels=not args.no_diarize,
                verbose=args.verbose
            )
        else:
            print(f"Error: Source not found: {source}", file=sys.stderr)
            sys.exit(1)

        # Transcribe local/downloaded file
        if audio_file:
            result = transcribe_audio(
                audio_file,
                speaker_labels=not args.no_diarize,
                verbose=args.verbose
            )

        # Format output
        if args.format == "json":
            output = to_json(result)
        elif args.format == "srt":
            output = to_srt(result)
        else:
            output = to_labeled_text(result)

        # Write output
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            if args.verbose:
                print(f"Wrote: {args.output}", file=sys.stderr)
                print(f"Speakers: {result.speaker_count}", file=sys.stderr)
                print(f"Utterances: {len(result.utterances)}", file=sys.stderr)
        else:
            print(output)

    finally:
        # Cleanup temp audio file
        if cleanup_audio and audio_file and Path(audio_file).exists():
            if args.verbose:
                print(f"Cleaning up: {audio_file}", file=sys.stderr)
            os.unlink(audio_file)


if __name__ == "__main__":
    main()
