"""
Logical Fallacy Detection Module

This module provides detection and analysis of logical fallacies in debate transcripts.
It integrates with the existing claim extraction pipeline to identify common reasoning errors.
"""

from .fallacy_models import FallacyType, FallacyResult, FallacyDetectionSummary
from .fallacy_detector import FallacyDetector, DebateFallacyDetector

__all__ = [
    'FallacyType', 
    'FallacyResult', 
    'FallacyDetectionSummary',
    'FallacyDetector', 
    'DebateFallacyDetector'
]
