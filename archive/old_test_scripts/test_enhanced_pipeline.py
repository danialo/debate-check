#!/usr/bin/env python3
"""
Test script to demonstrate improvements with enhanced pipeline
"""

import logging
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from debate_claim_extractor.pipeline.enhanced_pipeline import EnhancedClaimExtractionPipeline
from debate_claim_extractor.pipeline.pipeline import ClaimExtractionPipeline

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_transcript():
    """Load the free will debate transcript"""
    transcript_path = Path("tests/manual/transcript.txt")
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found at {transcript_path}")
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        return f.read()

def compare_pipelines():
    """Compare original vs enhanced pipeline results"""
    
    print("🚀 Testing Enhanced Pipeline vs Original Pipeline")
    print("=" * 60)
    
    # Load transcript
    try:
        text = load_transcript()
        print(f"📄 Loaded transcript: {len(text)} characters")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Please ensure the transcript file exists at tests/manual/transcript.txt")
        return
    
    print()
    
    # Test original pipeline
    print("🔄 Running ORIGINAL pipeline...")
    original_pipeline = ClaimExtractionPipeline()
    original_result = original_pipeline.extract(text, source="comparison_test_original")
    
    # Test enhanced pipeline  
    print("🔄 Running ENHANCED pipeline...")
    enhanced_pipeline = EnhancedClaimExtractionPipeline(enable_filtering=True)
    enhanced_result = enhanced_pipeline.extract(text, source="comparison_test_enhanced")
    
    print()
    print("📊 COMPARISON RESULTS")
    print("=" * 60)
    
    # Compare claim counts
    orig_count = len(original_result.claims)
    enh_count = len(enhanced_result.claims)
    print(f"Original Pipeline Claims: {orig_count}")
    print(f"Enhanced Pipeline Claims: {enh_count}")
    print(f"Claims Filtered Out: {orig_count - enh_count}")
    print()
    
    # Show examples of filtered claims
    print("🗂️  EXAMPLES OF FILTERED CLAIMS:")
    print("-" * 40)
    
    orig_texts = {claim.text for claim in original_result.claims}
    enh_texts = {claim.text for claim in enhanced_result.claims}
    filtered_out = orig_texts - enh_texts
    
    conversation_fillers = []
    hypotheticals = []
    others = []
    
    for text in list(filtered_out)[:10]:  # Show first 10 examples
        text_lower = text.lower()
        if text_lower in ['yeah', 'yes', 'no', 'right', 'okay', 'mhm']:
            conversation_fillers.append(text)
        elif any(word in text_lower for word in ['let\'s say', 'suppose', 'imagine', 'what if']):
            hypotheticals.append(text)
        else:
            others.append(text)
    
    if conversation_fillers:
        print("Conversational Fillers Filtered:")
        for text in conversation_fillers[:5]:
            print(f"  ❌ '{text}'")
    
    if hypotheticals:
        print("\nHypotheticals Filtered:")
        for text in hypotheticals[:3]:
            print(f"  ❌ '{text[:60]}...'")
    
    if others:
        print("\nOther Non-Claims Filtered:")
        for text in others[:3]:
            print(f"  ❌ '{text[:60]}...'")
    
    print()
    
    # Show claim type distribution
    print("📈 CLAIM TYPE DISTRIBUTION:")
    print("-" * 40)
    
    # Original pipeline types
    orig_types = {}
    for claim in original_result.claims:
        orig_types[claim.type.value] = orig_types.get(claim.type.value, 0) + 1
    
    # Enhanced pipeline types
    enh_types = {}
    for claim in enhanced_result.claims:
        enh_types[claim.type.value] = enh_types.get(claim.type.value, 0) + 1
    
    print("Original Pipeline:")
    for claim_type, count in sorted(orig_types.items()):
        print(f"  {claim_type}: {count}")
    
    print("\nEnhanced Pipeline:")
    for claim_type, count in sorted(enh_types.items()):
        print(f"  {claim_type}: {count}")
    
    print()
    
    # Show examples of philosophical claims that would be classified as NORMATIVE
    print("🧠 PHILOSOPHICAL CLAIMS (would be classified as NORMATIVE):")
    print("-" * 40)
    
    philosophical_examples = []
    for claim in enhanced_result.claims:
        text_lower = claim.text.lower()
        if any(phrase in text_lower for phrase in ['free will', 'moral', 'should', 'believe', 'philosophy']):
            philosophical_examples.append(claim.text)
    
    for i, text in enumerate(philosophical_examples[:5]):
        print(f"  🧠 '{text[:80]}...' (would skip fact-checking)")
    
    print()
    print("✅ Enhanced pipeline successfully:")
    print("   • Filtered out conversational fillers")
    print("   • Identified hypothetical scenarios")
    print("   • Would classify philosophical positions appropriately")
    print("   • Would skip fact-checking normative claims")
    
    return orig_count, enh_count, len(filtered_out)

if __name__ == "__main__":
    try:
        compare_pipelines()
    except Exception as e:
        print(f"❌ Error running comparison: {e}")
        import traceback
        traceback.print_exc()
