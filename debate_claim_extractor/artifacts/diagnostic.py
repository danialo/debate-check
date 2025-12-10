"""Diagnostic artifact for debugging and traceability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Artifact


@dataclass
class DiagnosticArtifact(Artifact):
    """
    Diagnostic information emitted during planning.

    Used for:
    - No method found errors
    - Budget exceeded warnings
    - Operator failures
    - Backtrack events
    """

    diagnostic_type: str = ""
    message: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # info, warning, error
