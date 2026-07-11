"""Tests for persistent BehavioralLearner calculations."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock


class FakeStore:
    """Minimal Home Assistant Store replacement used by unit tests."""

    def __init__(self, hass, version, key) -> None:
        """Capture storage metadata without file-system access."""
        self.data = None
        self.delayed_payload = None

    async def async_load(self):
        """Return the configured in-memory payload."""
        return self.data

    def async_delay_save(self, callback, delay) -> None:
        """Capture the payload that would be persisted by Home Assistant."""
        self.delayed_payload = callback()


homeassistant = ModuleType("homeassistant")
homeassistant_core = ModuleType("homeassistant.core")
homeassistant_core.HomeAssistant = object
homeassistant_exceptions = ModuleType("homeassistant.exceptions")
homeassistant_exceptions.HomeAssistantError = type(
    "HomeAssistantError", (Exception,), {}
)
homeassistant_helpers = ModuleType("homeassistant.helpers")
homeassistant_storage = ModuleType("homeassistant.helpers.storage")
homeassistant_storage.Store = FakeStore
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.core", homeassistant_core)
sys.modules.setdefault("homeassistant.exceptions", homeassistant_exceptions)
sys.modules.setdefault("homeassistant.helpers", homeassistant_helpers)
sys.modules.setdefault("homeassistant.helpers.storage", homeassistant_storage)

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "adaptive_cover"
    / "learning.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_cover_learning", MODULE_PATH)
learning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(learning)


class BehavioralLearnerTests(unittest.IsolatedAsyncioTestCase):
    """Verify learning, persistence payloads and reset behavior."""

    async def test_load_restores_persisted_offsets(self) -> None:
        """Restore valid persisted learning values."""
        learner = learning.BehavioralLearner(object(), Mock(), "entry")
        learner._store.data = {
            "position_biases": {"cover.room": 4.5},
            "temperature_offsets": {"cover.room": -0.3},
            "override_counts": {"cover.room": 3},
        }
        await learner.async_load()
        self.assertEqual(34, learner.get_adjusted_position("cover.room", 30))
        self.assertEqual(-0.3, learner.get_temp_offset("cover.room"))

    async def test_override_updates_and_schedules_persistence(self) -> None:
        """Learn bounded position and temperature preferences."""
        learner = learning.BehavioralLearner(object(), Mock(), "entry")
        learner.register_override("cover.room", 23.0, 50, 30, True)
        self.assertEqual(48, learner.get_adjusted_position("cover.room", 50))
        self.assertEqual(-0.1, learner.get_temp_offset("cover.room"))
        self.assertEqual(1, learner._store.delayed_payload["override_counts"]["cover.room"])

    async def test_reset_clears_all_learning(self) -> None:
        """Clear learned offsets and persist the empty state."""
        learner = learning.BehavioralLearner(object(), Mock(), "entry")
        learner.register_override("cover.room", 23.0, 50, 30, True)
        learner.reset()
        self.assertEqual(50, learner.get_adjusted_position("cover.room", 50))
        self.assertEqual({}, learner._store.delayed_payload["position_biases"])


if __name__ == "__main__":
    unittest.main()
