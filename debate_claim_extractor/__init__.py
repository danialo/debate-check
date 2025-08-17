"""
Debate Claim Extractor

A pipeline for extracting factual claims from debate transcripts.
"""

__version__ = "0.1.0"
__author__ = "debate-check"

from .pipeline import ClaimExtractionPipeline

__all__ = ["ClaimExtractionPipeline"]
