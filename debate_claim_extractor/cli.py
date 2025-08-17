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
from .utils.logging import setup_logging


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
        
        # Initialize pipeline
        config_path = Path(config) if config else None
        pipeline = ClaimExtractionPipeline(config_path=config_path)
        
        # Extract claims
        result = pipeline.extract(text, source=getattr(input, 'name', 'stdin'))
        
        # Output results
        if format == 'json':
            json.dump(
                result.model_dump(),
                output,
                indent=2,
                ensure_ascii=False
            )
            output.write('\n')  # Add final newline for better terminal output
        
        logger.info(f"Extracted {len(result.claims)} claims")
        for claim_type, count in result.meta.get('claim_types', {}).items():
            if count > 0:
                logger.info(f"  {claim_type}: {count}")
                
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
