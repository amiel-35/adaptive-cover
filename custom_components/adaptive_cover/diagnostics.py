"""Diagnostics for Adaptive Cover."""

from homeassistant import __version__ as ha_version
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import _cover_diagnostics, _entity_snapshot, _json_safe, _normalize_options
from .const import CONF_ENTITIES, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict:
    """Return configuration, current decisions and related cover states."""
    coordinator = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    options = _normalize_options(config_entry.options)
    covers = options.get(CONF_ENTITIES) or []
    attributes = getattr(getattr(coordinator, "data", None), "attributes", {})
    target = attributes.get("target_position")
    manager = getattr(coordinator, "manager", None)

    return _json_safe(
        {
            "home_assistant_version": ha_version,
            "timezone": hass.config.time_zone,
            "entry": {
                "title": config_entry.title,
                "data": dict(config_entry.data),
                "options": options,
            },
            "decision": {
                "states": getattr(getattr(coordinator, "data", None), "states", {}),
                "attributes": attributes,
            },
            "covers": {
                entity_id: _cover_diagnostics(
                    hass,
                    coordinator,
                    entity_id,
                    target,
                    options,
                )
                for entity_id in covers
            },
            "cover_states": {
                entity_id: _entity_snapshot(hass, entity_id)
                for entity_id in covers
            },
            "manager": {
                "cover_status": getattr(manager, "cover_status", {}),
                "status_reason": getattr(manager, "status_reason", {}),
                "last_skip_reason": getattr(manager, "last_skip_reason", {}),
                "last_service_error": getattr(manager, "last_service_error", {}),
            },
            "behavioral_learning": (
                coordinator.learner.diagnostics() if coordinator else {}
            ),
        }
    )
