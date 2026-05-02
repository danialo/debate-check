# Diarization Plan (Tentative)

Parked during Phase 3 development. Revisit for end-to-end testing.

## Approach

Local pipeline using free tools:

```
YouTube URL → yt-dlp (audio) → WhisperX → diarized transcript → SpeakerTurns → HTN
```

## Dependencies

```bash
pip install whisperx yt-dlp
# pyannote requires HuggingFace token (free, accept license)
```

## Cost

- Local CPU/GPU: $0
- Cloud GPU if needed: ~$0.02/transcript

## Alternative

transcriptapi.com: $36/month for 1000 transcripts with diarization ($0.036 each)

## Output Format Needed

```python
SpeakerTurn(
    speaker="SPEAKER_1",  # or resolved name
    text="...",
    span=(start, end),
    turn_index=0
)
```

## Status

NOT IMPLEMENTED - placeholder for post-Phase 3
