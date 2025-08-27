"""
Text preprocessing and speaker identification for debate transcripts
"""

import re
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# --- Timestamps -------------------------------------------------------------

# Matches (m.ss), (mm:ss), (hh:mm:ss), with optional decimals and optional end-range
PAREN_TS = r"""
\(
   (?:
      \d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?      # 1:23 , 01:02:03 , 01:02:03.456
      |
      \d{1,3}\.\d{2,3}                             # 3.90 , 12.345
   )
   (?:\s*[-–]\s*
      (?:
         \d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?
         |
         \d{1,3}\.\d{2,3}
      )
   )?
\)
"""

# Matches [mm:ss], [m.ss], [hh:mm:ss]
BRACK_TS = r"""
\[
   (?:
      \d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?
      |
      \d{1,3}\.\d{2,3}
   )
\]
"""

# Line-leading bare timestamps (and optional WebVTT arrow)
LINE_TS = r"""
^\s*
(?:
   \d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?       # 00:12 , 01:02:03.4
)
(?:\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?)?
\s*$
"""

TIMESTAMP_RE = re.compile(
    rf"(?:{PAREN_TS})|(?:{BRACK_TS})|(?:{LINE_TS})",
    re.VERBOSE | re.MULTILINE,
)

# --- Speaker labels ---------------------------------------------------------
# Line-leading forms only: "Speaker 1:", "SPEAKER 2 -", "S1:", "Speaker 3 (laughs):"
SPEAKER_LABEL_RE = re.compile(
    r"""(?imx)
^ \s*
(?:
   (?:speaker|spkr|spk|s)\s*
   (?:\d+|[A-Z])               # 1, 2, A, B...
   (?:\s*\([^)]+\))?           # optional parenthetical: (overlap), (off), etc.
   \s*[:\-]                    # colon or dash as delimiter
)
\s*
"""
)

# --- Boilerplate / footer links --------------------------------------------
# Matches Dictationer footer lines and similar marketing blurbs
BOILERPLATE_RE = re.compile(
    r"""(?imx)
^\s*
\[
? \s* transcribed \s+ by \s+ [^\]]+ \]? .* $     # [Transcribed by Dictationer...]
|
^\s* subscribe \s+ to \s+ remove \s+ this \s+ message .* $
""",
)

# General http(s) links on their own lines (kept strict to avoid collateral damage)
STANDALONE_URL_RE = re.compile(r"""(?im)^\s*https?://\S+\s*$""")

# --- Utilities --------------------------------------------------------------

MULTISPACE_RE = re.compile(r"[ \t]{2,}")
MULTINEWLINE_RE = re.compile(r"\n{3,}")

def _strip_inline_timestamps(text: str) -> str:
    # Remove () and [] timestamps anywhere; safe because we require ":" or decimal with 2–3 digits
    return TIMESTAMP_RE.sub("", text)

def _strip_line_boilerplate(text: str) -> str:
    # Remove whole-line boilerplate & standalone URLs
    lines = []
    for line in text.splitlines():
        if BOILERPLATE_RE.search(line):
            continue
        if STANDALONE_URL_RE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines)

def _strip_speaker_labels(text: str) -> str:
    # Only at line starts; we keep labels that are embedded in sentences
    def _repl(m: re.Match) -> str:
        return ""  # drop the label prefix
    return SPEAKER_LABEL_RE.sub(_repl, text)

def clean_text(text: str) -> str:
    """
    Clean transcript text of timestamps, line-leading speaker labels,
    and boilerplate before segmentation.
    """
    # 1) Remove Dictationer/boilerplate & raw link lines
    text = _strip_line_boilerplate(text)

    # 2) Remove inline timestamps in (), [] and bare line-leading time codes/WebVTT cues
    text = _strip_inline_timestamps(text)

    # 3) Remove line-leading speaker labels (we infer speakers later)
    text = _strip_speaker_labels(text)

    # 4) Normalize whitespace/newlines (but preserve single newlines as soft boundaries)
    text = MULTISPACE_RE.sub(" ", text)
    text = MULTINEWLINE_RE.sub("\n\n", text)

    # 5) Trim
    return text.strip()


class DebatePreprocessor:
    """
    Preprocesses raw debate transcript text by:
    1. Normalizing whitespace and removing stage directions
    2. Identifying speakers 
    3. Extracting clean utterances with speaker attribution
    """
    
    def __init__(self):
        # Common speaker patterns in debate transcripts
        self.speaker_patterns = [
            # Standard format: "SPEAKER NAME:"
            r'^([A-Z][A-Z\s\-\.]+):\s*(.*)$',
            # Moderator variations
            r'^(MODERATOR|HOST|ANCHOR):\s*(.*)$',
            # Numbered speakers: "SPEAKER 1:", "CANDIDATE A:"
            r'^([A-Z]+\s+[A-Z0-9]+):\s*(.*)$',
            # Bracketed speakers: "[SMITH]" or "(MODERATOR)"
            r'^\[([A-Z\s]+)\]\s*(.*)$',
            r'^\(([A-Z\s]+)\)\s*(.*)$',
        ]
        
        # Stage directions to remove (between parentheses or brackets)
        self.stage_direction_patterns = [
            r'\([^)]*\)',  # (applause), (laughter), etc.
            r'\[[^\]]*\]', # [crosstalk], [inaudible], etc.
        ]
        
        # Timestamp patterns to remove
        self.timestamp_patterns = [
            r'\d{1,2}:\d{2}:\d{2}',  # HH:MM:SS
            r'\d{1,2}:\d{2}',        # MM:SS
            r'@\d+:\d+',             # @MM:SS
        ]
    
    def process(self, text: str) -> List[Tuple[str, str, int]]:
        """
        Process raw transcript text into structured utterances.
        
        Args:
            text: Raw debate transcript text
            
        Returns:
            List of tuples: (speaker_id, utterance, line_number)
        """
        logger.debug(f"Processing {len(text)} characters of input text")
        
        # First, clean timestamps, boilerplate, and speaker labels
        text = clean_text(text)
        logger.debug(f"After cleaning: {len(text)} characters")
        
        lines = text.split('\n')
        utterances = []
        current_speaker = "UNKNOWN"
        
        for line_no, line in enumerate(lines, 1):
            # Skip empty lines
            if not line.strip():
                continue
                
            # Clean the line
            cleaned_line = self._clean_line(line)
            if not cleaned_line.strip():
                continue
            
            # Try to identify speaker
            speaker, utterance = self._extract_speaker_and_utterance(cleaned_line)
            
            if speaker:
                current_speaker = speaker
                # If utterance is empty after speaker extraction, continue to next line
                if utterance.strip():
                    utterances.append((current_speaker, utterance, line_no))
            else:
                # No speaker identified - this is a continuation of previous speaker
                utterances.append((current_speaker, cleaned_line, line_no))
        
        logger.info(f"Extracted {len(utterances)} utterances from {len(lines)} lines")
        
        # Log speaker distribution
        speakers = set(speaker for speaker, _, _ in utterances)
        logger.info(f"Identified speakers: {', '.join(sorted(speakers))}")
        
        return utterances
    
    def _clean_line(self, line: str) -> str:
        """Remove stage directions, timestamps, and normalize whitespace."""
        cleaned = line.strip()
        
        # Remove timestamps
        for pattern in self.timestamp_patterns:
            cleaned = re.sub(pattern, '', cleaned)
        
        # Remove stage directions  
        for pattern in self.stage_direction_patterns:
            cleaned = re.sub(pattern, '', cleaned)
        
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _extract_speaker_and_utterance(self, line: str) -> Tuple[Optional[str], str]:
        """
        Extract speaker and utterance from a line.
        
        Returns:
            Tuple of (speaker_id, utterance). Speaker is None if not found.
        """
        for pattern in self.speaker_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                speaker = match.group(1).upper().strip()
                utterance = match.group(2).strip() if len(match.groups()) > 1 else ""
                
                # Normalize common speaker names
                speaker = self._normalize_speaker_name(speaker)
                
                return speaker, utterance
        
        return None, line
    
    def _normalize_speaker_name(self, speaker: str) -> str:
        """Normalize speaker names for consistency."""
        # Remove common suffixes and prefixes
        speaker = re.sub(r'\b(MR|MS|MRS|DR|PROF|REP|SEN|PRES|VICE)\b\.?\s*', '', speaker)
        
        # Normalize common roles
        normalizations = {
            'MODERATOR': 'MODERATOR',
            'HOST': 'MODERATOR', 
            'ANCHOR': 'MODERATOR',
            'INTERVIEWER': 'MODERATOR',
        }
        
        for pattern, replacement in normalizations.items():
            if pattern in speaker:
                return replacement
        
        # If speaker name is very long, try to extract last name
        parts = speaker.split()
        if len(parts) > 2:
            # Use the last part as the speaker name
            return parts[-1]
        
        return speaker
