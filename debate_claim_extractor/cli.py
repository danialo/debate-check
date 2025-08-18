"""
Command line interface for debate claim extraction
"""

import sys
import json
import logging
from pathlib import Path
from typing import TextIO

import click

from .pipeline import ClaimExtractionPipeline
from .pipeline.youtube_pipeline import YouTubePipeline
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
def main(input: TextIO, output: TextIO, format: str, verbose: bool, config: str):
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
        
        # Choose pipeline based on text length and characteristics
        config_path = Path(config) if config else None
        
        # Use YouTube pipeline for long transcripts or continuous text without clear speakers
        if len(text) > 2000 or _should_use_youtube_pipeline(text):
            logger.info(f"Using YouTube-enhanced pipeline for {len(text)} character input")
            pipeline = YouTubePipeline(config_path=config_path)
            result_data = pipeline.extract(text, source=getattr(input, 'name', 'stdin'))
            
            # Convert to standard format for output
            if "error" in result_data:
                logger.error(f"YouTube pipeline failed: {result_data['error']}")
                sys.exit(1)
            
            # Convert enhanced result to standard result format for JSON output
            result = result_data
        else:
            logger.info("Using standard pipeline for short transcript")
            pipeline = ClaimExtractionPipeline(config_path=config_path)
            result = pipeline.extract(text, source=getattr(input, 'name', 'stdin'))
            result = result.model_dump()
        
        # Output results
        if format == 'json':
            json.dump(
                result,
                output,
                indent=2,
                ensure_ascii=False
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
