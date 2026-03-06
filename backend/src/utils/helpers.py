"""
Utility helpers for the UE Capability Parser backend.
"""

from __future__ import annotations
from typing import Any, Dict, Iterator, List, Optional, Tuple


def safe_get(d: Dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict with a chain of keys."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d


def flatten(
    d: Dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> Dict[str, Any]:
    """Flatten a nested dict into dot-separated keys."""
    items: List[Tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, elem in enumerate(v):
                list_key = f"{new_key}[{i}]"
                if isinstance(elem, dict):
                    items.extend(flatten(elem, list_key, sep=sep).items())
                else:
                    items.append((list_key, elem))
        else:
            items.append((new_key, v))
    return dict(items)


def to_bool(value: str) -> Optional[bool]:
    """Parse common boolean string representations."""
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    if v in ("true", "yes", "1", "supported", "enabled", "present"):
        return True
    if v in ("false", "no", "0", "not_supported", "disabled", "absent"):
        return False
    return None


def to_int(value: str) -> Optional[int]:
    """Safe int parse; returns None on failure."""
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def format_path(*parts: str) -> str:
    """Build a dotted field path from parts, skipping empty strings."""
    return ".".join(p for p in parts if p)
