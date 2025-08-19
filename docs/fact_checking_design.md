# Fact-Checking Integration Design

## Overview
This document outlines the design for integrating fact-checking capabilities into the debate claim extraction pipeline.

## Architecture

### Core Components

1. **Fact Verification Models** (`fact_models.py`)
   - FactCheckResult: Results from fact-checking APIs
   - VerificationSource: Information about fact-checking sources
   - CredibilityScore: Scoring system for claim verification

2. **Fact-Checking Service Layer** (`fact_services/`)
   - Abstract base service for unified interface
   - Google Fact Check Tools API wrapper
   - ClaimBuster API wrapper (academic)
   - Manual fact-checking database integration
   - Rate limiting and caching

3. **Fact Verification Pipeline** (`fact_pipeline.py`)
   - Orchestrates fact-checking across multiple services
   - Aggregates results and confidence scores
   - Handles API failures and fallbacks

4. **Integration Layer**
   - Extends existing ExtractionResult with fact-check data
   - Adds fact-checking to main pipeline and YouTube pipeline
   - CLI options for enabling/disabling fact-checking

## Available Fact-Checking APIs

### 1. Google Fact Check Tools API
- **URL**: https://developers.google.com/fact-check/tools/api
- **Coverage**: Global fact-checking organizations
- **Features**: 
  - Claims search by text query
  - Publisher verification
  - ClaimReview markup data
- **Rate Limits**: 1,000 requests/day (free tier)
- **Authentication**: API key required

### 2. ClaimBuster API (Academic)
- **URL**: https://idir.uta.edu/claimbuster/
- **Coverage**: Political claims (US-focused)
- **Features**:
  - Check-worthiness scoring (0-1)
  - Similar claims detection
  - Real-time fact-checking
- **Rate Limits**: Academic usage
- **Authentication**: API key required

### 3. Manual Fact-Check Database
- **Source**: Curated database of verified claims
- **Coverage**: High-profile political statements
- **Features**:
  - Exact text matching
  - Semantic similarity matching
  - Source attribution
- **Benefits**: No API limits, offline capability

## Data Flow

```
Extracted Claim
     ↓
Query Preprocessing (normalize text, extract key facts)
     ↓
Parallel API Calls
     ├── Google Fact Check Tools
     ├── ClaimBuster
     └── Local Database
     ↓
Result Aggregation & Scoring
     ↓
Enhanced Claim with Verification Data
```

## Verification Scoring System

### Overall Verification Score (0.0 - 1.0)
- **0.9-1.0**: Strongly verified as true
- **0.7-0.9**: Likely true with credible sources
- **0.4-0.7**: Mixed evidence / uncertain
- **0.2-0.4**: Likely false with credible sources
- **0.0-0.2**: Strongly verified as false

### Factors in Scoring
1. **Source Credibility** (40%)
   - Publisher reputation
   - Fact-checker track record
   - Academic vs. commercial sources
   
2. **Evidence Quality** (30%)
   - Primary vs. secondary sources
   - Data quality and methodology
   - Peer review status
   
3. **Consensus** (20%)
   - Agreement across multiple fact-checkers
   - Consistency of findings
   
4. **Recency** (10%)
   - How recent the fact-check is
   - Whether claim context has changed

## Configuration Options

```yaml
fact_checking:
  enabled: true
  timeout_seconds: 10
  services:
    google_fact_check:
      enabled: true
      api_key: "${GOOGLE_FACT_CHECK_API_KEY}"
    claimbuster:
      enabled: false  # Requires academic access
      api_key: "${CLAIMBUSTER_API_KEY}"
    local_database:
      enabled: true
      database_path: "data/fact_checks.db"
  caching:
    enabled: true
    ttl_hours: 24
    max_entries: 1000
```

## Implementation Plan

1. **Phase 1**: Core models and Google Fact Check Tools integration
2. **Phase 2**: Local database and caching system
3. **Phase 3**: Multiple service aggregation and scoring
4. **Phase 4**: CLI integration and testing

## Error Handling Strategy

- **API Unavailable**: Fall back to other services or local database
- **Rate Limiting**: Implement exponential backoff and caching
- **Invalid Responses**: Log errors and return partial results
- **Network Issues**: Timeout handling with graceful degradation

## Privacy and Ethics Considerations

- **No Personal Data**: Only fact-check public claims and statements
- **Source Attribution**: Always cite fact-checking sources
- **Bias Awareness**: Acknowledge limitations of fact-checking services
- **Transparency**: Make verification process and sources visible to users
