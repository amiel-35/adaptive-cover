"""Fetch sun data."""

from datetime import date, datetime, timedelta

import pandas as pd
from astral import Observer
from astral.sun import azimuth, elevation, sunrise, sunset
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

try:
    from homeassistant.helpers.sun import get_astral_observer
except ImportError:
    def get_astral_observer(hass: HomeAssistant) -> Observer:
        """Build an Astral observer for older Home Assistant releases."""
        return Observer(
            latitude=hass.config.latitude,
            longitude=hass.config.longitude,
            elevation=hass.config.elevation,
        )


class SunData:
    """Access local sun data."""

    def __init__(self, timezone, hass: HomeAssistant) -> None:  # noqa: D107
        self.hass = hass
        self.observer = get_astral_observer(self.hass)
        self.timezone = timezone

    @property
    def times(self) -> pd.DatetimeIndex:
        """Define time interval."""
        start_date = dt_util.now().date()
        end_date = start_date + timedelta(days=1)

        times = pd.date_range(
            start=start_date, end=end_date, freq="5min", tz=self.timezone, name="time"
        )
        return times

    @property
    def solar_azimuth(self) -> list:
        """Create list with solar azimuth data per 5 minutes."""
        return [azimuth(self.observer, moment) for moment in self.times]

    @property
    def solar_elevation(self) -> list:
        """Create list with solar elevation data per 5 minutes."""
        return [elevation(self.observer, moment) for moment in self.times]

    def sunset(self, on_date: date | None = None) -> datetime:
        """Fetch sunset time."""
        return sunset(self.observer, on_date or dt_util.now().date())

    def sunrise(self) -> datetime:
        """Fetch sunrise time."""
        return sunrise(self.observer, dt_util.now().date())

    # def df_today(self)-> pd.DataFrame:
    #     """Create dataframe with azimuth and elevation data"""
    #     df_today = pd.DataFrame({"azimuth":self.solar_azimuth, "elevation":self.solar_elevation})
    #     df_today = df_today.set_index(self.times)
    #     return df_today
