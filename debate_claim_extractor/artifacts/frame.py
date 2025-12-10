"""Argument frame artifact."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .base import Artifact


@dataclass
class ArgumentFrame(Artifact):
    """
    A structured argument containing claims and sub-frames.

    Represents the hierarchical structure:
    - Frame can contain child claims (supports, rebuttals)
    - Frame can contain nested frames (sub-arguments)
    """

    summary: str = ""
    frame_type: str = "CLAIM"  # CLAIM, SUPPORT, REBUTTAL
    speaker: Optional[str] = None
    child_claim_ids: list[str] = field(default_factory=list)
    child_frame_ids: list[str] = field(default_factory=list)
    coref_resolutions: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.7
    method_path: list[str] = field(default_factory=list)
