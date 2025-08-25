#!/usr/bin/env python3
"""
Test Results Viewer
===================

View and compare test results from the organized test_results directory.

Usage:
    python view_test_results.py                    # Show latest results
    python view_test_results.py --list             # List all result files
    python view_test_results.py --file FILENAME    # View specific result file
    python view_test_results.py --compare          # Compare latest vs previous
"""

import json
import argparse
from pathlib import Path
from datetime import datetime


def list_result_files():
    """List all available result files"""
    results_dir = Path("tests/results")
    if not results_dir.exists():
        print("❌ No test_results directory found")
        return []
    
    result_files = sorted(results_dir.glob("transcript_test_results_*.json"))
    
    print("📁 Available Test Results:")
    for i, file_path in enumerate(result_files, 1):
        size = file_path.stat().st_size
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        print(f"  {i}. {file_path.name} ({size:,} bytes, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
    
    return result_files


def load_results(file_path: Path) -> dict:
    """Load results from JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return {}


def display_results_summary(results: dict, title: str = "Test Results"):
    """Display a summary of test results"""
    print(f"\n📊 {title}")
    print("=" * len(title))
    
    if not results:
        print("❌ No results to display")
        return
    
    print(f"Test Date: {results.get('test_run_date', 'Unknown')}")
    print(f"Total Transcripts: {results.get('total_transcripts', 0)}")
    
    total_claims = sum(r.get('claims_extracted', 0) for r in results.get('results', []))
    avg_time = sum(r.get('processing_time', 0) for r in results.get('results', [])) / max(len(results.get('results', [])), 1)
    
    print(f"Total Claims: {total_claims:,}")
    print(f"Average Processing Time: {avg_time:.2f}s")
    
    print(f"\n📈 Per-Transcript Results:")
    for result in results.get('results', []):
        status = "✅" if not result.get('error') else "❌"
        print(f"  {status} {result.get('transcript_name', 'Unknown')}:")
        print(f"      Claims: {result.get('claims_extracted', 0)}")
        print(f"      Length: {result.get('transcript_length', 0):,} chars")
        print(f"      Time: {result.get('processing_time', 0):.2f}s")
        if result.get('chunks_used'):
            print(f"      Chunks: {result.get('chunks_processed', 0)}, Clusters: {result.get('clusters_found', 0)}")


def main():
    parser = argparse.ArgumentParser(description="View transcript test results")
    parser.add_argument("--list", action="store_true", help="List all result files")
    parser.add_argument("--file", help="View specific result file")
    parser.add_argument("--compare", action="store_true", help="Compare latest vs previous results")
    
    args = parser.parse_args()
    
    results_dir = Path("tests/results")
    
    if args.list:
        list_result_files()
        return
    
    if args.file:
        file_path = results_dir / args.file
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return
        results = load_results(file_path)
        display_results_summary(results, f"Results from {args.file}")
        return
    
    if args.compare:
        result_files = sorted(results_dir.glob("transcript_test_results_*.json"))
        if len(result_files) < 2:
            print("❌ Need at least 2 result files to compare")
            return
        
        latest = load_results(result_files[-1])
        previous = load_results(result_files[-2])
        
        display_results_summary(previous, f"Previous Results ({result_files[-2].name})")
        display_results_summary(latest, f"Latest Results ({result_files[-1].name})")
        
        # Quick comparison
        print(f"\n🔍 Comparison:")
        prev_claims = sum(r.get('claims_extracted', 0) for r in previous.get('results', []))
        latest_claims = sum(r.get('claims_extracted', 0) for r in latest.get('results', []))
        claim_diff = latest_claims - prev_claims
        
        if claim_diff > 0:
            print(f"   📈 Claims increased by {claim_diff}")
        elif claim_diff < 0:
            print(f"   📉 Claims decreased by {abs(claim_diff)}")
        else:
            print(f"   ➡️  Same number of claims ({latest_claims})")
        
        return
    
    # Default: show latest results
    latest_file = results_dir / "latest_results.json"
    if latest_file.exists():
        results = load_results(latest_file)
        display_results_summary(results, "Latest Test Results")
    else:
        print("❌ No latest results found. Run test_transcript_suite.py first.")


if __name__ == "__main__":
    main()
