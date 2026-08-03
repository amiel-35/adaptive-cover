"""Select platform for Adaptive Cover."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_MANUAL_OVERRIDE_DURATION, DOMAIN
from .options import normalize_options

OPTIONS = (
    "none",
    "15_min",
    "30_min",
    "60_min",
    "120_min",
    "240_min",
    "sunset",
)

MINUTES_TO_OPTION = {
    0: "none",
    15: "15_min",
    30: "30_min",
    60: "60_min",
    120: "120_min",
    240: "240_min",
    9999: "sunset",
}
OPTION_TO_MINUTES = {option: minutes for minutes, option in MINUTES_TO_OPTION.items()}
CUSTOM_PREFIX = "custom_"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AdaptiveCoverOverrideSelect(coordinator, config_entry)])


class AdaptiveCoverOverrideSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Select entity for Manual Override Duration."""

    _attr_has_entity_name = True
    _attr_translation_key = "manual_override"

    def __init__(self, coordinator, config_entry):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_override_duration"
        self._attr_icon = "mdi:timer-cog"
        self._attr_options = list(OPTIONS)
        duration_dict = normalize_options(config_entry.options)[
            CONF_MANUAL_OVERRIDE_DURATION
        ]
        minutes = max(0, int(duration_dict.get("minutes", 15)))
        current_option = MINUTES_TO_OPTION.get(minutes)
        if current_option is None:
            current_option = f"{CUSTOM_PREFIX}{minutes}_min"
            self._attr_options.append(current_option)
        self._attr_current_option = current_option

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.data.get("name", "Adaptive Cover"),
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option and SAVE permanently."""
        self._attr_current_option = option

        minutes = OPTION_TO_MINUTES.get(option)
        if (
            minutes is None
            and option.startswith(CUSTOM_PREFIX)
            and option.endswith("_min")
        ):
            minutes = int(option.removeprefix(CUSTOM_PREFIX).removesuffix("_min"))
        if minutes is None:
            raise ValueError(
                f"Nieobsługiwana wartość czasu sterowania ręcznego: {option}"
            )
        new_options = dict(self.config_entry.options)
        new_options[CONF_MANUAL_OVERRIDE_DURATION] = {"minutes": minutes}

        self.hass.config_entries.async_update_entry(
            self.config_entry, options=new_options
        )
        self.async_write_ha_state()
