# Logical Fallacy Detection System Design

This document outlines the design and implementation strategy for detecting logical fallacies in debate transcripts.

## Overview

Logical fallacies are errors in reasoning that weaken arguments. Our system will identify common fallacies that appear in political debates, discussions, and argumentative text.

## Target Fallacy Categories

### 1. Ad Hominem Attacks
**Definition**: Attacking the person making the argument rather than the argument itself.

**Patterns to Detect:**
- Personal insults or character attacks
- References to irrelevant personal characteristics
- Dismissing arguments based on who made them

**Language Patterns:**
```python
personal_attack_patterns = [
    r'\b(?:you|he|she|they)\s+(?:are|is)\s+(?:a|an|just|nothing but|always)\s+\w+',
    r'\b(?:typical|classic)\s+\w+\s+(?:response|answer|behavior)',
    r'\bcoming from (?:you|him|her|them|someone who)',
    r'\b(?:hypocrite|liar|fraud|corrupt|dishonest)\b',
    r'\bwhat (?:do you|does he|does she) know about'
]
```

**Examples:**
- "You're just a corrupt politician"
- "Coming from someone who's never held a real job"
- "That's typical liberal nonsense"

### 2. Straw Man Fallacy
**Definition**: Misrepresenting someone's argument to make it easier to attack.

**Patterns to Detect:**
- Extreme oversimplification of opponent's position
- "So you're saying..." followed by distortion
- False characterization of positions

**Language Patterns:**
```python
straw_man_patterns = [
    r'\bso (?:you\'re|he\'s|she\'s|they\'re) saying\b',
    r'\bwhat (?:you|he|she|they) (?:want|believe|think) is\b',
    r'\b(?:you|he|she|they) (?:want to|would) (?:destroy|eliminate|ban|get rid of)\b',
    r'\baccording to (?:you|him|her|them), (?:we should|everyone should)\b'
]
```

**Examples:**
- "So you're saying we should just open all the borders?"
- "What you want is to destroy the economy"
- "According to them, we should just give up on security"

### 3. False Dilemma/False Dichotomy
**Definition**: Presenting only two options when more exist.

**Patterns to Detect:**
- "Either... or..." constructions
- "Only two choices" language
- Binary thinking indicators

**Language Patterns:**
```python
false_dilemma_patterns = [
    r'\beither\s+.+\s+or\s+.+',
    r'\bonly (?:two|2) (?:choices|options|ways)\b',
    r'\b(?:you\'re|it\'s) either\s+.+\s+or\s+.+',
    r'\bthere are only (?:two|2) (?:options|choices|possibilities)\b',
    r'\bif (?:you\'re not|we don\'t).+then (?:you\'re|we\'re|you must be)\b'
]
```

**Examples:**
- "Either you support this bill or you hate America"
- "You're either with us or against us"
- "There are only two choices: freedom or socialism"

### 4. Appeal to Authority (Inappropriate)
**Definition**: Using authority figures inappropriately to support arguments.

**Patterns to Detect:**
- Citations of irrelevant authorities
- Appeals to popularity/celebrity
- Vague authority references

**Language Patterns:**
```python
appeal_to_authority_patterns = [
    r'\baccording to (?:many|most|all) (?:experts|scientists|doctors)\b',
    r'\b(?:everyone|everybody) (?:knows|agrees|says)\b',
    r'\ba (?:famous|well-known|prominent) \w+ said\b',
    r'\bstudies show\b(?! (?:specific|clear|detailed))',
    r'\bit\'s (?:common knowledge|widely known|obvious) that\b'
]
```

**Examples:**
- "According to many experts, this is wrong"
- "A famous scientist said this policy is bad"
- "Everyone knows that's not true"

### 5. Slippery Slope
**Definition**: Arguing that one event will lead to a chain of negative events.

**Patterns to Detect:**
- Chain reaction predictions
- Extreme consequence warnings
- "This will lead to..." constructions

**Language Patterns:**
```python
slippery_slope_patterns = [
    r'\bif we (?:allow|permit|do) this.+(?:then|next).+(?:will|would)\b',
    r'\bthis (?:will|would) lead to\b',
    r'\b(?:before you know it|next thing you know|soon)\b',
    r'\bonce we start.+(?:where does it end|there\'s no stopping)\b',
    r'\bthis is (?:just the beginning|the first step) (?:of|to|toward)\b'
]
```

**Examples:**
- "If we allow this, next thing you know they'll ban everything"
- "This will lead to the complete destruction of our freedoms"
- "Once we start down this path, there's no stopping"

### 6. Red Herring
**Definition**: Introducing irrelevant information to distract from the main issue.

**Patterns to Detect:**
- Topic shifts mid-argument
- Irrelevant tangential information
- "But what about..." deflections

**Language Patterns:**
```python
red_herring_patterns = [
    r'\bbut what about\b',
    r'\bspeaking of\b(?! (?:which|this|that))',
    r'\bthat reminds me\b',
    r'\bwhile we\'re (?:on the topic|talking about)\b',
    r'\bthat\'s not the real (?:issue|problem|question)\b'
]
```

**Examples:**
- "But what about the other candidate's emails?"
- "That reminds me of what happened in 2016"
- "Speaking of corruption, look at their voting record"

### 7. Appeal to Emotion (Inappropriate)
**Definition**: Using emotional manipulation instead of logical reasoning.

**Patterns to Detect:**
- Excessive emotional language
- Fear-mongering
- Pity appeals

**Language Patterns:**
```python
appeal_to_emotion_patterns = [
    r'\bthink (?:of|about) the (?:children|families|victims)\b',
    r'\b(?:imagine|picture) if (?:this|that) were your\b',
    r'\bwe (?:can\'t|cannot) allow (?:this|that) to (?:happen|continue)\b',
    r'\bthe (?:future|safety|security) of (?:our|America|democracy) (?:depends|hangs)\b',
    r'\b(?:dangerous|scary|terrifying|devastating) (?:consequences|results|effects)\b'
]
```

**Examples:**
- "Think of the children who will suffer"
- "Imagine if this were your family"
- "The future of America depends on stopping this"

## Architecture Design

### Core Components

```python
class FallacyType(Enum):
    AD_HOMINEM = "ad_hominem"
    STRAW_MAN = "straw_man"
    FALSE_DILEMMA = "false_dilemma"
    APPEAL_TO_AUTHORITY = "appeal_to_authority"
    SLIPPERY_SLOPE = "slippery_slope"
    RED_HERRING = "red_herring"
    APPEAL_TO_EMOTION = "appeal_to_emotion"
    BANDWAGON = "bandwagon"
    CIRCULAR_REASONING = "circular_reasoning"
    HASTY_GENERALIZATION = "hasty_generalization"
```

### Detection Pipeline

```
Input Text/Claims 
    ↓
Preprocessing
    ↓
Individual Fallacy Detectors (parallel)
    ↓
Confidence Scoring
    ↓
Context Analysis
    ↓
Fallacy Results Integration
    ↓
Output with Fallacy Annotations
```

### Integration with Existing Pipeline

The fallacy detection will integrate seamlessly with the existing claim extraction:

```python
class Claim:
    # Existing fields...
    fallacies: List[FallacyResult] = None
    fallacy_score: float = None  # Overall fallacy confidence
```

## Detection Methodology

### 1. Pattern-Based Detection
- Regular expressions for linguistic patterns
- Keyword matching for fallacy indicators
- Sentence structure analysis

### 2. Context-Aware Analysis
- Consider surrounding sentences
- Analyze speaker interactions
- Detect argument flow disruptions

### 3. Confidence Scoring
Each fallacy detection will have a confidence score based on:
- Pattern strength and specificity
- Context relevance
- Multiple pattern matches
- Linguistic certainty indicators

### 4. Multi-Detector Approach
Similar to claim detection, multiple specialized detectors will run in parallel:
- `AdHominemDetector`
- `StrawManDetector`
- `FalseDilemmaDetector`
- etc.

## Confidence Scoring for Fallacies

### High Confidence (0.8+)
- Multiple strong patterns detected
- Clear fallacy structure
- Unambiguous context

### Medium Confidence (0.5-0.8)
- Single strong pattern or multiple weak patterns
- Some contextual support
- Minor ambiguity

### Low Confidence (0.3-0.5)
- Weak patterns or limited context
- Possible alternative interpretations
- Requires human verification

## Implementation Strategy

### Phase 1: Core Detectors
Implement the top 5 most common fallacies:
1. Ad Hominem
2. Straw Man
3. False Dilemma
4. Appeal to Authority
5. Slippery Slope

### Phase 2: Advanced Detectors
Add more sophisticated fallacies:
6. Red Herring
7. Appeal to Emotion
8. Bandwagon
9. Circular Reasoning
10. Hasty Generalization

### Phase 3: Context Enhancement
- Cross-claim analysis
- Speaker pattern recognition
- Argument flow analysis

## Output Format

```json
{
  "claims": [...],
  "fallacies": [
    {
      "id": "fallacy_uuid",
      "type": "ad_hominem",
      "text": "You're just a corrupt politician who doesn't understand business",
      "target_claim_id": "claim_uuid",
      "speaker": "CANDIDATE_A",
      "confidence": 0.85,
      "patterns_matched": ["personal_attack", "character_dismissal"],
      "context": "Response to economic policy proposal",
      "explanation": "Personal attack on character rather than addressing the policy argument",
      "severity": "high"
    }
  ],
  "fallacy_summary": {
    "total_fallacies": 5,
    "by_type": {
      "ad_hominem": 2,
      "straw_man": 2,
      "false_dilemma": 1
    },
    "by_speaker": {
      "CANDIDATE_A": 3,
      "CANDIDATE_B": 2
    },
    "average_confidence": 0.72
  }
}
```

## Evaluation and Validation

### Manual Annotation
Create a dataset of manually annotated debate excerpts with known fallacies for validation.

### Precision/Recall Metrics
Track detection accuracy:
- True positives: Correctly identified fallacies
- False positives: Incorrectly flagged statements
- False negatives: Missed fallacies

### Expert Review
Have logic/philosophy experts review detection results for accuracy.

## Future Enhancements

### 1. Machine Learning Integration
- Train classifiers on annotated fallacy data
- Use embeddings for semantic fallacy detection
- Implement active learning for continuous improvement

### 2. Argument Structure Analysis
- Map argument chains and relationships
- Detect structural fallacies beyond pattern matching
- Analyze logical flow and coherence

### 3. Domain-Specific Tuning
- Political debate patterns
- Scientific discussion fallacies
- Legal argument analysis

### 4. Real-Time Scoring
- Live fallacy detection during debates
- Instantaneous confidence updates
- Interactive fallacy explanations

This comprehensive fallacy detection system will significantly enhance the analytical power of the debate claim extractor, providing users with deep insights into argument quality and logical reasoning patterns.
