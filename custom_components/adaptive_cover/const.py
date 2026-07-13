"""Constants for the Adaptive Cover integration."""

from copy import deepcopy
import logging

DOMAIN = "adaptive_cover"
INTEGRATION_VERSION = "1.5.1"
DIAGNOSTICS_SCHEMA_VERSION = 4
SETTINGS_SCHEMA_VERSION = 4
LOGGER = logging.getLogger(__package__)
_LOGGER = logging.getLogger(__name__)

ATTR_POSITION = "position"
ATTR_TILT_POSITION = "tilt_position"

CONF_AZIMUTH = "set_azimuth"
CONF_BLUEPRINT = "blueprint"
CONF_HEIGHT_WIN = "window_height"
CONF_DISTANCE = "distance_shaded_area"
CONF_WINDOW_DEPTH = "window_depth"
CONF_SILL_HEIGHT = "sill_height"
CONF_DEFAULT_HEIGHT = "default_percentage"
CONF_FOV_LEFT = "fov_left"
CONF_FOV_RIGHT = "fov_right"
CONF_ENTITIES = "group"
CONF_HEIGHT_AWNING = "height_awning"
CONF_LENGTH_AWNING = "length_awning"
CONF_AWNING_ANGLE = "angle"
CONF_SENSOR_TYPE = "sensor_type"
CONF_INVERSE_STATE = "inverse_state"
CONF_SUNSET_POS = "sunset_position"
CONF_SUNSET_OFFSET = "sunset_offset"
CONF_TILT_DEPTH = "slat_depth"
CONF_TILT_DISTANCE = "slat_distance"
CONF_TILT_MODE = "tilt_mode"
CONF_SUNSET_POS = "sunset_position"
CONF_SUNSET_OFFSET = "sunset_offset"
CONF_SUNRISE_OFFSET = "sunrise_offset"
CONF_TEMP_ENTITY = "temp_entity"
CONF_PRESENCE_ENTITY = "presence_entity"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_TEMP_LOW = "temp_low"
CONF_TEMP_HIGH = "temp_high"
CONF_MODE = "mode"
CONF_CLIMATE_MODE = "climate_mode"
CONF_WEATHER_STATE = "weather_state"
CONF_MAX_POSITION = "max_position"
CONF_MIN_POSITION = "min_position"
CONF_ENABLE_MAX_POSITION = "enable_max_position"
CONF_ENABLE_MIN_POSITION = "enable_min_position"
CONF_OUTSIDETEMP_ENTITY = "outside_temp"
CONF_ENABLE_BLIND_SPOT = "blind_spot"
CONF_BLIND_SPOT_RIGHT = "blind_spot_right"
CONF_BLIND_SPOT_LEFT = "blind_spot_left"
CONF_BLIND_SPOT_ELEVATION = "blind_spot_elevation"
CONF_MIN_ELEVATION = "min_elevation"
CONF_MAX_ELEVATION = "max_elevation"
CONF_TRANSPARENT_BLIND = "transparent_blind"
CONF_INTERP_START = "interp_start"
CONF_INTERP_END = "interp_end"
CONF_INTERP_LIST = "interp_list"
CONF_INTERP_LIST_NEW = "interp_list_new"
CONF_INTERP = "interp"
CONF_LUX_ENTITY = "lux_entity"
CONF_LUX_THRESHOLD = "lux_threshold"
CONF_IRRADIANCE_ENTITY = "irradiance_entity"
CONF_IRRADIANCE_THRESHOLD = "irradiance_threshold"
CONF_OUTSIDE_THRESHOLD = "outside_threshold"
CONF_DAWN_MONTH_START = "dawn_month_start"
CONF_DAWN_MONTH_END = "dawn_month_end"
CONF_DAWN_DURATION = "dawn_duration"
CONF_COLD_THRESHOLD = "cold_threshold"
CONF_WIND_THRESHOLD = "wind_threshold"
CONF_PURGE_POS = "purge_pos"
CONF_WORKDAY_ENTITY = "workday_entity"
CONF_START_TIME_WORKDAY = "start_time_workday"
CONF_START_TIME_WEEKEND = "start_time_weekend"
CONF_CLOSE_SUNSET_OFFSET = "close_sunset_offset"
CONF_RAIN_NIGHT_ONLY = "rain_night_only"
CONF_WEATHER_FORECAST_TEMP = "weather_forecast_temp"
CONF_RAIN_POSITION = "rain_position"
CONF_WIND_POSITION = "wind_position"
CONF_NIGHT_PURGE_ENABLED = "night_purge_enabled"
CONF_NIGHT_PURGE_END_TIME = "night_purge_end_time"
CONF_THERMAL_HOLD_AFTER_SUN = "thermal_hold_after_sun"
CONF_THERMAL_HOLD_POSITION = "thermal_hold_position"
CONF_THERMAL_HOLD_DURATION = "thermal_hold_duration"
CONF_THERMAL_HOLD_RELEASE_DELTA = "thermal_hold_release_delta"
CONF_LUX_THRESHOLD_ON = "lux_threshold_on"
CONF_LUX_THRESHOLD_OFF = "lux_threshold_off"
CONF_IRRADIANCE_THRESHOLD_ON = "irradiance_threshold_on"
CONF_IRRADIANCE_THRESHOLD_OFF = "irradiance_threshold_off"

CONF_DELTA_POSITION = "delta_position"
CONF_DELTA_TIME = "delta_time"
CONF_GLOBAL_COOLDOWN = "global_cooldown"
CONF_MAX_MOVES_PER_HOUR = "max_moves_per_hour"
CONF_MAX_MOVES_PER_DAY = "max_moves_per_day"
CONF_START_TIME = "start_time"
CONF_START_ENTITY = "start_entity"
CONF_END_TIME = "end_time"
CONF_END_ENTITY = "end_entity"
CONF_RETURN_SUNSET = "return_sunset"
CONF_MANUAL_OVERRIDE_DURATION = "manual_override_duration"
CONF_MANUAL_OVERRIDE_RESET = "manual_override_reset"
CONF_MANUAL_THRESHOLD = "manual_threshold"
CONF_MANUAL_IGNORE_INTERMEDIATE = "manual_ignore_intermediate"

CONF_WINDOW_ENTITY = "window_entity"
CONF_WINDOW_OPEN_ACTION = "window_open_action"
CONF_WINDOW_OPEN_POSITION = "window_open_position"
CONF_RAIN_ENTITY = "rain_entity"
CONF_WIND_ENTITY = "wind_entity"

WINDOW_ACTION_PAUSE = "pause"
WINDOW_ACTION_MOVE_TO_POSITION = "move_to_position"
WINDOW_ACTION_BLOCK_CLOSING_ONLY = "block_closing_only"
WINDOW_ACTION_RETURN_AFTER_CLOSE = "return_after_close"
WINDOW_OPEN_ACTIONS = [
    WINDOW_ACTION_PAUSE,
    WINDOW_ACTION_MOVE_TO_POSITION,
    WINDOW_ACTION_BLOCK_CLOSING_ONLY,
    WINDOW_ACTION_RETURN_AFTER_CLOSE,
]

STRATEGY_MODE_BASIC = "basic"
STRATEGY_MODE_CLIMATE = "climate"
STRATEGY_MODES = [
    STRATEGY_MODE_BASIC,
    STRATEGY_MODE_CLIMATE,
]

DEFAULT_OPTIONS = {
    CONF_MODE: STRATEGY_MODE_BASIC,
    CONF_AZIMUTH: 180,
    CONF_HEIGHT_WIN: None,
    CONF_DISTANCE: None,
    CONF_WINDOW_DEPTH: 0.0,
    CONF_SILL_HEIGHT: 0.0,
    CONF_DEFAULT_HEIGHT: 60,
    CONF_MAX_POSITION: None,
    CONF_MIN_POSITION: None,
    CONF_ENABLE_MAX_POSITION: False,
    CONF_ENABLE_MIN_POSITION: False,
    CONF_FOV_LEFT: 90,
    CONF_FOV_RIGHT: 90,
    CONF_ENTITIES: [],
    CONF_INVERSE_STATE: False,
    CONF_SUNSET_POS: 0,
    CONF_SUNSET_OFFSET: 0,
    CONF_SUNRISE_OFFSET: 0,
    CONF_LENGTH_AWNING: None,
    CONF_AWNING_ANGLE: None,
    CONF_TILT_DISTANCE: None,
    CONF_TILT_DEPTH: None,
    CONF_TILT_MODE: None,
    CONF_TEMP_ENTITY: None,
    CONF_PRESENCE_ENTITY: None,
    CONF_WEATHER_ENTITY: None,
    CONF_TEMP_LOW: 21,
    CONF_TEMP_HIGH: 25,
    CONF_OUTSIDETEMP_ENTITY: None,
    CONF_CLIMATE_MODE: False,
    CONF_WEATHER_STATE: ["sunny", "partlycloudy", "cloudy", "clear"],
    CONF_DELTA_POSITION: 1,
    CONF_DELTA_TIME: 2,
    CONF_GLOBAL_COOLDOWN: 5,
    CONF_MAX_MOVES_PER_HOUR: 8,
    CONF_MAX_MOVES_PER_DAY: 40,
    CONF_START_TIME: "00:00:00",
    CONF_START_ENTITY: None,
    CONF_END_TIME: "00:00:00",
    CONF_END_ENTITY: None,
    CONF_RETURN_SUNSET: False,
    CONF_MANUAL_OVERRIDE_DURATION: {"minutes": 15},
    CONF_MANUAL_OVERRIDE_RESET: False,
    CONF_MANUAL_THRESHOLD: None,
    CONF_MANUAL_IGNORE_INTERMEDIATE: False,
    CONF_BLIND_SPOT_RIGHT: None,
    CONF_BLIND_SPOT_LEFT: None,
    CONF_BLIND_SPOT_ELEVATION: None,
    CONF_ENABLE_BLIND_SPOT: False,
    CONF_MIN_ELEVATION: None,
    CONF_MAX_ELEVATION: None,
    CONF_TRANSPARENT_BLIND: False,
    CONF_INTERP: False,
    CONF_INTERP_START: None,
    CONF_INTERP_END: None,
    CONF_INTERP_LIST: [],
    CONF_INTERP_LIST_NEW: [],
    CONF_LUX_ENTITY: None,
    CONF_LUX_THRESHOLD: 1000,
    CONF_LUX_THRESHOLD_ON: 1200,
    CONF_LUX_THRESHOLD_OFF: 800,
    CONF_IRRADIANCE_ENTITY: None,
    CONF_IRRADIANCE_THRESHOLD: 300,
    CONF_IRRADIANCE_THRESHOLD_ON: 350,
    CONF_IRRADIANCE_THRESHOLD_OFF: 250,
    CONF_OUTSIDE_THRESHOLD: 0,
    CONF_RAIN_ENTITY: None,
    CONF_WIND_ENTITY: None,
    CONF_RAIN_POSITION: 0,
    CONF_WIND_POSITION: 0,
    CONF_DAWN_MONTH_START: 5,
    CONF_DAWN_MONTH_END: 10,
    CONF_DAWN_DURATION: 60,
    CONF_COLD_THRESHOLD: 16,
    CONF_WIND_THRESHOLD: 40,
    CONF_NIGHT_PURGE_ENABLED: True,
    CONF_NIGHT_PURGE_END_TIME: "07:00:00",
    CONF_PURGE_POS: 15,
    CONF_THERMAL_HOLD_AFTER_SUN: False,
    CONF_THERMAL_HOLD_POSITION: 30,
    CONF_THERMAL_HOLD_DURATION: 120,
    CONF_THERMAL_HOLD_RELEASE_DELTA: 1.0,
    CONF_RAIN_NIGHT_ONLY: False,
    CONF_WINDOW_ENTITY: None,
    CONF_WINDOW_OPEN_ACTION: WINDOW_ACTION_PAUSE,
    CONF_WINDOW_OPEN_POSITION: 100,
    CONF_WORKDAY_ENTITY: None,
    CONF_START_TIME_WORKDAY: "07:00:00",
    CONF_START_TIME_WEEKEND: "09:00:00",
    CONF_CLOSE_SUNSET_OFFSET: 0,
}


class SensorType:
    """Possible modes for a number selector."""

    BLIND = "cover_blind"
    AWNING = "cover_awning"
    TILT = "cover_tilt"


def normalize_options(options: dict | None) -> dict:
    """Return a complete, independent option dictionary."""
    normalized = deepcopy(DEFAULT_OPTIONS)
    normalized.update(dict(options or {}))
    if not isinstance(normalized.get(CONF_ENTITIES), list):
        normalized[CONF_ENTITIES] = []
    if not isinstance(normalized.get(CONF_MANUAL_OVERRIDE_DURATION), dict):
        normalized[CONF_MANUAL_OVERRIDE_DURATION] = deepcopy(
            DEFAULT_OPTIONS[CONF_MANUAL_OVERRIDE_DURATION]
        )
    if not normalized.get(CONF_NIGHT_PURGE_END_TIME):
        normalized[CONF_NIGHT_PURGE_END_TIME] = DEFAULT_OPTIONS[
            CONF_NIGHT_PURGE_END_TIME
        ]
    return normalized


def validate_options(options: dict | None) -> list[str]:
    """Return cross-field validation errors for persisted or imported options."""
    values = normalize_options(options)
    errors: list[str] = []

    temp_low = values[CONF_TEMP_LOW]
    temp_high = values[CONF_TEMP_HIGH]
    if temp_low is not None and temp_high is not None and temp_low >= temp_high:
        errors.append("temp_low_must_be_lower_than_temp_high")
    lux_off = values[CONF_LUX_THRESHOLD_OFF]
    lux_on = values[CONF_LUX_THRESHOLD_ON]
    if lux_off is not None and lux_on is not None and lux_off > lux_on:
        errors.append("lux_off_must_not_exceed_on")
    irradiance_off = values[CONF_IRRADIANCE_THRESHOLD_OFF]
    irradiance_on = values[CONF_IRRADIANCE_THRESHOLD_ON]
    if (
        irradiance_off is not None
        and irradiance_on is not None
        and irradiance_off > irradiance_on
    ):
        errors.append("irradiance_off_must_not_exceed_on")

    min_position = values[CONF_MIN_POSITION]
    max_position = values[CONF_MAX_POSITION]
    if min_position is not None and max_position is not None and min_position > max_position:
        errors.append("min_position_must_not_exceed_max_position")

    source = values[CONF_INTERP_LIST] or []
    target = values[CONF_INTERP_LIST_NEW] or []
    if values[CONF_INTERP] and len(source) != len(target):
        errors.append("interpolation_lists_must_have_equal_length")
    try:
        source_values = list(map(int, source))
        list(map(int, target))
        if source_values and sorted(source_values) != source_values:
            errors.append("interpolation_source_must_be_sorted")
    except (TypeError, ValueError):
        errors.append("interpolation_values_must_be_integers")

    return errors
