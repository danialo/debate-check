#!/usr/bin/env python3
"""
CLI debugging tools for the fact-checking system.

This script provides various debugging and analysis tools to help test,
monitor, and troubleshoot the fact-checking pipeline.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import time

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from debate_claim_extractor.fact_checking.fact_pipeline import FactVerificationPipeline
from debate_claim_extractor.fact_checking.fact_models import FactCheckConfig
from debate_claim_extractor.fact_checking.services.local_service import LocalFactCheckService
from debate_claim_extractor.fact_checking.debug_utils import (
    FactCheckLogger, FactCheckDebugger, FactCheckInspector
)
from debate_claim_extractor.fact_checking.metrics import (
    FactCheckMetricsCollector, PerformanceMonitor, MetricsReporter
)
from debate_claim_extractor.models import Claim, ClaimType
from tests.mock_services import (
    TestDataGenerator, MockGoogleFactCheckService, MockLocalFactCheckService,
    TestEnvironmentManager
)


class FactCheckingCLIDebugger:
    """Main CLI debugger for fact-checking system."""
    
    def __init__(self):
        """Initialize the CLI debugger."""
        self.metrics_collector = FactCheckMetricsCollector()
        self.performance_monitor = PerformanceMonitor(self.metrics_collector)
        self.metrics_reporter = MetricsReporter(self.metrics_collector)
        self.test_data = TestDataGenerator()
    
    async def test_basic_pipeline(self, verbose: bool = False) -> Dict[str, Any]:
        """Test basic fact-checking pipeline functionality."""
        print("🔧 Testing basic fact-checking pipeline...")
        
        # Create pipeline with local service
        config = FactCheckConfig(timeout_seconds=30)
        pipeline = FactVerificationPipeline(config=config)
        
        # Add local service with test data
        local_service = LocalFactCheckService()
        await local_service._populate_test_data([
            {
                "claim": "The sky is blue",
                "status": "VERIFIED_TRUE",
                "confidence": 0.99,
                "source": "Physics",
                "url": "https://physics.org/sky"
            }
        ])
        pipeline.add_service(local_service)
        
        # Test claim
        test_claim = Claim(
            text="The sky is blue",
            claim_type=ClaimType.FACTUAL,
            confidence=0.9
        )
        
        start_time = time.time()
        result = await pipeline.verify_claim(test_claim)
        duration = time.time() - start_time
        
        if verbose:
            print(f"  ✅ Claim verified in {duration:.2f}s")
            print(f"  Status: {result.verification_status.value}")
            print(f"  Confidence: {result.confidence_score:.2f}")
        
        return {
            "success": True,
            "duration": duration,
            "status": result.verification_status.value,
            "confidence": result.confidence_score
        }
    
    async def test_mock_services(self, verbose: bool = False) -> Dict[str, Any]:
        """Test with mock services for consistent results."""
        print("🧪 Testing with mock services...")
        
        # Create mock environment
        env_manager = TestEnvironmentManager()
        mock_services = env_manager.create_mock_environment()
        
        config = FactCheckConfig(timeout_seconds=10)
        pipeline = FactVerificationPipeline(config=config)
        
        for service in mock_services.values():
            pipeline.add_service(service)
        
        # Test with various claims
        test_claims = [
            "vaccines are safe",
            "climate change is a hoax",
            "the sky is blue"
        ]
        
        results = {}
        
        for claim_text in test_claims:
            claim = Claim(
                text=claim_text,
                claim_type=ClaimType.FACTUAL,
                confidence=0.8
            )
            
            start_time = time.time()
            result = await pipeline.verify_claim(claim)
            duration = time.time() - start_time
            
            results[claim_text] = {
                "status": result.verification_status.value,
                "confidence": result.confidence_score,
                "sources": len(result.sources),
                "duration": duration
            }
            
            if verbose:
                print(f"  '{claim_text}': {result.verification_status.value} "
                      f"(conf: {result.confidence_score:.2f})")
        
        return {
            "success": True,
            "total_claims": len(test_claims),
            "results": results
        }
    
    async def test_error_handling(self, verbose: bool = False) -> Dict[str, Any]:
        """Test error handling capabilities."""
        print("💥 Testing error handling...")
        
        from tests.mock_services import MockFailingService, MockSlowService
        
        config = FactCheckConfig(timeout_seconds=2)  # Short timeout
        pipeline = FactVerificationPipeline(config=config)
        
        # Add services that will cause different types of errors
        pipeline.add_service(MockFailingService(ConnectionError, "Network error"))
        pipeline.add_service(MockSlowService(delay_seconds=5))  # Will timeout
        
        test_claim = Claim(
            text="Test error handling",
            claim_type=ClaimType.FACTUAL,
            confidence=0.8
        )
        
        start_time = time.time()
        result = await pipeline.verify_claim(test_claim)
        duration = time.time() - start_time
        
        if verbose:
            print(f"  ⚠️  Pipeline handled errors gracefully in {duration:.2f}s")
            print(f"  Final status: {result.verification_status.value}")
        
        return {
            "success": True,
            "handled_errors": True,
            "duration": duration,
            "final_status": result.verification_status.value
        }
    
    async def run_performance_benchmark(self, num_claims: int = 10, 
                                       verbose: bool = False) -> Dict[str, Any]:
        """Run performance benchmark with multiple claims."""
        print(f"🚀 Running performance benchmark with {num_claims} claims...")
        
        # Setup mock environment
        env_manager = TestEnvironmentManager()
        mock_services = env_manager.create_mock_environment()
        
        config = FactCheckConfig(timeout_seconds=30)
        pipeline = FactVerificationPipeline(config=config)
        
        for service in mock_services.values():
            pipeline.add_service(service)
        
        # Generate test claims
        test_claims_text = self.test_data.generate_test_claims()[:num_claims]
        claims = [
            Claim(text=text, claim_type=ClaimType.FACTUAL, confidence=0.8)
            for text in test_claims_text
        ]
        
        start_time = time.time()
        results = await pipeline.verify_claims(claims)
        total_duration = time.time() - start_time
        
        # Record metrics
        self.metrics_collector.record_batch_verification(results)
        
        stats = {
            "total_claims": len(claims),
            "total_duration": total_duration,
            "avg_per_claim": total_duration / len(claims),
            "verified_count": sum(1 for r in results if r.verification_status.name != "UNVERIFIED"),
            "avg_confidence": sum(r.confidence_score for r in results) / len(results),
            "services_used": len(mock_services)
        }
        
        if verbose:
            print(f"  📊 Processed {stats['total_claims']} claims in {stats['total_duration']:.2f}s")
            print(f"  ⚡ Average: {stats['avg_per_claim']:.2f}s per claim")
            print(f"  ✅ Verified: {stats['verified_count']}/{stats['total_claims']}")
            print(f"  🎯 Avg confidence: {stats['avg_confidence']:.2f}")
        
        return stats
    
    def analyze_debug_session(self, session_file: str) -> Dict[str, Any]:
        """Analyze a debug session file."""
        print(f"🔍 Analyzing debug session: {session_file}")
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
        except FileNotFoundError:
            return {"error": f"File not found: {session_file}"}
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON in file: {session_file}"}
        
        analysis = {
            "session_id": session_data.get("session_id"),
            "duration": session_data.get("end_time", "Unknown"),
            "claims_processed": len(session_data.get("claims", [])),
            "service_calls": len(session_data.get("service_calls", [])),
            "errors": len(session_data.get("errors", []))
        }
        
        # Service performance analysis
        service_stats = {}
        for call in session_data.get("service_calls", []):
            service = call["service"]
            if service not in service_stats:
                service_stats[service] = {
                    "calls": 0, "successes": 0, "failures": 0, "total_time": 0
                }
            
            stats = service_stats[service]
            stats["calls"] += 1
            stats["total_time"] += call["duration"]
            
            if call["success"]:
                stats["successes"] += 1
            else:
                stats["failures"] += 1
        
        # Calculate rates
        for service, stats in service_stats.items():
            if stats["calls"] > 0:
                stats["success_rate"] = (stats["successes"] / stats["calls"]) * 100
                stats["avg_time"] = stats["total_time"] / stats["calls"]
        
        analysis["service_performance"] = service_stats
        
        print(f"  📈 Session {analysis['session_id']}")
        print(f"  🔢 Claims: {analysis['claims_processed']}, "
              f"Calls: {analysis['service_calls']}, "
              f"Errors: {analysis['errors']}")
        
        for service, stats in service_stats.items():
            print(f"  🔧 {service}: {stats['calls']} calls, "
                  f"{stats['success_rate']:.1f}% success, "
                  f"{stats['avg_time']:.2f}s avg")
        
        return analysis
    
    def generate_metrics_report(self) -> str:
        """Generate comprehensive metrics report."""
        return self.metrics_reporter.generate_text_report()
    
    def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        return self.performance_monitor.check_overall_health()


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Debug and test the fact-checking system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python debug_fact_checking.py --test-basic --verbose
  python debug_fact_checking.py --benchmark 20 --verbose
  python debug_fact_checking.py --analyze session_20241201_120000.json
  python debug_fact_checking.py --health-check
        """
    )
    
    parser.add_argument("--test-basic", action="store_true",
                       help="Run basic pipeline test")
    parser.add_argument("--test-mocks", action="store_true",
                       help="Test with mock services")
    parser.add_argument("--test-errors", action="store_true",
                       help="Test error handling")
    parser.add_argument("--benchmark", type=int, metavar="N",
                       help="Run performance benchmark with N claims")
    parser.add_argument("--analyze", metavar="FILE",
                       help="Analyze debug session file")
    parser.add_argument("--health-check", action="store_true",
                       help="Check system health")
    parser.add_argument("--metrics-report", action="store_true",
                       help="Generate metrics report")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    if not any([args.test_basic, args.test_mocks, args.test_errors, 
                args.benchmark, args.analyze, args.health_check, 
                args.metrics_report]):
        parser.print_help()
        return
    
    debugger = FactCheckingCLIDebugger()
    
    try:
        if args.test_basic:
            result = await debugger.test_basic_pipeline(verbose=args.verbose)
            if result["success"]:
                print("✅ Basic pipeline test passed")
            else:
                print("❌ Basic pipeline test failed")
        
        if args.test_mocks:
            result = await debugger.test_mock_services(verbose=args.verbose)
            if result["success"]:
                print("✅ Mock services test passed")
            else:
                print("❌ Mock services test failed")
        
        if args.test_errors:
            result = await debugger.test_error_handling(verbose=args.verbose)
            if result["success"]:
                print("✅ Error handling test passed")
            else:
                print("❌ Error handling test failed")
        
        if args.benchmark:
            result = await debugger.run_performance_benchmark(
                num_claims=args.benchmark,
                verbose=args.verbose
            )
            print(f"✅ Benchmark completed: {result['avg_per_claim']:.2f}s per claim")
        
        if args.analyze:
            result = debugger.analyze_debug_session(args.analyze)
            if "error" in result:
                print(f"❌ Analysis failed: {result['error']}")
            else:
                print("✅ Analysis completed")
        
        if args.health_check:
            health = debugger.check_system_health()
            status_emoji = "✅" if health["status"] == "healthy" else "⚠️"
            print(f"{status_emoji} System status: {health['status']}")
            
            if health["alerts"]:
                print("🚨 Alerts:")
                for alert in health["alerts"]:
                    print(f"  - {alert}")
        
        if args.metrics_report:
            report = debugger.generate_metrics_report()
            print(report)
    
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
