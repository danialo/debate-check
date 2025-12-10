"""Task definition for HTN planner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4


@dataclass
class Task:
    """
    A task in the HTN task network.

    Tasks are either:
    - Compound: decomposed into subtasks by methods
    - Primitive: executed directly by operators
    """

    task_id: str
    task_type: str
    params: dict[str, Any]
    span: tuple[int, int]
    parent_task_id: Optional[str] = None
    parent_artifact_id: Optional[str] = None
    depth: int = 0
    budget_ms: int = 1000
    dedup_key: Optional[str] = None

    def compute_dedup_key(self) -> str:
        """
        Compute stable hash for deduplication within batch.

        INCLUDES: task_type, span, params_hash
        EXCLUDES: mutable state (defeats dedup purpose)
        """
        if self.dedup_key:
            return self.dedup_key

        key_data = {
            "type": self.task_type,
            "span": list(self.span),
            "params_hash": hashlib.sha256(
                json.dumps(self.params, sort_keys=True, default=str).encode()
            ).hexdigest()[:16],
        }
        return hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()[:24]

    @classmethod
    def create(
        cls,
        task_type: str,
        params: dict[str, Any],
        span: tuple[int, int],
        parent: Optional[Task] = None,
        **kwargs: Any,
    ) -> Task:
        """Factory with auto-generated ID and inherited context."""
        task_id = f"{task_type}_{uuid4().hex[:8]}"
        return cls(
            task_id=task_id,
            task_type=task_type,
            params=params,
            span=span,
            parent_task_id=parent.task_id if parent else None,
            parent_artifact_id=kwargs.get("parent_artifact_id"),
            depth=(parent.depth + 1) if parent else 0,
            budget_ms=kwargs.get("budget_ms", 1000),
            dedup_key=kwargs.get("dedup_key"),
        )

    def __repr__(self) -> str:
        return f"Task({self.task_type}, depth={self.depth}, span={self.span})"
