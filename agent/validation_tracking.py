"""
Validation change tracking for Pydantic validators.

Tracks what validators change during model validation.
Used to log parser transformations for debugging and analysis.

Usage:
    changes = start_tracking()
    parsed = SomeModel.model_validate(data)
    stop_tracking()
    # changes now contains list of ValidatorChange

Thread-safe via contextvars.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidatorChange:
    """Record of a change made by a Pydantic validator."""
    validator: str      # Validator function name
    field: str          # Field that was changed
    old_value: Any      # Value before change
    new_value: Any      # Value after change
    reason: str         # Why the change was made
    path: str = ""      # Full path (filled by reconstruct_paths)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "validator": self.validator,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "path": self.path,
        }


# Thread-safe storage for current validation context
_changes: ContextVar[list[ValidatorChange] | None] = ContextVar(
    'validator_changes',
    default=None
)


def track_change(
    validator: str,
    field: str,
    old_value: Any,
    new_value: Any,
    reason: str,
) -> None:
    """
    Track a change made by a validator.

    Safe to call even when tracking is not active (does nothing).
    Never raises exceptions - validation must not break.

    Args:
        validator: Name of the validator function
        field: Field being changed
        old_value: Value before change
        new_value: Value after change
        reason: Human-readable explanation
    """
    try:
        changes = _changes.get()
        if changes is not None:
            changes.append(ValidatorChange(
                validator=validator,
                field=field,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
            ))
    except Exception:
        # NEVER break validation
        pass


def start_tracking() -> list[ValidatorChange]:
    """
    Start tracking validator changes.

    Returns:
        List that will be populated with changes during validation.
    """
    changes: list[ValidatorChange] = []
    _changes.set(changes)
    return changes


def stop_tracking() -> None:
    """Stop tracking validator changes."""
    _changes.set(None)


def is_tracking() -> bool:
    """Check if tracking is currently active."""
    return _changes.get() is not None


def reconstruct_paths(
    raw: dict,
    validated: Any,
    changes: list[ValidatorChange],
) -> list[ValidatorChange]:
    """
    Match tracked changes to full paths by comparing raw vs validated.

    Args:
        raw: Original dict before validation
        validated: Validated Pydantic model (with .steps attribute)
        changes: List of changes from tracking

    Returns:
        Same list with path field filled in
    """
    try:
        if not hasattr(validated, 'steps'):
            return changes

        raw_steps = raw.get("steps", [])

        for si, (raw_step, val_step) in enumerate(zip(raw_steps, validated.steps)):
            raw_atoms = raw_step.get("atoms", [])

            for ai, (raw_atom, val_atom) in enumerate(zip(raw_atoms, val_step.atoms)):
                # Check each field that validators might change
                for field_name in ["timeframe", "what", "filter"]:
                    raw_val = raw_atom.get(field_name)
                    val_val = getattr(val_atom, field_name, None)

                    if raw_val != val_val:
                        # Find matching change
                        for c in changes:
                            if (c.field == field_name and
                                c.old_value == raw_val and
                                c.new_value == val_val and
                                not c.path):
                                c.path = f"steps[{si}].atoms[{ai}].{field_name}"
                                break

            # Check step-level fields
            raw_op = raw_step.get("operation")
            val_op = getattr(val_step, "operation", None)
            if raw_op != val_op:
                for c in changes:
                    if (c.field == "operation" and
                        c.old_value == raw_op and
                        c.new_value == val_op and
                        not c.path):
                        c.path = f"steps[{si}].operation"
                        break

    except Exception:
        # Don't break if reconstruction fails
        pass

    return changes
