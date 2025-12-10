"""Method registration and lookup."""

from __future__ import annotations

from typing import Any

# Global registry: task_type -> list of method classes
_METHOD_REGISTRY: dict[str, list[type]] = {}


def method(
    name: str,
    task: str,
    base_cost: float = 10.0,
    requires_llm: bool = False,
) -> Any:
    """
    Decorator for method registration.

    Usage:
        @method(name="ExtractClaim", task="EXTRACT_CLAIM", base_cost=5.0)
        class ExtractClaim:
            def preconditions(self, state, task): ...
            def cost(self, state, task): ...
            def decompose(self, state, task): ...
            def execute(self, state, task): ...
    """

    def decorator(cls: type) -> type:
        cls._method_name = name
        cls._task_type = task
        cls._base_cost = base_cost
        cls._requires_llm = requires_llm

        if task not in _METHOD_REGISTRY:
            _METHOD_REGISTRY[task] = []
        _METHOD_REGISTRY[task].append(cls)

        return cls

    return decorator


def get_methods_for_task(task_type: str) -> list[type]:
    """Get all registered methods for a task type."""
    return _METHOD_REGISTRY.get(task_type, [])


def clear_registry() -> None:
    """Clear the method registry. Useful for testing."""
    _METHOD_REGISTRY.clear()


def list_registered_tasks() -> list[str]:
    """List all task types with registered methods."""
    return list(_METHOD_REGISTRY.keys())
