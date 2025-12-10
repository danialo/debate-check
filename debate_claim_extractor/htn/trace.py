"""Trace events for debugging and replay."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TraceEvent:
    """Single trace event capturing planner activity."""

    event_type: str
    timestamp_ms: int
    data: dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None
    method_name: Optional[str] = None
    depth: int = 0


class TraceRecorder:
    """Records trace events during planner execution."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def log(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        task_id: Optional[str] = None,
        method_name: Optional[str] = None,
        depth: int = 0,
    ) -> None:
        """Log a trace event."""
        self.events.append(
            TraceEvent(
                event_type=event_type,
                timestamp_ms=int(time.time() * 1000),
                data=data,
                task_id=task_id,
                method_name=method_name,
                depth=depth,
            )
        )

    def clear(self) -> None:
        """Clear all recorded events."""
        self.events.clear()

    def export_json(self, indent: int = 2) -> str:
        """Export trace as JSON string."""
        return json.dumps(
            [
                {
                    "event_type": e.event_type,
                    "timestamp_ms": e.timestamp_ms,
                    "data": e.data,
                    "task_id": e.task_id,
                    "method_name": e.method_name,
                    "depth": e.depth,
                }
                for e in self.events
            ],
            indent=indent,
        )

    def filter_by_type(self, event_type: str) -> list[TraceEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def filter_by_task(self, task_id: str) -> list[TraceEvent]:
        """Get all events for a specific task."""
        return [e for e in self.events if e.task_id == task_id]
