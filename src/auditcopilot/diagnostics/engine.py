"""Rule-based diagnostics engine for expected-vs-actual utility usage.

Assumptions:
- Inputs are monthly records with actual and predicted usage aligned to the same billing month.
- Electricity and gas are diagnosed independently where the requested signals are utility-specific.
- Diagnostics are heuristic signals for an MVP triage workflow, not a substitute for engineering review.

Limitations:
- Thresholds are intentionally simple and may need calibration for a specific portfolio.
- Trend detection uses a basic linear slope on normalized usage ratios.
- Data-quality diagnostics rely on model confidence and missingness, not on a full QA framework.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from auditcopilot.diagnostics.rubrics import confidence_from_score, severity_from_score


@dataclass(frozen=True)
class DiagnosticFinding:
    code: str
    title: str
    description: str
    evidence: dict[str, Any]
    severity: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_diagnostics(
    monthly_df: pd.DataFrame,
    model_metadata: dict[str, dict[str, Any]] | None = None,
) -> list[DiagnosticFinding]:
    """Return structured diagnostics from monthly actual-vs-expected utility data."""
    prepared_df = _prepare_dataframe(monthly_df)
    metadata = model_metadata or {}

    findings: list[DiagnosticFinding] = []

    electricity_df = _utility_subset(prepared_df, "electricity")
    gas_df = _utility_subset(prepared_df, "gas")

    if not electricity_df.empty:
        finding = _detect_consistently_high_usage(
            electricity_df,
            utility_type="electricity",
            code="high_electricity_relative_to_expected",
            title="Consistently High Electricity Relative To Expected",
        )
        if finding:
            findings.append(finding)

        finding = _detect_seasonal_spike(
            electricity_df,
            season_column="is_summer",
            code="summer_electric_spike",
            title="Summer Electric Spike",
            description_template=(
                "Electricity usage rises sharply during summer months compared with the expected "
                "baseline and shoulder-season behavior."
            ),
        )
        if finding:
            findings.append(finding)

        finding = _detect_elevated_baseload(electricity_df)
        if finding:
            findings.append(finding)

    if not gas_df.empty:
        finding = _detect_consistently_high_usage(
            gas_df,
            utility_type="gas",
            code="high_gas_relative_to_expected",
            title="Consistently High Gas Relative To Expected",
        )
        if finding:
            findings.append(finding)

        finding = _detect_seasonal_spike(
            gas_df,
            season_column="is_winter",
            code="winter_gas_spike",
            title="Winter Gas Spike",
            description_template=(
                "Gas usage rises sharply during winter months compared with the expected baseline "
                "and non-heating-season behavior."
            ),
        )
        if finding:
            findings.append(finding)

    finding = _detect_negative_trend(prepared_df)
    if finding:
        findings.append(finding)

    finding = _detect_low_confidence_or_poor_quality(prepared_df, metadata)
    if finding:
        findings.append(finding)

    return findings


def _prepare_dataframe(monthly_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"billing_month", "utility_type", "usage", "predicted_usage"}
    missing_columns = sorted(required_columns.difference(monthly_df.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Diagnostics input is missing required columns: {missing}")

    working_df = monthly_df.copy()
    working_df["billing_month"] = pd.to_datetime(working_df["billing_month"], format="%Y-%m")
    for column in ["usage", "predicted_usage"]:
        working_df[column] = pd.to_numeric(working_df[column], errors="coerce")

    working_df["utility_type"] = working_df["utility_type"].astype("string").str.lower()
    working_df["usage_ratio"] = np.where(
        working_df["predicted_usage"] > 0,
        working_df["usage"] / working_df["predicted_usage"],
        np.nan,
    )
    working_df["usage_gap"] = working_df["usage"] - working_df["predicted_usage"]
    working_df["month_index"] = working_df["billing_month"].dt.month

    if "is_summer" not in working_df.columns:
        working_df["is_summer"] = working_df["month_index"].isin([6, 7, 8])
    if "is_winter" not in working_df.columns:
        working_df["is_winter"] = working_df["month_index"].isin([12, 1, 2])

    return working_df.sort_values(["billing_month", "utility_type"]).reset_index(drop=True)


def _utility_subset(prepared_df: pd.DataFrame, utility_type: str) -> pd.DataFrame:
    return prepared_df.loc[prepared_df["utility_type"] == utility_type].copy()


def _detect_consistently_high_usage(
    utility_df: pd.DataFrame,
    utility_type: str,
    code: str,
    title: str,
) -> DiagnosticFinding | None:
    valid_df = utility_df.dropna(subset=["usage_ratio"])
    if len(valid_df) < 3:
        return None

    over_expected_mask = valid_df["usage_ratio"] >= 1.1
    over_expected_share = float(over_expected_mask.mean())
    mean_ratio = float(valid_df["usage_ratio"].mean())

    if over_expected_share < 0.7 or mean_ratio < 1.15:
        return None

    impact_score = min((mean_ratio - 1.0) / 0.35, 1.0)
    confidence_score = min(((over_expected_share - 0.7) / 0.3) + 0.55, 1.0)

    return DiagnosticFinding(
        code=code,
        title=title,
        description=(
            f"{utility_type.capitalize()} usage is above the expected baseline in most months, "
            "suggesting persistent excess consumption."
        ),
        evidence={
            "months_evaluated": int(len(valid_df)),
            "share_months_above_110pct_expected": round(over_expected_share, 3),
            "mean_usage_ratio": round(mean_ratio, 3),
        },
        severity=severity_from_score(impact_score),
        confidence=confidence_from_score(confidence_score),
    )


def _detect_seasonal_spike(
    utility_df: pd.DataFrame,
    season_column: str,
    code: str,
    title: str,
    description_template: str,
) -> DiagnosticFinding | None:
    valid_df = utility_df.dropna(subset=["usage_ratio"])
    if len(valid_df) < 4 or season_column not in valid_df.columns:
        return None

    seasonal_df = valid_df.loc[valid_df[season_column].astype(bool)]
    off_season_df = valid_df.loc[~valid_df[season_column].astype(bool)]
    if len(seasonal_df) < 2 or len(off_season_df) < 2:
        return None

    seasonal_ratio = float(seasonal_df["usage_ratio"].mean())
    off_season_ratio = float(off_season_df["usage_ratio"].mean())
    ratio_delta = seasonal_ratio - off_season_ratio

    if seasonal_ratio < 1.2 or ratio_delta < 0.15:
        return None

    impact_score = min((seasonal_ratio - 1.0) / 0.4, 1.0)
    confidence_score = min((ratio_delta / 0.35) * 0.7 + 0.2, 1.0)

    return DiagnosticFinding(
        code=code,
        title=title,
        description=description_template,
        evidence={
            "seasonal_mean_usage_ratio": round(seasonal_ratio, 3),
            "off_season_mean_usage_ratio": round(off_season_ratio, 3),
            "ratio_delta": round(ratio_delta, 3),
            "seasonal_month_count": int(len(seasonal_df)),
        },
        severity=severity_from_score(impact_score),
        confidence=confidence_from_score(confidence_score),
    )


def _detect_elevated_baseload(electricity_df: pd.DataFrame) -> DiagnosticFinding | None:
    valid_df = electricity_df.dropna(subset=["usage_ratio"])
    if len(valid_df) < 4:
        return None

    baseload_df = valid_df.loc[~valid_df["is_summer"].astype(bool)]
    if len(baseload_df) < 3:
        return None

    mean_ratio = float(baseload_df["usage_ratio"].mean())
    if mean_ratio < 1.15:
        return None

    impact_score = min((mean_ratio - 1.0) / 0.3, 1.0)
    confidence_score = min((len(baseload_df) / 6) * 0.6 + 0.25, 1.0)

    return DiagnosticFinding(
        code="elevated_baseload",
        title="Elevated Baseload",
        description=(
            "Electricity use remains elevated outside summer months, which can indicate excessive "
            "always-on load, controls drift, or scheduling issues."
        ),
        evidence={
            "non_summer_month_count": int(len(baseload_df)),
            "non_summer_mean_usage_ratio": round(mean_ratio, 3),
        },
        severity=severity_from_score(impact_score),
        confidence=confidence_from_score(confidence_score),
    )


def _detect_negative_trend(prepared_df: pd.DataFrame) -> DiagnosticFinding | None:
    valid_df = prepared_df.dropna(subset=["usage_ratio"]).copy()
    if len(valid_df) < 6:
        return None

    valid_df["time_index"] = range(len(valid_df))
    slope = np.polyfit(valid_df["time_index"], valid_df["usage_ratio"], 1)[0]
    first_half = valid_df.iloc[: max(len(valid_df) // 2, 1)]["usage_ratio"].mean()
    second_half = valid_df.iloc[len(valid_df) // 2 :]["usage_ratio"].mean()
    ratio_delta = float(second_half - first_half)

    if slope < 0.03 and ratio_delta < 0.12:
        return None

    impact_score = min(max(ratio_delta, 0.0) / 0.35, 1.0)
    confidence_score = min(max(slope, 0.0) / 0.08, 1.0)

    return DiagnosticFinding(
        code="negative_trend_over_time",
        title="Negative Trend Over Time",
        description=(
            "Actual usage relative to expected is worsening over time, which may indicate gradual "
            "performance degradation or operational drift."
        ),
        evidence={
            "trend_slope_ratio_per_month": round(float(slope), 4),
            "early_period_mean_ratio": round(float(first_half), 3),
            "late_period_mean_ratio": round(float(second_half), 3),
            "ratio_delta": round(ratio_delta, 3),
        },
        severity=severity_from_score(impact_score),
        confidence=confidence_from_score(confidence_score),
    )


def _detect_low_confidence_or_poor_quality(
    prepared_df: pd.DataFrame,
    model_metadata: dict[str, dict[str, Any]],
) -> DiagnosticFinding | None:
    missing_predicted_share = float(prepared_df["predicted_usage"].isna().mean())
    data_points = int(len(prepared_df))
    model_confidences = [
        float(metadata.get("confidence", 0.0))
        for metadata in model_metadata.values()
        if metadata.get("confidence") is not None
    ]
    min_model_confidence = min(model_confidences) if model_confidences else None
    uses_heuristic_model = any(
        metadata.get("training_mode") == "heuristic_fallback"
        for metadata in model_metadata.values()
    )

    triggers = [
        missing_predicted_share > 0.1,
        data_points < 6,
        min_model_confidence is not None and min_model_confidence < 0.5,
        uses_heuristic_model,
    ]
    if not any(triggers):
        return None

    impact_score = min(max(missing_predicted_share, 0.2 if uses_heuristic_model else 0.0) + 0.2, 1.0)
    confidence_score = 0.9

    return DiagnosticFinding(
        code="poor_data_quality_or_low_confidence",
        title="Poor Data Quality Or Low Confidence",
        description=(
            "The diagnostic context is limited by sparse history, missing predictions, or low model "
            "confidence. Findings should be treated as directional rather than definitive."
        ),
        evidence={
            "row_count": data_points,
            "missing_predicted_share": round(missing_predicted_share, 3),
            "minimum_model_confidence": None if min_model_confidence is None else round(min_model_confidence, 3),
            "uses_heuristic_model": uses_heuristic_model,
        },
        severity=severity_from_score(impact_score),
        confidence=confidence_from_score(confidence_score),
    )
