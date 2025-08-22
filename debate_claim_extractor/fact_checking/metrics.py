"""Performance monitoring and metrics for fact-checking system."""

import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics
import json
from pathlib import Path

from .fact_models import FactCheckResult, VerificationStatus


@dataclass
class ServiceMetrics:
    """Metrics for individual fact-checking service."""
    service_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    total_duration: float = 0.0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_counts: Dict[str, int] = field(default_factory=dict)
    last_call_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if self.total_calls == 0:
            return 0.0
        return self.total_duration / self.total_calls
    
    @property
    def median_response_time(self) -> float:
        """Calculate median response time from recent calls."""
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)
    
    @property
    def p95_response_time(self) -> float:
        """Calculate 95th percentile response time."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[min(index, len(sorted_times) - 1)]


@dataclass
class VerificationMetrics:
    """Metrics for verification results."""
    total_claims: int = 0
    verified_claims: int = 0
    unverified_claims: int = 0
    status_counts: Dict[str, int] = field(default_factory=dict)
    confidence_distribution: Dict[str, int] = field(default_factory=dict)
    sources_used: Dict[str, int] = field(default_factory=dict)
    
    def add_result(self, result: FactCheckResult):
        """Add a fact-check result to metrics."""
        self.total_claims += 1
        
        # Track verification status
        status = result.verification_status.value
        self.status_counts[status] = self.status_counts.get(status, 0) + 1
        
        if result.verification_status != VerificationStatus.UNVERIFIED:
            self.verified_claims += 1
        else:
            self.unverified_claims += 1
        
        # Track confidence distribution
        confidence_bucket = self._get_confidence_bucket(result.confidence_score)
        self.confidence_distribution[confidence_bucket] = (
            self.confidence_distribution.get(confidence_bucket, 0) + 1
        )
        
        # Track sources
        for source in result.sources:
            self.sources_used[source.name] = self.sources_used.get(source.name, 0) + 1
    
    def _get_confidence_bucket(self, confidence: float) -> str:
        """Get confidence bucket label."""
        if confidence >= 0.9:
            return "very_high"
        elif confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        elif confidence >= 0.4:
            return "low"
        else:
            return "very_low"
    
    @property
    def verification_rate(self) -> float:
        """Calculate verification rate as percentage."""
        if self.total_claims == 0:
            return 0.0
        return (self.verified_claims / self.total_claims) * 100


class FactCheckMetricsCollector:
    """Collect and manage fact-checking metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.service_metrics: Dict[str, ServiceMetrics] = {}
        self.verification_metrics = VerificationMetrics()
        self.session_start_time = datetime.now(timezone.utc)
        self.pipeline_calls = 0
        self.batch_sizes = deque(maxlen=100)
        
    def record_service_call(self, service_name: str, duration: float, 
                           success: bool, error: Optional[Exception] = None,
                           timed_out: bool = False):
        """Record metrics for a service call."""
        if service_name not in self.service_metrics:
            self.service_metrics[service_name] = ServiceMetrics(service_name)
        
        metrics = self.service_metrics[service_name]
        metrics.total_calls += 1
        metrics.total_duration += duration
        metrics.response_times.append(duration)
        metrics.last_call_time = datetime.now(timezone.utc)
        
        if timed_out:
            metrics.timeout_calls += 1
        elif success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1
            
            if error:
                error_type = type(error).__name__
                metrics.error_counts[error_type] = (
                    metrics.error_counts.get(error_type, 0) + 1
                )
    
    def record_verification_result(self, result: FactCheckResult):
        """Record a verification result."""
        self.verification_metrics.add_result(result)
    
    def record_batch_verification(self, results: List[FactCheckResult]):
        """Record a batch of verification results."""
        self.pipeline_calls += 1
        self.batch_sizes.append(len(results))
        
        for result in results:
            self.record_verification_result(result)
    
    def get_service_summary(self, service_name: str) -> Dict[str, Any]:
        """Get summary metrics for a specific service."""
        if service_name not in self.service_metrics:
            return {"error": f"No metrics found for service: {service_name}"}
        
        metrics = self.service_metrics[service_name]
        return {
            "service_name": service_name,
            "total_calls": metrics.total_calls,
            "success_rate": round(metrics.success_rate, 2),
            "avg_response_time": round(metrics.average_response_time, 3),
            "median_response_time": round(metrics.median_response_time, 3),
            "p95_response_time": round(metrics.p95_response_time, 3),
            "error_counts": metrics.error_counts,
            "timeout_calls": metrics.timeout_calls,
            "last_call": metrics.last_call_time.isoformat() if metrics.last_call_time else None
        }
    
    def get_overall_summary(self) -> Dict[str, Any]:
        """Get overall system metrics summary."""
        session_duration = datetime.now(timezone.utc) - self.session_start_time
        
        return {
            "session": {
                "start_time": self.session_start_time.isoformat(),
                "duration_seconds": session_duration.total_seconds(),
                "pipeline_calls": self.pipeline_calls
            },
            "verification": {
                "total_claims": self.verification_metrics.total_claims,
                "verified_claims": self.verification_metrics.verified_claims,
                "verification_rate": round(self.verification_metrics.verification_rate, 2),
                "status_distribution": self.verification_metrics.status_counts,
                "confidence_distribution": self.verification_metrics.confidence_distribution,
                "top_sources": sorted(
                    self.verification_metrics.sources_used.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            },
            "services": {
                name: self.get_service_summary(name)
                for name in self.service_metrics.keys()
            },
            "performance": {
                "avg_batch_size": statistics.mean(self.batch_sizes) if self.batch_sizes else 0,
                "total_service_calls": sum(m.total_calls for m in self.service_metrics.values()),
                "overall_success_rate": self._calculate_overall_success_rate()
            }
        }
    
    def _calculate_overall_success_rate(self) -> float:
        """Calculate overall success rate across all services."""
        total_calls = sum(m.total_calls for m in self.service_metrics.values())
        successful_calls = sum(m.successful_calls for m in self.service_metrics.values())
        
        if total_calls == 0:
            return 0.0
        
        return (successful_calls / total_calls) * 100
    
    def export_metrics(self, filepath: str) -> bool:
        """Export metrics to JSON file."""
        try:
            metrics_data = self.get_overall_summary()
            with open(filepath, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            return True
        except Exception:
            return False
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.service_metrics.clear()
        self.verification_metrics = VerificationMetrics()
        self.session_start_time = datetime.now(timezone.utc)
        self.pipeline_calls = 0
        self.batch_sizes.clear()


class PerformanceMonitor:
    """Monitor performance and detect issues in real-time."""
    
    def __init__(self, metrics_collector: FactCheckMetricsCollector):
        """Initialize performance monitor."""
        self.metrics = metrics_collector
        self.alerts: List[Dict[str, Any]] = []
        self.thresholds = {
            "max_response_time": 10.0,  # seconds
            "min_success_rate": 80.0,   # percentage
            "max_error_rate": 20.0,     # percentage
        }
    
    def check_service_health(self, service_name: str) -> List[str]:
        """Check health of a specific service and return alerts."""
        if service_name not in self.metrics.service_metrics:
            return []
        
        metrics = self.metrics.service_metrics[service_name]
        alerts = []
        
        # Check response time
        if metrics.average_response_time > self.thresholds["max_response_time"]:
            alerts.append(
                f"High response time: {metrics.average_response_time:.2f}s "
                f"(threshold: {self.thresholds['max_response_time']}s)"
            )
        
        # Check success rate
        if metrics.success_rate < self.thresholds["min_success_rate"]:
            alerts.append(
                f"Low success rate: {metrics.success_rate:.1f}% "
                f"(threshold: {self.thresholds['min_success_rate']}%)"
            )
        
        # Check for frequent errors
        total_errors = metrics.failed_calls + metrics.timeout_calls
        error_rate = (total_errors / metrics.total_calls * 100) if metrics.total_calls > 0 else 0
        
        if error_rate > self.thresholds["max_error_rate"]:
            alerts.append(
                f"High error rate: {error_rate:.1f}% "
                f"(threshold: {self.thresholds['max_error_rate']}%)"
            )
        
        return alerts
    
    def check_overall_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        health_status = {
            "status": "healthy",
            "alerts": [],
            "service_statuses": {}
        }
        
        for service_name in self.metrics.service_metrics:
            service_alerts = self.check_service_health(service_name)
            health_status["service_statuses"][service_name] = {
                "status": "healthy" if not service_alerts else "degraded",
                "alerts": service_alerts
            }
            
            if service_alerts:
                health_status["status"] = "degraded"
                health_status["alerts"].extend([
                    f"{service_name}: {alert}" for alert in service_alerts
                ])
        
        return health_status
    
    def get_performance_recommendations(self) -> List[str]:
        """Get performance improvement recommendations."""
        recommendations = []
        
        # Check for slow services
        for service_name, metrics in self.metrics.service_metrics.items():
            if metrics.average_response_time > 5.0:
                recommendations.append(
                    f"Consider optimizing {service_name} - "
                    f"average response time is {metrics.average_response_time:.2f}s"
                )
            
            if metrics.success_rate < 90.0:
                recommendations.append(
                    f"Investigate {service_name} reliability - "
                    f"success rate is {metrics.success_rate:.1f}%"
                )
        
        # Check verification coverage
        if self.metrics.verification_metrics.verification_rate < 70.0:
            recommendations.append(
                "Consider adding more fact-checking sources to improve verification coverage"
            )
        
        return recommendations


class MetricsReporter:
    """Generate human-readable reports from metrics."""
    
    def __init__(self, metrics_collector: FactCheckMetricsCollector):
        """Initialize metrics reporter."""
        self.metrics = metrics_collector
    
    def generate_text_report(self) -> str:
        """Generate a comprehensive text report."""
        summary = self.metrics.get_overall_summary()
        
        report = []
        report.append("=" * 60)
        report.append("FACT-CHECKING SYSTEM METRICS REPORT")
        report.append("=" * 60)
        
        # Session info
        session = summary["session"]
        duration = timedelta(seconds=session["duration_seconds"])
        report.append(f"\nSession Duration: {duration}")
        report.append(f"Pipeline Calls: {session['pipeline_calls']}")
        
        # Verification metrics
        verification = summary["verification"]
        report.append(f"\n📊 VERIFICATION METRICS")
        report.append(f"Total Claims Processed: {verification['total_claims']}")
        report.append(f"Verification Rate: {verification['verification_rate']}%")
        
        # Status distribution
        report.append(f"\n📈 STATUS DISTRIBUTION")
        for status, count in verification["status_distribution"].items():
            percentage = (count / verification["total_claims"] * 100) if verification["total_claims"] > 0 else 0
            report.append(f"  {status}: {count} ({percentage:.1f}%)")
        
        # Service performance
        report.append(f"\n🔧 SERVICE PERFORMANCE")
        for service_name, service_data in summary["services"].items():
            if "error" in service_data:
                continue
                
            report.append(f"\n{service_name.upper()}:")
            report.append(f"  Calls: {service_data['total_calls']}")
            report.append(f"  Success Rate: {service_data['success_rate']}%")
            report.append(f"  Avg Response: {service_data['avg_response_time']}s")
            report.append(f"  95th Percentile: {service_data['p95_response_time']}s")
            
            if service_data.get("error_counts"):
                report.append(f"  Errors: {service_data['error_counts']}")
        
        # Top sources
        report.append(f"\n📚 TOP SOURCES")
        for source, count in verification["top_sources"][:5]:
            report.append(f"  {source}: {count} verifications")
        
        return "\n".join(report)
    
    def generate_performance_summary(self) -> str:
        """Generate a brief performance summary."""
        summary = self.metrics.get_overall_summary()
        
        total_claims = summary["verification"]["total_claims"]
        verification_rate = summary["verification"]["verification_rate"]
        overall_success = summary["performance"]["overall_success_rate"]
        
        return (
            f"Processed {total_claims} claims with {verification_rate:.1f}% verification rate. "
            f"Overall service success rate: {overall_success:.1f}%."
        )


# Context managers for automatic metrics collection
class ServiceCallTimer:
    """Context manager for timing service calls."""
    
    def __init__(self, metrics_collector: FactCheckMetricsCollector, service_name: str):
        """Initialize service call timer."""
        self.metrics = metrics_collector
        self.service_name = service_name
        self.start_time = None
        self.success = False
        self.error = None
        self.timed_out = False
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and record metrics."""
        if self.start_time:
            duration = time.time() - self.start_time
            
            if exc_type is asyncio.TimeoutError:
                self.timed_out = True
                self.success = False
            elif exc_type is None:
                self.success = True
            else:
                self.success = False
                self.error = exc_val
            
            self.metrics.record_service_call(
                self.service_name,
                duration,
                self.success,
                self.error,
                self.timed_out
            )
        
        # Don't suppress exceptions
        return False


# Global metrics collector instance
_global_metrics_collector = None

def get_metrics_collector() -> FactCheckMetricsCollector:
    """Get global metrics collector instance."""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = FactCheckMetricsCollector()
    return _global_metrics_collector

def reset_global_metrics():
    """Reset global metrics collector."""
    global _global_metrics_collector
    _global_metrics_collector = None
