"""Monthly weather normalization and derived metric generation."""

from __future__ import annotations

import pandas as pd

from auditcopilot.weather.degree_days import calculate_cdd, calculate_hdd
from auditcopilot.weather.providers import WeatherProvider


REQUIRED_WEATHER_COLUMNS = {"year", "month", "avg_temp"}


def build_monthly_weather_dataframe(provider: WeatherProvider) -> pd.DataFrame:
    """Return normalized monthly weather with avg_temp, HDD, and CDD."""
    weather_df = provider.get_monthly_weather().copy()
    _validate_weather_schema(weather_df)

    weather_df["year"] = pd.to_numeric(weather_df["year"], errors="raise").astype(int)
    weather_df["month"] = pd.to_numeric(weather_df["month"], errors="raise").astype(int)
    weather_df["avg_temp"] = pd.to_numeric(weather_df["avg_temp"], errors="raise").astype(float)

    invalid_months = weather_df.loc[~weather_df["month"].between(1, 12)]
    if not invalid_months.empty:
        raise ValueError("Weather data contains invalid month values outside 1-12.")

    weather_df["billing_month"] = pd.to_datetime(
        dict(year=weather_df["year"], month=weather_df["month"], day=1)
    ).dt.strftime("%Y-%m")
    weather_df["hdd"] = weather_df["avg_temp"].apply(calculate_hdd)
    weather_df["cdd"] = weather_df["avg_temp"].apply(calculate_cdd)

    columns = ["billing_month", "year", "month", "avg_temp", "hdd", "cdd"]
    return weather_df[columns].sort_values(["year", "month"]).reset_index(drop=True)


def _validate_weather_schema(weather_df: pd.DataFrame) -> None:
    missing_columns = sorted(REQUIRED_WEATHER_COLUMNS.difference(weather_df.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Weather data is missing required columns: {missing}")
