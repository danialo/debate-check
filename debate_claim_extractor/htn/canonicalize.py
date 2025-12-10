"""Canonical hashing utilities for deduplication and caching."""

from __future__ import annotations

import hashlib
import re


def canonicalize_text(text: str) -> str:
    """
    Normalize text for stable hashing.

    Apply to: entity names, claim text, span content.
    """
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)  # Collapse whitespace
    text = re.sub(r"[^\w\s]", "", text)  # Remove punctuation
    return text


def canonical_hash(text: str) -> str:
    """SHA256 of canonicalized text. Full hash."""
    canonical = canonicalize_text(text)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_hash_short(text: str, length: int = 24) -> str:
    """Truncated hash for IDs and dedup keys."""
    return canonical_hash(text)[:length]


def entity_dedup_key(canonical_name: str) -> str:
    """Dedup key for entity registration."""
    return canonical_hash_short(canonical_name)


def claim_dedup_key(text: str, span: tuple[int, int]) -> str:
    """
    Dedup key for claim emission.

    Includes span for position-sensitivity.
    """
    combined = f"{canonical_hash(text)}:{span[0]}:{span[1]}"
    return hashlib.sha256(combined.encode()).hexdigest()[:24]


def llm_cache_key(prompt: str, schema_version: str, model: str) -> str:
    """
    Cache key for LLM calls.

    IMPORTANT: Include schema_version to invalidate on prompt changes.
    """
    normalized = canonicalize_text(prompt)
    combined = f"v{schema_version}:{model}:{normalized}"
    return hashlib.sha256(combined.encode()).hexdigest()
