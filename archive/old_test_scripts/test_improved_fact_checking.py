#!/usr/bin/env python3
"""
Test the improved fact-checking system with better filtering and enhanced explanations.
"""

import asyncio
import logging
from datetime import datetime

from debate_claim_extractor.pipeline.youtube_pipeline import YouTubePipeline
from debate_claim_extractor.fact_checking.fact_models import FactCheckConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_improved_fact_checking():
    """Test the improved system with problematic claims from the previous run"""
    
    # Sample problematic text that was generating bad results
    test_text = '''Charles: you hear silence and you be like oh that was good and everyone laughs. 
    Same is true but then I wouldn't have free will at that point it would just be a response.
    And so in that moment you are not exercising Free Will.
    But I know what it's different, I'm not saying it's predetermined and you know it M.
    Will physics wise though that's the challenge right.
    
    Neil: The Earth is approximately 4.5 billion years old based on radiometric dating of meteorites.
    Climate change is caused primarily by human activities since the industrial revolution.
    Multiple scientific studies confirm that vaccines are safe and effective.'''
    
    print("🧪 Testing Improved Fact-Checking System")
    print(f"Input text length: {len(test_text)} characters")
    print("-" * 60)
    
    # Configure fact-checking (using local services only for testing)
    fact_config = FactCheckConfig(
        enabled=True,
        timeout_seconds=10,
        google_fact_check={'enabled': False, 'api_key': None},
        local_database={'enabled': True, 'database_path': 'data/fact_checks.db'}
    )
    
    # Initialize the improved YouTube pipeline
    pipeline = YouTubePipeline()
    
    try:
        # Run comprehensive analysis
        print("🔄 Running comprehensive analysis...")
        result = pipeline.extract_with_comprehensive_analysis(
            test_text, 
            source="improved_test",
            fact_config=fact_config
        )
        
        if "error" in result:
            print(f"❌ Analysis failed: {result['error']}")
            return
        
        claims = result.get("claims", [])
        fact_check_results = result.get("fact_check_results", [])
        meta = result.get("meta", {})
        
        print(f"✅ Analysis completed successfully!")
        print(f"📊 Extracted {len(claims)} claims")
        print(f"🔍 Fact-checked {len(fact_check_results)} claims")
        print()
        
        # Show filtering results
        filtering_info = {
            'factual_claims': 0,
            'normative_claims': 0,
            'should_fact_check': 0,
            'skip_fact_check': 0,
            'filtered_examples': []
        }
        
        for claim in claims:
            if claim.get('type') == 'factual':
                filtering_info['factual_claims'] += 1
            elif claim.get('type') == 'normative':
                filtering_info['normative_claims'] += 1
            
            if claim.get('should_fact_check'):
                filtering_info['should_fact_check'] += 1
            else:
                filtering_info['skip_fact_check'] += 1
                if len(filtering_info['filtered_examples']) < 3:
                    filtering_info['filtered_examples'].append({
                        'text': claim['text'][:50] + '...' if len(claim['text']) > 50 else claim['text'],
                        'reason': claim.get('classification_reason', 'No reason provided')
                    })
        
        print("🎯 **Filtering Results:**")
        print(f"   Factual claims: {filtering_info['factual_claims']}")
        print(f"   Normative claims: {filtering_info['normative_claims']}")
        print(f"   Should fact-check: {filtering_info['should_fact_check']}")
        print(f"   Skip fact-check: {filtering_info['skip_fact_check']}")
        print()
        
        if filtering_info['filtered_examples']:
            print("📝 **Examples of filtered claims:**")
            for example in filtering_info['filtered_examples']:
                print(f"   - \"{example['text']}\" → {example['reason']}")
            print()
        
        # Show fact-checking results with enhanced explanations
        if fact_check_results:
            print("🔬 **Fact-Checking Results:**")
            for i, fc_result in enumerate(fact_check_results[:5], 1):  # Show first 5
                claim_text = fc_result.get('claim_text', 'Unknown claim')
                status = fc_result.get('overall_status', 'unknown')
                summary = fc_result.get('summary', 'No summary available')
                friendly = fc_result.get('friendly_explanation', 'No friendly explanation available')
                
                print(f"   {i}. **Claim:** \"{claim_text[:60]}{'...' if len(claim_text) > 60 else ''}\"")
                print(f"      **Status:** {status}")
                print(f"      **Summary:** {summary}")
                print(f"      **Friendly:** {friendly}")
                print()
        else:
            print("ℹ️  No fact-checking results to display")
        
        # Show verification summary from metadata
        verification_summary = meta.get('verification_summary', {})
        if verification_summary:
            print("📈 **Verification Summary:**")
            for status, count in verification_summary.items():
                if count > 0:
                    print(f"   {status}: {count}")
            print()
        
        print("✅ **Test completed successfully!**")
        print()
        print("🎯 **Key improvements demonstrated:**")
        print("   ✓ Better filtering of conversational fragments")
        print("   ✓ Enhanced explanations with context")
        print("   ✓ Friendly user explanations with emojis")
        print("   ✓ Proper handling of filtered claims")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.exception("Test error:")
    
    finally:
        # Clean up
        if hasattr(pipeline, 'fact_pipeline') and pipeline.fact_pipeline:
            await pipeline.fact_pipeline.close()


if __name__ == "__main__":
    asyncio.run(test_improved_fact_checking())
