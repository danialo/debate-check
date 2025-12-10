"""Base artifact class."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Artifact(ABC):
    """
    Base class for all emitted artifacts.

    artifact_type is auto-set from class name.
    """

    artifact_id: str
    artifact_type: str = field(init=False)
    created_by_task: Optional[str] = None
    created_by_method: Optional[str] = None
    span: tuple[int, int] = (0, 0)
    parent_artifact_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.artifact_type = self.__class__.__name__
