"""Utility bill CSV ingestion, validation, normalization, and monthly expansion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "billing_start",
    "billing_end",
    "utility_type",
    "usage",
    "usage_unit",
    "cost",
}

UTILITY_UNIT_NORMALIZERS: dict[str, tuple[str, dict[str, float]]] = {
    "electricity": (
        "kwh",
        {
            "kwh": 1.0,
            "wh": 0.001,
            "mwh": 1000.0,
        },
    ),
    "gas": (
        "therms",
        {
            "therm": 1.0,
            "therms": 1.0,
            "btu": 0.00001,
            "kbtu": 0.01,
            "mmbtu": 10.0,
            "ccf": 1.037,
            "mcf": 10.37,
        },
    ),
}


@dataclass(frozen=True)
class ValidationMessage:
    level: str
    code: str
    message: str
    row: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class UtilityBillIngestionResult:
    dataframe: pd.DataFrame
    messages: list[ValidationMessage]

    def message_dicts(self) -> list[dict[str, Any]]:
        """Return validation messages as plain dictionaries."""
        return [asdict(message) for message in self.messages]


def ingest_utility_bills(source: str | Path | pd.DataFrame) -> UtilityBillIngestionResult:
    """Read, validate, normalize, and monthly-expand utility bill records."""
    df = _read_source(source)
    messages = _validate_required_columns(df)
    if any(message.level == "error" for message in messages):
        return UtilityBillIngestionResult(dataframe=pd.DataFrame(), messages=messages)

    normalized_df, validation_messages = _normalize_and_validate_rows(df)
    messages.extend(validation_messages)
    if any(message.level == "error" for message in messages):
        return UtilityBillIngestionResult(dataframe=pd.DataFrame(), messages=messages)

    expanded_df = _expand_to_monthly_records(normalized_df)
    return UtilityBillIngestionResult(
        dataframe=expanded_df.reset_index(drop=True),
        messages=messages,
    )


def _read_source(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    return pd.read_csv(source)


def _validate_required_columns(df: pd.DataFrame) -> list[ValidationMessage]:
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    return [
        ValidationMessage(
            level="error",
            code="missing_required_column",
            message=f"Missing required column: {column}",
            column=column,
        )
        for column in missing_columns
    ]


def _normalize_and_validate_rows(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[ValidationMessage]]:
    working_df = df.copy()
    messages: list[ValidationMessage] = []

    working_df["billing_start"] = pd.to_datetime(
        working_df["billing_start"], errors="coerce"
    )
    working_df["billing_end"] = pd.to_datetime(working_df["billing_end"], errors="coerce")
    working_df["usage"] = pd.to_numeric(working_df["usage"], errors="coerce")
    working_df["cost"] = pd.to_numeric(working_df["cost"], errors="coerce")
    working_df["utility_type"] = working_df["utility_type"].astype("string").str.strip().str.lower()
    working_df["usage_unit"] = working_df["usage_unit"].astype("string").str.strip().str.lower()

    for row_index, row in working_df.iterrows():
        display_row = int(row_index) + 2

        for column in ("billing_start", "billing_end", "usage", "cost"):
            if pd.isna(row[column]):
                messages.append(
                    ValidationMessage(
                        level="error",
                        code="invalid_value",
                        message=f"Invalid value for {column}",
                        row=display_row,
                        column=column,
                    )
                )

        if pd.notna(row["billing_start"]) and pd.notna(row["billing_end"]):
            if row["billing_end"] < row["billing_start"]:
                messages.append(
                    ValidationMessage(
                        level="error",
                        code="invalid_billing_period",
                        message="billing_end must be on or after billing_start",
                        row=display_row,
                        column="billing_end",
                    )
                )

        utility_type = row["utility_type"]
        usage_unit = row["usage_unit"]

        if utility_type not in UTILITY_UNIT_NORMALIZERS:
            messages.append(
                ValidationMessage(
                    level="error",
                    code="unsupported_utility_type",
                    message=f"Unsupported utility_type: {utility_type}",
                    row=display_row,
                    column="utility_type",
                )
            )
            continue

        normalized_unit, conversion_factors = UTILITY_UNIT_NORMALIZERS[utility_type]
        if usage_unit not in conversion_factors:
            messages.append(
                ValidationMessage(
                    level="error",
                    code="unsupported_usage_unit",
                    message=f"Unsupported usage_unit '{usage_unit}' for utility_type '{utility_type}'",
                    row=display_row,
                    column="usage_unit",
                )
            )
            continue

        if pd.notna(row["usage"]):
            working_df.at[row_index, "usage"] = float(row["usage"]) * conversion_factors[usage_unit]
            working_df.at[row_index, "usage_unit"] = normalized_unit

    return working_df, messages


def _expand_to_monthly_records(df: pd.DataFrame) -> pd.DataFrame:
    monthly_records: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        month_ranges = _split_period_across_months(row["billing_start"], row["billing_end"])
        total_days = sum(record["days_in_period"] for record in month_ranges)

        for month_record in month_ranges:
            share = month_record["days_in_period"] / total_days if total_days else 0.0
            monthly_records.append(
                {
                    "billing_start": month_record["billing_start"],
                    "billing_end": month_record["billing_end"],
                    "billing_month": month_record["billing_month"],
                    "utility_type": row["utility_type"],
                    "usage": float(row["usage"]) * share,
                    "usage_unit": row["usage_unit"],
                    "cost": float(row["cost"]) * share,
                }
            )

    expanded_df = pd.DataFrame(monthly_records)
    numeric_columns = ["usage", "cost"]
    expanded_df[numeric_columns] = expanded_df[numeric_columns].round(6)
    return expanded_df


def _split_period_across_months(
    billing_start: pd.Timestamp,
    billing_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    current_start = billing_start.normalize()
    final_end = billing_end.normalize()

    while current_start <= final_end:
        month_end = min(current_start + pd.offsets.MonthEnd(0), final_end)
        days_in_period = (month_end - current_start).days + 1
        ranges.append(
            {
                "billing_start": current_start,
                "billing_end": month_end,
                "billing_month": current_start.strftime("%Y-%m"),
                "days_in_period": days_in_period,
            }
        )
        current_start = month_end + pd.Timedelta(days=1)

    return ranges
