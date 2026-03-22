"""Feature engineering functions for monthly utility and weather data."""

from __future__ import annotations

import pandas as pd


REQUIRED_FEATURE_COLUMNS = {"billing_month", "floor_area_sqft"}


def engineer_monthly_features(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Add common monthly intensity and seasonality features."""
    features_df = monthly_df.copy()
    _validate_feature_inputs(features_df)

    features_df["billing_month"] = pd.to_datetime(features_df["billing_month"], format="%Y-%m")
    features_df["month_index"] = features_df["billing_month"].dt.month

    features_df["is_winter"] = features_df["month_index"].isin([12, 1, 2])
    features_df["is_spring"] = features_df["month_index"].isin([3, 4, 5])
    features_df["is_summer"] = features_df["month_index"].isin([6, 7, 8])
    features_df["is_fall"] = features_df["month_index"].isin([9, 10, 11])

    features_df["heating_season"] = features_df["month_index"].isin([11, 12, 1, 2, 3])
    features_df["cooling_season"] = features_df["month_index"].isin([5, 6, 7, 8, 9])

    features_df["electric_kwh_per_sqft"] = _usage_per_sqft(features_df, "electricity", "kwh")
    features_df["gas_therms_per_sqft"] = _usage_per_sqft(features_df, "gas", "therms")

    features_df["billing_month"] = features_df["billing_month"].dt.strftime("%Y-%m")
    return features_df


def _validate_feature_inputs(features_df: pd.DataFrame) -> None:
    missing_columns = sorted(REQUIRED_FEATURE_COLUMNS.difference(features_df.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Feature inputs are missing required columns: {missing}")

    features_df["floor_area_sqft"] = pd.to_numeric(features_df["floor_area_sqft"], errors="raise")
    if (features_df["floor_area_sqft"] <= 0).any():
        raise ValueError("floor_area_sqft must be greater than zero.")


def _usage_per_sqft(
    features_df: pd.DataFrame,
    utility_type: str,
    normalized_unit: str,
) -> pd.Series:
    if {"utility_type", "usage", "usage_unit"}.difference(features_df.columns):
        return pd.Series(0.0, index=features_df.index)

    usage = pd.to_numeric(features_df["usage"], errors="coerce").fillna(0.0)
    is_matching_utility = (
        features_df["utility_type"].astype("string").str.lower() == utility_type
    ) & (features_df["usage_unit"].astype("string").str.lower() == normalized_unit)

    return usage.where(is_matching_utility, 0.0) / features_df["floor_area_sqft"]
