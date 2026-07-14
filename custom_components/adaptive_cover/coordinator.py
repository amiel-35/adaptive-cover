"""The Coordinator for Adaptive Cover."""

from __future__ import annotations

import homeassistant.util.dt as dt_util
import asyncio
from collections import deque
import datetime as dt
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .config_context_adapter import ConfigContextAdapter

from .calculation import (
    AdaptiveHorizontalCover,
    AdaptiveTiltCover,
    AdaptiveVerticalCover,
    ClimateCoverData,
    ClimateCoverState,
    NormalCoverState,
)
from .learning import BehavioralLearner
from .decision import (
    EMERGENCY_DECISION_CODES,
    LEARNABLE_DECISION_CODES,
    SCHEDULE_EXEMPT_DECISION_CODES,
    DecisionResult,
    decision_priority,
    position_requires_move,
)
from .const import (
    _LOGGER,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CONF_AWNING_ANGLE,
    CONF_AZIMUTH,
    CONF_BLIND_SPOT_ELEVATION,
    CONF_BLIND_SPOT_LEFT,
    CONF_BLIND_SPOT_RIGHT,
    CONF_CLIMATE_MODE,
    CONF_DEFAULT_HEIGHT,
    CONF_DELTA_POSITION,
    CONF_DELTA_TIME,
    CONF_DISTANCE,
    CONF_ENABLE_BLIND_SPOT,
    CONF_ENABLE_MAX_POSITION,
    CONF_ENABLE_MIN_POSITION,
    CONF_END_ENTITY,
    CONF_END_TIME,
    CONF_ENTITIES,
    CONF_FOV_LEFT,
    CONF_FOV_RIGHT,
    CONF_HEIGHT_WIN,
    CONF_WINDOW_DEPTH,
    CONF_SILL_HEIGHT,
    CONF_INTERP,
    CONF_INTERP_END,
    CONF_INTERP_LIST,
    CONF_INTERP_LIST_NEW,
    CONF_INTERP_START,
    CONF_INVERSE_STATE,
    CONF_IRRADIANCE_ENTITY,
    CONF_IRRADIANCE_THRESHOLD,
    CONF_IRRADIANCE_THRESHOLD_OFF,
    CONF_IRRADIANCE_THRESHOLD_ON,
    CONF_LENGTH_AWNING,
    CONF_LUX_ENTITY,
    CONF_LUX_THRESHOLD,
    CONF_LUX_THRESHOLD_OFF,
    CONF_LUX_THRESHOLD_ON,
    CONF_MANUAL_IGNORE_INTERMEDIATE,
    CONF_MANUAL_OVERRIDE_DURATION,
    CONF_MANUAL_OVERRIDE_RESET,
    CONF_MANUAL_THRESHOLD,
    CONF_GLOBAL_COOLDOWN,
    CONF_MAX_MOVES_PER_DAY,
    CONF_MAX_MOVES_PER_HOUR,
    CONF_MAX_ELEVATION,
    CONF_MAX_POSITION,
    CONF_MIN_ELEVATION,
    CONF_MIN_POSITION,
    CONF_NIGHT_PURGE_ENABLED,
    CONF_NIGHT_PURGE_END_TIME,
    CONF_OUTSIDE_THRESHOLD,
    CONF_OUTSIDETEMP_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_RETURN_SUNSET,
    CONF_START_ENTITY,
    CONF_START_TIME,
    CONF_START_TIME_WEEKEND,
    CONF_START_TIME_WORKDAY,
    CONF_SUNRISE_OFFSET,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_POS,
    CONF_TEMP_ENTITY,
    CONF_TEMP_HIGH,
    CONF_TEMP_LOW,
    CONF_TILT_DEPTH,
    CONF_TILT_DISTANCE,
    CONF_TILT_MODE,
    CONF_TRANSPARENT_BLIND,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_FORECAST_TEMP,
    CONF_WEATHER_STATE,
    CONF_WINDOW_ENTITY,
    CONF_WINDOW_OPEN_ACTION,
    CONF_WINDOW_OPEN_POSITION,
    CONF_WORKDAY_ENTITY,
    CONF_RAIN_ENTITY,
    CONF_RAIN_POSITION,
    CONF_WIND_ENTITY,
    CONF_WIND_POSITION,
    CONF_DAWN_MONTH_START,
    CONF_DAWN_MONTH_END,
    CONF_DAWN_DURATION,
    CONF_COLD_THRESHOLD,
    CONF_WIND_THRESHOLD,
    CONF_PURGE_POS,
    CONF_RAIN_NIGHT_ONLY,
    CONF_THERMAL_HOLD_AFTER_SUN,
    CONF_THERMAL_HOLD_DURATION,
    CONF_THERMAL_HOLD_POSITION,
    CONF_THERMAL_HOLD_RELEASE_DELTA,
    WINDOW_ACTION_BLOCK_CLOSING_ONLY,
    WINDOW_ACTION_MOVE_TO_POSITION,
    WINDOW_ACTION_PAUSE,
    WINDOW_ACTION_RETURN_AFTER_CLOSE,
    DOMAIN,
    LOGGER,
    normalize_options,
)
from .helpers import get_datetime_from_str, get_safe_state

def state_attr(hass, entity_id: str, attr_name: str):
    """Return a Home Assistant state attribute safely."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get(attr_name)


def _as_float(value, default=None):
    """Convert a Home Assistant value to float when possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

@dataclass
class StateChangedData:
    """StateChangedData class."""

    entity_id: str
    old_state: State | None
    new_state: State | None


@dataclass
class AdaptiveCoverData:
    """AdaptiveCoverData class."""

    climate_mode_toggle: bool
    states: dict
    attributes: dict


class AdaptiveDataUpdateCoordinator(DataUpdateCoordinator[AdaptiveCoverData]):
    """Adaptive cover data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:  # noqa: D107
        self.config_entry = config_entry
        super().__init__(hass, LOGGER, name=DOMAIN)

        initial_options = normalize_options(config_entry.options)
        self.logger = ConfigContextAdapter(_LOGGER)
        self.logger.set_config_name(self.config_entry.data.get("name"))
        self._cover_type = self.config_entry.data.get("sensor_type")
        self._climate_mode = initial_options[CONF_CLIMATE_MODE]
        self._switch_mode = True if self._climate_mode else False
        self._inverse_state = initial_options[CONF_INVERSE_STATE]
        self._use_interpolation = initial_options[CONF_INTERP]
        self._track_end_time = initial_options[CONF_RETURN_SUNSET]
        self._temp_toggle = None
        self._control_toggle = None
        self._manual_toggle = None
        self._lux_toggle = None
        self._irradiance_toggle = None
        self._strict_sun_block_toggle = False
        self._dry_run_toggle = False
        self._lux_low_light_state: bool | None = None
        self._irradiance_low_light_state: bool | None = None
        self._last_direct_sun_at: dt.datetime | None = None
        self._direct_sun_was_active = False
        self.last_decision: DecisionResult | None = None
        self.last_decision_trace: list[dict] = []
        self.decision_history: deque[dict] = deque(maxlen=50)
        self.last_climate_data: ClimateCoverData | None = None
        self._start_time = None
        self._sun_end_time = None
        self._sun_start_time = None
        # self._end_time = None
        self.manual_reset = initial_options[CONF_MANUAL_OVERRIDE_RESET]
        self.manual_duration = initial_options[CONF_MANUAL_OVERRIDE_DURATION]
        self.state_change = False
        self.cover_state_change = False
        self.first_refresh = False
        self.timed_refresh = False
        self.climate_state = None
        self.control_method = "intermediate"
        self.state_change_data: StateChangedData | None = None
        self.learner = BehavioralLearner(hass, self.logger, config_entry.entry_id)
        self.manager = AdaptiveCoverManager(self.manual_duration, self.logger, self.learner)
        self.wait_for_target = {}
        self.target_call = {}
        self.verify_tasks = {}
        self.verify_task_metadata: dict[str, dict] = {}
        self._command_generation: dict[str, int] = {}
        self._unloading = False
        self._runtime_initialized = False
        self._runtime_initialization_task = None
        self._diagnostic_refresh = False
        self._started_at = dt.datetime.now(dt.UTC)
        self._update_count = 0
        self._last_update_started_at: dt.datetime | None = None
        self._last_update_finished_at: dt.datetime | None = None
        self._last_update_duration_ms: float | None = None
        self._last_update_error: str | None = None
        self._active_options = normalize_options(config_entry.options)
        self.ignore_intermediate_states = initial_options[
            CONF_MANUAL_IGNORE_INTERMEDIATE
        ]
        self._update_listener = None
        self._scheduled_time: dt.datetime | None = None
        self._night_purge_update_listener = None
        self._night_purge_scheduled_time: dt.datetime | None = None
        self._forecast_temperature: float | None = None
        self._forecast_fetched_at: dt.datetime | None = None
        self._forecast_entity: str | None = None
        self.config_entry.async_on_unload(self._async_cancel_night_purge_listener)
        self.config_entry.async_on_unload(self._async_cancel_runtime_tasks)

    async def async_config_entry_first_refresh(self) -> None:
        """Config entry first refresh."""
        await self.learner.async_load()
        self._last_direct_sun_at = self.learner.last_direct_sun_at
        await super().async_config_entry_first_refresh()
        self.logger.debug("Config entry first refresh")

    def schedule_runtime_initialization(self) -> None:
        """Schedule one movement pass after startup entities settle."""
        if self._runtime_initialized or (
            self._runtime_initialization_task is not None
            and not self._runtime_initialization_task.done()
        ):
            return
        self._runtime_initialization_task = self._create_background_task(
            self.async_runtime_entities_initialized(),
            f"adaptive_cover initialize runtime for {self.config_entry.entry_id}",
        )

    async def async_runtime_entities_initialized(self) -> None:
        """Enable physical movement after Home Assistant startup stabilizes."""
        await asyncio.sleep(2)
        if self._unloading or self._runtime_initialized:
            return
        self.state_change = False
        self.cover_state_change = False
        self.state_change_data = None
        self._runtime_initialized = True
        self.first_refresh = True
        await self.async_refresh()

    async def async_diagnostic_refresh(self) -> None:
        """Refresh calculations without issuing physical cover commands."""
        self._diagnostic_refresh = True
        try:
            await self.async_request_refresh()
        finally:
            self._diagnostic_refresh = False

    def _create_background_task(self, target, name: str):
        """Create a lifecycle-bound task which never delays Home Assistant startup."""
        entry_create_task = getattr(
            self.config_entry,
            "async_create_background_task",
            None,
        )
        if entry_create_task is not None:
            return entry_create_task(self.hass, target, name)

        hass_create_task = getattr(self.hass, "async_create_background_task", None)
        if hass_create_task is not None:
            return hass_create_task(target, name)

        return self.hass.async_create_task(target, name)

    def _update_verify_metadata(
        self,
        entity: str,
        *,
        expected_generation: int | None = None,
        **changes,
    ) -> None:
        """Update the bounded retry snapshot retained for one cover."""
        metadata = self.verify_task_metadata.setdefault(entity, {})
        if (
            expected_generation is not None
            and metadata.get("generation") != expected_generation
        ):
            return
        metadata.update(changes)
        metadata["updated_at"] = dt.datetime.now(dt.UTC)

    async def async_timed_refresh(self, event) -> None:
        """Control state at end time."""
        self._update_listener = None
        self.timed_refresh = True
        self.logger.debug("Timed refresh triggered at %s", dt_util.now())
        await self.async_refresh()

    async def async_get_weather_forecast_temperature(
        self, weather_entity: str | None
    ) -> float | None:
        """Get today's forecast temperature using Home Assistant weather service."""
        if not weather_entity:
            return None

        cached_temperature = (
            self._forecast_temperature
            if self._forecast_entity == weather_entity
            else None
        )
        now = dt_util.utcnow()
        if (
            self._forecast_entity == weather_entity
            and self._forecast_fetched_at is not None
            and now - self._forecast_fetched_at < dt.timedelta(hours=1)
        ):
            return cached_temperature

        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError as err:
            self.logger.debug(
                "Unable to fetch weather forecast for %s: %s",
                weather_entity,
                err,
            )
            return cached_temperature

        forecast = response.get(weather_entity, {}).get("forecast", [])
        if not forecast:
            return cached_temperature
        self._forecast_entity = weather_entity
        self._forecast_fetched_at = now
        self._forecast_temperature = _as_float(forecast[0].get("temperature"))
        return self._forecast_temperature

    async def async_check_entity_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        self.logger.debug("Entity state change")
        self.state_change = True
        await self.async_refresh()

    async def async_check_cover_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        self.logger.debug("Cover state change")
        data = event.data
        if data["old_state"] is None or data["new_state"] is None:
            self.logger.debug("Incomplete cover state-change event")
            return
        self.state_change_data = StateChangedData(
            data["entity_id"], data["old_state"], data["new_state"]
        )
        if (
            self.ignore_intermediate_states
            and self.state_change_data.new_state.state in {"opening", "closing"}
        ):
            self.logger.debug("Ignoring intermediate cover state")
            return
        if self.state_change_data.old_state.state != "unknown":
            self.cover_state_change = True
            self.process_entity_state_change()
            await self.async_refresh()
        else:
            self.logger.debug("Old state is unknown, not processing")

    def process_entity_state_change(self):
        """Process state change event."""
        event = self.state_change_data
        if event is None or event.new_state is None:
            return
        self.logger.debug("Processing state change event: %s", event)
        entity_id = event.entity_id
        if self.ignore_intermediate_states and event.new_state.state in [
            "opening",
            "closing",
        ]:
            self.logger.debug("Ignoring intermediate state change for %s", entity_id)
            return
        if self.wait_for_target.get(entity_id):
            position = event.new_state.attributes.get(
                "current_position"
                if self._cover_type != "cover_tilt"
                else "current_tilt_position"
            )
            if position == self.target_call.get(entity_id):
                self.logger.debug("Position %s reached for %s", position, entity_id)
            self.logger.debug("Wait for target: %s", self.wait_for_target)
        else:
            self.logger.debug("No wait for target call for %s", entity_id)

    @callback
    def _async_cancel_update_listener(self) -> None:
        """Cancel the scheduled update."""
        if self._update_listener:
            self._update_listener()
            self._update_listener = None
        self._scheduled_time = None

    @callback
    def _async_cancel_night_purge_listener(self) -> None:
        """Anuluj zaplanowane zamknięcie po nocnym wietrzeniu."""
        if self._night_purge_update_listener:
            self._night_purge_update_listener()
            self._night_purge_update_listener = None
        self._night_purge_scheduled_time = None

    @callback
    def _async_cancel_runtime_tasks(self) -> None:
        """Cancel callbacks and verification tasks owned by this coordinator."""
        self._unloading = True
        self._async_cancel_update_listener()
        self._async_cancel_night_purge_listener()
        for task in self.verify_tasks.values():
            if not task.done():
                task.cancel()
        self.verify_tasks.clear()
        self.wait_for_target.clear()

    def _next_night_purge_close_time(self) -> dt.datetime | None:
        """Wyznacz najbliższą godzinę zamknięcia po nocnym wietrzeniu."""
        value = self._active_options.get(
            CONF_NIGHT_PURGE_END_TIME, "07:00:00"
        )
        try:
            close_time = dt.time.fromisoformat(value)
        except (TypeError, ValueError):
            self.logger.warning("Invalid night purge end time: %s", value)
            return None

        now_local = dt_util.now()
        target_local = dt.datetime.combine(
            now_local.date(),
            close_time,
            tzinfo=dt_util.DEFAULT_TIME_ZONE,
        )
        if target_local <= now_local:
            target_local = dt.datetime.combine(
                now_local.date() + dt.timedelta(days=1),
                close_time,
                tzinfo=dt_util.DEFAULT_TIME_ZONE,
            )
        return dt_util.as_utc(target_local)

    def _schedule_night_purge_close(self) -> None:
        """Zaplanuj punktualne zamknięcie po nocnym wietrzeniu."""
        enabled = self._active_options.get(CONF_NIGHT_PURGE_ENABLED, True)
        if not self._climate_mode or not enabled or not self.switch_mode:
            self._async_cancel_night_purge_listener()
            return

        target = self._next_night_purge_close_time()
        if target is None or target == self._night_purge_scheduled_time:
            return

        self._async_cancel_night_purge_listener()
        self._night_purge_update_listener = async_track_point_in_time(
            self.hass,
            self.async_close_after_night_purge,
            target,
        )
        self._night_purge_scheduled_time = target
        self.logger.debug("Night purge close scheduled at %s", target)

    async def async_close_after_night_purge(self, _event) -> None:
        """Zamknij rolety punktualnie po zakończeniu nocnego wietrzenia."""
        self._night_purge_update_listener = None
        self._night_purge_scheduled_time = None

        await self._async_apply_night_purge_close()
        await self.async_refresh()
        self._schedule_night_purge_close()

    async def _async_apply_night_purge_close(self) -> None:
        """Apply the configured post-purge position without daytime schedule gates."""

        if self._runtime_initialized and self.control_toggle and self.switch_mode:
            close_position = self._active_options.get(CONF_SUNSET_POS, 0)
            if self._inverse_state:
                close_position = inverse_state(close_position)

            await self.manager.reset_if_needed()
            for cover in self.entities:
                if await self.async_handle_window_policy(cover, close_position):
                    continue
                if self.manager.is_cover_manual(cover):
                    self.manager.set_status(
                        cover,
                        "skipped",
                        "manual_override_active",
                    )
                    continue
                await self.async_set_manual_position(
                    cover,
                    close_position,
                    enforce_current_target=False,
                )

    def _night_purge_close_overdue(self) -> bool:
        """Return whether startup occurred after a missed morning purge deadline."""
        if not (
            self._climate_mode
            and self.switch_mode
            and self._active_options.get(CONF_NIGHT_PURGE_ENABLED, True)
        ):
            return False
        try:
            close_time = dt.time.fromisoformat(
                self._active_options.get(CONF_NIGHT_PURGE_END_TIME, "07:00:00")
            )
        except (TypeError, ValueError):
            return False
        now_local = dt_util.now()
        return bool(
            close_time < dt.time(12)
            and now_local.time() >= close_time
            and self._start_time is not None
            and dt_util.utcnow() < self._start_time
        )

    async def async_timed_end_time(self) -> None:
        """Control state at end time."""
        self.logger.debug("Scheduling end time update at %s", self._end_time)
        self._async_cancel_update_listener()
        self.logger.debug(
            "End time: %s, Track end time: %s, Scheduled time: %s, Condition: %s",
            self._end_time,
            self._track_end_time,
            self._scheduled_time,
            self._end_time != self._scheduled_time,
        )
        self._update_listener = async_track_point_in_time(
            self.hass, self.async_timed_refresh, self._end_time
        )
        self._scheduled_time = self._end_time

    async def _async_update_data(self) -> AdaptiveCoverData:
        """Track coordinator health around one complete data refresh."""
        started = perf_counter()
        self._update_count += 1
        self._last_update_started_at = dt.datetime.now(dt.UTC)
        self._last_update_error = None
        try:
            return await self._async_calculate_update_data()
        except Exception as err:  # noqa: BLE001
            self._last_update_error = f"{type(err).__name__}: {err}"
            raise
        finally:
            self._last_update_finished_at = dt.datetime.now(dt.UTC)
            self._last_update_duration_ms = round((perf_counter() - started) * 1000, 3)

    async def _async_calculate_update_data(self) -> AdaptiveCoverData:
        """Calculate and apply one Adaptive Cover update."""
        self.logger.debug("Updating data")
        options = normalize_options(self.config_entry.options)
        self._active_options = options
        self._update_options(options)
        self._schedule_night_purge_close()

        # Get data for the blind
        cover_data = self.get_blind_data(options=options)

        # Update manager with covers
        self._update_manager_and_covers()

        # Access climate data if climate mode is enabled
        if self._climate_mode:
            options = dict(options)
            options[CONF_WEATHER_FORECAST_TEMP] = (
                await self.async_get_weather_forecast_temperature(
                    options.get(CONF_WEATHER_ENTITY)
                )
            )
            self.climate_mode_data(options, cover_data)
        else:
            self.last_climate_data = None
            self.last_decision_trace = []
            self.logger.debug("Control method is %s", self.control_method)

        # calculate the state of the cover
        self.normal_cover_state = NormalCoverState(cover_data)
        self.logger.debug(
            "Determined normal cover state to be %s", self.normal_cover_state
        )

        self.default_state = round(self.normal_cover_state.get_state())
        self.logger.debug("Determined default state to be %s", self.default_state)
        state = self.state

        await self.manager.reset_if_needed()

        end_time = self._end_time
        if self._track_end_time and end_time is not None:
            if end_time != self._scheduled_time:
                if end_time > dt_util.utcnow():
                    await self.async_timed_end_time()
                else:
                    self._async_cancel_update_listener()
                    self._scheduled_time = end_time
                    self.timed_refresh = True
        elif self._scheduled_time is not None:
            self._async_cancel_update_listener()

        # Handle types of changes
        if self._runtime_initialized and not self._diagnostic_refresh:
            if self.state_change:
                await self.async_handle_state_change(state, options)
            if self.cover_state_change:
                await self.async_handle_cover_state_change(state)
            if self.first_refresh:
                await self.async_handle_first_refresh(state, options)
            if self.timed_refresh:
                await self.async_handle_timed_refresh(state, options)

        normal_cover = self.normal_cover_state.cover
        # Run the solar_times method in a separate thread
        if (
            self.first_refresh
            or self._sun_start_time is None
            or dt_util.now().date() != dt_util.as_local(self._sun_start_time).date()
        ):
            self.logger.debug("Calculating solar times")
            loop = asyncio.get_event_loop()
            start, end = await loop.run_in_executor(None, normal_cover.solar_times)
            self._sun_start_time = start
            self._sun_end_time = end
            self.logger.debug("Sun start time: %s, Sun end time: %s", start, end)
        else:
            start, end = self._sun_start_time, self._sun_end_time

        explanation = getattr(cover_data, "state_info", "auto")
        state_reason = getattr(cover_data, "state_reason", "Działanie automatyczne.")
        if self.control_toggle is False:
            explanation = "control_disabled"
            state_reason = (
                "Automatyka jest wyłączona. Wyliczona pozycja nie zostanie ustawiona."
            )
        elif self.is_window_open:
            explanation = "window_open"
            state_reason = {
                WINDOW_ACTION_MOVE_TO_POSITION: (
                    f"Okno otwarte: używana jest bezpieczna pozycja "
                    f"{int(self.window_open_position)}%."
                ),
                WINDOW_ACTION_BLOCK_CLOSING_ONLY: (
                    "Okno otwarte: zablokowane są wyłącznie ruchy zamykające."
                ),
                WINDOW_ACTION_RETURN_AFTER_CLOSE: (
                    "Okno otwarte: adaptacja wstrzymana do ponownego zamknięcia."
                ),
            }.get(self.window_open_action, "Okno otwarte: wstrzymano adaptację.")

        if not any(
            item.get("code") == explanation and item.get("selected")
            for item in self.last_decision_trace
        ):
            for item in self.last_decision_trace:
                if item.get("selected"):
                    item["selected"] = False
                    item["outcome"] = "overridden_by_runtime_policy"
            self.last_decision_trace.append(
                {
                    "code": explanation,
                    "priority": decision_priority(explanation),
                    "active": True,
                    "selected": True,
                    "outcome": "selected",
                }
            )

        self.last_decision = DecisionResult(
            target_position=state,
            code=explanation,
            reason=state_reason,
            priority=decision_priority(explanation),
            inputs={
                "sun_azimuth": state_attr(self.hass, "sun.sun", "azimuth"),
                "sun_elevation": state_attr(self.hass, "sun.sun", "elevation"),
                "direct_sun_valid": normal_cover.direct_sun_valid,
                "inside_temperature": (
                    _as_float(self.last_climate_data.inside_temperature)
                    if self.last_climate_data
                    else None
                ),
                "outside_temperature": (
                    self.last_climate_data.outside_temperature
                    if self.last_climate_data
                    else None
                ),
                "irradiance": _as_float(
                    get_safe_state(self.hass, options.get(CONF_IRRADIANCE_ENTITY))
                ),
            },
        )
        learned_targets = {
            entity: self._target_for_entity(entity, state)
            for entity in self.entities
        }
        self.decision_history.append(
            {
                "timestamp": dt.datetime.now(dt.UTC),
                "decision": self.last_decision.as_dict(),
                "decision_trace": list(self.last_decision_trace),
                "learned_targets": learned_targets,
                "cover_status": dict(self.manager.cover_status),
                "status_reason": dict(self.manager.status_reason),
            }
        )

        return AdaptiveCoverData(
            climate_mode_toggle=self.switch_mode,
            states={
                "state": state,
                "start": start,
                "end": end,
                "control": self.control_method,
                "explanation": explanation,
                "state_reason": state_reason,
                "sun_motion": normal_cover.valid,
                "manual_override": self.manager.binary_cover_manual,
                "manual_list": self.manager.manual_controlled,
                "cover_status": self.manager.cover_status,
            },
            attributes={
                "default": options.get(CONF_DEFAULT_HEIGHT),
                "sunset_default": options.get(CONF_SUNSET_POS),
                "sunset_offset": options.get(CONF_SUNSET_OFFSET),
                "azimuth_window": options.get(CONF_AZIMUTH),
                "field_of_view": [
                    options.get(CONF_FOV_LEFT),
                    options.get(CONF_FOV_RIGHT),
                ],
                "blind_spot": options.get(CONF_BLIND_SPOT_ELEVATION),
                "target_position": state,
                "decision": self.last_decision.as_dict(),
                "decision_trace": list(self.last_decision_trace),
                "learned_targets": learned_targets,
                "dry_run": self.dry_run_toggle,
                "window_open": self.is_window_open,
                "window_open_action": self.window_open_action,
                "window_open_position": self.window_open_position,
                "night_purge_end_time": options.get(
                    CONF_NIGHT_PURGE_END_TIME, "07:00:00"
                ),
                "night_purge_next_close": (
                    self._night_purge_scheduled_time.isoformat()
                    if self._night_purge_scheduled_time
                    else None
                ),
                "sun_azimuth": state_attr(self.hass, "sun.sun", "azimuth"),
                "sun_elevation": state_attr(self.hass, "sun.sun", "elevation"),
                "last_skip_reason": self.manager.last_skip_reason,
                "status_reason": self.manager.status_reason,
                "last_service_call": self.manager.last_service_call,
                "last_service_error": self.manager.last_service_error,
                "movement_count_last_hour": self.manager.movement_counts(dt.timedelta(hours=1)),
                "movement_count_last_day": self.manager.movement_counts(dt.timedelta(days=1)),
                "cover_status": self.manager.cover_status,
                "lux_low_light": self._lux_low_light_state,
                "irradiance_low_light": self._irradiance_low_light_state,
                "lux": _as_float(get_safe_state(self.hass, options.get(CONF_LUX_ENTITY))),
                "irradiance": _as_float(
                    get_safe_state(self.hass, options.get(CONF_IRRADIANCE_ENTITY))
                ),
                "outside_temperature_entity": _as_float(
                    get_safe_state(self.hass, options.get(CONF_OUTSIDETEMP_ENTITY))
                ),
                "inside_temperature": (
                    _as_float(self.last_climate_data.inside_temperature)
                    if self.last_climate_data
                    else None
                ),
                "current_temperature": (
                    self.last_climate_data.get_current_temperature
                    if self.last_climate_data
                    else None
                ),
                "outside_temperature": (
                    self.last_climate_data.outside_temperature
                    if self.last_climate_data
                    else None
                ),
                "forecast_temperature": options.get(CONF_WEATHER_FORECAST_TEMP),
                "thermal_stress": (
                    self.last_climate_data.thermal_stress
                    if self.last_climate_data
                    else None
                ),
                "last_direct_sun_at": self._last_direct_sun_at,
                "is_raining": (
                    self.last_climate_data.is_raining if self.last_climate_data else None
                ),
                "rain_rate": _as_float(
                    get_safe_state(self.hass, options.get(CONF_RAIN_ENTITY))
                ),
                "weather_state": get_safe_state(self.hass, options.get(CONF_WEATHER_ENTITY)),
                "wind_speed": (
                    self.last_climate_data.current_wind_speed
                    if self.last_climate_data
                    else None
                ),
                "wind_gust": _as_float(
                    get_safe_state(self.hass, options.get(CONF_WIND_ENTITY))
                ),
            },
        )

    async def async_handle_state_change(self, state: int, options):
        """Handle state change from tracked entities."""
        if self.control_toggle:
            for cover in self.entities:
                await self.async_handle_call_service(cover, state, options)
        else:
            self.logger.debug("State change but control toggle is off")
        self.state_change = False
        self.logger.debug("State change handled")

    async def async_handle_cover_state_change(self, state: int):
        """Handle state change from assigned covers."""
        if self.manual_toggle and self.control_toggle:
            entity_id = (
                self.state_change_data.entity_id if self.state_change_data else None
            )
            expected_state = (
                self._target_for_entity(entity_id, state)
                if entity_id is not None
                else state
            )
            climate = self.last_climate_data
            self.manager.handle_state_change(
                self.state_change_data,
                expected_state,
                self._cover_type,
                self.manual_reset,
                self.wait_for_target,
                self.target_call,
                self.manual_threshold,
                position_tolerance=self.min_change,
                current_temp=(climate.get_current_temperature if climate else None),
                is_summer=(climate.is_summer if climate else False),
                manual_until=self._manual_override_deadline(
                    self.state_change_data.new_state.last_updated
                    if self.state_change_data and self.state_change_data.new_state
                    else dt_util.utcnow()
                ),
                allow_learning=(self._decision_code() in LEARNABLE_DECISION_CODES),
            )
        self.cover_state_change = False
        self.logger.debug("Cover state change handled")

    async def async_handle_window_policy(self, entity: str, target_state: int) -> bool:
        """Apply configured behavior while the window or door is open."""
        if not self.is_window_open:
            return False

        action = self.window_open_action
        if action == WINDOW_ACTION_BLOCK_CLOSING_ONLY:
            current = self._get_current_position(entity)
            if current is not None and target_state < current:
                self.manager.set_status(entity, "blocked", "window_open_block_closing")
                self.logger.debug("Window open: blocked closing movement for %s", entity)
                return True
            return False

        if action == WINDOW_ACTION_MOVE_TO_POSITION:
            target = int(self.window_open_position)
            self.manager.set_status(entity, "window_open", "moving_to_window_position")
            if self.check_position(entity, target):
                await self.async_set_manual_position(
                    entity, target, enforce_current_target=False
                )
            return True

        if action == WINDOW_ACTION_RETURN_AFTER_CLOSE:
            self.manager.set_status(entity, "paused", "window_open_return_after_close")
            return True

        self.manager.set_status(entity, "paused", "window_open_pause")
        self.logger.debug("Window is open. Pausing adaptive movement for %s", entity)
        return True

    async def async_handle_first_refresh(self, state: int, options):
        """Handle first refresh."""
        if self.control_toggle:
            if self._night_purge_close_overdue():
                await self._async_apply_night_purge_close()
                self.first_refresh = False
                self.logger.debug("Missed night-purge deadline handled at startup")
                return
            if self.timed_refresh:
                self.first_refresh = False
                self.logger.debug("First refresh delegated to overdue end-time handler")
                return
            for cover in self.entities:
                await self.async_handle_call_service(cover, state, options)
        else:
            self.logger.debug("First refresh but control toggle is off")
        self.first_refresh = False
        self.logger.debug("First refresh handled")

    async def async_handle_timed_refresh(self, state: int, options):
        """Handle timed refresh."""
        night_control = self.climate_night_control_active
        self.logger.debug(
            "Timed refresh: night control=%s, calculated state=%s, sunset position=%s",
            night_control,
            state,
            options.get(CONF_SUNSET_POS),
        )
        if self.control_toggle:
            for cover in self.entities:
                target = (
                    self._target_for_entity(cover, state)
                    if night_control
                    else (
                        inverse_state(options.get(CONF_SUNSET_POS))
                        if self._inverse_state
                        else options.get(CONF_SUNSET_POS)
                    )
                )
                if await self.async_handle_window_policy(cover, target):
                    continue
                if not self.manager.is_cover_manual(cover):
                    await self.async_set_manual_position(
                        cover, target, enforce_current_target=False
                    )
                else:
                    self.logger.debug("Skiping timed refresh for %s because it is under manual control", cover)
        else:
            self.logger.debug("Timed refresh but control toggle is off")
        self.timed_refresh = False
        self.logger.debug("Timed refresh handled")

    async def async_handle_call_service(self, entity, state: int, options):
        """Handle call service."""
        if not self._runtime_initialized:
            self.manager.set_status(entity, "skipped", "runtime_initializing")
            return
        state = self._target_for_entity(entity, state)
        if await self.async_handle_window_policy(entity, state):
            return

        block_reason = self.movement_block_reason(entity, state, options)
        if block_reason is None:
            await self.async_set_position(entity, state)
        elif block_reason in {"cooldown", "hourly_move_limit", "daily_move_limit"}:
            self.manager.set_status(entity, "blocked", block_reason)
        else:
            self.manager.set_status(entity, "skipped", block_reason)

    def _target_for_entity(self, entity: str, state: int) -> int:
        """Apply learning only to comfort decisions, never to safety positions."""
        if self._decision_code() in LEARNABLE_DECISION_CODES:
            return self.learner.get_adjusted_position(entity, state)
        return state

    def _decision_code(self) -> str:
        """Return the decision code currently selected by the calculator."""
        cover = getattr(getattr(self, "normal_cover_state", None), "cover", None)
        return getattr(cover, "state_info", "auto")

    def movement_block_reason(self, entity, state: int, options) -> str | None:
        """Zwróć konkretny powód zablokowania ruchu rolety."""
        decision_code = self._decision_code()
        emergency = decision_code in EMERGENCY_DECISION_CODES
        if (
            decision_code not in SCHEDULE_EXEMPT_DECISION_CODES
            and not self.adaptive_movement_allowed
        ):
            return "outside_adaptive_time"
        if not self.check_position_delta(entity, state, options):
            return "position_delta_too_small"
        if not emergency and not self.check_time_delta(entity):
            return "time_delta_not_passed"
        if not emergency and self.manager.is_cover_manual(entity):
            return "manual_override_active"
        if not emergency and not self.manager.can_move(
            entity,
            self.global_cooldown,
            self.max_moves_per_hour,
            self.max_moves_per_day,
        ):
            return self.manager.last_skip_reason.get(entity, "movement_limit")
        return None

    async def async_set_position(self, entity, state: int):
        """Call service to set cover position."""
        await self.async_set_manual_position(entity, state)

    async def async_set_manual_position(
        self,
        entity,
        state,
        *,
        enforce_current_target: bool = True,
    ):
        """Call the cover service and verify that the current command completes."""
        if self._unloading:
            return
        if self.check_position(entity, state):
            service = SERVICE_SET_COVER_POSITION
            service_data = {ATTR_ENTITY_ID: entity}

            if self._cover_type == "cover_tilt":
                service = SERVICE_SET_COVER_TILT_POSITION
                service_data[ATTR_TILT_POSITION] = state
            else:
                service_data[ATTR_POSITION] = state

            generation = self._command_generation.get(entity, 0) + 1
            self._command_generation[entity] = generation
            self.wait_for_target[entity] = True
            self.target_call[entity] = state
            self.logger.debug("Run %s with data %s", service, service_data)

            if self.dry_run_toggle:
                self.wait_for_target[entity] = False
                self.manager.record_move(entity, service, service_data, dry_run=True)
                self.manager.set_status(entity, "dry_run", f"would_set_{state}")
                self._update_verify_metadata(
                    entity,
                    generation=generation,
                    target=state,
                    state="dry_run",
                    outcome="not_executed",
                )
                self.logger.info("Dry run: skipped %s with data %s", service, service_data)
                return

            # 1. Anuluj poprzednie sprawdzanie dla tej rolety, jeśli istnieje
            if entity in self.verify_tasks:
                self.verify_tasks[entity].cancel()
                self._update_verify_metadata(
                    entity,
                    state="cancelled",
                    outcome="replaced_by_new_command",
                )

            try:
                await self.hass.services.async_call(
                    COVER_DOMAIN,
                    service,
                    service_data,
                    blocking=True,
                )
            except HomeAssistantError as err:
                self.wait_for_target[entity] = False
                self.manager.last_service_error[entity] = str(err)
                self.manager.set_status(entity, "blocked", "service_call_failed")
                self._update_verify_metadata(
                    entity,
                    generation=generation,
                    target=state,
                    state="failed",
                    outcome="service_call_failed",
                    error=str(err),
                )
                self.logger.error("Unable to move %s: %s", entity, err)
                return
            self.manager.record_move(entity, service, service_data)
            self.manager.set_status(entity, "waiting_for_target", f"target_{state}")

            wait_time = max(
                45,
                int(float(self.global_cooldown) * 60) + 1,
                int(float(self.time_threshold) * 60) + 1,
            )
            self.verify_task_metadata[entity] = {
                "created_at": dt.datetime.now(dt.UTC),
                "updated_at": dt.datetime.now(dt.UTC),
                "generation": generation,
                "target": state,
                "service": service,
                "service_data": dict(service_data),
                "state": "scheduled",
                "outcome": None,
                "attempt": 0,
                "max_retries": 2,
                "wait_seconds": wait_time,
                "next_check_at": dt.datetime.now(dt.UTC)
                + dt.timedelta(seconds=wait_time),
                "last_observed_position": self._get_current_position(entity),
                "enforce_current_target": enforce_current_target,
            }
            task = self._create_background_task(
                self.async_verify_and_retry(
                    entity,
                    state,
                    service,
                    service_data,
                    generation=generation,
                    enforce_current_target=enforce_current_target,
                    wait_time=wait_time,
                    max_retries=2,
                ),
                f"adaptive_cover verify target for {entity}",
            )
            self.verify_tasks[entity] = task
        else:
            self.wait_for_target[entity] = False
            self.target_call[entity] = state
            self.manager.set_status(entity, "auto", "target_within_tolerance")

    async def async_verify_and_retry(
        self,
        entity,
        target_state,
        service,
        service_data,
        *,
        generation,
        enforce_current_target=True,
        wait_time=45,
        max_retries=2,
    ):
        """Verify if cover reached the target and retry if needed."""
        try:
            for attempt in range(1, max_retries + 1):
                self._update_verify_metadata(
                    entity,
                    expected_generation=generation,
                    state="waiting",
                    attempt=attempt,
                    next_check_at=dt.datetime.now(dt.UTC)
                    + dt.timedelta(seconds=wait_time),
                )
                await asyncio.sleep(wait_time)

                if self._retry_is_stale(
                    entity,
                    target_state,
                    generation,
                    enforce_current_target,
                ):
                    self.wait_for_target[entity] = False
                    self.manager.set_status(entity, "skipped", "retry_conditions_changed")
                    self._update_verify_metadata(
                        entity,
                        expected_generation=generation,
                        state="finished",
                        outcome="retry_conditions_changed",
                    )
                    return

                if not self.wait_for_target.get(entity):
                    self.manager.set_status(entity, "auto", "target_verified")
                    self._update_verify_metadata(
                        entity,
                        expected_generation=generation,
                        state="finished",
                        outcome="target_verified_by_event",
                    )
                    return

                current_pos = self._get_current_position(entity)
                self._update_verify_metadata(
                    entity,
                    expected_generation=generation,
                    last_observed_position=current_pos,
                )
                if current_pos is not None and not position_requires_move(
                    current_pos,
                    target_state,
                    self.min_change,
                ):
                    self.wait_for_target[entity] = False
                    self.manager.set_status(entity, "auto", "target_verified")
                    self._update_verify_metadata(
                        entity,
                        expected_generation=generation,
                        state="finished",
                        outcome="target_within_tolerance",
                    )
                    return

                if not self.manager.can_move(
                    entity,
                    self.global_cooldown,
                    self.max_moves_per_hour,
                    self.max_moves_per_day,
                ):
                    self.wait_for_target[entity] = False
                    self._update_verify_metadata(
                        entity,
                        expected_generation=generation,
                        state="finished",
                        outcome=self.manager.last_skip_reason.get(entity, "movement_limit"),
                    )
                    return

                self.manager.set_status(entity, "retrying", f"retry_{attempt}")
                try:
                    await self.hass.services.async_call(
                        COVER_DOMAIN,
                        service,
                        service_data,
                        blocking=True,
                    )
                except HomeAssistantError as err:
                    self.manager.last_service_error[entity] = str(err)
                    self.manager.set_status(entity, "blocked", "retry_service_failed")
                    self.wait_for_target[entity] = False
                    self._update_verify_metadata(
                        entity,
                        expected_generation=generation,
                        state="failed",
                        outcome="retry_service_failed",
                        error=str(err),
                    )
                    return
                self.manager.record_move(entity, service, service_data)
                self._update_verify_metadata(
                    entity,
                    expected_generation=generation,
                    state="retry_sent",
                    outcome=None,
                )

            self.wait_for_target[entity] = False
            self.manager.set_status(entity, "blocked", "target_not_reached")
            self._update_verify_metadata(
                entity,
                expected_generation=generation,
                state="finished",
                outcome="target_not_reached",
            )
        except asyncio.CancelledError:
            self._update_verify_metadata(
                entity,
                expected_generation=generation,
                state="cancelled",
                outcome="task_cancelled",
            )
            raise
        finally:
            if self.verify_tasks.get(entity) is asyncio.current_task():
                self.verify_tasks.pop(entity, None)

    def _retry_is_stale(
        self,
        entity: str,
        target_state: int,
        generation: int,
        enforce_current_target: bool,
    ) -> bool:
        """Return whether a delayed retry no longer matches current conditions."""
        if (
            self._unloading
            or not self.control_toggle
            or self._command_generation.get(entity) != generation
            or self.manager.is_cover_manual(entity)
        ):
            return True
        if enforce_current_target and self.state != target_state:
            return True
        if self.is_window_open:
            current = self._get_current_position(entity)
            action = self.window_open_action
            if action in {WINDOW_ACTION_PAUSE, WINDOW_ACTION_RETURN_AFTER_CLOSE}:
                return True
            if action == WINDOW_ACTION_MOVE_TO_POSITION:
                return target_state != int(self.window_open_position)
            if (
                action == WINDOW_ACTION_BLOCK_CLOSING_ONLY
                and current is not None
                and target_state < current
            ):
                return True
        return False

    def _update_options(self, options):
        """Update options."""
        self.entities = options.get(CONF_ENTITIES, [])
        self.window_entity = options.get(CONF_WINDOW_ENTITY)
        self.min_change = options.get(CONF_DELTA_POSITION, 1)
        self.time_threshold = options.get(CONF_DELTA_TIME, 2)
        self.global_cooldown = options.get(CONF_GLOBAL_COOLDOWN, 5)
        self.max_moves_per_hour = options.get(CONF_MAX_MOVES_PER_HOUR, 8)
        self.max_moves_per_day = options.get(CONF_MAX_MOVES_PER_DAY, 40)
        self.window_open_action = options.get(CONF_WINDOW_OPEN_ACTION, WINDOW_ACTION_PAUSE)
        self.window_open_position = options.get(CONF_WINDOW_OPEN_POSITION, 100)
        self.start_time = options.get(CONF_START_TIME)
        self.start_time_entity = options.get(CONF_START_ENTITY)
        self.end_time = options.get(CONF_END_TIME)
        self.end_time_entity = options.get(CONF_END_ENTITY)
        self.manual_reset = options.get(CONF_MANUAL_OVERRIDE_RESET, False)
        self.manual_duration = options.get(
            CONF_MANUAL_OVERRIDE_DURATION, {"minutes": 15}
        )
        if hasattr(self, "manager"):
            self.manager.reset_duration = dt.timedelta(**self.manual_duration)
        self.manual_threshold = options.get(CONF_MANUAL_THRESHOLD)
        self.start_value = options.get(CONF_INTERP_START)
        self.end_value = options.get(CONF_INTERP_END)
        self.normal_list = options.get(CONF_INTERP_LIST)
        self.new_list = options.get(CONF_INTERP_LIST_NEW)

    def _update_manager_and_covers(self):
        self.manager.add_covers(self.entities)
        if not self._manual_toggle:
            for entity in self.manager.manual_controlled:
                self.manager.reset(entity)

    def get_blind_data(self, options):
        """Assign correct class for type of blind."""
        if self._cover_type == "cover_blind":
            cover_data = AdaptiveVerticalCover(
                self.hass,
                self.logger,
                *self.pos_sun,
                *self.common_data(options),
                *self.vertical_data(options),
            )
        if self._cover_type == "cover_awning":
            cover_data = AdaptiveHorizontalCover(
                self.hass,
                self.logger,
                *self.pos_sun,
                *self.common_data(options),
                *self.vertical_data(options),
                *self.horizontal_data(options),
            )
        if self._cover_type == "cover_tilt":
            cover_data = AdaptiveTiltCover(
                self.hass,
                self.logger,
                *self.pos_sun,
                *self.common_data(options),
                *self.tilt_data(options),
            )
        return cover_data

    @property
    def check_adaptive_time(self):
        """Check if time is within start and end times."""
        after_start = self.after_start_time
        end_time = self._end_time
        if self._start_time and end_time and self._start_time > end_time:
            now = dt_util.utcnow()
            return now >= self._start_time or now < end_time
        return self.before_end_time and after_start

    @property
    def climate_night_control_active(self) -> bool:
        """Zezwalaj trybowi klimatycznemu reagować przez całą noc."""
        return bool(
            self._switch_mode
            and getattr(self, "normal_cover_state", None)
            and self.normal_cover_state.cover.sunset_valid
        )

    @property
    def adaptive_movement_allowed(self) -> bool:
        """Uwzględnij nocne sterowanie klimatyczne poza dziennym harmonogramem."""
        return self.check_adaptive_time or self.climate_night_control_active

    @property
    def after_start_time(self):
        """Check if time is after start time."""
        now = dt_util.utcnow()
        start_str = self._effective_start_value()

        value = (
            get_safe_state(self.hass, self.start_time_entity)
            if self.start_time_entity is not None
            else start_str
        )
        time_local = self._local_datetime_from_value(value)
        if time_local is None:
            time_local = self._local_datetime_from_value(start_str)

        time_utc = dt_util.as_utc(time_local)

        self.logger.debug("Start time UTC: %s, now UTC: %s", time_utc, now)
        self._start_time = time_utc
        return now >= time_utc

    def _effective_start_value(self) -> str:
        """Return today's configured start time without guessing unavailable workdays."""
        options = self._active_options
        workday_entity = options.get(CONF_WORKDAY_ENTITY)
        if not workday_entity:
            return options.get(CONF_START_TIME, "00:00:00")

        is_workday = True
        workday_state = self.hass.states.get(workday_entity)
        if workday_state and workday_state.state in {"on", "off"}:
            is_workday = workday_state.state == "on"
        key = CONF_START_TIME_WORKDAY if is_workday else CONF_START_TIME_WEEKEND
        default = "07:00:00" if is_workday else "09:00:00"
        return options.get(key, default)

    def _manual_override_deadline(self, reference: dt.datetime) -> dt.datetime:
        """Return one fixed reset deadline for a newly detected manual override."""
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=dt.UTC)
        if self.manual_duration.get("minutes") != 9999:
            return reference + dt.timedelta(**self.manual_duration)

        cover = getattr(getattr(self, "normal_cover_state", None), "cover", None)
        if cover is None:
            return reference + dt.timedelta(minutes=9999)
        local_reference = dt_util.as_local(reference)
        sunset = cover.sun_data.sunset(local_reference.date()) + dt.timedelta(
            minutes=self._active_options.get(CONF_SUNSET_OFFSET, 0)
        )
        sunset_utc = dt_util.as_utc(sunset)
        if sunset_utc <= reference:
            sunset_utc = dt_util.as_utc(
                cover.sun_data.sunset(local_reference.date() + dt.timedelta(days=1))
                + dt.timedelta(
                    minutes=self._active_options.get(CONF_SUNSET_OFFSET, 0)
                )
            )
        return sunset_utc

    @property
    def _end_time(self) -> dt.datetime | None:
        """Get end time based on sunset or config."""
        time_utc = None
        if self.end_time_entity is not None:
            time_local = self._local_datetime_from_value(
                get_safe_state(self.hass, self.end_time_entity)
            )
            if time_local is not None:
                time_utc = dt_util.as_utc(time_local)
        elif self.end_time and self.end_time != "00:00:00":
            time_local = self._local_datetime_from_value(self.end_time)
            if time_local is not None:
                time_utc = dt_util.as_utc(time_local)
        else:
            # Zamykanie oparte na zachodzie słońca i suwaku (offset)
            cover_data = self.get_blind_data(options=self.config_entry.options)
            sunset = cover_data.sun_data.sunset() # To jest już bezpieczny czas UTC
            offset = self.config_entry.options.get("close_sunset_offset", 0)
            if sunset:
                time_utc = sunset + dt.timedelta(minutes=offset)

        return time_utc

    def _local_datetime_from_value(self, value) -> dt.datetime | None:
        """Interpret a time entity value on the current Home Assistant local date."""
        if value is None:
            return None
        text = str(value)
        try:
            time_value = dt.time.fromisoformat(text)
            return dt.datetime.combine(
                dt_util.now().date(),
                time_value,
                tzinfo=dt_util.DEFAULT_TIME_ZONE,
            )
        except ValueError:
            parsed = get_datetime_from_str(text)
            if parsed is None:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return dt_util.as_local(parsed)

    @property
    def before_end_time(self):
        """Check if time is before end time."""
        if self._end_time is not None:
            now = dt_util.utcnow()
            self.logger.debug(
                "End time UTC: %s, now UTC: %s, now < time: %s",
                self._end_time,
                now,
                now < self._end_time,
            )
            return now < self._end_time
        return True

    def _get_current_position(self, entity) -> int | None:
        """Get current position of cover."""
        if self._cover_type == "cover_tilt":
            return state_attr(self.hass, entity, "current_tilt_position")
        return state_attr(self.hass, entity, "current_position")

    def check_position(self, entity, state):
        """Check if position is different as state."""
        position = self._get_current_position(entity)
        if position is not None:
            return position_requires_move(position, state, self.min_change)
        self.logger.debug("No current position available for %s", entity)
        return False

    @property
    def is_window_open(self):
        """Check if the physical window/door is open."""
        if getattr(self, 'window_entity', None):
            state = self.hass.states.get(self.window_entity)
            # W Home Assistant kontaktrony (binary_sensor) mają stan 'on', gdy magnes jest oddalony (okno otwarte)
            if state and state.state == "on":
                return True
        return False

    def check_position_delta(self, entity, state: int, options):
        """Check cover positions to reduce calls."""
        position = self._get_current_position(entity)
        if position is not None:
            condition = position_requires_move(position, state, self.min_change)
            self.logger.debug(
                "Entity: %s,  position: %s, state: %s, delta position: %s, min_change: %s, condition: %s",
                entity,
                position,
                state,
                abs(position - state),
                self.min_change,
                condition,
            )
            return condition
        return True

    def check_time_delta(self, entity):
        """Check if time delta is passed."""
        now = dt.datetime.now(dt.UTC)
        movement_history = self.manager.movement_history.get(entity, [])
        if movement_history:
            last_movement = max(movement_history)
            condition = now - last_movement >= dt.timedelta(minutes=float(self.time_threshold))
            self.logger.debug(
                "Entity: %s, time delta: %s, threshold: %s, condition: %s",
                entity,
                now - last_movement,
                self.time_threshold,
                condition,
            )
            return condition
        return True

    @property
    def pos_sun(self):
        """Fetch information for sun position."""
        return [
            state_attr(self.hass, "sun.sun", "azimuth"),
            state_attr(self.hass, "sun.sun", "elevation"),
        ]

    def common_data(self, options):
        """Update shared parameters."""
        default_pos = options.get(CONF_DEFAULT_HEIGHT)

        return [
            options.get(CONF_SUNSET_POS),
            options.get(CONF_SUNSET_OFFSET),
            options.get(CONF_SUNRISE_OFFSET, options.get(CONF_SUNSET_OFFSET)),
            self.hass.config.time_zone,
            options.get(CONF_FOV_LEFT),
            options.get(CONF_FOV_RIGHT),
            options.get(CONF_AZIMUTH),
            default_pos,
            options.get(CONF_MAX_POSITION),
            options.get(CONF_MIN_POSITION),
            options.get(CONF_ENABLE_MAX_POSITION, False),
            options.get(CONF_ENABLE_MIN_POSITION, False),
            options.get(CONF_BLIND_SPOT_LEFT),
            options.get(CONF_BLIND_SPOT_RIGHT),
            options.get(CONF_BLIND_SPOT_ELEVATION),
            options.get(CONF_ENABLE_BLIND_SPOT, False),
            options.get(CONF_MIN_ELEVATION, None),
            options.get(CONF_MAX_ELEVATION, None),
        ]

    def _low_light_hysteresis(
        self,
        entity_id: str | None,
        threshold_on: float | None,
        threshold_off: float | None,
        previous: bool | None,
    ) -> bool | None:
        """Return a stable low-light state using separate on/off thresholds."""
        if not entity_id or threshold_on is None or threshold_off is None:
            return previous

        value = _as_float(get_safe_state(self.hass, entity_id))
        if value is None:
            return previous

        low_on = float(threshold_off)
        low_off = float(threshold_on)
        if value <= low_on:
            return True
        if value >= low_off:
            return False
        return previous

    def get_climate_data(self, options, cover_data=None):
        """Update climate data."""
        temp_high = options.get(CONF_TEMP_HIGH)
        # Apply Behavioral ML offset for temp high
        if self.entities and temp_high is not None:
            offsets = [
                self.learner.get_temp_offset(entity) for entity in self.entities
            ]
            temp_high += sum(offsets) / len(offsets)

        self._lux_low_light_state = self._low_light_hysteresis(
            options.get(CONF_LUX_ENTITY),
            options.get(CONF_LUX_THRESHOLD_ON, options.get(CONF_LUX_THRESHOLD)),
            options.get(CONF_LUX_THRESHOLD_OFF, options.get(CONF_LUX_THRESHOLD)),
            self._lux_low_light_state,
        )
        self._irradiance_low_light_state = self._low_light_hysteresis(
            options.get(CONF_IRRADIANCE_ENTITY),
            options.get(CONF_IRRADIANCE_THRESHOLD_ON, options.get(CONF_IRRADIANCE_THRESHOLD)),
            options.get(CONF_IRRADIANCE_THRESHOLD_OFF, options.get(CONF_IRRADIANCE_THRESHOLD)),
            self._irradiance_low_light_state,
        )

        return [
            self.hass,
            self.logger,
            options.get(CONF_TEMP_ENTITY),
            options.get(CONF_TEMP_LOW),
            temp_high,
            options.get(CONF_PRESENCE_ENTITY),
            options.get(CONF_WEATHER_ENTITY),
            options.get(CONF_WEATHER_STATE),
            options.get(CONF_OUTSIDETEMP_ENTITY),
            self._temp_toggle,
            self._cover_type,
            options.get(CONF_TRANSPARENT_BLIND),
            options.get(CONF_LUX_ENTITY),
            options.get(CONF_IRRADIANCE_ENTITY),
            options.get(CONF_LUX_THRESHOLD),
            options.get(CONF_IRRADIANCE_THRESHOLD),
            options.get(CONF_LUX_THRESHOLD_ON, options.get(CONF_LUX_THRESHOLD)),
            options.get(CONF_LUX_THRESHOLD_OFF, options.get(CONF_LUX_THRESHOLD)),
            options.get(CONF_IRRADIANCE_THRESHOLD_ON, options.get(CONF_IRRADIANCE_THRESHOLD)),
            options.get(CONF_IRRADIANCE_THRESHOLD_OFF, options.get(CONF_IRRADIANCE_THRESHOLD)),
            options.get(CONF_OUTSIDE_THRESHOLD),
            self._lux_toggle,
            self._irradiance_toggle,
            self._lux_low_light_state,
            self._irradiance_low_light_state,
            options.get(CONF_RAIN_ENTITY),
            options.get(CONF_WIND_ENTITY),
            options.get(CONF_DAWN_MONTH_START, 5),
            options.get(CONF_DAWN_MONTH_END, 10),
            options.get(CONF_DAWN_DURATION, 60),
            options.get(CONF_COLD_THRESHOLD, 16),
            options.get(CONF_WIND_THRESHOLD, 40),
            options.get(CONF_PURGE_POS, 15),
            options.get(CONF_RAIN_NIGHT_ONLY, False),
            options.get(CONF_RAIN_POSITION, 0),
            options.get(CONF_WIND_POSITION, 0),
            self._strict_sun_block_toggle,
            options.get(CONF_WEATHER_FORECAST_TEMP),
            options.get(CONF_THERMAL_HOLD_AFTER_SUN, False),
            options.get(CONF_THERMAL_HOLD_POSITION, 30),
            options.get(CONF_THERMAL_HOLD_DURATION, 120),
            options.get(CONF_THERMAL_HOLD_RELEASE_DELTA, 1.0),
            bool(cover_data and cover_data.direct_sun_valid),
            self._last_direct_sun_at,
            options.get(CONF_NIGHT_PURGE_ENABLED, True),
            options.get(CONF_NIGHT_PURGE_END_TIME, "07:00:00"),
        ]

    def climate_mode_data(self, options, cover_data):
        """Update climate mode data and control method."""
        climate = ClimateCoverData(*self.get_climate_data(options, cover_data))
        has_direct_sun = cover_data.direct_sun_valid and not climate.is_raining
        if climate.irradiance_entity:
            irradiance = _as_float(get_safe_state(self.hass, climate.irradiance_entity))
            direct_sun_threshold = (
                climate.irradiance_threshold_off
                if climate.irradiance_threshold_off is not None
                else climate.irradiance_threshold
            )
            has_direct_sun = bool(
                has_direct_sun
                and irradiance is not None
                and direct_sun_threshold is not None
                and irradiance > float(direct_sun_threshold)
            )
        elif climate.weather_entity:
            has_direct_sun = has_direct_sun and climate.is_sunny

        if has_direct_sun:
            self._last_direct_sun_at = dt_util.utcnow()
            self.learner.remember_direct_sun(self._last_direct_sun_at)
        elif self._direct_sun_was_active and self._last_direct_sun_at is not None:
            self.learner.remember_direct_sun(self._last_direct_sun_at, force=True)
        self._direct_sun_was_active = has_direct_sun

        climate.last_direct_sun_at = self._last_direct_sun_at
        climate_state = ClimateCoverState(cover_data, climate)
        self.climate_state = round(climate_state.get_state())
        self.last_decision_trace = list(climate_state.decision_trace)
        climate_data = climate_state.climate_data
        self.last_climate_data = climate_data
        self.control_method = "intermediate"
        if climate_data.is_summer and self.switch_mode:
            self.control_method = "summer"
        elif climate_data.is_winter and self.switch_mode:
            self.control_method = "winter"
        self.logger.debug(
            "Climate mode control method was set to %s", self.control_method
        )

    def vertical_data(self, options):
        """Update data for vertical blinds."""
        return [
            options.get(CONF_DISTANCE),
            options.get(CONF_HEIGHT_WIN),
            options.get(CONF_WINDOW_DEPTH) if options.get(CONF_WINDOW_DEPTH) is not None else 0.0,
            options.get(CONF_SILL_HEIGHT) if options.get(CONF_SILL_HEIGHT) is not None else 0.0,
        ]

    def horizontal_data(self, options):
        """Update data for horizontal blinds."""
        return [
            options.get(CONF_LENGTH_AWNING),
            options.get(CONF_AWNING_ANGLE),
        ]

    def tilt_data(self, options):
        """Update data for tilted blinds."""
        return [
            options.get(CONF_TILT_DISTANCE),
            options.get(CONF_TILT_DEPTH),
            options.get(CONF_TILT_MODE),
        ]

    @property
    def state(self) -> int:
        """Handle the output of the state based on mode."""
        self.logger.debug(
            "Basic position: %s; Climate position: %s; Using climate position? %s",
            self.default_state,
            self.climate_state,
            self._switch_mode,
        )
        if self._switch_mode:
            state = self.climate_state
        else:
            state = self.default_state

        if self._use_interpolation:
            self.logger.debug("Interpolating position: %s", state)
            state = self.interpolate_states(state)

        if self._inverse_state and self._use_interpolation:
            self.logger.info(
                "Inverse state is not supported with interpolation, you can inverse the state by arranging the list from high to low"
            )

        if self._inverse_state and not self._use_interpolation:
            state = inverse_state(state)
            self.logger.debug("Inversed position: %s", state)

        if not np.isfinite(state):
            self.logger.error("Calculated position is not finite; using default position")
            state = self.default_state
        state = int(np.clip(round(state), 0, 100))
        self.logger.debug("Final position to use: %s", state)
        return state

    def interpolate_states(self, state):
        """Interpolate states."""
        normal_range = [0, 100]
        new_range = []
        if self.start_value is not None and self.end_value is not None:
            new_range = [self.start_value, self.end_value]
        if self.normal_list and self.new_list:
            normal_range = list(map(int, self.normal_list))
            new_range = list(map(int, self.new_list))
        if new_range:
            state = np.interp(state, normal_range, new_range)
            if state == new_range[0]:
                state = 0
            if state == new_range[-1]:
                state = 100
        return state

    @property
    def switch_mode(self):
        """Let switch toggle climate mode."""
        return self._switch_mode

    @switch_mode.setter
    def switch_mode(self, value):
        self._switch_mode = value

    @property
    def temp_toggle(self):
        """Let switch toggle between inside or outside temperature."""
        return self._temp_toggle

    @temp_toggle.setter
    def temp_toggle(self, value):
        self._temp_toggle = value

    @property
    def control_toggle(self):
        """Toggle automation."""
        return self._control_toggle

    @control_toggle.setter
    def control_toggle(self, value):
        self._control_toggle = value

    @property
    def manual_toggle(self):
        """Toggle automation."""
        return self._manual_toggle

    @manual_toggle.setter
    def manual_toggle(self, value):
        self._manual_toggle = value

    @property
    def lux_toggle(self):
        """Toggle automation."""
        return self._lux_toggle

    @lux_toggle.setter
    def lux_toggle(self, value):
        self._lux_toggle = value

    @property
    def irradiance_toggle(self):
        """Toggle automation."""
        return self._irradiance_toggle

    @irradiance_toggle.setter
    def irradiance_toggle(self, value):
        self._irradiance_toggle = value

    @property
    def strict_sun_block_toggle(self):
        """Toggle strict sun block."""
        return self._strict_sun_block_toggle

    @strict_sun_block_toggle.setter
    def strict_sun_block_toggle(self, value):
        self._strict_sun_block_toggle = value

    @property
    def dry_run_toggle(self):
        """Toggle dry-run mode."""
        return self._dry_run_toggle

    @dry_run_toggle.setter
    def dry_run_toggle(self, value):
        self._dry_run_toggle = value


class AdaptiveCoverManager:
    """Track position changes."""

    def __init__(self, reset_duration: dict[str, int], logger, learner=None) -> None:
        """Initialize the AdaptiveCoverManager."""
        self.covers: set[str] = set()

        self.manual_control: dict[str, bool] = {}
        self.manual_control_time: dict[str, dt.datetime] = {}
        self.manual_control_until: dict[str, dt.datetime] = {}
        self.reset_duration = dt.timedelta(**reset_duration)
        self.logger = logger
        self.learner = learner
        self.cover_status: dict[str, str] = {}
        self.status_reason: dict[str, str] = {}
        self.last_skip_reason: dict[str, str] = {}
        self.last_service_call: dict[str, dict] = {}
        self.last_service_error: dict[str, str] = {}
        self.movement_history: dict[str, list[dt.datetime]] = {}
        self.command_history: dict[str, list[dict]] = {}

    def add_covers(self, entity):
        """Update set with entities."""
        self.covers.update(entity)
        for cover in entity:
            self.cover_status.setdefault(cover, "auto")
            self.movement_history.setdefault(cover, [])
            self.command_history.setdefault(cover, [])

    def set_status(self, entity_id: str, status: str, reason: str | None = None) -> None:
        """Store current automation status for diagnostics."""
        self.cover_status[entity_id] = status
        if reason is not None:
            self.status_reason[entity_id] = reason
            if status in {"blocked", "skipped", "paused"}:
                self.last_skip_reason[entity_id] = reason

    def _prune_history(self, entity_id: str) -> None:
        """Keep movement history bounded to the last day."""
        since = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
        self.movement_history[entity_id] = [
            moved_at for moved_at in self.movement_history.get(entity_id, [])
            if moved_at >= since
        ]

    def can_move(
        self,
        entity_id: str,
        cooldown_minutes: int | float | None,
        max_per_hour: int | None,
        max_per_day: int | None,
    ) -> bool:
        """Return whether the cover may move without exceeding limits."""
        now = dt.datetime.now(dt.UTC)
        self._prune_history(entity_id)
        history = self.movement_history.setdefault(entity_id, [])

        if cooldown_minutes and history:
            cooldown = dt.timedelta(minutes=float(cooldown_minutes))
            if now - history[-1] < cooldown:
                self.set_status(entity_id, "blocked", "cooldown")
                return False

        last_hour = [moved_at for moved_at in history if now - moved_at <= dt.timedelta(hours=1)]
        if max_per_hour and len(last_hour) >= int(max_per_hour):
            self.set_status(entity_id, "blocked", "hourly_move_limit")
            return False

        if max_per_day and len(history) >= int(max_per_day):
            self.set_status(entity_id, "blocked", "daily_move_limit")
            return False

        return True

    def record_move(self, entity_id: str, service: str, service_data: dict, dry_run: bool = False) -> None:
        """Record a requested movement for diagnostics and rate limits."""
        now = dt.datetime.now(dt.UTC)
        if not dry_run:
            self.movement_history.setdefault(entity_id, []).append(now)
            self._prune_history(entity_id)
        self.last_service_call[entity_id] = {
            "service": service,
            "data": dict(service_data),
            "dry_run": dry_run,
            "time": now.isoformat(),
        }
        history = self.command_history.setdefault(entity_id, [])
        history.append(
            {
                "service": service,
                "data": dict(service_data),
                "dry_run": dry_run,
                "requested_at": now,
            }
        )
        del history[:-50]
        self.last_service_error.pop(entity_id, None)

    def movement_counts(self, period: dt.timedelta) -> dict[str, int]:
        """Return movement counts for every known cover in a period."""
        now = dt.datetime.now(dt.UTC)
        return {
            entity_id: len([moved_at for moved_at in history if now - moved_at <= period])
            for entity_id, history in self.movement_history.items()
        }

    def handle_state_change(
        self,
        states_data,
        our_state,
        blind_type,
        allow_reset,
        wait_target_call,
        target_call,
        manual_threshold,
        position_tolerance=1,
        current_temp=None,
        is_summer=False,
        manual_until=None,
        allow_learning=True,
    ):
        """Process state change event."""
        event = states_data
        if event is None:
            return
        entity_id = event.entity_id
        if entity_id not in self.covers:
            return

        new_state = event.new_state
        if new_state is None:
            return

        if blind_type == "cover_tilt":
            new_position = new_state.attributes.get("current_tilt_position")
        else:
            new_position = new_state.attributes.get("current_position")

        if wait_target_call.get(entity_id):
            target = target_call.get(entity_id)
            if target is not None and new_position is not None:
                if new_state.state in ["open", "closed", "ok", "stopped"]:
                    tolerance = max(
                        float(position_tolerance),
                        float(manual_threshold) if manual_threshold is not None else 2.0,
                    )
                    if position_requires_move(new_position, target, tolerance):
                        self.logger.debug("Motor stopped at %s instead of target %s. Manual override!", new_position, target)
                        wait_target_call[entity_id] = False
                    else:
                        wait_target_call[entity_id] = False
                        return
                else:
                    return
            else:
                return

        if new_position is None or our_state is None:
            self.logger.debug("No usable position in state change for %s", entity_id)
            return

        if new_position != our_state:
            if (
                manual_threshold is not None
                and abs(our_state - new_position) < manual_threshold
            ):
                self.logger.debug(
                    "Position change is less than threshold %s for %s",
                    manual_threshold,
                    entity_id,
                )
                return
            self.logger.debug(
                "Manual change detected for %s. Our state: %s, new state: %s",
                entity_id,
                our_state,
                new_position,
            )
            self.logger.debug(
                "Set manual control for %s, for at least %s seconds, reset_allowed: %s",
                entity_id,
                self.reset_duration.total_seconds(),
                allow_reset,
            )
            self.mark_manual_control(entity_id)
            self.set_last_updated(entity_id, new_state, allow_reset, manual_until)

            if self.learner and allow_learning:
                self.learner.register_override(
                    entity_id,
                    current_temp,
                    our_state,
                    new_position,
                    is_summer,
                )

    def set_last_updated(self, entity_id, new_state, allow_reset, manual_until=None):
        """Set last updated time for manual control."""
        if entity_id not in self.manual_control_time or allow_reset:
            last_updated = new_state.last_updated
            self.manual_control_time[entity_id] = last_updated
            self.manual_control_until[entity_id] = (
                manual_until
                if manual_until is not None
                else last_updated + self.reset_duration
            )
            self.logger.debug(
                "Updating last updated for manual control to %s for %s. Allow reset:%s",
                last_updated,
                entity_id,
                allow_reset,
            )
        elif not allow_reset:
            self.logger.debug(
                "Already manual control time specified for %s, reset is not allowed by user setting:%s",
                entity_id,
                allow_reset,
            )

    def mark_manual_control(self, cover: str) -> None:
        """Mark cover as under manual control."""
        self.manual_control[cover] = True
        self.set_status(cover, "manual_override", "manual_position_change")

    async def reset_if_needed(self):
        """Reset manual control state of the covers."""
        current_time = dt.datetime.now(dt.UTC)
        manual_control_time_copy = dict(self.manual_control_time)
        for entity_id, last_updated in manual_control_time_copy.items():
            deadline = self.manual_control_until.get(
                entity_id, last_updated + self.reset_duration
            )
            if current_time >= deadline:
                self.logger.debug(
                    "Resetting manual override for %s, because duration has elapsed",
                    entity_id,
                )
                self.reset(entity_id)

    def reset(self, entity_id):
        """Reset manual control for a cover."""
        self.manual_control[entity_id] = False
        self.manual_control_time.pop(entity_id, None)
        self.manual_control_until.pop(entity_id, None)
        self.set_status(entity_id, "auto", "manual_override_reset")
        self.logger.debug("Reset manual override for %s", entity_id)

    def is_cover_manual(self, entity_id):
        """Check if a cover is under manual control."""
        return self.manual_control.get(entity_id, False)

    @property
    def binary_cover_manual(self):
        """Check if any cover is under manual control."""
        return any(value for value in self.manual_control.values())

    @property
    def manual_controlled(self):
        """Get the list of covers under manual control."""
        return [k for k, v in self.manual_control.items() if v]


def inverse_state(state: int) -> int:
    """Inverse state."""
    return 100 - state
