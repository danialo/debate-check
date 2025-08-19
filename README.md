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

### 🆕 YouTube/Podcast Transcript Processing
- **Smart Chunking**: Intelligently breaks long transcripts into logical segments
- **Speaker Inference**: Identifies speakers using name mentions and linguistic patterns
- **Claim Clustering**: Groups related claims by topic and argumentative stance
- **Context Preservation**: Maintains claim context across transcript segments

### ✨ **NEW**: Fact-Checking Integration
- **Multi-Service Verification**: Integrates Google Fact Check Tools API and local database
- **Credibility Scoring**: Assigns verification scores and confidence ratings to claims
- **Source Attribution**: Links verified claims to credible fact-checking sources
- **Aggregated Results**: Combines multiple verification sources for comprehensive scoring

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

### Example 5: 🆕 YouTube/Long Transcript Processing
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

### JSON Structure
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

## 📝 Roadmap

### ✅ Completed
- [x] **Claims extraction pipeline** - Core 5-type claim detection
- [x] **Smart transcript chunking** - YouTube/podcast transcript handling
- [x] **Speaker inference** - Automatic speaker identification from context
- [x] **Claim clustering** - Groups related claims by topic and stance
- [x] **Enhanced JSON output** - Rich metadata and analysis
- [x] **Fact-checking integration** - Multi-service verification with Google Fact Check Tools and local database

### 🚧 In Progress
- [ ] **Logical fallacy detection** - Pattern recognition for common fallacies

### 🎯 Planned
- [ ] **Multi-dimensional scoring** - Your comprehensive debate scoring system
- [ ] **Audio processing** - Direct YouTube URL to claims pipeline
- [ ] **Web interface** - User-friendly GUI for transcript upload/analysis
- [ ] **Real-time analysis** - Live debate scoring and visualization
