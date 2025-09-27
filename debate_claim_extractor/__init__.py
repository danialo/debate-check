"""Debate Claim Extractor package."""

__version__ = "0.2.0"
__author__ = "debate-check"

from .core.pipeline import ClaimExtractionPipeline, ExtractionConfig

__all__ = ["ClaimExtractionPipeline", "ExtractionConfig"]

