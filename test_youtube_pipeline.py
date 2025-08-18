#!/usr/bin/env python3
"""
Test the enhanced YouTube pipeline with the free will transcript
"""

import json
import sys
from pathlib import Path

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent))

from debate_claim_extractor.pipeline.youtube_pipeline import YouTubePipeline


def test_youtube_pipeline():
    """Test the YouTube pipeline with the free will debate transcript"""
    
    transcript_path = "/home/d/Obsidian/politics/Debate-Transcripts/Two Astrophysicists Debate Free Will.md"
    
    print("🚀 Testing YouTube Pipeline with Free Will Debate")
    print(f"📁 Loading transcript from: {transcript_path}")
    
    try:
        # Load the transcript
        with open(transcript_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        print(f"📊 Transcript loaded: {len(text)} characters")
        
        # Initialize YouTube pipeline
        print("🔧 Initializing YouTube-enhanced pipeline...")
        pipeline = YouTubePipeline()
        
        # Process the transcript
        print("⚙️  Processing transcript with smart chunking and clustering...")
        result = pipeline.extract(text, source="Two Astrophysicists Debate Free Will")
        
        # Display results
        print("\n" + "="*60)
        print("📋 RESULTS SUMMARY")
        print("="*60)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return
        
        print(f"✅ Processing method: {result.get('meta', {}).get('processing_method', 'standard')}")
        print(f"📝 Total claims found: {result.get('claims_count', 0)}")
        print(f"🎯 Clusters created: {result.get('cluster_analysis', {}).get('total_clusters', 0)}")
        
        if result.get('chunks_used'):
            chunk_analysis = result.get('chunk_analysis', {})
            print(f"📦 Chunks processed: {chunk_analysis.get('total_chunks', 0)}")
            print(f"📏 Average chunk size: {chunk_analysis.get('avg_chunk_size', 0)} chars")
            print(f"👥 Speaker inference: {chunk_analysis.get('speaker_inference', {})}")
        
        # Display cluster information
        clusters = result.get('clusters', [])
        if clusters:
            print(f"\n🎯 CLAIM CLUSTERS:")
            for i, cluster in enumerate(clusters[:3]):  # Show top 3 clusters
                print(f"\nCluster {i+1}: {cluster['type']} ({cluster['stance']})")
                print(f"  📊 {cluster['claims_count']} claims, confidence: {cluster['confidence']:.2f}")
                print(f"  🏷️  Topics: {', '.join(cluster['topics'])}")
                print(f"  💬 Primary: \"{cluster['primary_claim']['text'][:100]}...\"")
        
        # Display top claims
        claims = result.get('claims', [])
        if claims:
            print(f"\n💎 TOP CLAIMS (by confidence):")
            for i, claim in enumerate(sorted(claims, key=lambda c: c['confidence'], reverse=True)[:5]):
                print(f"\n{i+1}. [{claim['type']}] {claim['speaker']} (conf: {claim['confidence']:.2f})")
                print(f"   \"{claim['text'][:150]}...\"")
        
        # Save detailed results
        output_file = "youtube_pipeline_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        print("🎉 YouTube pipeline test completed successfully!")
        
    except FileNotFoundError:
        print(f"❌ Transcript file not found: {transcript_path}")
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_youtube_pipeline()
