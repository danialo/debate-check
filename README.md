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

This initial version focuses on identifying and categorizing different types of claims:

- **Factual Claims**: Objective statements that can be verified
- **Statistical Claims**: Numerical data and percentages  
- **Causal Claims**: Cause-and-effect relationships
- **Comparative Claims**: Comparisons between entities
- **Historical Claims**: References to past events

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

### Tips for Best Results
1. **Clear Speaker Labels**: Use consistent `SPEAKER:` format
2. **Complete Sentences**: The system works better with full sentences
3. **Remove Timestamps**: The preprocessor handles basic cleanup, but manual removal of complex timestamps helps
4. **Stage Directions**: Basic stage directions like `(applause)` are automatically removed

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

- [x] Claims extraction pipeline
- [ ] Fact-checking integration
- [ ] Logical fallacy detection
- [ ] Multi-dimensional scoring
- [ ] Audio processing (speech-to-text)
- [ ] Web interface
- [ ] Real-time analysis
