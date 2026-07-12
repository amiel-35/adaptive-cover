"""Pure helpers for Adaptive Cover exports and diagnostics."""

from __future__ import annotations

from datetime import datetime
import re

DATE_PREFIX_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}_")


def dated_filename(filename: str, now_local: datetime, include_date: bool = True) -> str:
    """Return an export filename with one current local-date prefix."""
    if not include_date:
        return filename
    base_name = DATE_PREFIX_PATTERN.sub("", filename)
    return f"{now_local:%d.%m.%Y}_{base_name}"


def position_diagnostics(
    current_position: int | float | None,
    target_position: int | float | None,
    tolerance: int | float,
) -> dict[str, float | bool | None]:
    """Describe whether a physical cover position satisfies its target."""
    if current_position is None or target_position is None:
        return {
            "position_error": None,
            "effective_tolerance": float(tolerance),
            "target_satisfied": None,
        }
    error = abs(float(current_position) - float(target_position))
    threshold = max(0.0, float(tolerance))
    return {
        "position_error": error,
        "effective_tolerance": threshold,
        "target_satisfied": error == 0 or (threshold > 0 and error < threshold),
    }
