#!/usr/bin/env python3
"""
Web interface for Debate Claim Extractor
Provides a clean, simple interface for transcript analysis
"""

import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from debate_claim_extractor.pipeline.pipeline import ClaimExtractionPipeline
from debate_claim_extractor.pipeline.enhanced_pipeline import EnhancedClaimExtractionPipeline
from debate_claim_extractor.pipeline.youtube_pipeline import YouTubePipeline
from debate_claim_extractor.fact_checking import FactCheckConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'debate-analysis-secret-key'  # Change in production

# Configuration
DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

def should_use_youtube_pipeline(text: str) -> bool:
    """Determine if text should use YouTube pipeline"""
    # Same logic as CLI
    if len(text) > 2000:
        return True
    
    lines = text.strip().split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    
    if len(non_empty_lines) <= 2:
        return True
    
    speaker_pattern_lines = 0
    for line in non_empty_lines[:10]:
        line = line.strip()
        if (':' in line and 
            (line.split(':', 1)[0].isupper() or 
             line.startswith('[') or 
             line.startswith('('))):
            speaker_pattern_lines += 1
    
    speaker_ratio = speaker_pattern_lines / len(non_empty_lines[:10])
    return speaker_ratio < 0.3

import asyncio

async def run_comprehensive_analysis_async(text: str, analysis_id: str) -> dict:
    """Run comprehensive analysis on transcript text"""
    try:
        logger.info(f"Starting analysis {analysis_id} for {len(text)} characters")
        
        # Configure fact-checking (disabled for web to avoid asyncio conflicts)
        # TODO: Fix asyncio.run() conflicts in enhanced pipeline  
        fact_config = FactCheckConfig(
            enabled=False,  # Temporarily disabled due to asyncio conflicts
            timeout_seconds=10,
            google_fact_check={'enabled': False, 'api_key': None},
            local_database={'enabled': False, 'database_path': None}
        )
        
        # Choose appropriate pipeline
        if should_use_youtube_pipeline(text):
            logger.info("Using YouTube-enhanced pipeline")
            pipeline = YouTubePipeline()
            result_data = await pipeline.extract_with_comprehensive_analysis(
                text, 
                source=f"web_analysis_{analysis_id}",
                fact_config=fact_config
            )
        else:
            logger.info("Using enhanced pipeline with intelligent filtering")
            pipeline = EnhancedClaimExtractionPipeline(enable_filtering=True)
            # Enhanced pipeline is synchronous
            result_obj = pipeline.extract_with_comprehensive_analysis(
                text, 
                source=f"web_analysis_{analysis_id}",
                fact_config=fact_config
            )
            result_data = result_obj.model_dump()
        
        logger.info(f"Analysis {analysis_id} completed successfully")
        return {
            'success': True,
            'result': result_data,
            'error': None
        }
        
    except Exception as e:
        logger.error(f"Analysis {analysis_id} failed: {e}", exc_info=True)
        return {
            'success': False,
            'result': None,
            'error': str(e)
        }

def save_analysis_result(analysis_id: str, text: str, result: dict) -> None:
    """Save analysis result to local storage"""
    analysis_data = {
        'id': analysis_id,
        'timestamp': datetime.now().isoformat(),
        'input_text': text,
        'input_length': len(text),
        'analysis_result': result
    }
    
    def json_serializer(obj):
        """Custom JSON serializer for non-serializable objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
    
    file_path = DATA_DIR / f"{analysis_id}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False, default=json_serializer)
    
    logger.info(f"Saved analysis result to {file_path}")

def load_analysis_result(analysis_id: str) -> dict:
    """Load analysis result from local storage"""
    file_path = DATA_DIR / f"{analysis_id}.json"
    if not file_path.exists():
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_recent_analyses(limit: int = 10) -> list:
    """Get list of recent analyses"""
    analyses = []
    
    for file_path in DATA_DIR.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                analyses.append({
                    'id': data['id'],
                    'timestamp': data['timestamp'],
                    'input_length': data.get('input_length', 0),
                    'claims_count': len(data.get('analysis_result', {}).get('result', {}).get('claims', [])),
                    'success': data.get('analysis_result', {}).get('success', False)
                })
        except Exception as e:
            logger.warning(f"Error loading analysis from {file_path}: {e}")
    
    # Sort by timestamp, most recent first
    analyses.sort(key=lambda x: x['timestamp'], reverse=True)
    return analyses[:limit]

@app.route('/debug')
def debug():
    """Simple debug endpoint"""
    return {
        'status': 'working',
        'message': 'Flask is running correctly',
        'data_dir': str(DATA_DIR),
        'project_root': str(project_root)
    }

@app.route('/')
def home():
    """Home page with transcript input form"""
    try:
        recent_analyses = get_recent_analyses()
        logger.info(f"Found {len(recent_analyses)} recent analyses")
    except Exception as e:
        logger.error(f"Error getting recent analyses: {e}")
        recent_analyses = []  # Fallback to empty list
    
    return render_template('home.html', recent_analyses=recent_analyses)

@app.route('/analyze', methods=['POST'])
def analyze():
    """Process transcript analysis"""
    text = request.form.get('transcript', '').strip()
    
    if not text:
        flash('Please enter a transcript to analyze.', 'error')
        return redirect(url_for('home'))
    
    if len(text) < 50:
        flash('Transcript is too short. Please enter a longer text for meaningful analysis.', 'warning')
        return redirect(url_for('home'))
    
    # Generate unique analysis ID
    analysis_id = str(uuid.uuid4())[:8]
    
    # Run comprehensive analysis
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        analysis_result = loop.run_until_complete(run_comprehensive_analysis_async(text, analysis_id))
    finally:
        loop.close()
    
    # Save result to local storage
    save_analysis_result(analysis_id, text, analysis_result)
    
    if analysis_result['success']:
        flash('Analysis completed successfully!', 'success')
    else:
        flash(f'Analysis failed: {analysis_result["error"]}', 'error')
    
    return redirect(url_for('results', analysis_id=analysis_id))

@app.route('/results/<analysis_id>')
def results(analysis_id):
    """Display analysis results"""
    analysis_data = load_analysis_result(analysis_id)
    
    if not analysis_data:
        flash('Analysis not found.', 'error')
        return redirect(url_for('home'))
    
    return render_template('results.html', 
                         analysis_id=analysis_id,
                         analysis_data=analysis_data)

@app.route('/api/analysis/<analysis_id>')
def api_analysis(analysis_id):
    """API endpoint to get analysis data as JSON"""
    analysis_data = load_analysis_result(analysis_id)
    
    if not analysis_data:
        return jsonify({'error': 'Analysis not found'}), 404
    
    return jsonify(analysis_data)

@app.route('/recent')
def recent_analyses():
    """Show list of recent analyses"""
    recent = get_recent_analyses(20)
    return render_template('recent.html', analyses=recent)

if __name__ == '__main__':
    print("Starting Debate Analysis Web Interface...")
    print(f"Data storage: {DATA_DIR}")
    app.run(debug=True, host='0.0.0.0', port=8080)
