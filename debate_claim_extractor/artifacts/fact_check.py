"""Fact-check result artifact."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .base import Artifact


class VerificationStatus(Enum):
    """Status of fact verification."""

    VERIFIED = "verified"  # Claim is supported by evidence
    UNVERIFIED = "unverified"  # Claim could not be verified
    DISPUTED = "disputed"  # Mixed evidence or conflicting sources
    FALSE = "false"  # Claim contradicted by evidence
    NO_DATA = "no_data"  # No fact-check data available


@dataclass
class FactCheckResult(Artifact):
    """
    Result of fact-checking an empirical claim.

    Links to the claim it verified and stores evidence/sources.
    """

    claim_id: str = ""  # ID of the claim that was checked
    claim_text: str = ""  # Text of the claim for reference
    status: VerificationStatus = VerificationStatus.NO_DATA
    confidence: float = 0.0  # 0.0-1.0 confidence in the verdict
    summary: str = ""  # Human-readable summary of findings
    sources: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    raw_response: Optional[dict] = None  # Original API response
    method_path: list[str] = field(default_factory=list)
    created_by_task: Optional[str] = None
    created_by_method: Optional[str] = None
