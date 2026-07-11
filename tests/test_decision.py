"""Tests for pure Adaptive Cover decisions."""

from datetime import UTC, datetime, time, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "adaptive_cover"
    / "decision.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_cover_decision", MODULE_PATH)
decision = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = decision
SPEC.loader.exec_module(decision)


class NightPurgeTests(unittest.TestCase):
    """Verify the hard night-purge deadline."""

    def test_window_ends_even_when_sunrise_is_later(self) -> None:
        """Stop purge exactly at the configured deadline before sunrise."""
        sunset = datetime(2026, 12, 1, 16, 0, tzinfo=UTC)
        self.assertTrue(
            decision.is_night_purge_window_active(
                datetime(2026, 12, 2, 5, 59, tzinfo=UTC),
                sunset,
                time(6, 0),
            )
        )
        self.assertFalse(
            decision.is_night_purge_window_active(
                datetime(2026, 12, 2, 6, 0, tzinfo=UTC),
                sunset,
                time(6, 0),
            )
        )

    def test_daytime_is_not_part_of_night_purge(self) -> None:
        """Exclude ordinary daytime before the next sunset."""
        now = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
        sunset = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)
        self.assertFalse(
            decision.is_night_purge_window_active(now, sunset, time(6, 0))
        )


class ThermalHoldTests(unittest.TestCase):
    """Verify room-specific post-sun protection."""

    def test_cooler_outside_air_releases_hold(self) -> None:
        """Release shading when outdoor cooling has a clear advantage."""
        now = datetime(2026, 7, 11, 10, 0, tzinfo=UTC)
        self.assertFalse(
            decision.should_hold_thermal_protection(
                now=now,
                last_direct_sun_at=now - timedelta(minutes=15),
                duration_minutes=120,
                direct_sun_valid=False,
                inside_temperature=22.5,
                outside_temperature=19.0,
                release_delta=1.0,
                thermal_stress=1.0,
            )
        )

    def test_hold_requires_previous_direct_sun(self) -> None:
        """Do not call ordinary shade a post-sun thermal hold."""
        self.assertFalse(
            decision.should_hold_thermal_protection(
                now=datetime(2026, 7, 11, 10, 0, tzinfo=UTC),
                last_direct_sun_at=None,
                duration_minutes=120,
                direct_sun_valid=False,
                inside_temperature=23.0,
                outside_temperature=23.0,
                release_delta=1.0,
                thermal_stress=1.0,
            )
        )

    def test_recent_sun_and_no_cooling_keeps_hold(self) -> None:
        """Retain recent protection while the room cannot cool effectively."""
        now = datetime(2026, 7, 11, 10, 0, tzinfo=UTC)
        self.assertTrue(
            decision.should_hold_thermal_protection(
                now=now,
                last_direct_sun_at=now - timedelta(minutes=15),
                duration_minutes=120,
                direct_sun_valid=False,
                inside_temperature=23.0,
                outside_temperature=22.5,
                release_delta=1.0,
                thermal_stress=0.5,
            )
        )


class UnitConversionTests(unittest.TestCase):
    """Verify weather input normalization."""

    def test_wind_speed_is_normalized_to_kmh(self) -> None:
        """Convert meters per second before applying the km/h threshold."""
        self.assertAlmostEqual(36.0, decision.wind_speed_to_kmh(10.0, "m/s"))


class DecisionResultTests(unittest.TestCase):
    """Verify explainable decision metadata."""

    def test_safety_decision_has_higher_priority_than_comfort(self) -> None:
        """Keep safety rules above thermal comfort decisions."""
        self.assertGreater(
            decision.decision_priority("rain_detected"),
            decision.decision_priority("thermal_hold"),
        )

    def test_decision_is_serializable(self) -> None:
        """Expose complete decision data to diagnostics."""
        result = decision.DecisionResult(
            target_position=0,
            code="strict_sun_block",
            reason="sun",
            priority=decision.decision_priority("strict_sun_block"),
            inputs={"irradiance": 413.0},
        )
        self.assertEqual(413.0, result.as_dict()["inputs"]["irradiance"])


if __name__ == "__main__":
    unittest.main()
