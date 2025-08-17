"""
Logging configuration for the claim extraction pipeline
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: Optional[str] = None,
    verbose: bool = False,
    format_string: Optional[str] = None
) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        verbose: If True, enable DEBUG level logging
        format_string: Custom format string for log messages
    """
    if verbose:
        level = "DEBUG"
    elif level is None:
        level = "INFO"
        
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stderr)  # Log to stderr to avoid mixing with output
        ]
    )
    
    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
