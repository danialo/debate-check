#!/usr/bin/env python3
"""
Test script to verify YouTube pipeline filtering functionality
"""

import sys
sys.path.append('/home/d/Git/debate-check')

from debate_claim_extractor.pipeline.youtube_pipeline import YouTubePipeline

def test_youtube_filtering():
    """Test YouTube pipeline with a long transcript containing filler content"""
    
    # Create a test transcript with content that should be filtered out
    test_transcript = """
Charles: Uh, so let's talk about free will. You know, um, I think physics gives us some insights here.
Neil: Yeah, absolutely. Uh, I mean, we've talked about this before, but, um, the idea that everything is predetermined is really interesting.
Speaker A: I don't know, I think there's something to be said for, like, spontaneous decisions. You know?
Charles: Right, right. But, uh, if you consider quantum mechanics, there's still randomness in the universe.
Neil: Hmm, that's true. But, you know, does randomness really equal free will? I'm not so sure.
Speaker B: Well, I mean, maybe it's like when you're playing football and you have to make a split-second decision.
Charles: That's a good example, actually. Um, you know, there's this deterministic aspect but also, uh, these quantum effects.
Neil: Yeah, and then you have to consider, like, the social aspects. You know, how society views responsibility.
Speaker A: Right, I think that's really important. Um, we need to think about compassion and, uh, restorative justice.
Speaker B: I guess what I'm wondering is, does anxiety medication affect free will? Like, you know, brain chemistry and all that.
Charles: That's such a good question. I mean, if your brain chemistry is altered, are you still, um, making free choices?
Neil: And that gets into the whole question of, like, where do we draw the line between biology and choice?
    """.strip()
    
    print(f"Test transcript length: {len(test_transcript)} characters")
    print("Testing YouTube pipeline with enhanced filtering...\n")
    
    # Initialize YouTube pipeline (should now use EnhancedClaimPostprocessor with filtering)
    pipeline = YouTubePipeline()
    
    # Run the comprehensive analysis
    result = pipeline.extract_with_comprehensive_analysis(test_transcript, source="test_filtering")
    
    print(f"Pipeline used: {'YouTube (long transcript)' if len(test_transcript) > 2000 else 'Regular'}")
    print(f"Claims extracted: {len(result.get('claims', []))}")
    print(f"Processing method: {result.get('meta', {}).get('processing_method', 'unknown')}")
    
    if 'meta' in result:
        meta = result['meta']
        if 'chunks_processed' in meta:
            print(f"Chunks processed: {meta['chunks_processed']}")
        if 'enhanced_postprocessor_filtering_enabled' in meta:
            print(f"Enhanced filtering enabled: {meta['enhanced_postprocessor_filtering_enabled']}")
            if 'claims_filtered_out' in meta:
                print(f"Claims filtered out: {meta['claims_filtered_out']}")
        
    print(f"YouTube enhanced: {result.get('youtube_enhanced', False)}")
    print(f"Chunks used: {result.get('chunks_used', False)}")
    
    if result.get('claims'):
        print(f"\nFirst few claims:")
        for i, claim in enumerate(result['claims'][:5]):
            if isinstance(claim, dict):
                print(f"  {i+1}. [{claim.get('type', 'unknown')}] {claim.get('text', '')[:100]}...")
            else:
                print(f"  {i+1}. [{claim.type}] {claim.text[:100]}...")
    
    return result

if __name__ == "__main__":
    result = test_youtube_filtering()
