"""Debugging and logging utilities for fact-checking system."""

import logging
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

from .fact_models import FactCheckResult, AggregatedVerification
from ..models import Claim


class FactCheckLogger:
    """Enhanced logger for fact-checking operations."""
    
    def __init__(self, name: str = "fact_checking", level: int = logging.INFO):
        """Initialize logger with custom formatting."""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def log_claim_verification_start(self, claim: Claim, services: List[str]):
        """Log start of claim verification."""
        self.logger.info(
            f"Starting verification for claim: '{claim.text[:50]}...' "
            f"using services: {services}"
        )
    
    def log_service_result(self, service_name: str, claim_text: str, 
                          results: List[FactCheckResult], duration: float):
        """Log results from individual service."""
        self.logger.debug(
            f"Service '{service_name}' completed in {duration:.2f}s. "
            f"Found {len(results)} results for: '{claim_text[:30]}...'"
        )
        
        for i, result in enumerate(results):
            self.logger.debug(
                f"  Result {i+1}: {result.status.value} "
                f"(confidence: {result.confidence:.2f})"
            )
    
    def log_aggregation_details(self, claim_text: str, individual_results: List[FactCheckResult],
                               final_result: FactCheckResult):
        """Log details about result aggregation."""
        self.logger.debug(f"Aggregating {len(individual_results)} results for: '{claim_text[:30]}...'")
        
        for i, result in enumerate(individual_results):
            self.logger.debug(
                f"  Input {i+1}: {result.verification_status.value} "
                f"(conf: {result.confidence_score:.2f}, sources: {len(result.sources)})"
            )
        
        self.logger.info(
            f"Final aggregated result: {final_result.verification_status.value} "
            f"(conf: {final_result.confidence_score:.2f}, "
            f"sources: {len(final_result.sources)}) for: '{claim_text[:30]}...'"
        )
    
    def log_error(self, service_name: str, claim_text: str, error: Exception):
        """Log service errors."""
        self.logger.error(
            f"Service '{service_name}' failed for claim '{claim_text[:30]}...': "
            f"{type(error).__name__}: {str(error)}"
        )
    
    def log_timeout(self, service_name: str, claim_text: str, timeout: float):
        """Log service timeouts."""
        self.logger.warning(
            f"Service '{service_name}' timed out after {timeout}s "
            f"for claim: '{claim_text[:30]}...'"
        )


class FactCheckDebugger:
    """Debugging utilities for fact-checking pipeline."""
    
    def __init__(self, output_dir: Optional[str] = None):
        """Initialize debugger with optional output directory."""
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_data = {
            "session_id": self.session_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "claims": [],
            "service_calls": [],
            "errors": []
        }
    
    def record_claim_start(self, claim: Claim) -> str:
        """Record start of claim processing and return claim ID."""
        claim_id = f"claim_{len(self.debug_data['claims'])}"
        
        claim_record = {
            "id": claim_id,
            "text": claim.text,
            "type": claim.claim_type.value if claim.claim_type else None,
            "confidence": claim.confidence,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "services": [],
            "final_result": None
        }
        
        self.debug_data["claims"].append(claim_record)
        return claim_id
    
    def record_service_call(self, claim_id: str, service_name: str, 
                           results: List[FactCheckResult], duration: float,
                           error: Optional[Exception] = None):
        """Record service call results."""
        service_record = {
            "claim_id": claim_id,
            "service": service_name,
            "duration": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": error is None,
            "results_count": len(results) if results else 0,
            "error": str(error) if error else None
        }
        
        if results:
            service_record["results"] = [
                {
                    "status": r.verification_status.value,
                    "confidence": r.confidence_score,
                    "sources_count": len(r.sources)
                }
                for r in results
            ]
        
        self.debug_data["service_calls"].append(service_record)
        
        # Update claim record
        for claim in self.debug_data["claims"]:
            if claim["id"] == claim_id:
                claim["services"].append(service_record)
                break
    
    def record_final_result(self, claim_id: str, result: FactCheckResult):
        """Record final aggregated result for a claim."""
        result_record = {
            "status": result.verification_status.value,
            "confidence": result.confidence_score,
            "sources_count": len(result.sources),
            "summary": result.verification_summary.model_dump() if result.verification_summary else None
        }
        
        # Update claim record
        for claim in self.debug_data["claims"]:
            if claim["id"] == claim_id:
                claim["final_result"] = result_record
                claim["end_time"] = datetime.now(timezone.utc).isoformat()
                break
    
    def record_error(self, context: str, error: Exception, details: Dict[str, Any] = None):
        """Record an error with context."""
        error_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "details": details or {}
        }
        
        self.debug_data["errors"].append(error_record)
    
    def save_debug_session(self) -> Optional[str]:
        """Save debug session to file."""
        if not self.output_dir:
            return None
        
        self.debug_data["end_time"] = datetime.now(timezone.utc).isoformat()
        
        filename = f"fact_check_debug_{self.session_id}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.debug_data, f, indent=2)
        
        return str(filepath)
    
    def print_summary(self):
        """Print debugging summary to console."""
        print(f"\n=== Fact-Checking Debug Summary (Session: {self.session_id}) ===")
        print(f"Claims processed: {len(self.debug_data['claims'])}")
        print(f"Service calls made: {len(self.debug_data['service_calls'])}")
        print(f"Errors encountered: {len(self.debug_data['errors'])}")
        
        # Service performance
        service_stats = {}
        for call in self.debug_data['service_calls']:
            service = call['service']
            if service not in service_stats:
                service_stats[service] = {'calls': 0, 'total_time': 0, 'errors': 0}
            
            service_stats[service]['calls'] += 1
            service_stats[service]['total_time'] += call['duration']
            if not call['success']:
                service_stats[service]['errors'] += 1
        
        print("\n=== Service Performance ===")
        for service, stats in service_stats.items():
            avg_time = stats['total_time'] / stats['calls'] if stats['calls'] > 0 else 0
            error_rate = (stats['errors'] / stats['calls'] * 100) if stats['calls'] > 0 else 0
            print(f"{service}:")
            print(f"  Calls: {stats['calls']}, Avg time: {avg_time:.2f}s")
            print(f"  Error rate: {error_rate:.1f}%")
        
        # Claim results distribution
        status_counts = {}
        for claim in self.debug_data['claims']:
            if claim['final_result']:
                status = claim['final_result']['status']
                status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\n=== Result Distribution ===")
        for status, count in status_counts.items():
            print(f"{status}: {count}")
        
        if self.debug_data['errors']:
            print("\n=== Recent Errors ===")
            for error in self.debug_data['errors'][-3:]:  # Last 3 errors
                print(f"{error['timestamp']}: {error['error_type']} in {error['context']}")
                print(f"  {error['error_message']}")


@contextmanager
def time_operation(operation_name: str, logger: Optional[FactCheckLogger] = None):
    """Context manager to time operations."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        if logger:
            logger.logger.debug(f"Operation '{operation_name}' took {duration:.2f}s")
        else:
            print(f"[TIMING] {operation_name}: {duration:.2f}s")


class FactCheckInspector:
    """Utilities to inspect and analyze fact-checking results."""
    
    @staticmethod
    def analyze_confidence_distribution(results: List[FactCheckResult]) -> Dict[str, Any]:
        """Analyze confidence score distribution in results."""
        if not results:
            return {"error": "No results to analyze"}
        
        confidences = [r.confidence_score for r in results]
        
        return {
            "count": len(confidences),
            "mean": sum(confidences) / len(confidences),
            "min": min(confidences),
            "max": max(confidences),
            "high_confidence": len([c for c in confidences if c >= 0.8]),
            "medium_confidence": len([c for c in confidences if 0.5 <= c < 0.8]),
            "low_confidence": len([c for c in confidences if c < 0.5])
        }
    
    @staticmethod
    def analyze_source_quality(results: List[FactCheckResult]) -> Dict[str, Any]:
        """Analyze source quality across results."""
        all_sources = []
        for result in results:
            all_sources.extend(result.sources)
        
        if not all_sources:
            return {"error": "No sources to analyze"}
        
        credibilities = [s.credibility_score for s in all_sources if s.credibility_score is not None]
        
        source_names = {}
        for source in all_sources:
            source_names[source.name] = source_names.get(source.name, 0) + 1
        
        return {
            "total_sources": len(all_sources),
            "unique_sources": len(source_names),
            "most_common_sources": sorted(source_names.items(), key=lambda x: x[1], reverse=True)[:5],
            "credibility_stats": {
                "mean": sum(credibilities) / len(credibilities) if credibilities else 0,
                "min": min(credibilities) if credibilities else 0,
                "max": max(credibilities) if credibilities else 0,
                "count": len(credibilities)
            }
        }
    
    @staticmethod
    def compare_service_agreement(results_by_service: Dict[str, List[FactCheckResult]]) -> Dict[str, Any]:
        """Compare agreement between different fact-checking services."""
        if len(results_by_service) < 2:
            return {"error": "Need at least 2 services to compare"}
        
        # Find common claims
        common_claims = set()
        for service_results in results_by_service.values():
            claim_texts = {r.claim_text for r in service_results}
            if not common_claims:
                common_claims = claim_texts
            else:
                common_claims &= claim_texts
        
        agreements = []
        disagreements = []
        
        for claim_text in common_claims:
            service_statuses = []
            for service, results in results_by_service.items():
                for result in results:
                    if result.claim_text == claim_text:
                        service_statuses.append((service, result.verification_status.value))
                        break
            
            if len(set(status for _, status in service_statuses)) == 1:
                agreements.append((claim_text, service_statuses))
            else:
                disagreements.append((claim_text, service_statuses))
        
        return {
            "common_claims": len(common_claims),
            "agreements": len(agreements),
            "disagreements": len(disagreements),
            "agreement_rate": len(agreements) / len(common_claims) if common_claims else 0,
            "disagreement_examples": disagreements[:3]  # First 3 disagreements
        }


def create_debug_cli_command():
    """Create a CLI command for debugging fact-checking results."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug fact-checking results")
    parser.add_argument("--session-file", help="Path to debug session JSON file")
    parser.add_argument("--analyze", action="store_true", help="Run analysis on session data")
    
    args = parser.parse_args()
    
    if args.session_file:
        with open(args.session_file) as f:
            session_data = json.load(f)
        
        if args.analyze:
            # Perform analysis
            print(f"=== Analysis of Session {session_data['session_id']} ===")
            
            # Service performance analysis
            service_calls = session_data.get('service_calls', [])
            services = {}
            for call in service_calls:
                service = call['service']
                if service not in services:
                    services[service] = []
                services[service].append(call)
            
            for service_name, calls in services.items():
                durations = [call['duration'] for call in calls]
                success_rate = len([c for c in calls if c['success']]) / len(calls) * 100
                
                print(f"\n{service_name}:")
                print(f"  Total calls: {len(calls)}")
                print(f"  Avg duration: {sum(durations)/len(durations):.2f}s")
                print(f"  Success rate: {success_rate:.1f}%")
    
    return parser


if __name__ == "__main__":
    # Run debug CLI if called directly
    create_debug_cli_command()
