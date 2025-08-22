#!/usr/bin/env python3
"""
Realistic test for fact-checking complex YouTube-style claims.

This script tests the fact-checking system with the type of complex,
conversational claims actually extracted from YouTube transcripts.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Add the project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from debate_claim_extractor.fact_checking.fact_models import (
    FactCheckResult, VerificationSource, VerificationStatus, 
    AggregatedVerification, FactCheckConfig, SourceType
)
from debate_claim_extractor.fact_checking.services.local_service import LocalFactCheckService
from debate_claim_extractor.fact_checking.fact_pipeline import FactVerificationPipeline
from debate_claim_extractor.pipeline.models import Claim, ClaimType


class RealisticClaimProcessor:
    """Process and simplify complex claims for fact-checking."""
    
    def __init__(self):
        self.claim_simplifiers = {
            'physics_determinism': self._simplify_physics_claims,
            'causality': self._simplify_causality_claims,
            'behavioral': self._simplify_behavioral_claims,
        }
    
    def _simplify_physics_claims(self, claim_text: str) -> list:
        """Extract checkable facts from physics claims."""
        simplified = []
        
        # Look for specific physics concepts
        if 'causality' in claim_text.lower():
            simplified.append("Causality is a fundamental principle in physics")
        
        if 'determinism' in claim_text.lower() or 'predetermined' in claim_text.lower():
            simplified.append("Physical systems follow deterministic laws")
        
        if 'quantum' in claim_text.lower() or 'uncertainty' in claim_text.lower():
            simplified.append("Quantum mechanics involves fundamental uncertainty")
        
        if 'stochastic' in claim_text.lower() or 'randomness' in claim_text.lower():
            simplified.append("Random processes exist in nature")
            
        return simplified
    
    def _simplify_causality_claims(self, claim_text: str) -> list:
        """Extract checkable causal relationships."""
        simplified = []
        
        if 'free will' in claim_text.lower() and ('no' in claim_text.lower() or 'not' in claim_text.lower()):
            simplified.append("Determinism is incompatible with free will")
        
        if 'experience' in claim_text.lower() and 'decision' in claim_text.lower():
            simplified.append("Past experiences influence decision making")
            
        if 'training' in claim_text.lower() and 'reflex' in claim_text.lower():
            simplified.append("Training creates reflexive responses")
            
        return simplified
    
    def _simplify_behavioral_claims(self, claim_text: str) -> list:
        """Extract checkable behavioral claims."""
        simplified = []
        
        if 'joke' in claim_text.lower() and 'experience' in claim_text.lower():
            simplified.append("Comedians improve through experience")
        
        if '10,000 hours' in claim_text.lower() or '10000 hours' in claim_text.lower():
            simplified.append("10,000 hours of practice leads to expertise")
            
        if 'neuros' in claim_text.lower() or 'neural' in claim_text.lower():
            simplified.append("Neural pathways can be trained")
            
        return simplified
    
    def process_claim(self, claim: Claim) -> list:
        """Process a complex claim and extract fact-checkable components."""
        claim_text = claim.text.lower()
        
        all_simplified = []
        
        # Try each simplifier
        for category, simplifier in self.claim_simplifiers.items():
            simplified = simplifier(claim.text)
            if simplified:
                for simple_claim in simplified:
                    # Create a new simplified claim
                    simple_claim_obj = Claim(
                        type=claim.type,
                        text=simple_claim,
                        speaker=claim.speaker,
                        sentence_id=claim.sentence_id,
                        turn_id=claim.turn_id,
                        char_start=claim.char_start,
                        char_end=claim.char_end,
                        confidence=claim.confidence * 0.8,  # Lower confidence for simplified
                        context=f"Simplified from: {claim.text[:100]}..."
                    )
                    all_simplified.append(simple_claim_obj)
        
        return all_simplified if all_simplified else [claim]


async def test_realistic_claims():
    """Test fact-checking with realistic complex claims."""
    print("🌟 Testing Realistic Claim Processing")
    print("=" * 60)
    
    # Load actual extracted claims
    try:
        with open('sample_claims.json', 'r') as f:
            data = json.load(f)
            sample_claims = data['claims'][:10]  # First 10 claims
    except FileNotFoundError:
        print("❌ sample_claims.json not found. Run claim extraction first.")
        return False
    
    processor = RealisticClaimProcessor()
    
    # Create enhanced local database with relevant fact-checks
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db = f.name
    
    try:
        service = LocalFactCheckService(database_path=temp_db)
        
        # Add realistic fact-check data
        enhanced_data = [
            {
                "claim": "Causality is a fundamental principle in physics",
                "status": "VERIFIED_TRUE",
                "confidence": 0.95,
                "source": "Physics Textbook",
                "url": "https://physics.org/causality"
            },
            {
                "claim": "Physical systems follow deterministic laws",
                "status": "LIKELY_TRUE", 
                "confidence": 0.85,
                "source": "Stanford Encyclopedia",
                "url": "https://stanford.edu/determinism"
            },
            {
                "claim": "Quantum mechanics involves fundamental uncertainty",
                "status": "VERIFIED_TRUE",
                "confidence": 0.95,
                "source": "Quantum Physics Journal",
                "url": "https://quantum.org/uncertainty"
            },
            {
                "claim": "Random processes exist in nature",
                "status": "VERIFIED_TRUE",
                "confidence": 0.90,
                "source": "Nature Journal",
                "url": "https://nature.com/randomness"
            },
            {
                "claim": "Determinism is incompatible with free will",
                "status": "MIXED",
                "confidence": 0.70,
                "source": "Philosophy Database",
                "url": "https://philosophy.org/freewill"
            },
            {
                "claim": "Past experiences influence decision making",
                "status": "VERIFIED_TRUE",
                "confidence": 0.90,
                "source": "Psychology Research",
                "url": "https://psychology.org/decisions"
            },
            {
                "claim": "10,000 hours of practice leads to expertise",
                "status": "MIXED",
                "confidence": 0.60,
                "source": "Skills Research Institute",
                "url": "https://skills.org/10000hours"
            },
            {
                "claim": "Neural pathways can be trained",
                "status": "VERIFIED_TRUE",
                "confidence": 0.95,
                "source": "Neuroscience Journal",
                "url": "https://neuro.org/plasticity"
            }
        ]
        
        # Populate database
        await service._populate_test_data(enhanced_data)
        
        # Create pipeline
        config = FactCheckConfig(timeout_seconds=30)
        pipeline = FactVerificationPipeline(config=config)
        pipeline.services = [service]
        
        print(f"📊 Processing {len(sample_claims)} realistic claims...")
        print()
        
        processed_count = 0
        verified_count = 0
        
        for i, claim_data in enumerate(sample_claims):
            # Convert to Claim object
            claim = Claim(**claim_data)
            
            print(f"🔍 Claim {i+1}: {claim.text[:80]}...")
            
            # Process and simplify the claim
            simplified_claims = processor.process_claim(claim)
            
            if len(simplified_claims) > 1:
                print(f"   🔄 Simplified into {len(simplified_claims)} checkable claims:")
                for j, simple_claim in enumerate(simplified_claims):
                    print(f"      {j+1}. {simple_claim.text}")
            else:
                print(f"   📝 Using original claim (no simplification)")
            
            # Fact-check each simplified claim
            for simple_claim in simplified_claims:
                processed_count += 1
                result = await pipeline.verify_claim(simple_claim)
                
                if result.overall_status != VerificationStatus.UNVERIFIED:
                    verified_count += 1
                    print(f"   ✅ {result.overall_status.value} (confidence: {result.confidence:.2f})")
                    if result.primary_sources:
                        source_names = [s.name for s in result.primary_sources[:2]]
                        print(f"      Sources: {', '.join(source_names)}")
                else:
                    print(f"   ❓ No verification data found")
            
            print()
        
        print("=" * 60)
        print("📈 RESULTS SUMMARY")
        print("=" * 60)
        print(f"Total claims processed: {processed_count}")
        print(f"Claims with verification: {verified_count}")
        print(f"Verification rate: {verified_count/processed_count*100:.1f}%")
        
        return True
        
    finally:
        # Clean up
        import os
        if os.path.exists(temp_db):
            os.unlink(temp_db)


async def test_claim_preprocessing():
    """Test our claim preprocessing logic."""
    print("\n🔬 Testing Claim Preprocessing")
    print("=" * 60)
    
    processor = RealisticClaimProcessor()
    
    # Test with actual complex claims
    test_claims = [
        {
            "type": "causal",
            "text": "so if you take it to its logical conclusion then there is no free will because everything is predetermined by things that everything has an antecedent whether you know it or not something is causing it to happen",
            "speaker": "CHARLES",
            "sentence_id": "test_1",
            "turn_id": 1,
            "char_start": 0,
            "char_end": 100,
            "confidence": 0.65
        },
        {
            "type": "factual",
            "text": "but you've been in a 100 cases where you had a joke bomb you have data on how to pull out of it so statistically you have a chance of getting people smile instantaneously",
            "speaker": "CHARLES", 
            "sentence_id": "test_2",
            "turn_id": 2,
            "char_start": 0,
            "char_end": 100,
            "confidence": 0.60
        },
        {
            "type": "factual",
            "text": "there is also stochastic uncertainty in the universe it's built in there's randomness there's unpredictability",
            "speaker": "CHARLES",
            "sentence_id": "test_3", 
            "turn_id": 3,
            "char_start": 0,
            "char_end": 100,
            "confidence": 0.70
        }
    ]
    
    for i, claim_data in enumerate(test_claims):
        claim = Claim(**claim_data)
        print(f"🧠 Original claim {i+1}:")
        print(f"   {claim.text}")
        
        simplified = processor.process_claim(claim)
        print(f"💡 Simplified to {len(simplified)} claims:")
        
        for j, simple_claim in enumerate(simplified):
            print(f"   {j+1}. {simple_claim.text}")
        print()
    
    return True


async def main():
    """Run realistic claim testing."""
    print("🎯 REALISTIC FACT-CHECKING TEST")
    print("Testing with complex YouTube-style claims")
    print("=" * 60)
    
    tests = [
        ("Claim Preprocessing", test_claim_preprocessing),
        ("Realistic Claims", test_realistic_claims),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = await test_func()
            results.append((test_name, success, None))
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}\n")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"❌ {test_name}: FAILED - {e}\n")
    
    print("=" * 60)
    print("🏁 FINAL RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if error:
            print(f"      Error: {error}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All realistic tests passed!")
        print("\n💡 Next steps:")
        print("1. Get Google Fact Check API key")
        print("2. Test with real API calls")
        print("3. Integrate claim preprocessing into main pipeline")
    else:
        print("🔍 Some tests failed - check errors above")


if __name__ == "__main__":
    asyncio.run(main())
