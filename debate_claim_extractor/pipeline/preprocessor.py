"""
Text preprocessing and speaker identification for debate transcripts
"""

import re
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


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
