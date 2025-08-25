#!/usr/bin/env python3
"""
Test script to verify YouTube pipeline filtering functionality with long transcript
"""

import sys
sys.path.append('/home/d/Git/debate-check')

from debate_claim_extractor.pipeline.youtube_pipeline import YouTubePipeline

def test_youtube_long_filtering():
    """Test YouTube pipeline with a long transcript containing filler content"""
    
    # Create a longer test transcript that will trigger chunked processing (>2000 chars)
    test_transcript = """
Charles: Uh, so let's talk about free will. You know, um, I think physics gives us some insights here. Let me explain what I mean by that. You know, in classical physics, everything was thought to be deterministic - if you knew the position and momentum of every particle in the universe at any given moment, you could, in principle, predict the entire future and retrodict the entire past. This is known as Laplace's demon, named after Pierre-Simon Laplace.

Neil: Yeah, absolutely. Uh, I mean, we've talked about this before, but, um, the idea that everything is predetermined is really interesting. But then quantum mechanics came along and introduced this element of genuine randomness into the universe. You know, when we measure a quantum system, the outcome is fundamentally unpredictable - it's not just that we lack information, but that the outcome is genuinely random according to the probabilities given by the wave function.

Speaker A: I don't know, I think there's something to be said for, like, spontaneous decisions. You know? Like yesterday I was walking down the street and I suddenly decided to turn left instead of right, and I have no idea why I made that choice. It just felt like it came out of nowhere. But was that really free will, or was it just the result of some complex brain processes that I'm not consciously aware of?

Charles: Right, right. But, uh, if you consider quantum mechanics, there's still randomness in the universe. But here's the thing - does randomness equal free will? I mean, if my decisions are just the result of random quantum events in my brain, are they really "free" in any meaningful sense? It seems like true free will would require something that's neither determined nor random - something that's genuinely chosen by me as an agent.

Neil: Hmm, that's true. But, you know, does randomness really equal free will? I'm not so sure. And then there's the whole question of compatibilism versus hard determinism versus libertarianism. Compatibilists argue that free will is compatible with determinism - that as long as our actions flow from our own desires and aren't coerced, they can be considered free even if they're determined. Hard determinists say there's no free will at all. And libertarians argue that we have genuine free will that's incompatible with determinism.

Speaker B: Well, I mean, maybe it's like when you're playing football and you have to make a split-second decision. Like, you see the defense coming and you have maybe a quarter of a second to decide whether to throw the ball or take the sack. In that moment, it really feels like you're making a choice, even though your brain is processing all this information incredibly quickly. Is that free will, or is it just a very fast computational process?

Charles: That's a good example, actually. Um, you know, there's this deterministic aspect but also, uh, these quantum effects. Some philosophers and scientists have speculated that quantum indeterminacy in the brain might be the source of free will, but I think that's problematic for the reason I mentioned earlier - randomness doesn't seem to be the same thing as freedom. If my choice to have eggs instead of cereal for breakfast was determined by a random quantum event, that doesn't seem to make it more "free" than if it was determined by my taste preferences.

Neil: Yeah, and then you have to consider, like, the social aspects. You know, how society views responsibility. I mean, if hard determinism is true, then in some sense no one is truly responsible for their actions - they're just the inevitable result of prior causes stretching back to the Big Bang. But our entire legal and moral system is based on the assumption that people are responsible for their choices. Should we abandon concepts like praise and blame and punishment if free will is an illusion?

Speaker A: Right, I think that's really important. Um, we need to think about compassion and, uh, restorative justice. Even if people aren't ultimately responsible for their actions in some ultimate cosmic sense, we still need practical ways of organizing society. Maybe instead of retributive justice focused on punishment, we could focus more on rehabilitation and preventing future harm. You know, like Norway's prison system, which has much lower recidivism rates than the US.

Speaker B: I guess what I'm wondering is, does anxiety medication affect free will? Like, you know, brain chemistry and all that. I mean, if I take Xanax for my anxiety, and it makes me calmer and more rational, are the decisions I make while on the medication less "free" than the ones I make when I'm anxious and panicky? It seems weird to say that being more rational makes you less free, but the medication is definitely influencing my brain chemistry.

Charles: That's such a good question. I mean, if your brain chemistry is altered, are you still, um, making free choices? But then again, your "natural" brain chemistry is also the result of genetics, diet, sleep, exercise, and countless other factors that are largely outside your control. So in what sense is the "unmedicated" you more free than the "medicated" you? Maybe the whole concept of a "natural" or "unaltered" state of consciousness is problematic.

Neil: And that gets into the whole question of, like, where do we draw the line between biology and choice? I mean, everything we do is ultimately implemented by our brains, which are biological systems following the laws of physics and chemistry. Our thoughts, feelings, and decisions are all patterns of neural activity. Does that mean they're not really "ours" in some important sense? Or does it just mean that we are biological systems, and our choices are biological processes?

Speaker A: You know what's interesting is the idea from that movie Arrival, where, uh, learning a new language changes how you perceive time. Like maybe our sense of free will is partly dependent on how we think about time and causation. If you could perceive all of time at once like the aliens in that movie, would the concept of choice even make sense? Or would everything just be part of one big four-dimensional block universe?

Charles: That reminds me of the ancient Greek concept of fate. You know, even the gods were subject to fate in Greek mythology. It wasn't that they lacked power, but that there was something even more fundamental than power - this cosmic order that everything, even divine beings, had to follow. Maybe free will versus determinism is a false dichotomy, and there's some third option that we haven't fully grasped yet.
    """.strip()
    
    print(f"Test transcript length: {len(test_transcript)} characters")
    print("Testing YouTube pipeline with enhanced filtering (long transcript)...\n")
    
    # Initialize YouTube pipeline (should now use EnhancedClaimPostprocessor with filtering)
    pipeline = YouTubePipeline()
    
    # Run the comprehensive analysis
    result = pipeline.extract_with_comprehensive_analysis(test_transcript, source="test_long_filtering")
    
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
    
    # Count different claim types
    if result.get('claims'):
        claim_types = {}
        for claim in result['claims']:
            if isinstance(claim, dict):
                claim_type = claim.get('type', 'unknown')
            else:
                claim_type = str(claim.type)
            claim_types[claim_type] = claim_types.get(claim_type, 0) + 1
        
        print(f"\nClaim types distribution:")
        for claim_type, count in claim_types.items():
            print(f"  {claim_type}: {count}")
        
        print(f"\nFirst few claims:")
        for i, claim in enumerate(result['claims'][:8]):
            if isinstance(claim, dict):
                print(f"  {i+1}. [{claim.get('type', 'unknown')}] {claim.get('text', '')[:120]}...")
            else:
                print(f"  {i+1}. [{claim.type}] {claim.text[:120]}...")
    
    return result

if __name__ == "__main__":
    result = test_youtube_long_filtering()
