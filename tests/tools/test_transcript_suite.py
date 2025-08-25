#!/usr/bin/env python3
"""
Comprehensive Transcript Testing Suite
=====================================

Tests the YouTube pipeline against multiple real transcripts to ensure:
- Consistency across different content types
- Reliability of claim extraction
- Proper async fact-checking functionality
- Performance tracking over time

Usage:
    python test_transcript_suite.py
    python test_transcript_suite.py --transcript CK-01.txt
    python test_transcript_suite.py --with-fact-checking
"""

import asyncio
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import argparse

sys.path.append('.')
from debate_claim_extractor.pipeline.youtube_pipeline import YouTubePipeline


@dataclass
class TranscriptTestResult:
    """Results from testing a single transcript"""
    transcript_name: str
    transcript_length: int
    processing_time: float
    claims_extracted: int
    chunks_used: bool
    chunks_processed: int
    clusters_found: int
    speaker_inference: Dict[str, int]
    fact_checking_enabled: bool = False
    fact_checked_claims: int = 0
    fact_checking_error: Optional[str] = None
    top_claims: List[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "transcript_name": self.transcript_name,
            "transcript_length": self.transcript_length,
            "processing_time": self.processing_time,
            "claims_extracted": self.claims_extracted,
            "chunks_used": self.chunks_used,
            "chunks_processed": self.chunks_processed,
            "clusters_found": self.clusters_found,
            "speaker_inference": self.speaker_inference,
            "fact_checking_enabled": self.fact_checking_enabled,
            "fact_checked_claims": self.fact_checked_claims,
            "fact_checking_error": self.fact_checking_error,
            "top_claims": self.top_claims or [],
            "error": self.error
        }


class TranscriptTestSuite:
    """Test suite for validating YouTube pipeline across multiple transcripts"""
    
    def __init__(self, transcript_dir: Path = None):
        self.transcript_dir = transcript_dir or Path("tests/manual")
        self.pipeline = YouTubePipeline()
        self.results: List[TranscriptTestResult] = []
    
    def discover_transcripts(self) -> List[Path]:
        """Find all transcript files in the test directory"""
        transcript_files = []
        if self.transcript_dir.exists():
            transcript_files.extend(self.transcript_dir.glob("*.txt"))
        
        # Sort for consistent ordering
        return sorted(transcript_files)
    
    def load_transcript(self, transcript_path: Path) -> str:
        """Load and clean transcript content"""
        with open(transcript_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Handle line-numbered format if present
        lines = content.split('\n')
        if len(lines) > 1 and '|' in lines[0]:
            # Extract text after line numbers
            transcript = ''
            for line in lines:
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) > 1:
                        transcript += parts[1] + ' '
            return transcript.strip()
        
        return content
    
    async def test_transcript_basic(self, transcript_path: Path) -> TranscriptTestResult:
        """Test basic extraction on a single transcript"""
        transcript_name = transcript_path.name
        print(f"\n📄 Testing: {transcript_name}")
        
        try:
            # Load transcript
            transcript = self.load_transcript(transcript_path)
            print(f"   Length: {len(transcript):,} characters")
            
            # Time the extraction
            start_time = time.time()
            result = self.pipeline.extract(transcript, source=transcript_name)
            processing_time = time.time() - start_time
            
            # Extract key metrics
            claims = result.get('claims', [])
            chunk_analysis = result.get('chunk_analysis', {})
            
            # Get top claims for analysis
            top_claims = []
            for claim in claims[:5]:  # Top 5 claims
                top_claims.append({
                    'type': claim['type'],
                    'text': claim['text'][:100] + '...' if len(claim['text']) > 100 else claim['text'],
                    'speaker': claim['speaker'],
                    'confidence': claim['confidence']
                })
            
            test_result = TranscriptTestResult(
                transcript_name=transcript_name,
                transcript_length=len(transcript),
                processing_time=processing_time,
                claims_extracted=len(claims),
                chunks_used=result.get('chunks_used', False),
                chunks_processed=chunk_analysis.get('total_chunks', 0),
                clusters_found=len(result.get('clusters', [])),
                speaker_inference=chunk_analysis.get('speaker_inference', {}),
                top_claims=top_claims
            )
            
            print(f"   ✅ {len(claims)} claims extracted in {processing_time:.2f}s")
            if result.get('chunks_used'):
                print(f"   📊 {chunk_analysis.get('total_chunks', 0)} chunks, {len(result.get('clusters', []))} clusters")
                print(f"   🎤 Speakers: {chunk_analysis.get('speaker_inference', {})}")
            
            return test_result
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return TranscriptTestResult(
                transcript_name=transcript_name,
                transcript_length=0,
                processing_time=0,
                claims_extracted=0,
                chunks_used=False,
                chunks_processed=0,
                clusters_found=0,
                speaker_inference={},
                error=str(e)
            )
    
    async def test_transcript_with_fact_checking(self, transcript_path: Path) -> TranscriptTestResult:
        """Test extraction with fact-checking on a single transcript"""
        transcript_name = transcript_path.name
        print(f"\n🔍 Testing with fact-checking: {transcript_name}")
        
        try:
            # Load transcript
            transcript = self.load_transcript(transcript_path)
            
            # Time the extraction with fact-checking
            start_time = time.time()
            result = await self.pipeline.extract_with_fact_checking(transcript, source=transcript_name)
            processing_time = time.time() - start_time
            
            # Extract key metrics
            claims = result.get('claims', [])
            chunk_analysis = result.get('chunk_analysis', {})
            meta = result.get('meta', {})
            
            # Get top claims for analysis
            top_claims = []
            for claim in claims[:5]:  # Top 5 claims
                top_claims.append({
                    'type': claim['type'],
                    'text': claim['text'][:100] + '...' if len(claim['text']) > 100 else claim['text'],
                    'speaker': claim['speaker'],
                    'confidence': claim['confidence']
                })
            
            test_result = TranscriptTestResult(
                transcript_name=transcript_name,
                transcript_length=len(transcript),
                processing_time=processing_time,
                claims_extracted=len(claims),
                chunks_used=result.get('chunks_used', False),
                chunks_processed=chunk_analysis.get('total_chunks', 0),
                clusters_found=len(result.get('clusters', [])),
                speaker_inference=chunk_analysis.get('speaker_inference', {}),
                fact_checking_enabled=result.get('fact_checking_enabled', False),
                fact_checked_claims=meta.get('fact_checked_claims', 0),
                fact_checking_error=meta.get('fact_checking_error'),
                top_claims=top_claims
            )
            
            print(f"   ✅ {len(claims)} claims extracted in {processing_time:.2f}s")
            print(f"   🔍 Fact-checking: {meta.get('fact_checked_claims', 0)} claims checked")
            if meta.get('fact_checking_error'):
                print(f"   ⚠️  Fact-checking error: {meta['fact_checking_error']}")
            
            return test_result
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return TranscriptTestResult(
                transcript_name=transcript_name,
                transcript_length=0,
                processing_time=0,
                claims_extracted=0,
                chunks_used=False,
                chunks_processed=0,
                clusters_found=0,
                speaker_inference={},
                error=str(e)
            )
    
    async def run_full_suite(self, with_fact_checking: bool = False, specific_transcript: Optional[str] = None):
        """Run the complete test suite"""
        print("🚀 YouTube Pipeline Transcript Test Suite")
        print("=" * 50)
        
        # Discover transcripts
        transcripts = self.discover_transcripts()
        if specific_transcript:
            transcripts = [t for t in transcripts if t.name == specific_transcript]
        
        if not transcripts:
            print("❌ No transcript files found!")
            return
        
        print(f"📁 Found {len(transcripts)} transcript(s) to test:")
        for t in transcripts:
            size = t.stat().st_size
            print(f"   - {t.name} ({size:,} bytes)")
        
        print()
        
        # Run tests
        for transcript_path in transcripts:
            if with_fact_checking:
                result = await self.test_transcript_with_fact_checking(transcript_path)
            else:
                result = await self.test_transcript_basic(transcript_path)
            
            self.results.append(result)
        
        # Print summary
        self.print_summary()
        
        # Save results
        self.save_results()
    
    def print_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 50)
        print("📊 TEST SUITE SUMMARY")
        print("=" * 50)
        
        total_transcripts = len(self.results)
        successful_tests = len([r for r in self.results if r.error is None])
        total_claims = sum(r.claims_extracted for r in self.results)
        avg_processing_time = sum(r.processing_time for r in self.results) / max(len(self.results), 1)
        
        print(f"Transcripts tested: {successful_tests}/{total_transcripts}")
        print(f"Total claims extracted: {total_claims:,}")
        print(f"Average processing time: {avg_processing_time:.2f}s")
        
        if any(r.fact_checking_enabled for r in self.results):
            fact_checked = sum(r.fact_checked_claims for r in self.results)
            print(f"Total claims fact-checked: {fact_checked:,}")
        
        print("\n📈 Per-Transcript Results:")
        for result in self.results:
            status = "✅" if result.error is None else "❌"
            print(f"{status} {result.transcript_name}:")
            print(f"    Length: {result.transcript_length:,} chars")
            print(f"    Claims: {result.claims_extracted}")
            if result.chunks_used:
                print(f"    Chunks: {result.chunks_processed}, Clusters: {result.clusters_found}")
            print(f"    Time: {result.processing_time:.2f}s")
            if result.error:
                print(f"    Error: {result.error}")
            print()
        
        # Show sample claims from each transcript
        print("🎯 Sample Claims by Transcript:")
        for result in self.results:
            if result.top_claims and not result.error:
                print(f"\n{result.transcript_name}:")
                for i, claim in enumerate(result.top_claims[:3], 1):
                    print(f"  {i}. [{claim['type']}] {claim['text']} (Speaker: {claim['speaker']})")
    
    def save_results(self, output_file: str = None):
        """Save test results to JSON file for tracking over time"""
        # Create organized results directory
        results_dir = Path("tests/results")
        results_dir.mkdir(exist_ok=True)
        
        # Generate timestamped filename if not specified
        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = results_dir / f"transcript_test_results_{timestamp}.json"
        else:
            output_file = results_dir / output_file
        
        results_data = {
            "timestamp": time.time(),
            "test_run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_transcripts": len(self.results),
            "results": [result.to_dict() for result in self.results]
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        # Also save a "latest" version for easy access
        latest_file = results_dir / "latest_results.json"
        with open(latest_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        print(f"💾 Latest results also saved to: {latest_file}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="YouTube Pipeline Transcript Test Suite")
    parser.add_argument("--transcript", help="Test specific transcript file")
    parser.add_argument("--with-fact-checking", action="store_true", 
                       help="Include fact-checking tests (slower)")
    parser.add_argument("--transcript-dir", default="tests/manual", 
                       help="Directory containing transcript files")
    
    args = parser.parse_args()
    
    # Create test suite
    suite = TranscriptTestSuite(transcript_dir=Path(args.transcript_dir))
    
    # Run tests
    await suite.run_full_suite(
        with_fact_checking=args.with_fact_checking,
        specific_transcript=args.transcript
    )


if __name__ == "__main__":
    asyncio.run(main())
