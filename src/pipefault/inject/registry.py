"""Registry of available defect injectors."""

from __future__ import annotations

import importlib

from pipefault.inject.base import Injector

_REGISTRY: dict[str, Injector] = {}

# Imported on first use so the registry stays cheap and cycle-free.
_BUILTINS: dict[str, tuple[str, str]] = {
    "D1": ("pipefault.inject.fanout", "JoinFanout"),
    "D3": ("pipefault.inject.late_dimension", "LatestVersionJoin"),
    "D5": ("pipefault.inject.duplicate", "DuplicateIngestion"),
    "D6": ("pipefault.inject.coercion", "SilentCoercion"),
}


def register(injector: Injector) -> Injector:
    """Add an injector. Duplicate names are a programming error."""
    name = injector.name.strip().upper()
    if not name:
        raise ValueError("injector name must be non-empty")
    if name in _REGISTRY:
        raise ValueError(f"injector {name!r} is already registered")
    _REGISTRY[name] = injector
    return injector


def _load_builtin(name: str) -> Injector | None:
    target = _BUILTINS.get(name)
    if target is None:
        return None
    module_name, class_name = target
    module = importlib.import_module(module_name)
    return register(getattr(module, class_name)())


def get(name: str) -> Injector:
    """Look up an injector by name, loading built-ins on first use."""
    key = name.strip().upper()
    if key in _REGISTRY:
        return _REGISTRY[key]
    builtin = _load_builtin(key)
    if builtin is not None:
        return builtin
    known = ", ".join(sorted({*_REGISTRY, *_BUILTINS})) or "none"
    raise ValueError(f"unknown injector {name!r}; registered: {known}")


def available() -> tuple[str, ...]:
    return tuple(sorted({*_REGISTRY, *_BUILTINS}))
