#!/usr/bin/env python3
"""
Test enhanced claim filtering on problematic examples
"""

import sys
sys.path.append('/home/d/Git/debate-check')

from debate_claim_extractor.pipeline.youtube_pipeline import YouTubePipeline

def test_enhanced_filtering():
    """Test enhanced filtering with specific problematic examples"""
    
    # Create a test transcript with the specific problematic claims we've seen
    test_transcript = """
Charles: right it falls flat in that moment you have many things you could do to turn it into a laugh Point true right

Neil: that's the thing there

Charles: right did you have free will to not see that's right

Neil: But quantum mechanics introduces genuine randomness into physical processes.

Charles: The concept of determinism suggests that every event is the result of prior causes.

Neil: I think free will is fundamentally about our capacity to make meaningful choices.

Charles: yeah right exactly

Neil: You know what I mean

Charles: uh huh sure

Neil: The philosophical implications of determinism for moral responsibility are significant.
    """.strip()
    
    print(f"Testing enhanced filtering with problematic claims...")
    print(f"Transcript length: {len(test_transcript)} characters\n")
    
    # Initialize YouTube pipeline with enhanced filtering
    pipeline = YouTubePipeline()
    
    # Run analysis
    result = pipeline.extract_with_comprehensive_analysis(test_transcript, source="test_problematic")
    
    print(f"Claims extracted: {len(result.get('claims', []))}")
    print(f"Processing method: {result.get('meta', {}).get('processing_method', 'unknown')}")
    
    claims = result.get('claims', [])
    if claims:
        print(f"\nExtracted claims:")
        for i, claim in enumerate(claims):
            if isinstance(claim, dict):
                claim_text = claim.get('text', '')
                claim_type = claim.get('type', 'unknown')
                claim_confidence = claim.get('confidence', 0)
            else:
                claim_text = claim.text
                claim_type = str(claim.type)
                claim_confidence = claim.confidence
            
            print(f"  {i+1}. [{claim_type}] (conf: {claim_confidence:.1f}%) {claim_text}")
    else:
        print("\nNo claims extracted.")
    
    # Test specific problematic strings to see if they would be filtered
    print(f"\n" + "="*50)
    print("Testing specific problematic examples:")
    
    problematic_examples = [
        "right it falls flat in that moment you have many things you could do to turn it into a laugh Point true right",
        "that's the thing there", 
        "right did you have free will to not see that's right",
        "yeah right exactly",
        "You know what I mean",
        "uh huh sure"
    ]
    
    from debate_claim_extractor.pipeline.claim_filters import ImprovedClaimFilteringSystem
    from debate_claim_extractor.pipeline.models import Claim, ClaimType
    
    filtering_system = ImprovedClaimFilteringSystem()
    
    for text in problematic_examples:
        # Create a dummy claim for testing
        dummy_claim = Claim(
            id=f"test_{hash(text)}",
            type=ClaimType.FACTUAL,
            text=text,
            speaker="TEST",
            sentence_id="test_sentence",
            turn_id=0,
            char_start=0,
            char_end=len(text),
            confidence=0.5
        )
        
        # Test each filter
        should_exclude = False
        exclusion_reason = ""
        
        for filter_obj in filtering_system.filters:
            exclude, reason = filter_obj.should_exclude(text, dummy_claim)
            if exclude:
                should_exclude = True
                exclusion_reason = reason
                break
        
        status = "FILTERED OUT" if should_exclude else "WOULD PASS"
        print(f"  {status}: '{text[:60]}{'...' if len(text) > 60 else ''}'")
        if should_exclude:
            print(f"    Reason: {exclusion_reason}")

if __name__ == "__main__":
    test_enhanced_filtering()
