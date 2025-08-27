"""
Claim filtering and classification system to improve claim detection accuracy
"""

import re
import logging
from typing import List, Set, Optional, Tuple, Iterable
from abc import ABC, abstractmethod

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from .models import Claim, ClaimType

logger = logging.getLogger(__name__)

# Domain anchors (case-insensitive)
DEFAULT_ANCHORS: Set[str] = {
    # existing/governmental
    "senate", "house", "congress", "constitution", "federal", "state", "country",
    # acronyms and orgs
    "dei", "doj", "epa", "opec", "oecd", "nato", "cdc"
}

COPULA_SHORT_OK = re.compile(r"^(it|this|that|they|we|he|she)\s+(is|’s|'s)\s+\w+[.!]?$", re.IGNORECASE)

def contains_anchor(text: str, anchors: Iterable[str]) -> bool:
    if not anchors:
        return False
    al = {a.lower() for a in anchors}
    # cheap tokenization
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text):
        if tok.lower() in al:
            return True
    return False


class ClaimFilter(ABC):
    """Abstract base class for claim filters"""
    
    @abstractmethod
    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        """
        Determine if a claim should be excluded.
        
        Returns:
            (should_exclude: bool, reason: str)
        """
        pass


class ConversationalFilter(ClaimFilter):
    """Filters out conversational fillers, acknowledgments, and non-substantive content"""
    
    def __init__(self):
        # Pure conversational fillers (entire utterance)
        self.filler_utterances = {
            'yeah', 'yes', 'no', 'right', 'okay', 'ok', 'mhm', 'mmm', 'uh', 'uhh',
            'um', 'umm', 'ah', 'oh', 'hm', 'hmm', 'well', 'so', 'now', 'then',
            'exactly', 'absolutely', 'definitely', 'sure', 'fine', 'good', 'nice',
            'great', 'awesome', 'cool', 'true', 'fair enough', 'that\'s the thing',
            'that\'s it', 'there you go', 'here we go', 'that\'s right',
            'that\'s the thing there', 'you know what i mean', 'uh huh sure',
            'yeah right exactly', 'hello', 'hi', 'thanks', 'welcome', 'goodbye'
        }
        
        # Conversational patterns (regex patterns to match)
        self.filler_patterns = [
            r'^(yeah|yes|no|right|okay|ok|mhm)\s*$',  # Just the filler word
            r'^(yeah|yes|no|right|okay|ok)\s+(right|exactly|sure)\s*$',  # "yeah right", "yes sure"
            r'^\w+\s+(I|you|we|they)\s+(want|need)\s+to\s+(compare|discuss|talk about)',  # Topic introductions
            r'^\w+\s+I\s+want\s+to\s+compare\s+notes',  # "Charles I want to compare notes"
            r'^\w+\s+I\s+want\s+to\s+compare\s+notes\s+okay\s+on',  # "Charles I want to compare notes okay on"
            r'^(let me|let\'s|I want to|I think we should)',  # Conversation starters
            r'^(wow|oh|ah)\s+(that was|that\'s|how)\s+',  # Reactions
            r'^(I see|I get it|I understand|got it|makes sense)\s*$',  # Acknowledgments
            r'^(right|yeah|well|so|now|then)\s+.{0,30}\s+(right|there|true)\s*$',  # Conversational bridges
            r'^that\'s\s+(it|right|true|the\s+thing)(?:\s+there)?\s*$',  # "that's the thing", "that's it", etc.
        ]
        
        # Vague reference patterns that don't make substantive claims
        self.vague_patterns = [
            r'^that\'s\s+the\s+thing\s+there\s*$',  # "that's the thing there"
            r'^(this|that|it)\s+is\s+(it|the\s+thing|what\s+it\s+is)\s*$',  # "this is it", "that is the thing"
            r'^(here|there)\s+(it|that)\s+is\s*$',  # "here it is", "there that is"
            r'^you\s+hear\s+\w+\s+and\s+you\s+be\s+like\s*$',  # "you hear silence and you be like"
            r'^same\s+is\s+true\s*$',  # "same is true"
            r'^and\s+you\s+know\s+it\s+\w*\s*$',  # "and you know it M"
            r'^but\s+I\s+know\s+what\s+it\'s\s+\w+\s*$',  # "but I know what it's different"
            r'^and\s+so\s+in\s+that\s+moment\s+you\s+are\s+not\s+\w+\s*$',  # "and so in that moment you are not exercising Free"
            r'^\w+\s+physics\s+wise\s+though\s+that\'s\s+the\s+challenge\s*$',  # "Will physics wise though that's the challenge"
        ]
        
        # Minimum word count for substantive claims
        self.min_substantive_words = 4  # Increased from 3
    
    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        text_lower = text.lower().strip()
        
        # Check if it's a pure filler utterance
        if text_lower in self.filler_utterances:
            return True, f"Pure conversational filler: '{text_lower}'"
        
        # Check specific topic introduction patterns
        if ('want to compare notes' in text_lower and 
            ('okay on' in text_lower or 'about' in text_lower)):
            return True, f"Topic introduction: '{text_lower}'"
        
        # Check filler patterns
        for pattern in self.filler_patterns:
            if re.match(pattern, text_lower):
                return True, f"Conversational pattern: '{text_lower}'"
        
        # Check vague reference patterns
        for pattern in self.vague_patterns:
            if re.match(pattern, text_lower):
                return True, f"Vague conversational fragment: '{text_lower}'"
        
        # Check word count (but allow some short substantive claims)
        words = text_lower.split()
        if len(words) < self.min_substantive_words and not any(word in ['is', 'are', 'was', 'were', 'has', 'have'] for word in words):
            return True, f"Too short and non-substantive: {len(words)} words"
        
        return False, ""


class QuestionFilter(ClaimFilter):
    """Filters out questions, which are not claims"""
    def __init__(self, drop_questions: bool = True):
        self.drop_questions = drop_questions
    
    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        text_stripped = text.strip()
        
        # Direct question markers
        if text_stripped.endswith('?'):
            return (True, "Direct question") if self.drop_questions else (False, "question-allowed-for-review")
        
        # Question word patterns
        question_patterns = [
            r'^\s*(what|how|why|when|where|who|which|whose)\s+',
            r'^\s*(do|does|did|can|could|would|should|will|is|are|was|were)\s+you\s+',
            r'^\s*(are|is|was|were|do|does|did)\s+',
        ]
        
        text_lower = text.lower()
        for pattern in question_patterns:
            if re.match(pattern, text_lower):
                return True, "Question pattern detected"
        
        return False, ""


class HypotheticalFilter(ClaimFilter):
    """Filters out hypothetical scenarios, examples, and thought experiments"""
    
    def __init__(self):
        self.hypothetical_indicators = [
            'let\'s say', 'suppose', 'imagine', 'what if', 'if you', 'if we',
            'consider', 'for example', 'for instance', 'hypothetically',
            'in theory', 'theoretically', 'let me give you an example',
            'picture this', 'think about', 'let\'s imagine'
        ]
    
    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        text_lower = text.lower()
        
        for indicator in self.hypothetical_indicators:
            if indicator in text_lower:
                return True, f"Hypothetical scenario: contains '{indicator}'"
        
        return False, ""


class SponsorContentFilter(ClaimFilter):
    def __init__(self, state=None):
        flags = re.I | re.UNICODE
        self.state = state  # optional shared dict: {"in_sponsor": False, "ttl": 0}

        self.promo_patterns = [
            re.compile(r"\b(head over to|use (?:the )?exclusive link|use code|sponsored(?: by)?|our partners? at)\b", flags),
            re.compile(r"https?://", flags),
            re.compile(r"\bwww\.[^\s]+\b", flags),
            re.compile(r"\.(?:com|org|net|io|co)\b", flags),  # word boundary fixes "become"
            re.compile(r"\b(?:save|off)\s*\d{1,3}\s*%|\bper\s*cent\b", flags),
            re.compile(r"\bVantage plan\b", flags),
            re.compile(r"\b(ground\s*news|spotify|apple\s*podcasts?|google\s*podcasts?|patreon|substack)\b", flags),
        ]
        self.start_block = re.compile(r"\b(this (?:episode|segment) is (?:brought|sponsored) by|our sponsor[s]?\b)", flags)
        self.end_block = re.compile(r"\b(let'?s|get) back to (?:the )?show|and we'?re back\b", flags)

        self.meta_patterns = [
            re.compile(r"\b(check it out|I tweeted|I put a link)\b", flags),
            re.compile(r"\bmultiple ways to ingest\b", flags),
        ]

    def should_exclude(self, text, claim, **kwargs):
        tl = text.lower()

        # block-mode (optional)
        if self.state is not None:
            if self.state.get("in_sponsor"):
                if self.end_block.search(tl):
                    self.state["in_sponsor"] = False
                    return True, "Sponsor block (ending line)"
                else:
                    # keep dropping while in sponsor
                    return True, "Sponsor block"
            elif self.start_block.search(tl):
                self.state["in_sponsor"] = True
                return True, "Sponsor block (starting line)"

        for pat in self.promo_patterns:
            if pat.search(tl):
                return True, f"Promotional content: {pat.pattern}"

        for pat in self.meta_patterns:
            if pat.search(tl):
                return True, f"Meta show control: {pat.pattern}"

        return False, ""


class MetadataFilter(ClaimFilter):
    def __init__(self):
        flags = re.I | re.UNICODE
        # verbs that "rescue" titles
        self.factual_verbs = re.compile(r"\b(argues?|shows?|found|finds|demonstrat(?:es|ed|ing)|reports?|claims?)\b", flags)
        # title-ish lines: many ProperNouns with no verbs
        self.titleish = re.compile(r"^(?:[A-Z][\w''-]+(?:\s+[A-Z][\w''-]+){2,})(?:\s*[:—,-].*)?$")
        self.yearish = re.compile(r"\b(19|20)\d{2}\b")
        self.has_verb = re.compile(r"\b(is|are|was|were|has|have|had|does|did|do|be|being|been|[a-z]+ed|[a-z]+ing|[a-z]+s)\b", flags)
        self.rhetorical = [
            re.compile(r"^(what'?s|who'?s|where'?s|when'?s|how'?s)\b.*", flags),
            re.compile(r"^do you remember\b", flags),
            re.compile(r"^(can|could|would|should)\s+you\b", flags),
        ]

    def should_exclude(self, text, claim, **kwargs):
        t = text.strip()
        tl = t.lower()

        if self.factual_verbs.search(tl):
            return False, ""  # rescued by explicit reporting verb

        # Pure title/label: many ProperNouns, no verbs, optional year
        if self.titleish.match(t) and not self.has_verb.search(tl):
            return True, "Title/label without predicate"

        # Rhetorical questions with no declarative payload
        if t.endswith("?"):
            for pat in self.rhetorical:
                if pat.match(tl):
                    return True, f"Rhetorical/meta question: {pat.pattern}"

        return False, ""


class MinimumContentFilter(ClaimFilter):
    def __init__(self, min_content_words: int = 5, anchors: Optional[Set[str]] = None, context_window_chars: int = 250):
        flags = re.I | re.UNICODE
        self.min_content_words = min_content_words
        self.anchors: Set[str] = set(a.lower() for a in (anchors or DEFAULT_ANCHORS))
        self.context_window_chars = context_window_chars
        self.filler_leads = re.compile(r"^(um+|uh+|erm+|like|you know|i mean)\b", flags)
        self.aux = re.compile(r"\b(is|are|was|were|has|have|had|does|do|did|can|could|should|would|may|might|must)\b", flags)
        self.verbish = re.compile(r"\b[a-z]+(?:ed|ing|en)\b", flags)
        self.anchor_num = re.compile(r"\d", flags)
        self.anchor_money_pct = re.compile(r"(?:[$€£]\s*\d|\d+\s*%)", flags)
        self.anchor_propers = re.compile(r"(?:\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,})")
        self.word = re.compile(r"[A-Za-z]+")
        # compact stop/filler (lowercased)
        self.stop = {
            'a','an','the','and','or','but','in','on','at','to','for','of','with','by','from','up','about','into','through',
            'during','before','after','above','below','between','among','under','over','out','off','down','well','so','ok','okay',
            'uh','um','like','you','know','i','me','my','mine','we','us','our','ours','your','yours','he','him','his','she',
            'her','hers','it','its','they','them','their','theirs'
        }

    def _anchored(self, t: str) -> bool:
        return bool(
            self.anchor_num.search(t) or
            self.anchor_money_pct.search(t) or
            self.anchor_propers.search(t) or
            contains_anchor(t, self.anchors)
        )

    def allow_short_copula(self, claim: Claim, context_before: str, context_after: str) -> bool:
        if not COPULA_SHORT_OK.match(claim.text.strip()):
            return False
        # require nearby preceding context to attach meaning
        return len((context_before or '').strip()) >= 40

    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        tl = text.lower().strip()
        tokens = tl.split()
        n_tokens = len(tokens)
        context_before = kwargs.get('context_before', '') or ''
        context_after = kwargs.get('context_after', '') or ''

        # very short + unanchored: allow short copula if sufficient context
        if n_tokens < 7 and not self._anchored(text):
            if self.allow_short_copula(claim, context_before, context_after):
                return False, "short-copula-with-context"
            return True, f"Too short: {n_tokens} tokens (no anchors)"

        # filler lead-ins need substance soon
        if self.filler_leads.search(tl) and n_tokens < 12:
            return True, "Filler lead-in with insufficient content"

        # content words
        content = [w for w in tokens if self.word.fullmatch(w) and w not in self.stop]
        if len(content) < self.min_content_words and not self._anchored(text):
            if self.allow_short_copula(claim, context_before, context_after):
                return False, "short-copula-with-context"
            return True, f"Too few content words: {len(content)}/{self.min_content_words} (no anchors)"

        # require some predicate signal
        if not (self.aux.search(tl) or self.verbish.search(tl)):
            return True, "No predicate signal"

        return False, ""


class ShowIntroPleasantryFilter(ClaimFilter):
    """Filters show intros/outros, meta control lines, and pleasantries."""
    def __init__(self):
        flags = re.I | re.UNICODE
        # Show intros / role self-announce
        self.intro = re.compile(
            r"\b(this\s+is\s+[A-Z][\w''-]+|i'?m\s+[A-Z][\w''-]+\s+(?:your|the)\s+\w+|welcome\s+back\s+to)\b",
            flags,
        )
        # Meta: back to show / subscribe / check it out
        self.meta = re.compile(
            r"\b(let'?s\s+get\s+back\s+to\s+(?:the\s+)?show|thanks\s+for\s+watching|check\s+it\s+out|subscribe|rate\s+and\s+review)\b",
            flags,
        )
        # Pleasantries
        self.pleasantry = re.compile(
            r"^(thank\s+you(\s+very\s+much)?|thanks(?:\s+so\s+much)?|it'?s\s+great\s+to\s+be\s+here|welcome\s+back)\b",
            flags,
        )

        # rescue: if there's a clear predicate about an external entity, keep
        self.has_predicate = re.compile(r"\b(is|are|was|were|has|have|had|does|did|do|can|could|should|would|may|might|must)\b", flags)
        self.anchor_propers = re.compile(r"(?:\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,})")

    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        t = text.strip()
        tl = t.lower()

        if self.intro.search(t) or self.meta.search(tl) or self.pleasantry.search(tl):
            # Rescue if it's an actual proposition about an external entity (rare in intros)
            if not (self.has_predicate.search(tl) and self.anchor_propers.search(t)):
                return True, "Show intro/meta/pleasantry"
        return False, ""


class BiographicalFilter(ClaimFilter):
    """Filters out first-person biographical anecdotes / asides."""
    def __init__(self):
        flags = re.I | re.UNICODE
        # first-person starts that usually denote personal anecdote
        self.bio_starts = re.compile(
            r"^\s*i\s+(?:was|am|went|met|vot(?:ed|e)|graduat(?:ed|e)|remember|think|feel|believe|told|got|said|tweet(?:ed)?|posted)\b",
            flags,
        )
        # phrases that often mark personal-memory justification
        self.memory_just = re.compile(r"\b(i\s+remember|i\s+recall|it\s+was\s+the\b.*(year|month))", flags)

        # allowlist anchors that can rescue a truly checkable claim
        self.anchor_num = re.compile(r"\d")
        self.anchor_money_pct = re.compile(r"(?:[$€£]\s*\d|\d+\s*%)", flags)
        self.anchor_propers = re.compile(r"(?:\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,})")

    def _anchored(self, text: str) -> bool:
        return bool(self.anchor_num.search(text) or
                    self.anchor_money_pct.search(text) or
                    self.anchor_propers.search(text))

    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        t = text.strip()
        tl = t.lower()

        # If it's clearly a normative/non-checkable, let the normative gate handle it elsewhere.
        if getattr(claim, "type", "").lower() == "normative" and not getattr(claim, "should_fact_check", True):
            return False, ""

        # First-person anecdote + no strong external anchors → drop
        if self.bio_starts.search(tl) or self.memory_just.search(tl):
            # keep only if the line includes an external, checkable proposition (entity/date) *and* a predicate beyond the self
            if not self._anchored(t) or len(t.split()) < 9:
                return True, "First-person biographical aside (not generally fact-checkable)"
        return False, ""


class TruncationFragmentFilter(ClaimFilter):
    """Filters truncated sentences and dangling fragments that slip through segmentation."""
    def __init__(self):
        flags = re.I | re.UNICODE
        # ends mid-word or with dangling 'the b', 'becau', '...' etc.
        self.midword_tail = re.compile(r"[A-Za-z]{1,3}$")
        self.ellipsis = re.compile(r"(?:\.\.\.|…)\s*$")
        # tailing bare conjunctions / discourse markers
        self.conj_tail = re.compile(r"(?:,\s*)?(?:and|but|so|or|because)\s*$", flags)
        # leading filler+conj with too few tokens
        self.filler_lead = re.compile(r"^(um+|uh+|erm+|you\s+know|i\s+mean|like)\s+(and|so|but)\b", flags)

        # rescue anchors
        self.anchor_num = re.compile(r"\d")
        self.anchor_propers = re.compile(r"(?:\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,})")

    def _anchored(self, t: str) -> bool:
        return bool(self.anchor_num.search(t) or self.anchor_propers.search(t))

    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        t = text.strip()
        tl = t.lower()
        tokens = tl.split()

        # classic truncation: ellipsis or very short dangling token at end
        if self.ellipsis.search(t):
            return True, "Truncated with ellipsis"
        if len(tokens) <= 10 and self.midword_tail.search(t) and not t.endswith(('.', '!', '?')):
            return True, "Truncated mid-word/unfinished tail"

        # conjunction tail: "… because", "… and" etc.
        if self.conj_tail.search(tl):
            return True, "Dangling conjunction tail"

        # filler + conjunction lead with too little substance
        if self.filler_lead.search(tl) and len(tokens) < 12 and not self._anchored(t):
            return True, "Filler/conjunction lead with insufficient content"

        return False, ""


class PronounVaguenessFilter(ClaimFilter):
    """Filters out vague pronoun references without concrete content"""
    
    def __init__(self):
        flags = re.I | re.UNICODE
        
        # Vague pronoun starts
        self.vague_starts = re.compile(r"^(he|she|they|this|that|it)\s+(was|were|is|are|did|does|had|has)\b", flags)
        
        # Concrete nouns that rescue vague references
        self.concrete_nouns = re.compile(r"\b(museum|university|book|study|research|evidence|data|theory|law|principle|discovery|invention|species|planet|element|molecule|gene|protein|disease|medication|treatment|country|city|war|battle|treaty|constitution|government|president|minister|company|product|technology|computer|internet|website|database|algorithm)\b", flags)
    
    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        tl = text.lower()
        
        # Check for vague pronoun start
        if self.vague_starts.search(tl):
            # Check if rescued by concrete noun
            if not self.concrete_nouns.search(tl):
                return True, "Vague pronoun reference without concrete content"
        
        return False, ""


class DiscourseFragmentFilter(ClaimFilter):
    """Filters out discourse fragments, incomplete sentences, and conversational noise"""

    def __init__(self):
        flags = re.I | re.UNICODE

        # Allowlist: if any of these are present, we presume potential claimness
        # (checked early to reduce false drops)
        self.allow_digit = re.compile(r"\d", flags)
        self.allow_money_pct = re.compile(r"[$€£]\s*\d|%\b", flags)
        self.allow_two_propers = re.compile(r"(?:\b[A-Z][a-z]+\b.*){2,}", 0)  # cheap proper-noun proxy

        # Discourse markers leading to weak propositions
        self.discourse_fragment_patterns = [
            re.compile(r"^(?:well|so|but|and|or|now|then)\b(?:[,\s]+(?:look|listen))?\b", flags),
            re.compile(r"^(?:i\s+think|i\s+feel|i\s+believe)\b.*\b(?:i\s+think|i\s+feel|i\s+believe)\b", flags),
            re.compile(r"^(?:so|but|and)\b.{5,50}\b(?:and|but|so)\s*$", flags),
            re.compile(r"^(?:well|so|but)\b.{5,40}\b(?:though|anyway)\s*$", flags),
        ]

        # Incomplete / extremely generic copular clauses (short + no anchors)
        self.incomplete_patterns = [
            re.compile(r"\b(?:and|but|or|so)\s*$", flags),  # trailing conjunction
            # Pronoun + copula + single adjective/noun, only if very short
            re.compile(r"^(?:he|she|it|they|this|that)\s+(?:was|were|is|are)\s+\w+\s*$", flags),
            # "it's not that X" / "it's not that X" — only if short & generic
            re.compile(r"^it['']s\s+(?:not\s+that\s+)?\w+\s*$", flags),
            re.compile(r"^(?:so|and|but)\s+(?:you|i|we)\s+(?:skip|jump|go)\b.*$", flags),
        ]

        # Conversational noise
        self.noise_patterns = [
            re.compile(r"^(?:well|so|but|and|or)\b.*\b(?:i\s+think|i\s+mean|you\s+know)\b", flags),
            re.compile(r"\b(?:we|i|you)\s+(?:have|had|got)\s+a\s+lot\s+of\s+catching\s+up\b", flags),
            re.compile(r"^(?:and|so)\s+i\s+got\s+to\s+tell\s+(?:him|her|you)\b", flags),
        ]

        # Pronoun boundary counter for mashed fragments (handles caps & contractions)
        self.boundary_token = re.compile(r"\b(?:i|we|you|i['']m|we['']re|you['']re)\b", flags)

    def _likely_claim_anchor(self, text_lower: str) -> bool:
        # Fast allowlist: digits, money/percent, or 2+ capitalized tokens (cheap NER proxy)
        return (
            bool(self.allow_digit.search(text_lower)) or
            bool(self.allow_money_pct.search(text_lower)) or
            bool(self.allow_two_propers.search(text_lower))
        )

    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        t = text.strip()
        tl = t.lower()

        # Respect upstream signal: normative + not fact-checkable → drop here
        if getattr(claim, "type", "").lower() == "normative" and not getattr(claim, "should_fact_check", True):
            return True, "Normative/subjective (not fact-checkable)"

        # Very short utterances (fast path)
        if len(tl.split()) < 6 and not self._likely_claim_anchor(t):
            return True, "Fragment/too short"

        # If strong anchors exist, be conservative (avoid dropping real claims)
        anchored = self._likely_claim_anchor(t)

        # Discourse fragments
        for pat in self.discourse_fragment_patterns:
            if pat.search(tl) and not anchored:
                return True, f"Discourse fragment: {pat.pattern}"

        # Incomplete sentences (only if short and unanchored)
        if len(tl.split()) <= 8 and not anchored:
            for pat in self.incomplete_patterns:
                if pat.search(tl):
                    return True, f"Incomplete sentence: {pat.pattern}"

        # Conversational noise
        for pat in self.noise_patterns:
            if pat.search(tl) and not anchored:
                return True, f"Conversational noise: {pat.pattern}"

        # Multiple sentence fragments without punctuation
        if len(tl.split()) > 15 and not any(p in t for p in [".", "!", "?", ";", ":"]):
            boundaries = len(self.boundary_token.findall(tl))
            if boundaries >= 2:
                return True, f"Multiple sentence fragments without punctuation ({boundaries} boundaries)"

        return False, ""


class MangledTextFilter(ClaimFilter):
    """Filters out mangled, incomplete, or corrupted text that doesn't form coherent claims"""
    
    def __init__(self):
        # Patterns indicating mangled or incomplete text
        self.mangled_patterns = [
            r'^\w+\s*(right|yeah|well)\s+.{5,30}\s+(right|there|true|Point)\s+\w*\s*$',  # "right it falls flat... Point true right"
            r'\s+Point\s+(true|right)\s*$',  # Text ending with "Point true" or "Point right"
            r'^(right|yeah|well)\s+\w+\s+(did|have|had|was|were)\s+\w+\s+to\s+(not|n\'t)\s+',  # "right did you have X to not Y"
            r'\s+(falls flat|point true|that\'s right)\s*$',  # Ending with conversational markers
        ]
        
        # Common signs of text corruption or concatenation issues
        self.corruption_indicators = [
            'Point true',  # Seems to be artifact from transcription
            'Point right',  # Another artifact
            'falls flat in that moment you have many things',  # Specific mangled pattern
        ]
    
    def should_exclude(self, text: str, claim: Claim, **kwargs) -> Tuple[bool, str]:
        text_lower = text.lower()
        
        # Check for corruption indicators
        for indicator in self.corruption_indicators:
            if indicator.lower() in text_lower:
                return True, f"Text corruption detected: contains '{indicator}'"
        
        # Check mangled patterns
        for pattern in self.mangled_patterns:
            if re.search(pattern, text_lower):
                return True, f"Mangled text pattern: {pattern}"
        
        # Check for very long sentences that might be concatenated
        words = text_lower.split()
        if len(words) > 30 and not any(punct in text for punct in ['.', '!', '?', ';', ':']):
            # Long run-on without punctuation is suspicious
            return True, f"Suspiciously long unpunctuated text: {len(words)} words"
        
        # Check for sentences with too many repeated filler words
        filler_words = ['right', 'yeah', 'well', 'uh', 'um', 'so', 'like', 'you know']
        filler_count = sum(1 for word in words if word in filler_words)
        if len(words) > 5 and filler_count / len(words) > 0.4:
            return True, f"Too many filler words: {filler_count}/{len(words)} ({filler_count/len(words)*100:.1f}%)"
        
        return False, ""


class ClaimTypeClassifier:
    """Classifies claims into appropriate types, distinguishing factual from normative/philosophical"""
    
    def __init__(self):
        self.philosophical_indicators = [
            # Free will and determinism
            'free will', 'determinism', 'predetermined', 'choice', 'agency',
            'moral responsibility', 'consciousness', 'causality', 'causal',
            'antecedent', 'everything is predetermined', 'logical conclusion',
            'stochastic uncertainty', 'randomness', 'unpredictability',
            
            # Philosophical concepts
            'philosophy', 'philosophical', 'metaphysics', 'ontology',
            'epistemology', 'ethics', 'morality',
            
            # Normative language
            'should', 'ought to', 'must', 'right', 'wrong', 'good', 'bad',
            'better', 'worse', 'moral', 'ethical', 'justice', 'fair', 'unfair',
            
            # Belief and opinion language
            'I believe', 'I think', 'I feel', 'in my opinion', 'my view',
            'perspective', 'philosophy', 'worldview',
            
            # Value judgments (but be careful not to conflict with empirical usage)
            'important', 'valuable', 'meaningful', 'worthwhile',
            'desirable', 'undesirable', 'preferable'
        ]
        
        self.empirical_indicators = [
            # Scientific/empirical language
            'study shows', 'research indicates', 'data suggests', 'evidence',
            'measured', 'observed', 'recorded', 'documented', 'tested',
            
            # Factual reporting
            'according to', 'reported', 'stated', 'announced', 'confirmed',
            'verified', 'established fact', 'proven'
        ]
    
    def classify_claim_nature(self, text: str, current_type: ClaimType) -> Tuple[ClaimType, bool, str]:
        """
        Classify whether a claim is empirical/factual or normative/philosophical.
        
        Returns:
            (claim_type, should_fact_check, classification_reason)
        """
        text_lower = text.lower()
        
        # Check for philosophical content
        philosophical_matches = [ind for ind in self.philosophical_indicators if ind in text_lower]
        empirical_matches = [ind for ind in self.empirical_indicators if ind in text_lower]
        
        if philosophical_matches:
            return (
                ClaimType.NORMATIVE,  # We'll need to add this to the enum
                False,  # Don't fact-check philosophical positions
                f"Philosophical content detected: {philosophical_matches}"
            )
        
        if empirical_matches:
            return (
                current_type,
                True,  # Do fact-check empirical claims
                f"Empirical content detected: {empirical_matches}"
            )
        
        # For claims without clear philosophical or empirical indicators,
        # be conservative and allow fact-checking but with lower confidence
        return (current_type, True, "Neutral content - allowing fact-checking")


class ImprovedClaimFilteringSystem:
    """Comprehensive claim filtering and classification system"""
    
    def __init__(self, shared_state=None, anchors: Optional[Set[str]] = None, drop_questions: bool = True,
                 min_content_words: int = 5, context_window_chars: int = 250, **_):
        self.filters = [
            SponsorContentFilter(state=shared_state),
            MetadataFilter(),
            MinimumContentFilter(min_content_words=min_content_words, anchors=anchors or DEFAULT_ANCHORS,
                                 context_window_chars=context_window_chars),
            ShowIntroPleasantryFilter(),
            BiographicalFilter(),
            TruncationFragmentFilter(),
            PronounVaguenessFilter(),
            DiscourseFragmentFilter(),  # Improved version for complex discourse patterns
            ConversationalFilter(),
            QuestionFilter(drop_questions=drop_questions), 
            HypotheticalFilter(),
            MangledTextFilter()
        ]
        
        self.classifier = ClaimTypeClassifier()
        logger.info(f"Initialized claim filtering system with {len(self.filters)} filters (drop_questions={drop_questions})")
    
    def filter_and_classify_claims(self, claims: List[Claim], context_map: Optional[dict] = None) -> List[Claim]:
        """
        Filter out non-claims and properly classify remaining claims.
        
        Returns:
            List of valid, properly classified claims
        """
        valid_claims = []
        excluded_count = 0
        reclassified_count = 0
        
        for claim in claims:
            # Check if claim should be excluded
            should_exclude = False
            exclusion_reason = ""
            
            # extract transient context for filters
            ctx = context_map.get(claim.id, {}) if context_map else {}
            ctx_before = ctx.get('before', '')
            ctx_after = ctx.get('after', '')

            for filter_obj in self.filters:
                exclude, reason = filter_obj.should_exclude(
                    claim.text, claim,
                    context_before=ctx_before,
                    context_after=ctx_after
                )
                if exclude:
                    should_exclude = True
                    exclusion_reason = reason
                    break
            
            if should_exclude:
                excluded_count += 1
                logger.debug(f"Excluded claim: '{claim.text[:50]}...' - {exclusion_reason}")
                continue
            
            # Classify the claim's nature and determine if it should be fact-checked
            new_type, should_fact_check, classification_reason = self.classifier.classify_claim_nature(
                claim.text, claim.type
            )
            
            # Update claim with new classification
            if new_type != claim.type:
                reclassified_count += 1
                logger.debug(f"Reclassified claim from {claim.type} to {new_type}: {classification_reason}")
            
            # Add metadata about fact-checking appropriateness
            claim.type = new_type
            claim.should_fact_check = should_fact_check
            claim.classification_reason = classification_reason
            
            valid_claims.append(claim)
        
        logger.info(f"Claim filtering results:")
        logger.info(f"  Original claims: {len(claims)}")
        logger.info(f"  Excluded: {excluded_count}")
        logger.info(f"  Reclassified: {reclassified_count}")
        logger.info(f"  Valid claims: {len(valid_claims)}")
        
        return valid_claims
