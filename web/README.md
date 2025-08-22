# Debate Analysis Web Interface

A clean, professional web interface for comprehensive debate analysis.

## 🚀 Quick Start

### Method 1: Bash Script (Recommended)
```bash
cd /home/d/Git/debate-check
./start_web.sh
```

### Method 2: Python Script
```bash
cd /home/d/Git/debate-check
python run_web.py
```

### Method 3: Direct Flask Run
```bash
cd /home/d/Git/debate-check/web
export PYTHONPATH="$(pwd)/..":$PYTHONPATH
python app.py
```

## 🌐 Access

Once started, open your browser to:
- **http://127.0.0.1:8080** (or the port shown in terminal)

## ✨ Features

- **One-Click Analysis**: Paste transcript → Click Analyze → Get comprehensive results
- **Multi-Dimensional Scoring**: Overall debate score with 4 dimension breakdowns
- **Claim Extraction**: Identifies factual, statistical, causal claims with confidence
- **Fact-Checking**: Wikipedia + local database verification with status indicators  
- **Fallacy Detection**: Logical fallacy identification with explanations
- **Speaker Analysis**: Individual performance and credibility scores
- **Local Storage**: All analyses saved locally for future reference
- **Clean UI**: Professional design with responsive layout

## 🎯 Usage Workflow

1. **Paste Transcript** - Any debate format (structured or YouTube-style)
2. **Click "Analyze Transcript"** - Runs comprehensive analysis automatically
3. **View Results** - Rich display with scoring, claims, fact-checks, fallacies
4. **Browse History** - Access previous analyses anytime

## 🔧 Troubleshooting

### Port Issues
If you see "Address already in use" errors:

```bash
# Kill existing Flask processes
pkill -f "python.*app.py"

# Or kill all Python processes (be careful!)
pkill python

# Then try starting again
./start_web.sh
```

### Import Errors
If you see module import errors:

```bash
# Make sure you're in the project root
cd /home/d/Git/debate-check

# Activate virtual environment if you have one
source venv/bin/activate

# Check that the debate_claim_extractor module is available
python -c "import debate_claim_extractor; print('✅ Module imports OK')"
```

### Permission Errors
If you can't execute the scripts:

```bash
chmod +x start_web.sh
chmod +x run_web.py
chmod +x start_web_interface.py
```

## 📊 What You'll See

### Home Page
- Clean textarea for transcript input
- Recent analyses list
- Feature explanation

### Results Page
- **Debate Score Summary**: Overall score + 4 dimensions
- **Speaker Performance**: Individual credibility scores
- **Claims List**: Each claim with confidence bar and fact-check status
- **Fallacies**: Detected logical fallacies with explanations
- **Analysis Details**: Processing metadata and pipeline info

## 🗃️ Data Storage

All analyses are saved as JSON files in:
```
web/data/
├── {analysis-id-1}.json
├── {analysis-id-2}.json
└── ...
```

Each file contains:
- Original input text
- Complete analysis results
- Timestamp and metadata
- All scoring, fact-checking, and fallacy data

## 🔗 API Access

Programmatic access available via:
- `GET /api/analysis/{analysis_id}` - Get analysis results as JSON

## 🛠️ Technical Details

- **Framework**: Flask with Jinja2 templates
- **Storage**: Local JSON files
- **Pipeline**: Automatic selection (standard vs YouTube-enhanced)
- **Analysis**: Full integration with comprehensive analysis pipeline
- **Styling**: Clean, professional CSS with responsive design

## 📝 Example Transcripts

### Structured Format
```
SPEAKER A: Climate change is caused primarily by human activities.
SPEAKER B: I disagree. Climate change is natural throughout history.
SPEAKER A: The current rate of warming is unprecedented.
```

### YouTube/Podcast Format
```
so I think climate change is real and caused by humans but my guest today disagrees completely he thinks it's all natural cycles so let's get into this debate about what's really causing global warming...
```

Both formats work automatically - the system detects the format and processes accordingly.
