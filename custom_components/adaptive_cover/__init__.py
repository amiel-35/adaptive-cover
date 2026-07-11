"""The Adaptive Cover integration."""

from __future__ import annotations

import datetime as dt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.helpers.event import (
    async_track_state_change_event,
)
import homeassistant.helpers.config_validation as cv
import json
import os
from pathlib import Path
import voluptuous as vol

from .const import (
    CONF_END_ENTITY,
    CONF_ENTITIES,
    CONF_PRESENCE_ENTITY,
    CONF_TEMP_ENTITY,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_ENTITY,
    CONF_RAIN_ENTITY,
    CONF_IRRADIANCE_ENTITY,
    CONF_LUX_ENTITY,
    CONF_OUTSIDETEMP_ENTITY,
    CONF_START_ENTITY,
    CONF_WORKDAY_ENTITY,
    CONF_WIND_ENTITY,
    DOMAIN,
    _LOGGER,
    normalize_options,
    validate_options,
)
from .coordinator import AdaptiveDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SELECT, Platform.TIME, Platform.NUMBER]
CONF_SUN = ["sun.sun"]


def _normalize_options(options: dict | None) -> dict:
    """Zwróć opcje ze wszystkimi znanymi kluczami i zachowaj zapisane wartości."""
    return normalize_options(options)


def _config_file_path(hass: HomeAssistant, filename: str) -> str:
    """Resolve a service filename without allowing writes outside /config."""
    if Path(filename).name != filename:
        raise ValueError("Filename must not contain a directory path")
    return hass.config.path(filename)


def _json_safe(value):
    """Zamień obiekty Home Assistant i runtime na wartości bezpieczne dla JSON."""
    if isinstance(value, State):
        return {
            "entity_id": value.entity_id,
            "state": value.state,
            "attributes": _json_safe(dict(value.attributes)),
            "last_changed": value.last_changed.isoformat(),
            "last_updated": value.last_updated.isoformat(),
        }
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    return value


def _entity_snapshot(hass: HomeAssistant, entity_id: str | None) -> dict | None:
    """Zwróć aktualny stan encji Home Assistant."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return {"entity_id": entity_id, "state": None, "available": False}
    snapshot = _json_safe(state)
    snapshot["available"] = True
    return snapshot


def _cover_position_from_snapshot(snapshot: dict | None, cover_type: str | None) -> int | float | None:
    """Zwróć aktualną pozycję rolety ze zrzutu stanu Home Assistant."""
    attributes = (snapshot or {}).get("attributes") or {}
    if cover_type == "cover_tilt":
        return attributes.get("current_tilt_position")
    return attributes.get("current_position", attributes.get("current_tilt_position"))


def _int_position(value: int | float | str | None) -> int | None:
    """Zwróć pozycję jako liczbę całkowitą, jeśli da się ją bezpiecznie odczytać."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _cover_diagnostics(
    hass: HomeAssistant,
    coordinator: AdaptiveDataUpdateCoordinator | None,
    entity_id: str,
    target_position: int | float | None,
    options: dict,
) -> dict:
    """Zwróć krótkie podsumowanie diagnostyczne dla pojedynczej rolety."""
    snapshot = _entity_snapshot(hass, entity_id)
    cover_type = getattr(coordinator, "_cover_type", None)
    manager = getattr(coordinator, "manager", None)
    target_position_int = _int_position(target_position)
    if coordinator is not None and target_position_int is not None:
        target_position_int = coordinator._target_for_entity(
            entity_id, target_position_int
        )
    movement_checks = {}

    if coordinator is not None:
        movement_checks = {
            "adaptive_time_ok": bool(getattr(coordinator, "check_adaptive_time", True)),
            "position_delta_ok": (
                coordinator.check_position_delta(entity_id, target_position_int, options)
                if target_position_int is not None
                else None
            ),
            "time_delta_ok": coordinator.check_time_delta(entity_id),
            "manual_override_active": (
                manager.is_cover_manual(entity_id) if manager is not None else None
            ),
        }

    return {
        "entity_id": entity_id,
        "available": (snapshot or {}).get("available", False),
        "ha_state": (snapshot or {}).get("state"),
        "friendly_name": ((snapshot or {}).get("attributes") or {}).get("friendly_name"),
        "current_position": _cover_position_from_snapshot(snapshot, cover_type),
        "target_position": target_position_int,
        "cover_status": (
            getattr(manager, "cover_status", {}).get(entity_id)
            if manager is not None
            else None
        ),
        "last_skip_reason": (
            getattr(manager, "last_skip_reason", {}).get(entity_id)
            if manager is not None
            else None
        ),
        "status_reason": (
            getattr(manager, "status_reason", {}).get(entity_id)
            if manager is not None
            else None
        ),
        "last_service_call": (
            getattr(manager, "last_service_call", {}).get(entity_id)
            if manager is not None
            else None
        ),
        "last_service_error": (
            getattr(manager, "last_service_error", {}).get(entity_id)
            if manager is not None
            else None
        ),
        "wait_for_target": (
            getattr(coordinator, "wait_for_target", {}).get(entity_id)
            if coordinator is not None
            else None
        ),
        "target_call": (
            getattr(coordinator, "target_call", {}).get(entity_id)
            if coordinator is not None
            else None
        ),
        "movement_checks": movement_checks,
        "state_snapshot": snapshot,
    }


async def async_setup(hass: HomeAssistant, config: dict) -> bool:  # noqa: C901
    """Set up the Adaptive Cover component."""

    async def export_config(call: ServiceCall) -> None:
        """Export all config entries to a JSON file."""
        filename = call.data.get("filename", "adaptive_cover_settings.json")
        filepath = _config_file_path(hass, filename)

        entries = {}
        for entry in hass.config_entries.async_entries(DOMAIN):
            entries[entry.entry_id] = {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "data": dict(entry.data),
                "options": _normalize_options(entry.options),
            }

        export_data = {"schema_version": 3, "entries": entries}

        def write_file():
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4)

        await hass.async_add_executor_job(write_file)
        _LOGGER.info("Exported Adaptive Cover configuration to %s", filepath)

    async def import_config(call: ServiceCall) -> None:
        """Import config entries from a JSON file."""
        filename = call.data.get("filename", "adaptive_cover_settings.json")
        filepath = _config_file_path(hass, filename)

        def read_file():
            if not os.path.exists(filepath):
                return None
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)

        import_data = await hass.async_add_executor_job(read_file)

        if import_data is None:
            _LOGGER.error("Import file not found: %s", filepath)
            return

        stored_entries = import_data.get("entries", import_data)
        if not isinstance(stored_entries, dict):
            _LOGGER.error("Invalid Adaptive Cover import structure")
            return

        invalid_entries = {}
        cover_owners: dict[str, str] = {}
        for stored_id, stored_data in stored_entries.items():
            if not isinstance(stored_data, dict):
                invalid_entries[stored_id] = ["entry_must_be_an_object"]
                continue
            errors = validate_options(stored_data.get("options"))
            for cover in _normalize_options(stored_data.get("options")).get(
                CONF_ENTITIES, []
            ):
                if cover in cover_owners:
                    errors.append(
                        f"cover_assigned_to_multiple_entries:{cover_owners[cover]}:{cover}"
                    )
                else:
                    cover_owners[cover] = stored_id
            if errors:
                invalid_entries[stored_id] = errors
        if invalid_entries:
            _LOGGER.error("Adaptive Cover import rejected: %s", invalid_entries)
            return

        current_entries = hass.config_entries.async_entries(DOMAIN)
        for entry in current_entries:
            matched_data = None
            if entry.entry_id in stored_entries:
                matched_data = stored_entries[entry.entry_id]
            else:
                for _stored_id, stored_data in stored_entries.items():
                    if stored_data.get("title") == entry.title:
                        matched_data = stored_data
                        break

            if matched_data:
                new_data = dict(matched_data.get("data", entry.data))
                new_options = _normalize_options(matched_data.get("options", entry.options))
                if dict(entry.data) != new_data or dict(entry.options) != new_options:
                    hass.config_entries.async_update_entry(
                        entry,
                        data=new_data,
                        options=new_options,
                    )

        current_entry_ids = {entry.entry_id for entry in current_entries}
        current_titles = {entry.title for entry in current_entries}
        for stored_id, stored_data in stored_entries.items():
            if stored_id not in current_entry_ids and stored_data.get("title") not in current_titles:
                _LOGGER.warning(
                    "Skipped Adaptive Cover backup entry %s (%s): no matching config entry",
                    stored_id,
                    stored_data.get("title"),
                )
        _LOGGER.info("Imported Adaptive Cover configuration from %s", filepath)

    async def export_diagnostics(call: ServiceCall) -> None:
        """Export current config, runtime decisions and related HA states."""
        filename = call.data.get("filename", "adaptive_cover_diagnostics.json")
        refresh = call.data.get("refresh", True)
        filepath = _config_file_path(hass, filename)

        export_data = {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "domain": DOMAIN,
            "schema_version": 3,
            "entries": {},
        }

        tracked_option_keys = [
            CONF_TEMP_ENTITY,
            CONF_PRESENCE_ENTITY,
            CONF_WEATHER_ENTITY,
            CONF_END_ENTITY,
            CONF_WINDOW_ENTITY,
            CONF_RAIN_ENTITY,
            CONF_WIND_ENTITY,
            CONF_OUTSIDETEMP_ENTITY,
            CONF_LUX_ENTITY,
            CONF_IRRADIANCE_ENTITY,
            CONF_WORKDAY_ENTITY,
            CONF_START_ENTITY,
        ]

        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
            if refresh and coordinator is not None:
                await coordinator.async_request_refresh()

            options = _normalize_options(entry.options)
            cover_entities = options.get(CONF_ENTITIES) or []
            related_entities = set(CONF_SUN)
            related_entities.update(cover_entities)
            for key in tracked_option_keys:
                entity_id = options.get(key)
                if entity_id:
                    related_entities.add(entity_id)

            runtime = {}
            if coordinator is not None:
                manager = getattr(coordinator, "manager", None)
                runtime = {
                    "coordinator_loaded": True,
                    "state": getattr(coordinator, "state", None),
                    "default_state": getattr(coordinator, "default_state", None),
                    "climate_state": getattr(coordinator, "climate_state", None),
                    "control_method": getattr(coordinator, "control_method", None),
                    "switches": {
                        "switch_mode": getattr(coordinator, "switch_mode", None),
                        "control_toggle": getattr(coordinator, "control_toggle", None),
                        "manual_toggle": getattr(coordinator, "manual_toggle", None),
                        "temp_toggle": getattr(coordinator, "temp_toggle", None),
                        "lux_toggle": getattr(coordinator, "lux_toggle", None),
                        "irradiance_toggle": getattr(coordinator, "irradiance_toggle", None),
                        "strict_sun_block_toggle": getattr(coordinator, "strict_sun_block_toggle", None),
                        "dry_run_toggle": getattr(coordinator, "dry_run_toggle", None),
                    },
                    "coordinator_data": {
                        "states": getattr(getattr(coordinator, "data", None), "states", {}),
                        "attributes": getattr(getattr(coordinator, "data", None), "attributes", {}),
                    },
                    "wait_for_target": getattr(coordinator, "wait_for_target", {}),
                    "target_call": getattr(coordinator, "target_call", {}),
                    "manager": {
                        "manual_control": getattr(manager, "manual_control", {}),
                        "manual_control_time": getattr(manager, "manual_control_time", {}),
                        "cover_status": getattr(manager, "cover_status", {}),
                        "last_skip_reason": getattr(manager, "last_skip_reason", {}),
                        "status_reason": getattr(manager, "status_reason", {}),
                        "last_service_call": getattr(manager, "last_service_call", {}),
                        "last_service_error": getattr(manager, "last_service_error", {}),
                        "movement_history": getattr(manager, "movement_history", {}),
                        "manual_controlled": getattr(manager, "manual_controlled", []),
                    },
                    "behavioral_learning": coordinator.learner.diagnostics(),
                }
            else:
                runtime = {"coordinator_loaded": False}

            coordinator_data = getattr(getattr(coordinator, "data", None), "attributes", {})
            target_position = coordinator_data.get("target_position")

            export_data["entries"][entry.entry_id] = {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "data": dict(entry.data),
                "options": options,
                "configured_covers": cover_entities,
                "cover_diagnostics": {
                    entity_id: _json_safe(
                        _cover_diagnostics(
                            hass,
                            coordinator,
                            entity_id,
                            target_position,
                            options,
                        )
                    )
                    for entity_id in cover_entities
                },
                "runtime": _json_safe(runtime),
                "related_entities": {
                    entity_id: _entity_snapshot(hass, entity_id)
                    for entity_id in sorted(related_entities)
                },
            }

        def write_file():
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(_json_safe(export_data), f, indent=4, ensure_ascii=False)

        await hass.async_add_executor_job(write_file)
        _LOGGER.info("Exported Adaptive Cover diagnostics to %s", filepath)

    hass.services.async_register(
        DOMAIN,
        "export_config",
        export_config,
        schema=vol.Schema({
            vol.Optional("filename", default="adaptive_cover_settings.json"): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN,
        "import_config",
        import_config,
        schema=vol.Schema({
            vol.Optional("filename", default="adaptive_cover_settings.json"): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN,
        "export_diagnostics",
        export_diagnostics,
        schema=vol.Schema({
            vol.Optional("filename", default="adaptive_cover_diagnostics.json"): cv.string,
            vol.Optional("refresh", default=True): cv.boolean,
        })
    )

    return True

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy entries to complete, validated option schema version 2."""
    if entry.version > 2:
        _LOGGER.error("Unsupported Adaptive Cover config version: %s", entry.version)
        return False

    options = _normalize_options(entry.options)
    errors = validate_options(options)
    if errors:
        _LOGGER.error("Cannot migrate %s: %s", entry.title, errors)
        return False

    if entry.version < 2 or dict(entry.options) != options:
        hass.config_entries.async_update_entry(
            entry,
            options=options,
            version=2,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Adaptive Cover from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    options = _normalize_options(entry.options)
    selected_covers = set(options.get(CONF_ENTITIES, []))
    for other_entry in hass.config_entries.async_entries(DOMAIN):
        if other_entry.entry_id == entry.entry_id:
            continue
        overlap = selected_covers.intersection(
            _normalize_options(other_entry.options).get(CONF_ENTITIES, [])
        )
        if overlap:
            _LOGGER.error(
                "Cannot load %s because covers are assigned more than once: %s",
                entry.title,
                sorted(overlap),
            )
            return False

    coordinator = AdaptiveDataUpdateCoordinator(hass, entry)
    _temp_entity = options.get(CONF_TEMP_ENTITY)
    _presence_entity = options.get(CONF_PRESENCE_ENTITY)
    _weather_entity = options.get(CONF_WEATHER_ENTITY)
    _cover_entities = options.get(CONF_ENTITIES, [])
    _end_time_entity = options.get(CONF_END_ENTITY)
    _window_entity = options.get(CONF_WINDOW_ENTITY)
    _rain_entity = options.get(CONF_RAIN_ENTITY)
    _wind_entity = options.get(CONF_WIND_ENTITY)
    _outside_temp_entity = options.get(CONF_OUTSIDETEMP_ENTITY)
    _lux_entity = options.get(CONF_LUX_ENTITY)
    _irradiance_entity = options.get(CONF_IRRADIANCE_ENTITY)
    _workday_entity = options.get(CONF_WORKDAY_ENTITY)
    _start_time_entity = options.get(CONF_START_ENTITY)

    _entities = ["sun.sun"]

    for entity in [
        _temp_entity,
        _presence_entity,
        _weather_entity,
        _end_time_entity,
        _window_entity,
        _rain_entity,
        _wind_entity,
        _outside_temp_entity,
        _lux_entity,
        _irradiance_entity,
        _workday_entity,
        _start_time_entity,
    ]:
        if entity is not None:
            _entities.append(entity)

    _LOGGER.debug("Setting up entry %s", entry.data.get("name"))

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            _entities,
            coordinator.async_check_entity_state_change,
        )
    )

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            _cover_entities,
            coordinator.async_check_cover_state_change,
        )
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
