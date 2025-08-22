# Testing and Debugging Guide for Fact-Checking System

This document provides comprehensive guidance on testing, debugging, and monitoring the fact-checking system integrated into the debate claim extractor.

## Overview

Your fact-checking system is now fully integrated with comprehensive testing and debugging capabilities:

✅ **Comprehensive Test Suite** - Unit and integration tests  
✅ **Debugging Framework** - Detailed logging and error tracking  
✅ **Performance Monitoring** - Metrics collection and analysis  
✅ **Mock Services** - Reliable testing environments  
✅ **CLI Debug Tools** - Command-line debugging utilities  

## Testing Components

### 1. Comprehensive Test Suite (`tests/test_fact_checking.py`)

**Complete unit and integration tests covering:**
- ✅ Fact-checking data models (FactCheckResult, VerificationSource, etc.)
- ✅ Local fact-checking service with database operations
- ✅ Google Fact Check Tools API service (with mocked responses)
- ✅ Fact verification pipeline orchestration
- ✅ Error handling and timeout scenarios
- ✅ JSON serialization and data integrity
- ✅ End-to-end pipeline integration

**Run the full test suite:**
```bash
python -m pytest tests/test_fact_checking.py -v
```

### 2. Simplified Test Suite (`tests/test_fact_checking_simple.py`)

**Lightweight tests for core functionality:**
- ✅ Basic model creation and validation
- ✅ Service initialization and availability
- ✅ Pipeline creation and empty service handling
- ✅ Basic integration testing

**Run simplified tests:**
```bash
python -m pytest tests/test_fact_checking_simple.py -v
```

### 3. Mock Services (`tests/mock_services.py`)

**Complete mock implementations for reliable testing:**

- **MockGoogleFactCheckService**: Simulates Google Fact Check API with configurable responses
- **MockLocalFactCheckService**: Simulates local database with text similarity matching
- **MockFailingService**: Tests error handling scenarios
- **MockSlowService**: Tests timeout handling
- **TestDataGenerator**: Provides comprehensive test datasets
- **TestEnvironmentManager**: Manages different testing scenarios

### 4. Debug Test Script (`test_fact_checking_debug.py`)

**Simple debugging script for quick validation:**
```bash
python test_fact_checking_debug.py
```

**Tests include:**
- ✅ Basic model creation and serialization
- ✅ Local service functionality
- ✅ Pipeline behavior with no services
- ✅ Metrics collection and reporting

## Debugging Framework

### 1. Enhanced Logging (`debug_utils.py`)

**FactCheckLogger** provides detailed logging with:
- Claim verification start/end tracking
- Service call results and timing
- Aggregation details and confidence scoring
- Error and timeout logging
- Configurable log levels

**Usage:**
```python
from debate_claim_extractor.fact_checking.debug_utils import FactCheckLogger

logger = FactCheckLogger("fact_checking", level=logging.DEBUG)
logger.log_claim_verification_start(claim, ["google", "local"])
```

### 2. Debug Session Recording (`FactCheckDebugger`)

**Comprehensive debugging with session recording:**
- Records all claim processing with unique IDs
- Tracks service calls, results, and timing
- Captures errors with full context
- Generates session summaries and reports
- Saves debug sessions to JSON files

**Usage:**
```python
from debate_claim_extractor.fact_checking.debug_utils import FactCheckDebugger

debugger = FactCheckDebugger(output_dir="debug_sessions")
claim_id = debugger.record_claim_start(claim)
# ... process claim ...
debugger.record_final_result(claim_id, result)
debugger.save_debug_session()
debugger.print_summary()
```

### 3. Result Analysis (`FactCheckInspector`)

**Advanced analysis utilities:**
- `analyze_confidence_distribution()`: Analyzes confidence score patterns
- `analyze_source_quality()`: Evaluates source credibility metrics
- `compare_service_agreement()`: Compares results across services

## Performance Monitoring

### 1. Metrics Collection (`metrics.py`)

**FactCheckMetricsCollector** tracks:
- Service call timing and success rates
- Error counts and types by service
- Verification result distribution
- Source usage patterns
- Session-level performance stats

### 2. Performance Monitoring (`PerformanceMonitor`)

**Real-time health monitoring:**
- Service health checks with configurable thresholds
- Alert generation for performance degradation
- Performance improvement recommendations

**Thresholds:**
- Max response time: 10 seconds
- Min success rate: 80%
- Max error rate: 20%

### 3. Metrics Reporting (`MetricsReporter`)

**Human-readable reports:**
- Comprehensive system metrics reports
- Brief performance summaries
- Service performance comparisons

**Example:**
```python
from debate_claim_extractor.fact_checking.metrics import get_metrics_collector

collector = get_metrics_collector()
reporter = MetricsReporter(collector)
print(reporter.generate_text_report())
```

## CLI Debugging Tools

### 1. Main Debug CLI (`debug_fact_checking.py`)

**Comprehensive command-line debugging tool:**

```bash
# Test basic pipeline functionality
python debug_fact_checking.py --test-basic --verbose

# Test with mock services  
python debug_fact_checking.py --test-mocks --verbose

# Test error handling
python debug_fact_checking.py --test-errors --verbose

# Run performance benchmark
python debug_fact_checking.py --benchmark 20 --verbose

# Analyze debug session
python debug_fact_checking.py --analyze session_20241201_120000.json

# Check system health
python debug_fact_checking.py --health-check

# Generate metrics report
python debug_fact_checking.py --metrics-report
```

## Usage Examples

### Basic Fact-Checking Test

```python
from debate_claim_extractor.fact_checking import FactVerificationPipeline, FactCheckConfig
from debate_claim_extractor.pipeline.models import Claim, ClaimType

# Configure and create pipeline
config = FactCheckConfig(timeout_seconds=30)
pipeline = FactVerificationPipeline(config=config)

# Create a test claim
claim = Claim(
    type=ClaimType.FACTUAL,
    text="Vaccines are safe and effective",
    speaker="Dr. Smith",
    sentence_id="sent_1",
    turn_id=1,
    char_start=0,
    char_end=32,
    confidence=0.9
)

# Verify the claim
result = await pipeline.verify_claim(claim)
print(f"Status: {result.overall_status}")
print(f"Confidence: {result.confidence}")
print(f"Sources: {len(result.primary_sources)}")
```

### Performance Monitoring Example

```python
from debate_claim_extractor.fact_checking.metrics import (
    get_metrics_collector, PerformanceMonitor, ServiceCallTimer
)

collector = get_metrics_collector()
monitor = PerformanceMonitor(collector)

# Monitor service call
with ServiceCallTimer(collector, "local_database"):
    result = await service.verify_claim("Test claim")

# Check system health
health = monitor.check_overall_health()
print(f"System status: {health['status']}")

# Get recommendations
recommendations = monitor.get_performance_recommendations()
for rec in recommendations:
    print(f"💡 {rec}")
```

### Debug Session Example

```python
from debate_claim_extractor.fact_checking.debug_utils import FactCheckDebugger

debugger = FactCheckDebugger(output_dir="./debug_output")

# Record claim processing
claim_id = debugger.record_claim_start(claim)

# Record service calls
debugger.record_service_call(claim_id, "google", results, 1.2)
debugger.record_service_call(claim_id, "local", results, 0.5)

# Record final result
debugger.record_final_result(claim_id, aggregated_result)

# Generate summary and save session
debugger.print_summary()
session_file = debugger.save_debug_session()
print(f"Debug session saved to: {session_file}")
```

## Troubleshooting Common Issues

### 1. Service Not Available

**Problem**: `Google Fact Check service not available (missing API key)`
**Solution**: 
- Set `GOOGLE_FACT_CHECK_API_KEY` environment variable
- Or provide API key in configuration
- Or disable Google service for testing

### 2. Database Connection Issues

**Problem**: Local database service fails to initialize
**Solution**:
- Check database path permissions
- Ensure parent directory exists
- Verify SQLite is available

### 3. Timeout Issues

**Problem**: Services timing out frequently
**Solution**:
- Increase timeout in `FactCheckConfig`
- Check network connectivity for API services
- Monitor service health with `PerformanceMonitor`

### 4. JSON Serialization Errors

**Problem**: `datetime is not JSON serializable`
**Solution**:
- Use custom serializers in models
- The system handles datetime serialization automatically
- Check model `model_dump()` methods

## Best Practices

### Testing
1. **Use Mock Services** for unit tests to avoid external dependencies
2. **Test Error Scenarios** with `MockFailingService` and `MockSlowService`
3. **Verify Serialization** of all models with datetime fields
4. **Test Pipeline Integration** end-to-end with real services

### Debugging
1. **Enable Debug Logging** during development: `level=logging.DEBUG`
2. **Use Debug Sessions** for complex issue investigation
3. **Monitor Performance Metrics** in production environments
4. **Set up Health Checks** for continuous monitoring

### Performance
1. **Monitor Service Response Times** and set appropriate timeouts
2. **Track Success Rates** and investigate failures quickly  
3. **Use Batch Processing** for multiple claims
4. **Cache Results** when appropriate to reduce API calls

## Future Enhancements

### Planned Features
- **Real-time Dashboard** for system monitoring
- **Automated Alerting** for service degradation
- **A/B Testing Framework** for comparing service configurations
- **Enhanced Analytics** with trend analysis and predictions
- **Integration Testing** with CI/CD pipelines

### Extension Points
- **Custom Fact-Check Services** using `FactCheckService` base class
- **Custom Metrics** using `FactCheckMetricsCollector`
- **Custom Debug Utilities** extending `FactCheckDebugger`
- **Custom Analysis Tools** using `FactCheckInspector`

## Resources

- **Test Files**: `tests/test_fact_checking*.py`
- **Debug Tools**: `debug_fact_checking.py`, `test_fact_checking_debug.py`
- **Documentation**: `docs/fact_checking_design.md`
- **Examples**: `tests/mock_services.py` for usage patterns

---

*This testing and debugging framework ensures robust, reliable, and maintainable fact-checking capabilities in your debate analysis system.*
