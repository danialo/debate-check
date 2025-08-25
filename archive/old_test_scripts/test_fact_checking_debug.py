#!/usr/bin/env python3
"""
Simple debugging test for the fact-checking system.
"""

import asyncio
import json
import tempfile
from pathlib import Path

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


async def test_basic_models():
    """Test basic model creation and serialization."""
    print("🔧 Testing basic models...")
    
    # Test FactCheckResult creation
    result = FactCheckResult(
        service_name="test_service",
        query="The sky is blue", 
        claim_text="The sky is blue",
        status=VerificationStatus.VERIFIED_TRUE,
        confidence=0.95,
        verification_score=0.95,
        sources=[
            VerificationSource(
                name="Test Source",
                url="https://test.com",
                source_type=SourceType.ACADEMIC,
                credibility_score=0.9
            )
        ]
    )
    
    print(f"  ✅ Created FactCheckResult: {result.status.value}")
    
    # Test serialization (avoiding datetime issues)
    data = result.model_dump()
    print(f"  ✅ Serialized result, status: {data['status']}")
    
    return True


async def test_local_service():
    """Test local fact-checking service."""
    print("🧪 Testing local service...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db = f.name
    
    try:
        service = LocalFactCheckService(database_path=temp_db)
        print(f"  ✅ Created local service: {service.name}")
        print(f"  ✅ Service available: {service.is_available()}")
        
        # Test verification with no matches (should work with sample data)
        result = await service.verify_claim("The moon is made of cheese")
        print(f"  ✅ Verified claim, status: {result.status.value}")
        
        return True
        
    finally:
        # Clean up
        import os
        if os.path.exists(temp_db):
            os.unlink(temp_db)


async def test_pipeline():
    """Test fact verification pipeline."""
    print("🚀 Testing verification pipeline...")
    
    config = FactCheckConfig(timeout_seconds=10)
    pipeline = FactVerificationPipeline(config=config)
    
    print(f"  ✅ Created pipeline with {len(pipeline.services)} services")
    
    # Test with empty services (should handle gracefully)
    pipeline.services = []
    
    claim = Claim(
        type=ClaimType.FACTUAL,
        text="Test claim for pipeline",
        speaker="TestSpeaker",
        sentence_id="test_sentence_1",
        turn_id=1,
        char_start=0,
        char_end=len("Test claim for pipeline"),
        confidence=0.8
    )
    
    result = await pipeline.verify_claim(claim)
    print(f"  ✅ Pipeline result: {result.overall_status.value}")
    
    return True


async def test_metrics_collection():
    """Test metrics collection."""
    print("📊 Testing metrics collection...")
    
    from debate_claim_extractor.fact_checking.metrics import (
        FactCheckMetricsCollector, MetricsReporter
    )
    
    collector = FactCheckMetricsCollector()
    reporter = MetricsReporter(collector)
    
    # Record some fake metrics
    collector.record_service_call("test_service", 0.5, True)
    collector.record_service_call("test_service", 0.7, True)
    collector.record_service_call("test_service", 1.2, False, Exception("Test error"))
    
    print(f"  ✅ Recorded 3 service calls")
    
    # Generate summary
    summary = collector.get_overall_summary()
    print(f"  ✅ Generated summary with {summary['performance']['total_service_calls']} calls")
    
    # Test brief report
    brief = reporter.generate_performance_summary()
    print(f"  ✅ Generated report: {brief}")
    
    return True


async def main():
    """Run all debugging tests."""
    print("=" * 60)
    print("FACT-CHECKING SYSTEM DEBUG TEST")
    print("=" * 60)
    
    tests = [
        ("Basic Models", test_basic_models),
        ("Local Service", test_local_service), 
        ("Pipeline", test_pipeline),
        ("Metrics", test_metrics_collection),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = await test_func()
            results.append((test_name, success, None))
            print(f"✅ {test_name}: PASSED\n")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"❌ {test_name}: FAILED - {e}\n")
    
    print("=" * 60)
    print("SUMMARY")
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
        print("🎉 All tests passed!")
    else:
        print("🔍 Some tests failed - check errors above")


if __name__ == "__main__":
    asyncio.run(main())
