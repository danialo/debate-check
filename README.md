# Debate Check - Claims Extraction Pipeline

A text analysis tool for extracting factual claims from debate transcripts. This tool forms the foundation for a comprehensive debate analysis platform that will eventually include fact-checking, logical fallacy detection, and multi-dimensional scoring.

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-username/debate-check.git
cd debate-check

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install the package
pip install -e .

# 4. Run on sample data
python -m debate_claim_extractor --input sample_transcript.txt --output claims.json
```

## 📋 Features

### Core Claim Detection
Identifies and categorizes different types of claims:

- **Factual Claims**: Objective statements that can be verified
- **Statistical Claims**: Numerical data and percentages  
- **Causal Claims**: Cause-and-effect relationships
- **Comparative Claims**: Comparisons between entities
- **Historical Claims**: References to past events

#### Confidence Scoring
Each claim is assigned a confidence score (0.0-1.0) based on linguistic patterns:
- **High (0.7-1.0)**: Strong factual statements with clear markers
- **Medium (0.5-0.7)**: Reasonable claims with some uncertainty
- **Low (0.3-0.5)**: Ambiguous or uncertain statements
Detailed documentation on confidence scoring is available in [docs/confidence_scoring.md](docs/confidence_scoring.md).

### 🆕 YouTube/Podcast Transcript Processing
- **Smart Chunking**: Intelligently breaks long transcripts into logical segments
- **Speaker Inference**: Identifies speakers using name mentions and linguistic patterns
- **Claim Clustering**: Groups related claims by topic and argumentative stance
- **Context Preservation**: Maintains claim context across transcript segments

### ✨ **NEW**: Fact-Checking Integration
- **Multi-Service Verification**: Integrates Google Fact Check Tools API, Wikipedia, and local database
- **Credibility Scoring**: Assigns verification scores and confidence ratings to claims
- **Source Attribution**: Links verified claims to credible fact-checking sources
- **Aggregated Results**: Combines multiple verification sources for comprehensive scoring

### 🔥 **NEW**: Logical Fallacy Detection
- **5 Core Fallacy Types**: Detects Ad Hominem, Straw Man, False Dilemma, Appeal to Authority, and Slippery Slope
- **Pattern Recognition**: Uses advanced regex patterns and linguistic analysis
- **Confidence Scoring**: Assigns confidence levels (High/Medium/Low) based on pattern strength
- **Contextual Analysis**: Links fallacies to specific claims and speakers
- **Severity Assessment**: Rates fallacy severity and provides explanations

### 🚀 **NEW**: Full Analysis Mode
- **Combined Pipeline**: Single command runs both fact-checking and fallacy detection
- **Comprehensive Results**: Unified output with verification scores and fallacy identification
- **Cross-Referenced Analysis**: Links fact-check results with detected logical fallacies

## 🔧 Setup Instructions

### 1. Navigate to the Project Directory
```bash
cd /path/to/debate-check
```

### 2. Create and Activate the Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` appear in your terminal prompt, indicating the virtual environment is active.

### 3. Install the Package
```bash
pip install -e .
```

### 4. Verify Installation
```bash
python -m debate_claim_extractor --help
```

## 🚀 Usage Examples

### Example 1: Process the Sample Healthcare Debate
```bash
python -m debate_claim_extractor --input sample_transcript.txt --output healthcare_claims.json
```

This will:
- Read the sample healthcare debate transcript
- Extract claims and categorize them
- Save structured results to `healthcare_claims.json`
- Display progress in the terminal

### Example 2: Quick Test with Simple Input
```bash
python -m debate_claim_extractor --input test_input.txt
```

This processes the short test file and displays results directly in the terminal.

### Example 3: Process from Standard Input (Pipe)
```bash
echo "SPEAKER A: Unemployment decreased by 15% last year. SPEAKER B: That's false - it only decreased by 8% according to BLS data." | python -m debate_claim_extractor
```

### Example 4: Verbose Mode for Debugging
```bash
python -m debate_claim_extractor --input sample_transcript.txt --verbose
```

This shows detailed processing information including:
- Speaker identification
- Sentence segmentation counts
- Claim detection by type
- Post-processing steps

### Example 4b: 🔥 **NEW**: Fact-Checking with Local Database
```bash
python -m debate_claim_extractor --input sample_transcript.txt --fact-check --verbose
```

This enables fact-checking using the built-in local database, which includes:
- Pre-verified claims about vaccines, climate change, unemployment data
- Automatic similarity matching to find related fact-checks
- Verification scores and source attribution

### Example 4c: 🔥 **NEW**: Fact-Checking with Google API
```bash
# Set your Google Fact Check Tools API key
export GOOGLE_FACT_CHECK_API_KEY="your-api-key-here"

# Run with both Google API and local database
python -m debate_claim_extractor --input sample_transcript.txt --fact-check --google-api-key $GOOGLE_FACT_CHECK_API_KEY --verbose
```

This enables comprehensive fact-checking using:
- Google Fact Check Tools API for professional fact-checkers
- Local database for common claims
- Aggregated verification scores from multiple sources

### Example 5: 🔥 **NEW**: Logical Fallacy Detection
```bash
python -m debate_claim_extractor --input sample_transcript.txt --fallacy-detection --verbose
```

This enables logical fallacy detection, which identifies:
- **Ad Hominem**: Personal attacks instead of addressing arguments
- **Straw Man**: Misrepresenting opponent's position
- **False Dilemma**: Presenting only two options when more exist
- **Appeal to Authority**: Inappropriate appeals to vague or irrelevant authorities
- **Slippery Slope**: Claiming one event will lead to extreme consequences

### Example 6: 🚀 **NEW**: Full Analysis Mode (Fact-Checking + Fallacy Detection)
```bash
# Complete analysis with both fact-checking and fallacy detection
python -m debate_claim_extractor --input sample_transcript.txt --full-analysis --verbose

# Alternative: Enable both features explicitly
python -m debate_claim_extractor --input sample_transcript.txt --fact-check --fallacy-detection --verbose
```

This comprehensive analysis provides:
- **Claim extraction** with confidence scoring
- **Fact verification** using multiple sources (Wikipedia, local database, Google API if available)
- **Fallacy detection** with pattern matching and severity assessment
- **Cross-referenced results** linking claims to verification status and detected fallacies

### Example 7: 🆕 YouTube/Long Transcript Processing
```bash
# Test with the enhanced YouTube pipeline
cd /path/to/debate-check
source venv/bin/activate
python test_youtube_pipeline.py
```

For long transcripts (>2000 characters), the system automatically:
- **Chunks intelligently** at natural conversation boundaries
- **Infers speakers** using name mentions and linguistic patterns
- **Clusters related claims** by topic and stance
- **Preserves context** across chunks

**Sample YouTube Pipeline Output:**
```json
{
  "claims": [...],
  "youtube_enhanced": true,
  "chunks_used": true,
  "chunk_analysis": {
    "total_chunks": 9,
    "avg_chunk_size": 1454,
    "speaker_inference": {
      "CHARLES": 2,
      "NEIL": 3,
      "SPEAKER_A": 3,
      "SPEAKER_B": 1
    }
  },
  "clusters": [
    {
      "id": "cluster_0",
      "type": "causal",
      "stance": "neutral", 
      "claims_count": 8,
      "topics": ["choice", "psychology", "philosophy"],
      "primary_claim": {
        "text": "Representative claim from cluster",
        "confidence": 0.65
      }
    }
  ]
}
```

## 📊 Understanding the Output

### Basic JSON Structure
```json
{
  "claims": [
    {
      "id": "unique-uuid",
      "type": "statistical",
      "text": "Unemployment is at 3.7%",
      "speaker": "CANDIDATE_A",
      "sentence_id": "sent_123",
      "turn_id": 3,
      "char_start": 245,
      "char_end": 265,
      "context": "Previous sentence. Unemployment is at 3.7%. Following sentence.",
      "confidence": 0.85,
      "timestamp": null
    }
  ],
  "meta": {
    "generated_at": "2025-08-17T20:00:00Z",
    "claims_count": 42,
    "speakers": ["MODERATOR", "CANDIDATE_A", "CANDIDATE_B"],
    "claim_types": {
      "factual": 25,
      "statistical": 8,
      "causal": 4,
      "comparative": 3,
      "historical": 2
    },
    "source": "transcript.txt",
    "utterances_processed": 15,
    "sentences_processed": 57,
    "raw_claims_detected": 68
  }
}
```

### 🔥 **NEW**: Full Analysis Output (with Fact-Checking + Fallacy Detection)
```json
{
  "claims": [
    {
      "id": "claim-001",
      "type": "statistical", 
      "text": "Unemployment decreased by 15% last year",
      "speaker": "CANDIDATE_A",
      "confidence": 0.85,
      "fact_check_result": {
        "status": "likely_false",
        "confidence": 0.78,
        "sources": [
          {
            "service": "wikipedia",
            "status": "likely_false",
            "confidence": 0.65,
            "explanation": "Wikipedia articles on unemployment statistics contradict this claim"
          },
          {
            "service": "local_database",
            "status": "verified_false",
            "confidence": 0.90,
            "explanation": "BLS data shows unemployment decreased by only 8% last year"
          }
        ]
      }
    }
  ],
  "fallacies": [
    {
      "id": "fallacy-001",
      "type": "ad_hominem",
      "text": "You can't trust him because he's a typical politician",
      "speaker": "CANDIDATE_B",
      "target_claim_id": "claim-001",
      "confidence": 0.82,
      "severity": "high",
      "patterns_matched": ["personal_attack", "character_dismissal"],
      "explanation": "Ad hominem fallacy: Attacking the person making the argument rather than addressing the argument itself."
    }
  ],
  "meta": {
    "fact_checking_performed": true,
    "fact_checked_claims": 15,
    "fact_checking_services": ["wikipedia", "local_database"],
    "verification_summary": {
      "likely_true": 4,
      "mixed": 6,
      "likely_false": 5
    },
    "fallacy_detection_performed": true,
    "fallacies_detected": 3
  },
  "fallacy_summary": {
    "by_type": {
      "ad_hominem": 1,
      "straw_man": 1,
      "false_dilemma": 1
    },
    "by_severity": {
      "high": 2,
      "medium": 1,
      "low": 0
    },
    "confidence_distribution": {
      "high": 2,
      "medium": 1,
      "low": 0
    }
  }
}
```

### Claim Types Explained
- **Statistical**: Claims with numbers, percentages, data ("GDP grew by 3.2%")
- **Causal**: Cause-and-effect statements ("because", "due to", "leads to")
- **Comparative**: Comparisons between entities ("better than", "more effective")
- **Historical**: References to past events ("In 2019", "since 1995")
- **Factual**: General assertions and statements

## 🎯 Input Format Requirements

### Supported Transcript Formats
The system works best with these speaker formats:

**Standard Format:**
```
SPEAKER NAME: Their statement here.
ANOTHER SPEAKER: Their response.
```

**Variations Supported:**
```
MODERATOR: Question here.
CANDIDATE A: Answer here.
CANDIDATE SMITH: Another answer.
[JONES]: Statement in brackets.
(INTERVIEWER): Statement in parentheses.
```

### 🆕 YouTube/Podcast Transcript Format
**NEW**: The system now handles **long transcripts without speaker labels**!

**YouTube Auto-Transcript Format (Supported):**
```
Charles I want to compare notes okay on free will oh one of my favorite things here's my take it is true that at some level of resolution that we can observe causality is absolutely true given these initial conditions this is what will happen afterwards that's the physicist speaking so if you take it to its logical conclusion then there is no free will because everything is predetermined...
```

The enhanced pipeline automatically:
- ✅ **Chunks** long text into conversation segments
- ✅ **Infers speakers** from name mentions ("Neil", "Charles")
- ✅ **Maintains context** across segments
- ✅ **Groups related claims** into clusters

### Tips for Best Results
1. **Standard Transcripts**: Use consistent `SPEAKER:` format when available
2. **YouTube Transcripts**: System handles continuous text automatically
3. **Complete Sentences**: The system works better with full sentences
4. **Remove Timestamps**: The preprocessor handles basic cleanup
5. **Stage Directions**: Basic stage directions like `(applause)` are automatically removed

## 🔧 Troubleshooting

### Common Issues and Solutions

**Issue: "Command not found"**
```bash
# Make sure you're in the right directory and virtual environment is activated
cd /path/to/debate-check
source venv/bin/activate
```

**Issue: "spaCy model not found" warnings**
This is normal! The system falls back to rule-based processing which works well:
```
WARNING: spaCy English model not found. Install with: python -m spacy download en_core_web_sm
```

To install spaCy model (optional enhancement):
```bash
python -m spacy download en_core_web_sm
```

**Issue: No claims detected**
- Check that your input has clear speaker labels (`SPEAKER:`)
- Try with `--verbose` to see processing details
- Ensure sentences contain factual assertions, not just questions

### Checking Processing Details
Use verbose mode to understand what's happening:
```bash
python -m debate_claim_extractor --input your_file.txt --verbose
```

## 💡 Pro Tips

1. **Pipe to jq for better JSON viewing** (if installed):
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt | jq '.'
   ```

2. **Extract just the claims text**:
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt | jq -r '.claims[].text'
   ```

3. **Count claims by speaker**:
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt | jq '.claims | group_by(.speaker) | .[] | {speaker: .[0].speaker, count: length}'
   ```

4. **Filter high-confidence claims**:
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt | jq '.claims[] | select(.confidence > 0.6)'
   ```

5. **🔥 Extract detected fallacies only**:
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt --fallacy-detection | jq '.fallacies[]'
   ```

6. **🔥 Show fact-check verification status summary**:
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt --fact-check | jq '.meta.verification_summary'
   ```

7. **🚀 Run full analysis and extract only high-severity fallacies**:
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt --full-analysis | jq '.fallacies[] | select(.severity == "high")'
   ```

8. **🚀 Show fact-checked claims with their verification status**:
   ```bash
   python -m debate_claim_extractor --input sample_transcript.txt --fact-check | jq '.claims[] | {text: .text, verification: .fact_check_result.status, confidence: .fact_check_result.confidence}'
   ```

## 📝 Roadmap

### ✅ Completed
- [x] **Claims extraction pipeline** - Core 5-type claim detection
- [x] **Smart transcript chunking** - YouTube/podcast transcript handling
- [x] **Speaker inference** - Automatic speaker identification from context
- [x] **Claim clustering** - Groups related claims by topic and stance
- [x] **Enhanced JSON output** - Rich metadata and analysis
- [x] **Fact-checking integration** - Multi-service verification with Wikipedia, Google API, and local database
- [x] **Logical fallacy detection** - 5 core fallacy types with pattern recognition and confidence scoring
- [x] **Full analysis mode** - Combined fact-checking and fallacy detection pipeline

### 🎯 Planned
- [ ] **Multi-dimensional scoring** - Your comprehensive debate scoring system
- [ ] **Audio processing** - Direct YouTube URL to claims pipeline
- [ ] **Web interface** - User-friendly GUI for transcript upload/analysis
- [ ] **Real-time analysis** - Live debate scoring and visualization
