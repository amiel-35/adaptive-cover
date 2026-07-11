"""Helper functions."""

from dateutil import parser
from homeassistant.core import HomeAssistant, split_entity_id


def get_safe_state(hass: HomeAssistant, entity_id: str):
    """Get a safe state value if not available."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if not state or state.state in ["unknown", "unavailable"]:
        return None
    return state.state


def get_domain(entity: str):
    """Get domain of entity."""
    if entity is not None:
        domain, object_id = split_entity_id(entity)
        return domain


def get_datetime_from_str(string: str):
    """Convert datetime string to datetime."""
    if string is not None:
        return parser.parse(string, ignoretz=True)
