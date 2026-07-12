"""Tests for pure diagnostics and export helpers."""

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "adaptive_cover"
    / "diagnostic_helpers.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adaptive_cover_diagnostic_helpers",
    MODULE_PATH,
)
helpers = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helpers
SPEC.loader.exec_module(helpers)


class FilenameTests(unittest.TestCase):
    """Verify local-date export filenames."""

    def test_current_date_is_prefixed(self) -> None:
        """Add the Home Assistant local date to the default base filename."""
        now = datetime(2026, 7, 12, 21, 0, tzinfo=UTC)
        self.assertEqual(
            "12.07.2026_adaptive_cover_diagnostics.json",
            helpers.dated_filename(
                "adaptive_cover_diagnostics.json",
                now,
            ),
        )

    def test_existing_date_is_replaced(self) -> None:
        """Avoid accumulating date prefixes when a name is reused."""
        now = datetime(2026, 7, 12, 21, 0, tzinfo=UTC)
        self.assertEqual(
            "12.07.2026_adaptive_cover_settings.json",
            helpers.dated_filename(
                "11.07.2026_adaptive_cover_settings.json",
                now,
            ),
        )

    def test_date_prefix_can_be_disabled(self) -> None:
        """Preserve an explicit filename when date prefixing is disabled."""
        now = datetime(2026, 7, 12, 21, 0, tzinfo=UTC)
        self.assertEqual(
            "custom.json",
            helpers.dated_filename("custom.json", now, include_date=False),
        )


class PositionDiagnosticsTests(unittest.TestCase):
    """Verify readable target-tolerance diagnostics."""

    def test_position_inside_tolerance_is_satisfied(self) -> None:
        """Treat 97 percent as satisfying a 100 percent target at tolerance 10."""
        result = helpers.position_diagnostics(97, 100, 10)
        self.assertEqual(3.0, result["position_error"])
        self.assertTrue(result["target_satisfied"])

    def test_missing_position_remains_unknown(self) -> None:
        """Do not claim success when the physical position is unavailable."""
        result = helpers.position_diagnostics(None, 100, 10)
        self.assertIsNone(result["target_satisfied"])


if __name__ == "__main__":
    unittest.main()
