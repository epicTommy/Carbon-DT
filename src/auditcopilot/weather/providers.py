"""Weather provider abstractions and demo/network implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
from pathlib import Path

import pandas as pd
import requests


class WeatherProvider(ABC):
    """Abstract interface for fetching monthly weather observations."""

    @abstractmethod
    def get_monthly_weather(self) -> pd.DataFrame:
        """Return raw monthly weather records."""


class DemoMonthlyWeatherProvider(WeatherProvider):
    """Load monthly weather records from sample data for local demos."""

    def __init__(self, source: str | Path) -> None:
        self.source = Path(source)

    def get_monthly_weather(self) -> pd.DataFrame:
        return pd.read_csv(self.source)


@dataclass(frozen=True)
class OpenMeteoLocation:
    latitude: float
    longitude: float
    name: str


class OpenMeteoWeatherProvider(WeatherProvider):
    """Fetch and cache historical monthly weather from Open-Meteo.

    The provider geocodes the supplied location query, requests daily mean temperature for the billing
    window, and aggregates the response to monthly average temperature in Fahrenheit.
    """

    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(
        self,
        query: str,
        start_date: str,
        end_date: str,
        cache_dir: str | Path,
        session: requests.Session | None = None,
        request_timeout_seconds: int = 20,
    ) -> None:
        self.query = query
        self.start_date = start_date
        self.end_date = end_date
        self.cache_dir = Path(cache_dir)
        self.session = session or requests.Session()
        self.request_timeout_seconds = request_timeout_seconds
        self.last_location: OpenMeteoLocation | None = None

    def get_monthly_weather(self) -> pd.DataFrame:
        cache_path = self._cache_path()
        if cache_path.exists():
            return pd.read_json(cache_path)

        location = self._geocode_address()
        weather_df = self._fetch_daily_weather(location)
        monthly_df = (
            weather_df.assign(
                year=lambda frame: pd.to_datetime(frame["date"]).dt.year,
                month=lambda frame: pd.to_datetime(frame["date"]).dt.month,
            )
            .groupby(["year", "month"], as_index=False)["avg_temp"]
            .mean()
            .sort_values(["year", "month"])
            .reset_index(drop=True)
        )

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        monthly_df.to_json(cache_path, orient="records")
        return monthly_df

    def _cache_path(self) -> Path:
        payload = f"{self.query}|{self.start_date}|{self.end_date}".encode("utf-8")
        cache_key = hashlib.sha256(payload).hexdigest()[:20]
        return self.cache_dir / f"open_meteo_{cache_key}.json"

    def _geocode_address(self) -> OpenMeteoLocation:
        response = self.session.get(
            self.GEOCODING_URL,
            params={
                "name": self.query,
                "count": 1,
                "format": "json",
            },
            timeout=self.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            raise ValueError(f"Open-Meteo geocoding returned no results for query: {self.query}")

        top_result = results[0]
        location = OpenMeteoLocation(
            latitude=float(top_result["latitude"]),
            longitude=float(top_result["longitude"]),
            name=self._format_location_name(top_result),
        )
        self.last_location = location
        return location

    def _fetch_daily_weather(self, location: OpenMeteoLocation) -> pd.DataFrame:
        response = self.session.get(
            self.ARCHIVE_URL,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "daily": "temperature_2m_mean",
                "temperature_unit": "fahrenheit",
                "timezone": "America/New_York",
            },
            timeout=self.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        daily = payload.get("daily")
        if not daily:
            raise ValueError("Open-Meteo archive response did not contain daily weather data.")

        weather_df = pd.DataFrame(
            {
                "date": daily["time"],
                "avg_temp": daily["temperature_2m_mean"],
            }
        )
        weather_df["avg_temp"] = pd.to_numeric(weather_df["avg_temp"], errors="raise")
        return weather_df

    def _format_location_name(self, geocoding_result: dict) -> str:
        name_parts = [
            geocoding_result.get("name"),
            geocoding_result.get("admin1"),
            geocoding_result.get("country_code"),
        ]
        return ", ".join(str(part) for part in name_parts if part)
