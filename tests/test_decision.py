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

    def test_daytime_deadline_before_sunset_does_not_activate_all_day(self) -> None:
        """Treat a deadline such as 18:00 as inactive before a later sunset."""
        now = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
        sunset = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)
        self.assertFalse(
            decision.is_night_purge_window_active(now, sunset, time(18, 0))
        )

    def test_same_evening_deadline_after_sunset_is_supported(self) -> None:
        """Allow a valid same-evening deadline later than sunset."""
        now = datetime(2026, 12, 1, 21, 0, tzinfo=UTC)
        sunset = datetime(2026, 12, 1, 16, 0, tzinfo=UTC)
        self.assertTrue(
            decision.is_night_purge_window_active(now, sunset, time(22, 0))
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


class PositionToleranceTests(unittest.TestCase):
    """Verify movement suppression for devices with imprecise end positions."""

    def test_reported_97_percent_satisfies_100_percent_target(self) -> None:
        """Do not retry a 100% target below the configured 10% movement delta."""
        self.assertFalse(decision.position_requires_move(97, 100, 10))

    def test_difference_equal_to_threshold_requires_movement(self) -> None:
        """Preserve movement when the position difference reaches the threshold."""
        self.assertTrue(decision.position_requires_move(90, 100, 10))

    def test_exact_position_never_requires_movement(self) -> None:
        """Avoid redundant calls even when the configured threshold is zero."""
        self.assertFalse(decision.position_requires_move(100, 100, 0))


class NumericSignalTests(unittest.TestCase):
    """Verify that missing sensor data never becomes a strong-sun signal."""

    def test_missing_irradiance_is_not_strong_sun(self) -> None:
        """Treat startup null values as unavailable, not above threshold."""
        self.assertFalse(decision.numeric_value_above_threshold(None, 300))
        self.assertFalse(
            decision.numeric_value_above_threshold("unavailable", 300)
        )

    def test_irradiance_must_exceed_threshold(self) -> None:
        """Use the actual numeric reading for Strict Sun Block."""
        self.assertFalse(decision.numeric_value_above_threshold(145.78, 300))
        self.assertTrue(decision.numeric_value_above_threshold(413, 300))


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

    def test_only_comfort_decisions_are_learnable(self) -> None:
        """Do not learn user preferences from rain or wind safety targets."""
        self.assertIn("thermal_hold", decision.LEARNABLE_DECISION_CODES)
        self.assertNotIn("rain_detected", decision.LEARNABLE_DECISION_CODES)
        self.assertIn("rain_detected", decision.EMERGENCY_DECISION_CODES)


if __name__ == "__main__":
    unittest.main()
