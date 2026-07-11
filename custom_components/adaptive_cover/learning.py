"""Persistent behavioral learning for Adaptive Cover."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

STORAGE_VERSION = 1
POSITION_BIAS_LIMIT = 25.0
TEMPERATURE_OFFSET_LIMIT = 3.0


class BehavioralLearner:
    """Learn small user preference offsets from genuine manual overrides."""

    def __init__(self, hass: HomeAssistant, logger, entry_id: str) -> None:
        """Initialize persistent learning for one config entry."""
        self.hass = hass
        self.logger = logger
        self.alpha = 0.1
        self.position_biases: dict[str, float] = {}
        self.temperature_offsets: dict[str, float] = {}
        self.override_counts: dict[str, int] = {}
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"adaptive_cover.learning.{entry_id}",
        )

    async def async_load(self) -> None:
        """Restore learned values from Home Assistant storage."""
        try:
            data: dict[str, Any] = await self._store.async_load() or {}
        except (HomeAssistantError, OSError) as err:
            self.logger.error("Unable to load behavioral learning: %s", err)
            return
        try:
            self.position_biases = {
                str(key): float(value)
                for key, value in data.get("position_biases", {}).items()
            }
            self.temperature_offsets = {
                str(key): float(value)
                for key, value in data.get("temperature_offsets", {}).items()
            }
            self.override_counts = {
                str(key): int(value)
                for key, value in data.get("override_counts", {}).items()
            }
        except (AttributeError, TypeError, ValueError):
            self.logger.error("Invalid behavioral learning storage; using defaults")
            self.position_biases.clear()
            self.temperature_offsets.clear()
            self.override_counts.clear()

    def register_override(
        self,
        entity_id: str,
        current_temp: float | None,
        our_state: int,
        new_position: int,
        is_summer: bool,
    ) -> None:
        """Update learned offsets after a verified manual position change."""
        position_delta = float(new_position) - float(our_state)
        if abs(position_delta) < 2:
            return

        old_bias = self.position_biases.get(entity_id, 0.0)
        learned_bias = (1 - self.alpha) * old_bias + self.alpha * position_delta
        self.position_biases[entity_id] = max(
            -POSITION_BIAS_LIMIT,
            min(POSITION_BIAS_LIMIT, learned_bias),
        )
        self.override_counts[entity_id] = self.override_counts.get(entity_id, 0) + 1

        if current_temp is not None:
            old_offset = self.temperature_offsets.get(entity_id, 0.0)
            direction = -0.1 if new_position < our_state else 0.1
            if not is_summer and new_position > our_state:
                direction = 0.05
            self.temperature_offsets[entity_id] = max(
                -TEMPERATURE_OFFSET_LIMIT,
                min(TEMPERATURE_OFFSET_LIMIT, old_offset + direction),
            )

        self.logger.info(
            "Learned preference for %s: position bias %.1f%%, temperature offset %.1f°C",
            entity_id,
            self.position_biases[entity_id],
            self.temperature_offsets.get(entity_id, 0.0),
        )
        self._schedule_save()

    def get_adjusted_position(self, entity_id: str, target: int) -> int:
        """Apply the learned position bias and clamp the result."""
        bias = self.position_biases.get(entity_id, 0.0)
        return max(0, min(100, round(float(target) + bias)))

    def get_temp_offset(self, entity_id: str) -> float:
        """Return the learned comfort-temperature offset."""
        return self.temperature_offsets.get(entity_id, 0.0)

    def reset(self, entity_id: str | None = None) -> None:
        """Reset learned values for one cover or the whole config entry."""
        if entity_id is None:
            self.position_biases.clear()
            self.temperature_offsets.clear()
            self.override_counts.clear()
        else:
            self.position_biases.pop(entity_id, None)
            self.temperature_offsets.pop(entity_id, None)
            self.override_counts.pop(entity_id, None)
        self._schedule_save()

    def diagnostics(self) -> dict[str, dict]:
        """Return JSON-safe learning diagnostics."""
        return {
            "position_biases": dict(self.position_biases),
            "temperature_offsets": dict(self.temperature_offsets),
            "override_counts": dict(self.override_counts),
        }

    def _schedule_save(self) -> None:
        """Coalesce frequent overrides into one storage write."""
        self._store.async_delay_save(self.diagnostics, 1)
