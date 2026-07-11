"""Fetch sun data."""

from datetime import datetime, timedelta

import pandas as pd
from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_location
from homeassistant.util import dt as dt_util


class SunData:
    """Access local sun data."""

    def __init__(self, timezone, hass: HomeAssistant) -> None:  # noqa: D107
        self.hass = hass
        location, elevation = get_astral_location(self.hass)
        self.location = location  # astral.location.Location
        self.elevation = elevation
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
        return [
            self.location.solar_azimuth(moment, self.elevation)
            for moment in self.times
        ]

    @property
    def solar_elevation(self) -> list:
        """Create list with solar elevation data per 5 minutes."""
        return [
            self.location.solar_elevation(moment, self.elevation)
            for moment in self.times
        ]

    def sunset(self) -> datetime:
        """Fetch sunset time."""
        return self.location.sunset(dt_util.now().date(), local=False)

    def sunrise(self) -> datetime:
        """Fetch sunrise time."""
        return self.location.sunrise(dt_util.now().date(), local=False)

    # def df_today(self)-> pd.DataFrame:
    #     """Create dataframe with azimuth and elevation data"""
    #     df_today = pd.DataFrame({"azimuth":self.solar_azimuth, "elevation":self.solar_elevation})
    #     df_today = df_today.set_index(self.times)
    #     return df_today
