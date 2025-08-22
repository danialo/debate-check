"""
Command line interface for debate claim extraction
"""

import sys
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TextIO

import click

from .pipeline import ClaimExtractionPipeline
from .pipeline.youtube_pipeline import YouTubePipeline
from .fact_checking import FactCheckConfig
from .utils.logging import setup_logging


def _should_use_youtube_pipeline(text: str) -> bool:
    """
    Determine if text should use the YouTube pipeline based on format characteristics.
    
    Args:
        text: Input text to analyze
        
    Returns:
        True if YouTube pipeline should be used
    """
    # Check for lack of clear speaker patterns (YouTube-style continuous text)
    lines = text.strip().split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    
    if len(non_empty_lines) <= 2:
        # Very few lines suggests continuous transcript
        return True
    
    # Count lines that look like speaker labels ("SPEAKER:", "[Name]:", etc.)
    speaker_pattern_lines = 0
    for line in non_empty_lines[:10]:  # Check first 10 lines
        line = line.strip()
        if (':' in line and 
            (line.split(':', 1)[0].isupper() or 
             line.startswith('[') or 
             line.startswith('('))):
            speaker_pattern_lines += 1
    
    # If less than 30% of lines have speaker patterns, likely continuous transcript
    speaker_ratio = speaker_pattern_lines / len(non_empty_lines[:10])
    return speaker_ratio < 0.3


@click.command()
@click.option(
    "--input", "-i",
    type=click.File('r'),
    default=sys.stdin,
    help="Input file (defaults to stdin)"
)
@click.option(
    "--output", "-o", 
    type=click.File('w'),
    default=sys.stdout,
    help="Output file (defaults to stdout)"
)
@click.option(
    "--format", "-f",
    type=click.Choice(['json']),
    default='json',
    help="Output format"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose logging"
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True),
    help="Configuration file path"
)
@click.option(
    "--fact-check", "-fc",
    is_flag=True,
    help="Enable fact-checking of extracted claims"
)
@click.option(
    "--google-api-key",
    envvar="GOOGLE_FACT_CHECK_API_KEY",
    help="Google Fact Check Tools API key (can also use GOOGLE_FACT_CHECK_API_KEY env var)"
)
@click.option(
    "--fact-db-path",
    type=click.Path(),
    help="Path to local fact-checking database"
)
@click.option(
    "--fact-timeout",
    type=int,
    default=10,
    help="Fact-checking timeout in seconds (default: 10)"
)
@click.option(
    "--fallacy-detection", "-fd",
    is_flag=True,
    help="Enable logical fallacy detection in claims"
)
@click.option(
    "--full-analysis", "-fa",
    is_flag=True,
    help="Enable both fact-checking and fallacy detection (equivalent to --fact-check --fallacy-detection)"
)
@click.option(
    "--scoring", "-s",
    is_flag=True,
    help="Enable multi-dimensional debate scoring (requires claim extraction)"
)
@click.option(
    "--comprehensive-analysis", "-ca",
    is_flag=True,
    help="Enable all analysis features: fact-checking, fallacy detection, and scoring"
)
def main(input: TextIO, output: TextIO, format: str, verbose: bool, config: str, 
         fact_check: bool, google_api_key: str, fact_db_path: str, fact_timeout: int,
         fallacy_detection: bool, full_analysis: bool, scoring: bool, comprehensive_analysis: bool):
    """
    Extract factual claims from debate transcripts.
    
    Example usage:
        python -m debate_claim_extractor --input transcript.txt --output claims.json
        cat debate.txt | python -m debate_claim_extractor > claims.json
    """
    # Set up logging
    setup_logging(verbose=verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Read input text
        text = input.read()
        if not text.strip():
            logger.error("No input text provided")
            sys.exit(1)
            
        logger.info(f"Processing {len(text)} characters of input text")
        
        # Handle comprehensive analysis flag (all features)
        if comprehensive_analysis:
            fact_check = True
            fallacy_detection = True
            scoring = True
            logger.info("Comprehensive analysis enabled: fact-checking + fallacy detection + scoring")
        
        # Handle full analysis flag (fact-checking + fallacy detection)
        if full_analysis:
            fact_check = True
            fallacy_detection = True
            logger.info("Full analysis enabled: fact-checking + fallacy detection")
        
        # Log analysis options
        if fallacy_detection:
            logger.info("Fallacy detection enabled")
        if scoring:
            logger.info("Multi-dimensional scoring enabled")
        
        # Configure fact-checking if enabled
        fact_config = None
        if fact_check:
            logger.info("Fact-checking enabled")
            fact_config = FactCheckConfig(
                enabled=True,
                timeout_seconds=fact_timeout,
                google_fact_check={
                    'enabled': bool(google_api_key),
                    'api_key': google_api_key
                },
                local_database={
                    'enabled': True,
                    'database_path': fact_db_path or 'data/fact_checks.db'
                }
            )
            
            # Log fact-checking configuration
            services = []
            if google_api_key:
                services.append("Google Fact Check Tools")
            services.append("Local Database")
            logger.info(f"Fact-checking services: {', '.join(services)}")
        
        # Choose pipeline based on text length and characteristics
        config_path = Path(config) if config else None
        source_name = getattr(input, 'name', 'stdin')
        
        # Use YouTube pipeline for long transcripts or continuous text without clear speakers
        if len(text) > 2000 or _should_use_youtube_pipeline(text):
            logger.info(f"Using YouTube-enhanced pipeline for {len(text)} character input")
            pipeline = YouTubePipeline(config_path=config_path)
            
            # Choose the right extraction method based on enabled features
            if fact_check and fallacy_detection:
                result_data = pipeline.extract_with_all_analysis(text, source=source_name, fact_config=fact_config)
            elif fact_check:
                result_data = pipeline.extract_with_fact_checking(text, source=source_name, fact_config=fact_config)
            elif fallacy_detection:
                result_data = pipeline.extract_with_fallacy_detection(text, source=source_name)
            else:
                result_data = pipeline.extract(text, source=source_name)
            
            # Convert to standard format for output
            if "error" in result_data:
                logger.error(f"YouTube pipeline failed: {result_data['error']}")
                sys.exit(1)
            
            # Convert enhanced result to standard result format for JSON output
            result = result_data
        else:
            logger.info("Using standard pipeline for short transcript")
            pipeline = ClaimExtractionPipeline(config_path=config_path)
            
            # Choose the right extraction method based on enabled features
            if fact_check and fallacy_detection:
                result_obj = pipeline.extract_with_all_analysis(text, source=source_name, fact_config=fact_config)
            elif fact_check:
                result_obj = pipeline.extract_with_fact_checking(text, source=source_name, fact_config=fact_config)
            elif fallacy_detection:
                result_obj = pipeline.extract_with_fallacy_detection(text, source=source_name)
            else:
                result_obj = pipeline.extract(text, source=source_name)
            
            result = result_obj.model_dump()
        
        # Output results
        if format == 'json':
            def json_serializer(obj):
                """Custom JSON serializer for non-serializable objects"""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
            
            json.dump(
                result,
                output,
                indent=2,
                ensure_ascii=False,
                default=json_serializer
            )
            output.write('\n')  # Add final newline for better terminal output
        
        # Handle both standard and YouTube pipeline result formats
        claims_count = len(result.get('claims', []))
        logger.info(f"Extracted {claims_count} claims")
        
        # Show claim type breakdown if available
        claim_types = result.get('meta', {}).get('claim_types', {})
        if not claim_types and 'claims' in result:
            # Calculate claim types from claims list for YouTube pipeline results
            from collections import Counter
            claim_types = Counter(claim.get('type', 'unknown') for claim in result['claims'])
        
        for claim_type, count in claim_types.items():
            if count > 0:
                logger.info(f"  {claim_type}: {count}")
                
        # Log YouTube pipeline specific info if available
        if result.get('youtube_enhanced'):
            if result.get('chunks_used'):
                chunk_analysis = result.get('chunk_analysis', {})
                logger.info(f"YouTube pipeline: {chunk_analysis.get('total_chunks', 0)} chunks processed")
                speaker_inference = chunk_analysis.get('speaker_inference', {})
                if speaker_inference:
                    logger.info(f"Speakers identified: {', '.join(speaker_inference.keys())}")
            
            clusters_count = result.get('cluster_analysis', {}).get('total_clusters', 0)
            if clusters_count > 0:
                logger.info(f"Claim clusters created: {clusters_count}")
        
        # Log fact-checking info if available
        if result.get('fact_checking_enabled'):
            fact_meta = result.get('meta', {})
            if fact_meta.get('fact_checking_performed'):
                fact_checked_count = fact_meta.get('fact_checked_claims', 0)
                services_used = fact_meta.get('fact_checking_services', [])
                logger.info(f"Fact-checking: {fact_checked_count} claims verified using {', '.join(services_used)}")
                
                # Show verification summary
                verification_summary = fact_meta.get('verification_summary', {})
                for status, count in verification_summary.items():
                    if count > 0:
                        logger.info(f"  {status.replace('_', ' ').title()}: {count}")
            elif fact_meta.get('fact_checking_attempted'):
                error_msg = fact_meta.get('fact_checking_error', 'Unknown error')
                logger.warning(f"Fact-checking failed: {error_msg}")
        
        # Log fallacy detection info if available
        if result.get('fallacy_detection_enabled'):
            fallacy_meta = result.get('meta', {})
            fallacy_summary = result.get('fallacy_summary', {})
            
            if fallacy_meta.get('fallacy_detection_performed'):
                fallacies_detected = fallacy_meta.get('fallacies_detected', 0)
                logger.info(f"Fallacy detection: {fallacies_detected} logical fallacies detected")
                
                # Show fallacy type breakdown
                fallacy_types = fallacy_summary.get('by_type', {})
                for fallacy_type, count in fallacy_types.items():
                    if count > 0:
                        logger.info(f"  {fallacy_type.replace('_', ' ').title()}: {count}")
                
                # Show fallacy severity distribution
                severity_dist = fallacy_summary.get('by_severity', {})
                if severity_dist:
                    logger.info(f"Fallacy severity distribution:")
                    for severity, count in severity_dist.items():
                        if count > 0:
                            logger.info(f"  {severity.title()}: {count}")
                
                # Show confidence distribution
                confidence_dist = fallacy_summary.get('confidence_distribution', {})
                if confidence_dist:
                    total_high = confidence_dist.get('high', 0)
                    total_medium = confidence_dist.get('medium', 0)
                    total_low = confidence_dist.get('low', 0)
                    logger.info(f"Fallacy confidence: {total_high} high, {total_medium} medium, {total_low} low")
                
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        if verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
