"""Diagnostics for Adaptive Cover."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import _build_diagnostics_payload


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict:
    """Return configuration, current decisions and related cover states."""
    return _build_diagnostics_payload(hass, [config_entry])
