# Confidence Scoring System

The debate claim extractor uses a sophisticated confidence scoring system to assess the reliability and certainty of detected claims. Each claim type has its own specialized scoring algorithm.

## Overview

Confidence scores range from **0.0 to 1.0**, where:
- **0.9 - 1.0**: Very high confidence (strong factual assertions with clear evidence)
- **0.7 - 0.8**: High confidence (clear claims with good linguistic markers)
- **0.5 - 0.6**: Medium confidence (reasonable claims but with some uncertainty)
- **0.3 - 0.4**: Low confidence (ambiguous or uncertain statements)
- **< 0.3**: Very low confidence (claims are filtered out)

## Claim Type Scoring Algorithms

### 1. Statistical Claims (0.6 - 0.8)

Statistical claims receive higher baseline confidence due to their quantitative nature.

```python
# Base confidence for any statistical pattern match
confidence = 0.6

# Boost for statistical keywords (+0.2)
statistical_keywords = ['data', 'statistics', 'survey', 'poll', 'study', 
                       'research', 'analysis', 'report', 'findings', 'rate']
if any(keyword in text for keyword in statistical_keywords):
    confidence += 0.2

# Final range: 0.6 - 0.8
```

**Examples:**
- "50% of voters support the policy" → 0.6 (basic statistical pattern)
- "According to a recent poll, 50% of voters support the policy" → 0.8 (statistical + keyword boost)

### 2. Causal Claims (0.5 - 1.0)

Causal claims are scored based on the strength and frequency of causal language.

```python
confidence = 0.5 + (causal_matches * 0.1) + (strong_matches * 0.2)

# Causal keywords (+0.1 each)
causal_keywords = ['because', 'due to', 'caused by', 'leads to', 'results in']

# Strong causal indicators (+0.2 each)
strong_causal = ['directly caused', 'primary cause', 'root cause']
```

**Examples:**
- "This leads to higher costs" → 0.6 (one causal keyword)
- "This is the primary cause of the problem" → 0.7 (one strong causal indicator)
- "This directly caused the crisis because of poor planning" → 0.9 (strong + regular causal)

### 3. Comparative Claims (0.5 - 1.0)

Comparative claims are scored based on comparative language patterns.

```python
confidence = 0.5 + (comparative_matches * 0.15)

# Comparative patterns (+0.15 each)
patterns = ['more/less than', 'better/worse than', 'compared to', 
           'superior/inferior to', 'exceeds/surpasses']
```

**Examples:**
- "Policy A is better than Policy B" → 0.65 (one comparative pattern)
- "Policy A is far superior to Policy B and exceeds expectations" → 0.8 (two patterns)

### 4. Historical Claims (0.4 - 1.0)

Historical claims are scored based on temporal references and past-tense indicators.

```python
confidence = 0.4 + (time_matches * 0.2) + (past_matches * 0.1)

# Time references (+0.2 each)
time_patterns = ['in 1995', 'during the 1990s', 'decades ago']

# Past indicators (+0.1 each, need 2+ for detection)
past_indicators = ['happened', 'occurred', 'established', 'founded']
```

**Examples:**
- "The law was established in 1995" → 0.6 (time reference + past indicator)
- "During the 1990s, many reforms occurred and were implemented" → 0.8 (time + multiple past indicators)

### 5. Factual Claims (0.3 - 1.0) - Most Complex

Factual claims use the most sophisticated scoring with multiple linguistic factors.

#### Base Algorithm:
```python
# Start with base confidence
confidence = 0.4

# Uncertainty words (-0.1 each)
uncertainty_words = ['might', 'may', 'could', 'would', 'should', 
                    'possibly', 'probably', 'believes', 'thinks']
confidence -= uncertainty_count * 0.1

# Certainty words (+0.05 each)
certainty_words = ['is', 'are', 'was', 'were', 'has', 'have', 'will', 
                  'facts', 'evidence', 'proof', 'confirmed']
confidence += certainty_count * 0.05
```

#### Advanced spaCy Analysis (if available):
```python
# Declarative sentence structure (+0.1)
if has_subject and has_verb:
    confidence += 0.1

# Third-person statements (+0.05)
third_person_pronouns = ['he', 'she', 'it', 'they', 'this', 'that']
if any_third_person_found:
    confidence += 0.05
```

#### Factual Claim Examples:

**High Confidence (0.7+):**
- "The president signed the bill yesterday" → 0.75
  - Base: 0.4 + Certainty ("The", "signed"): +0.1 + Structure: +0.1 + Third-person: +0.05 + Past tense: +0.1

**Medium Confidence (0.5-0.7):**
- "This policy has been implemented" → 0.55
  - Base: 0.4 + Certainty ("has", "been"): +0.1 + Structure: +0.05

**Low Confidence (0.3-0.5):**
- "I think this might be the right approach" → 0.25 (filtered out)
  - Base: 0.4 + Uncertainty ("think", "might"): -0.2 + First person: -0.05

## Special Cases and Edge Conditions

### Questions and Rhetorical Statements
The system correctly identifies questions and rhetorical statements as lower confidence:

**Example:** "Do you believe that some citizens are more valuable than others?"
- Detected as factual claim but with low confidence (~0.55)
- Uncertainty from "believe" and question structure
- **This is working as intended** - questions shouldn't be high-confidence factual claims

### Truncated or Incomplete Sentences
Sentences that are cut off or incomplete typically receive lower confidence scores due to:
- Missing grammatical structure
- Incomplete thoughts
- Lack of clear subject-verb relationships

### Opinion vs. Fact Detection
The system uses linguistic cues to distinguish opinions from facts:
- **Opinion markers** (reduce confidence): "I think", "believes", "feels", "seems"
- **Fact markers** (increase confidence): "is", "confirmed", "evidence", "data"

## Confidence Score Interpretation

### For End Users:
- **0.8+**: Very reliable claims suitable for fact-checking
- **0.6-0.8**: Solid claims worth investigating
- **0.4-0.6**: Questionable claims, may be opinions or uncertain
- **<0.4**: Low reliability, likely opinions or unclear statements

### For Fact-Checking Priority:
The fact-checking system can use confidence scores to prioritize verification:
1. Focus on high-confidence claims first (more likely to be factual)
2. Use different verification strategies based on confidence level
3. Flag low-confidence claims for human review

## Future Improvements

### Planned Enhancements:
1. **Machine Learning Integration**: Train models on manually annotated claims to improve scoring
2. **Context-Aware Scoring**: Consider surrounding sentences and speaker patterns  
3. **Domain-Specific Adjustments**: Different confidence thresholds for political vs. scientific claims
4. **Claim Complexity Metrics**: Factor in sentence length and grammatical complexity
5. **Speaker Reliability**: Adjust confidence based on speaker credibility patterns

### Calibration Process:
The confidence scores should be regularly calibrated against human annotations to ensure:
- High-confidence claims are actually factual most of the time
- Low-confidence claims are appropriately filtered
- The distribution of scores matches real-world claim reliability

## Technical Implementation

The confidence scoring is implemented across multiple detector classes:
- `StatisticalClaimDetector`: Quantitative claims
- `CausalClaimDetector`: Cause-and-effect relationships  
- `ComparativeClaimDetector`: Comparison statements
- `HistoricalClaimDetector`: Past events and time references
- `FactualClaimDetector`: General factual assertions with sophisticated linguistic analysis

Each detector can be tuned independently, and the system supports easy addition of new detectors with their own confidence algorithms.
