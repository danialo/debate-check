"""
Turn detection for continuous transcripts without speaker labels.

Handles wall-of-text transcripts (like YouTube auto-captions) by:
1. Splitting into sentences
2. Detecting turn boundaries via heuristics
3. Inferring speakers from name mentions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Titles that shouldn't end sentences
_TITLES = {'Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Sen', 'Rep', 'Gov', 'Jr', 'Sr'}

# Stage directions like [Applause], (laughter)
_STAGE_DIRECTION_RE = re.compile(r'\[([^\]]+)\]|\(([^\)]+)\)')

# Turn boundary signals - high confidence
_TURN_START_STRONG = re.compile(
    r'^(?:'
    r'(?:Thank you|Thanks)(?:\s+(?:very much|so much))?[.,]?\s*'  # Thanks (often ends/starts turn)
    r'|(?:Yes|No|Yeah|Nope|Nah|Right|Okay|OK|Correct|Exactly|Absolutely|Sure)[.,]?\s+'  # Affirmation/negation start
    r'|(?:Well|So|Look|See|Now|Okay|Alright|Actually)[.,]\s+'  # Discourse markers
    r'|(?:Hold on|Wait|Time out|Timeout|Let me)[.,]?\s+'  # Interruption markers
    r'|(?:I mean|I think|I believe|I would|I\'d|In my)[.,]?\s+'  # First person opinion start
    r')',
    re.IGNORECASE
)

# Question detection
_QUESTION_RE = re.compile(r'\?\s*$')

# Direct address patterns (often indicate speaker change when at start)
_DIRECT_ADDRESS_RE = re.compile(
    r'^(?:Charlie|Mr\.?\s*Kirk|Kirk)[.,]?\s+',
    re.IGNORECASE
)

# Name mention patterns for speaker inference
_NAME_MENTION_RE = re.compile(
    r'\b(Charlie|Kirk|Mr\.?\s*Kirk)\b',
    re.IGNORECASE
)

# Common names that might appear in transcripts (extend as needed)
_KNOWN_SPEAKERS = {
    'charlie': 'KIRK',
    'kirk': 'KIRK',
    'mr kirk': 'KIRK',
    'mr. kirk': 'KIRK',
}


@dataclass
class Turn:
    """A detected speaker turn (one or more sentences)."""
    sentences: List[str] = field(default_factory=list)
    speaker: str = "UNKNOWN"
    start_char: int = 0
    end_char: int = 0
    confidence: float = 0.5

    @property
    def text(self) -> str:
        return " ".join(self.sentences)


def split_sentences(text: str) -> List[Tuple[str, int, int]]:
    """
    Split text into sentences with character offsets.
    Returns: List of (sentence_text, start_char, end_char)
    """
    # Normalize whitespace first
    text = re.sub(r'\s+', ' ', text).strip()

    sentences = []
    current_start = 0
    i = 0

    while i < len(text):
        char = text[i]

        # Check for sentence-ending punctuation
        if char in '.!?':
            # Look ahead to see if this is really a sentence end
            # Need whitespace followed by capital letter (or quote + capital)
            rest = text[i+1:i+4] if i+1 < len(text) else ""

            # Check if this looks like an abbreviation
            is_abbrev = False
            if char == '.':
                # Look back for title abbreviations
                for title in _TITLES:
                    check_start = i - len(title)
                    if check_start >= 0:
                        word = text[check_start:i]
                        if word == title:
                            # Check it's word-bounded
                            if check_start == 0 or not text[check_start-1].isalpha():
                                is_abbrev = True
                                break

                # Single capital letter + period (like "A.")
                if i >= 1 and text[i-1].isupper():
                    if i < 2 or not text[i-2].isalpha():
                        is_abbrev = True

            # Check if followed by space + capital (sentence boundary)
            has_boundary = bool(re.match(r'\s+[A-Z"\[]', rest))

            if has_boundary and not is_abbrev:
                # This is a sentence end
                sentence = text[current_start:i+1].strip()
                if sentence:
                    sentences.append((sentence, current_start, i+1))
                # Skip whitespace
                i += 1
                while i < len(text) and text[i].isspace():
                    i += 1
                current_start = i
                continue

        i += 1

    # Don't forget the last sentence
    if current_start < len(text):
        sentence = text[current_start:].strip()
        if sentence:
            sentences.append((sentence, current_start, len(text)))

    return sentences


def is_turn_boundary(prev_sentence: str, curr_sentence: str) -> Tuple[bool, float]:
    """
    Determine if there's likely a speaker change between two sentences.
    Returns: (is_boundary, confidence)
    """
    confidence = 0.0
    signals = 0

    # Previous sentence was a question, current is declarative
    if _QUESTION_RE.search(prev_sentence) and not _QUESTION_RE.search(curr_sentence):
        confidence += 0.3
        signals += 1

    # Current sentence starts with turn signal
    if _TURN_START_STRONG.match(curr_sentence):
        confidence += 0.35
        signals += 1

    # Direct address at start
    if _DIRECT_ADDRESS_RE.match(curr_sentence):
        confidence += 0.4
        signals += 1

    # Stage direction between sentences (like [Applause])
    if prev_sentence.rstrip().endswith(']') or prev_sentence.rstrip().endswith(')'):
        stage_match = _STAGE_DIRECTION_RE.search(prev_sentence[-50:])
        if stage_match:
            confidence += 0.5
            signals += 1

    # "Thank you" patterns are very strong signals
    if re.match(r'^(?:Thank you|Thanks)', curr_sentence, re.IGNORECASE):
        confidence += 0.25
        signals += 1
    if re.search(r'(?:Thank you|Thanks)(?:\s+(?:very much|so much))?[.!]?\s*$', prev_sentence, re.IGNORECASE):
        confidence += 0.25
        signals += 1

    # Normalize confidence to 0-1
    confidence = min(confidence, 1.0)

    # Need at least some signal to call it a boundary
    is_boundary = confidence >= 0.3

    return is_boundary, confidence


def infer_speaker_from_context(sentences: List[str], prev_speaker: str) -> str:
    """
    Try to infer who is speaking based on context.
    Very basic heuristic - can be enhanced.
    """
    text = " ".join(sentences[:2])  # Look at first couple sentences

    # If someone is addressed, they're probably NOT the speaker
    for pattern, speaker_id in _KNOWN_SPEAKERS.items():
        if re.search(rf'\b{re.escape(pattern)}\b', text.lower()):
            # This person is being addressed, so speaker is someone else
            if prev_speaker == speaker_id:
                return "QUESTIONER"
            elif prev_speaker == "QUESTIONER" or prev_speaker == "UNKNOWN":
                return speaker_id

    # Simple alternation heuristic
    if prev_speaker == "KIRK":
        return "QUESTIONER"
    elif prev_speaker in ("QUESTIONER", "UNKNOWN"):
        return "KIRK"

    return "UNKNOWN"


def detect_turns(text: str, min_turn_sentences: int = 1, max_turn_sentences: int = 20) -> List[Turn]:
    """
    Detect speaker turns in continuous text.

    Args:
        text: Raw transcript text (wall of text)
        min_turn_sentences: Minimum sentences per turn
        max_turn_sentences: Maximum sentences before forcing a boundary

    Returns:
        List of Turn objects with detected boundaries
    """
    sentences = split_sentences(text)

    if not sentences:
        return []

    turns: List[Turn] = []
    current_turn = Turn(
        sentences=[sentences[0][0]],
        start_char=sentences[0][1],
        end_char=sentences[0][2],
        speaker="UNKNOWN"
    )

    for i in range(1, len(sentences)):
        sent_text, start_char, end_char = sentences[i]
        prev_sent = sentences[i-1][0]

        is_boundary, confidence = is_turn_boundary(prev_sent, sent_text)

        # Force boundary if turn is getting too long
        turn_too_long = len(current_turn.sentences) >= max_turn_sentences

        if is_boundary or turn_too_long:
            # Close current turn
            current_turn.end_char = sentences[i-1][2]
            turns.append(current_turn)

            # Start new turn
            current_turn = Turn(
                sentences=[sent_text],
                start_char=start_char,
                end_char=end_char,
                speaker="UNKNOWN",
                confidence=confidence
            )
        else:
            # Continue current turn
            current_turn.sentences.append(sent_text)
            current_turn.end_char = end_char

    # Don't forget the last turn
    if current_turn.sentences:
        turns.append(current_turn)

    # Second pass: infer speakers
    for i, turn in enumerate(turns):
        prev_speaker = turns[i-1].speaker if i > 0 else "UNKNOWN"
        turn.speaker = infer_speaker_from_context(turn.sentences, prev_speaker)

    return turns


def turns_to_utterances(turns: List[Turn]) -> List[dict]:
    """
    Convert turns to utterance-like dicts matching the Utterance structure.
    """
    from uuid import uuid4

    utterances = []
    for i, turn in enumerate(turns):
        utterances.append({
            'speaker': turn.speaker,
            'text': turn.text,
            'line_number': i + 1,  # Synthetic line numbers
            'segment_id': str(uuid4()),
            'segment_position': 0,
            'char_start': turn.start_char,
            'char_end': turn.end_char,
            'turn_confidence': turn.confidence,
        })

    return utterances


def detect_continuous_text(lines: List[str], threshold_chars: int = 5000) -> bool:
    """
    Detect if this is a continuous wall of text (no natural breaks).
    """
    total_text = " ".join(line.strip() for line in lines if line.strip())
    non_empty_lines = [l for l in lines if l.strip()]

    # If there's only 1-2 lines but thousands of characters, it's a wall
    if len(non_empty_lines) <= 2 and len(total_text) > threshold_chars:
        return True

    # If average line length is very high, probably continuous
    if non_empty_lines:
        avg_line_len = len(total_text) / len(non_empty_lines)
        if avg_line_len > 2000:
            return True

    return False


if __name__ == "__main__":
    # Quick test with sample text
    test_text = """
    Okay, thank you. Can we settle down, please? We're going to move on to our questions.
    Our first question is from Zina Zubar from Sydney, Sussex. Come up and ask a question.
    Remember, you have the right of response. Um, I have quite a simple question for you.
    Now, I know you've debated Dean Withers on Jubilee before. I was wondering why you now
    refuse to engage with further debate with him. Wait, hold on. First of all, he's coming
    on my show this summer. And let me get this straight. I flew 5,000 miles across the world
    to have you ask why I'm not going to debate a left-wing YouTuber. Well, I mean, he
    continuously tries to get your attention at your campus. Again, you just ignore him.
    I've debated him twice in the last calendar year. Thank you very much. Thank you. Right.
    So, thank you for coming, Charlie. My question to you, I mean, I'm a medical student.
    """

    print("=== Sentence Splitting ===")
    sentences = split_sentences(test_text)
    for i, (sent, start, end) in enumerate(sentences):
        print(f"{i+1}. [{start}:{end}] {sent[:60]}...")

    print("\n=== Turn Detection ===")
    turns = detect_turns(test_text)
    for i, turn in enumerate(turns):
        print(f"\n--- Turn {i+1} [{turn.speaker}] (conf={turn.confidence:.2f}) ---")
        print(f"{turn.text[:150]}...")
