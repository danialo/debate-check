"""
Multi-dimensional debate scoring system.

This module provides comprehensive scoring metrics for debate analysis including:
- Debate Quality Score: Overall debate analysis quality
- Speaker Credibility Score: Individual speaker performance 
- Argument Strength Score: Evidence-based argument quality
- Overall Debate Score: Composite metric combining all dimensions
"""

from .models import (
    ScoreType,
    ScoringConfig,
    SpeakerScore,
    ArgumentScore,
    DebateScore,
    ScoringResult
)

from .scorers import (
    DebateQualityScorer,
    SpeakerCredibilityScorer,
    ArgumentStrengthScorer,
    OverallDebateScorer
)

from .pipeline import ScoringPipeline

__all__ = [
    # Models
    'ScoreType',
    'ScoringConfig', 
    'SpeakerScore',
    'ArgumentScore',
    'DebateScore',
    'ScoringResult',
    
    # Scorers
    'DebateQualityScorer',
    'SpeakerCredibilityScorer', 
    'ArgumentStrengthScorer',
    'OverallDebateScorer',
    
    # Pipeline
    'ScoringPipeline'
]
