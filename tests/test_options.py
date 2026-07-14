"""Tests for Adaptive Cover option normalization and validation."""

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "adaptive_cover"
    / "const.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_cover_const", MODULE_PATH)
const = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(const)


class OptionValidationTests(unittest.TestCase):
    """Verify persisted settings before they reach runtime calculations."""

    def test_normalization_does_not_mutate_defaults(self) -> None:
        """Return independent mutable defaults for every config entry."""
        first = const.normalize_options({const.CONF_ENTITIES: ["cover.test"]})
        first[const.CONF_ENTITIES].append("cover.second")
        second = const.normalize_options(None)
        self.assertEqual([], second[const.CONF_ENTITIES])

    def test_temperature_order_is_validated(self) -> None:
        """Reject an inverted comfort-temperature range."""
        errors = const.validate_options(
            {const.CONF_TEMP_LOW: 24, const.CONF_TEMP_HIGH: 22}
        )
        self.assertIn("temp_low_must_be_lower_than_temp_high", errors)

    def test_hysteresis_order_is_validated(self) -> None:
        """Reject an inverted irradiance hysteresis range."""
        errors = const.validate_options(
            {
                const.CONF_IRRADIANCE_THRESHOLD_OFF: 400,
                const.CONF_IRRADIANCE_THRESHOLD_ON: 300,
            }
        )
        self.assertIn("irradiance_off_must_not_exceed_on", errors)

    def test_valid_defaults_have_no_errors(self) -> None:
        """Keep the built-in defaults internally consistent."""
        self.assertEqual([], const.validate_options(None))

    def test_non_climate_legacy_entry_accepts_empty_temperatures(self) -> None:
        """Allow legacy basic entries without configured climate thresholds."""
        self.assertEqual(
            [],
            const.validate_options(
                {const.CONF_TEMP_LOW: None, const.CONF_TEMP_HIGH: None}
            ),
        )

    def test_invalid_night_purge_time_is_rejected(self) -> None:
        """Reject malformed deadlines before runtime scheduling."""
        errors = const.validate_options(
            {const.CONF_NIGHT_PURGE_END_TIME: "25:61"}
        )
        self.assertIn("night_purge_end_time_must_be_valid", errors)

    def test_interpolation_source_must_be_strictly_increasing(self) -> None:
        """Reject duplicate source points unsupported by interpolation."""
        errors = const.validate_options(
            {
                const.CONF_INTERP: True,
                const.CONF_INTERP_LIST: [0, 50, 50, 100],
                const.CONF_INTERP_LIST_NEW: [0, 25, 75, 100],
            }
        )
        self.assertIn(
            "interpolation_source_must_be_strictly_increasing", errors
        )

    def test_interpolation_values_must_stay_in_cover_range(self) -> None:
        """Reject target positions outside the cover service range."""
        errors = const.validate_options(
            {
                const.CONF_INTERP: True,
                const.CONF_INTERP_LIST: [0, 100],
                const.CONF_INTERP_LIST_NEW: [-1, 101],
            }
        )
        self.assertIn("interpolation_values_must_be_between_0_and_100", errors)


if __name__ == "__main__":
    unittest.main()
