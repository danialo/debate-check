#!/usr/bin/env python3
"""
Test script to verify enhanced fact-checking explanations work correctly.

This script tests:
1. Enhanced detailed explanations incorporating service evidence
2. Filtered claim handling with appropriate warnings
3. Friendly user explanations with emojis and clear language
4. False claim explanations with specific evidence
"""

import asyncio
import logging
from typing import List, Optional

from debate_claim_extractor.fact_checking.fact_pipeline import FactVerificationPipeline
from debate_claim_extractor.fact_checking.fact_models import (
    FactCheckConfig, FactCheckResult, VerificationStatus, VerificationSource, SourceType
)
from debate_claim_extractor.pipeline.models import Claim, ClaimType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_claims() -> List[Claim]:
    """Create test claims with different characteristics"""
    
    claims = []
    
    # 1. Normal factual claim (should get good explanation)
    claim1 = Claim(
        id="test_1",
        type=ClaimType.FACTUAL,
        text="The Earth is round and orbits the Sun",
        speaker="TestSpeaker",
        sentence_id="sent_1",
        turn_id=1,
        char_start=0,
        char_end=35,
        confidence=0.9
    )
    claims.append(claim1)
    
    # 2. Filtered claim (conversational filler)
    claim2 = Claim(
        id="test_2", 
        type=ClaimType.FACTUAL,
        text="that's the thing there",
        speaker="TestSpeaker",
        sentence_id="sent_2", 
        turn_id=2,
        char_start=0,
        char_end=22,
        confidence=0.3,
        should_fact_check=False,
        classification_reason="Pure conversational filler: 'that's the thing there'"
    )
    claims.append(claim2)
    
    # 3. Question (should be filtered)
    claim3 = Claim(
        id="test_3",
        type=ClaimType.FACTUAL,
        text="Do you think climate change is real?",
        speaker="TestSpeaker", 
        sentence_id="sent_3",
        turn_id=3,
        char_start=0,
        char_end=36,
        confidence=0.4,
        should_fact_check=False,
        classification_reason="Direct question"
    )
    claims.append(claim3)
    
    # 4. Hypothetical scenario
    claim4 = Claim(
        id="test_4",
        type=ClaimType.FACTUAL,
        text="Suppose we had unlimited clean energy",
        speaker="TestSpeaker",
        sentence_id="sent_4", 
        turn_id=4,
        char_start=0,
        char_end=37,
        confidence=0.5,
        should_fact_check=False,
        classification_reason="Hypothetical scenario: contains 'suppose'"
    )
    claims.append(claim4)
    
    return claims


class MockFactCheckService:
    """Mock fact-checking service for testing"""
    
    def __init__(self, name: str, responses: dict):
        self.name = name
        self.responses = responses
    
    def is_available(self) -> bool:
        return True
        
    async def verify_claim(self, claim_text: str) -> FactCheckResult:
        """Return mock results based on claim text"""
        
        # Default response
        status = VerificationStatus.UNVERIFIED
        score = 0.5
        confidence = 0.1
        explanation = f"No fact-checks found for this claim by {self.name}"
        sources = []
        
        # Specific responses for test claims
        if "Earth is round" in claim_text:
            status = VerificationStatus.VERIFIED_TRUE
            score = 0.95
            confidence = 0.9
            explanation = f"{self.name}: Multiple scientific sources confirm Earth's spherical shape and heliocentric orbit. NASA, ESA, and peer-reviewed research validate this claim."
            sources = [
                VerificationSource(
                    name="NASA",
                    url="https://nasa.gov/earth-facts",
                    source_type=SourceType.GOVERNMENT,
                    credibility_score=0.95
                ),
                VerificationSource(
                    name="National Geographic",
                    url="https://nationalgeographic.com/earth-shape",
                    source_type=SourceType.ACADEMIC,
                    credibility_score=0.85
                )
            ]
        
        elif "that's the thing there" in claim_text:
            status = VerificationStatus.LIKELY_FALSE
            score = 0.2
            confidence = 0.3
            explanation = f"{self.name}: This appears to be conversational filler rather than a factual claim."
            sources = [
                VerificationSource(
                    name="Thing Database",
                    url=None,
                    source_type=SourceType.LOCAL_DATABASE,
                    credibility_score=0.6
                )
            ]
            
        elif "climate change is real" in claim_text:
            status = VerificationStatus.LIKELY_TRUE
            score = 0.8
            confidence = 0.8
            explanation = f"{self.name}: Scientific consensus strongly supports climate change reality. However, this was phrased as a question."
            sources = [
                VerificationSource(
                    name="IPCC",
                    url="https://ipcc.ch/reports",
                    source_type=SourceType.GOVERNMENT,
                    credibility_score=0.95
                )
            ]
            
        elif "unlimited clean energy" in claim_text:
            status = VerificationStatus.UNVERIFIED
            score = 0.5
            confidence = 0.2
            explanation = f"{self.name}: This is a hypothetical scenario that cannot be fact-checked."
        
        return FactCheckResult(
            service_name=self.name,
            query=claim_text,
            claim_text=claim_text,
            status=status,
            confidence=confidence,
            verification_score=score,
            sources=sources,
            explanation=explanation
        )
    
    def create_error_result(self, claim_text: str, error_msg: str) -> FactCheckResult:
        return FactCheckResult(
            service_name=self.name,
            query=claim_text,
            claim_text=claim_text,
            status=VerificationStatus.ERROR,
            confidence=0.0,
            verification_score=0.5,
            explanation=f"Error: {error_msg}"
        )


async def test_enhanced_explanations():
    """Test the enhanced explanation system"""
    
    print("🧪 Testing Enhanced Fact-Checking Explanations\n")
    
    # Create test pipeline with mock services
    config = FactCheckConfig(
        enabled=True,
        timeout_seconds=5,
        google_fact_check={'enabled': False},  # Disable real services
        local_database={'enabled': False}
    )
    
    pipeline = FactVerificationPipeline(config)
    
    # Replace with mock services
    mock_google = MockFactCheckService("MockGoogle", {})
    mock_local = MockFactCheckService("MockLocal", {})
    
    pipeline.services = [mock_google, mock_local]
    
    # Test claims
    test_claims = create_test_claims()
    
    print(f"Testing {len(test_claims)} claims...\n")
    
    # Verify each claim
    for i, claim in enumerate(test_claims, 1):
        print(f"{'='*60}")
        print(f"TEST {i}: {claim.text}")
        print(f"{'='*60}")
        
        try:
            result = await pipeline.verify_claim(claim)
            
            print(f"📊 **Status**: {result.overall_status.value}")
            print(f"📈 **Score**: {result.overall_score:.2f}")
            print(f"🎯 **Confidence**: {result.confidence:.2f}")
            print(f"📝 **Services**: {', '.join(result.services_used)}")
            print(f"📚 **Sources**: {result.sources_count}")
            
            print(f"\n📄 **Technical Summary**:")
            print(f"   {result.summary}")
            
            print(f"\n😊 **User-Friendly Explanation**:")
            print(f"   {result.friendly_explanation}")
            
            # Show filtering info if available
            if hasattr(claim, 'should_fact_check') and claim.should_fact_check is False:
                print(f"\n⚠️  **Filtering Info**:")
                print(f"   Should fact-check: {claim.should_fact_check}")
                print(f"   Reason: {getattr(claim, 'classification_reason', 'N/A')}")
            
            print(f"\n")
            
        except Exception as e:
            print(f"❌ Error testing claim: {e}")
            logger.exception("Error in test")
    
    await pipeline.close()
    print("✅ Testing completed!")


async def test_false_claim_explanations():
    """Test explanations specifically for false claims"""
    
    print("\n" + "="*60)
    print("🔍 Testing False Claim Explanations")
    print("="*60)
    
    # Create a false claim with detailed contradictory evidence
    false_claim = Claim(
        id="false_test",
        type=ClaimType.FACTUAL,
        text="Vaccines cause autism",
        speaker="TestSpeaker",
        sentence_id="sent_false",
        turn_id=5,
        char_start=0,
        char_end=20,
        confidence=0.8
    )
    
    # Create pipeline
    config = FactCheckConfig(enabled=True, timeout_seconds=5)
    pipeline = FactVerificationPipeline(config)
    
    # Mock service with detailed false claim response
    class MockFalseClaimService:
        def __init__(self):
            self.name = "MockFalseChecker"
        
        def is_available(self):
            return True
            
        async def verify_claim(self, claim_text: str) -> FactCheckResult:
            if "autism" in claim_text.lower():
                return FactCheckResult(
                    service_name=self.name,
                    query=claim_text,
                    claim_text=claim_text,
                    status=VerificationStatus.VERIFIED_FALSE,
                    confidence=0.95,
                    verification_score=0.05,
                    sources=[
                        VerificationSource(
                            name="CDC",
                            url="https://cdc.gov/vaccines-autism",
                            source_type=SourceType.GOVERNMENT, 
                            credibility_score=0.95
                        ),
                        VerificationSource(
                            name="The Lancet",
                            url="https://thelancet.com/retracted-study",
                            source_type=SourceType.ACADEMIC,
                            credibility_score=0.9
                        )
                    ],
                    explanation="Extensive scientific research has thoroughly debunked any link between vaccines and autism. The original study claiming this link was retracted due to fraudulent data. Multiple large-scale studies involving millions of children show no causal relationship."
                )
            
            return FactCheckResult(
                service_name=self.name,
                query=claim_text,
                claim_text=claim_text,
                status=VerificationStatus.UNVERIFIED,
                confidence=0.1,
                verification_score=0.5
            )
        
        def create_error_result(self, claim_text: str, error_msg: str):
            return FactCheckResult(
                service_name=self.name,
                query=claim_text,
                claim_text=claim_text,
                status=VerificationStatus.ERROR,
                confidence=0.0,
                verification_score=0.5
            )
    
    pipeline.services = [MockFalseClaimService()]
    
    result = await pipeline.verify_claim(false_claim)
    
    print(f"Claim: {false_claim.text}")
    print(f"Status: {result.overall_status.value}")
    print(f"\nTechnical Summary:")
    print(f"  {result.summary}")
    print(f"\nFriendly Explanation:")
    print(f"  {result.friendly_explanation}")
    
    await pipeline.close()
    

if __name__ == "__main__":
    asyncio.run(test_enhanced_explanations())
    asyncio.run(test_false_claim_explanations())
