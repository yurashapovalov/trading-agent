"""
Domain knowledge for trading data assistant.

Contains:
- defaults.py: Default values and assumption tracking
"""

from .defaults import (
    DEFAULT_MARKER,
    Assumption,
    apply_defaults,
    get_session_default,
    create_assumption,
)

__all__ = [
    "DEFAULT_MARKER",
    "Assumption",
    "apply_defaults",
    "get_session_default",
    "create_assumption",
]
