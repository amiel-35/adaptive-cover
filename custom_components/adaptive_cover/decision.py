"""Pure decision helpers shared by the Adaptive Cover runtime and tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Describe one complete, explainable Adaptive Cover decision."""

    target_position: int
    code: str
    reason: str
    priority: int
    inputs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for diagnostics."""
        return asdict(self)


DECISION_PRIORITIES = {
    "control_disabled": 110,
    "window_open": 105,
    "rain_detected": 100,
    "wind_detected": 100,
    "cold_protection": 95,
    "dawn_protection": 90,
    "strict_sun_block": 85,
    "night_purge": 80,
    "max_limit": 75,
    "min_limit": 75,
    "thermal_hold": 60,
    "night_mode": 50,
    "sun_shadow": 40,
    "auto": 10,
}


def decision_priority(code: str) -> int:
    """Return a stable priority for a decision code."""
    return DECISION_PRIORITIES.get(code, 0)


def position_requires_move(
    current_position: int | float,
    target_position: int | float,
    minimum_change: int | float,
) -> bool:
    """Return whether the configured position difference requires movement."""
    threshold = max(0.0, float(minimum_change))
    difference = abs(float(current_position) - float(target_position))
    if difference == 0:
        return False
    return threshold == 0 or difference >= threshold


def is_night_purge_window_active(
    now_local: datetime,
    sunset_local: datetime,
    purge_end: time,
) -> bool:
    """Return whether now belongs to the sunset-to-deadline purge window."""
    sunset_today = datetime.combine(
        now_local.date(),
        sunset_local.timetz().replace(tzinfo=None),
        tzinfo=now_local.tzinfo,
    )
    end_today = datetime.combine(
        now_local.date(),
        purge_end,
        tzinfo=now_local.tzinfo,
    )
    if now_local >= sunset_today:
        end_date = now_local.date()
        if purge_end <= sunset_today.time():
            end_date += timedelta(days=1)
        return now_local < datetime.combine(
            end_date,
            purge_end,
            tzinfo=now_local.tzinfo,
        )
    return now_local < end_today


def should_hold_thermal_protection(
    *,
    now: datetime,
    last_direct_sun_at: datetime | None,
    duration_minutes: float,
    direct_sun_valid: bool,
    inside_temperature: float | None,
    outside_temperature: float | None,
    release_delta: float,
    thermal_stress: float,
) -> bool:
    """Return whether post-sun thermal shading should remain active."""
    if direct_sun_valid or last_direct_sun_at is None or inside_temperature is None:
        return False
    if now.tzinfo is None or last_direct_sun_at.tzinfo is None:
        raise ValueError("Thermal hold timestamps must be timezone-aware")
    if now - last_direct_sun_at > timedelta(minutes=float(duration_minutes)):
        return False
    if (
        outside_temperature is not None
        and outside_temperature <= inside_temperature - float(release_delta)
    ):
        return False
    return thermal_stress > 0.0


def wind_speed_to_kmh(value: float, unit: str | None) -> float:
    """Normalize common Home Assistant wind-speed units to km/h."""
    normalized_unit = (unit or "km/h").lower().replace(" ", "")
    if normalized_unit in {"m/s", "mps"}:
        return value * 3.6
    if normalized_unit in {"mph", "mi/h"}:
        return value * 1.609344
    if normalized_unit in {"kn", "kt", "knot", "knots"}:
        return value * 1.852
    return value
