"""Backend orchestration for the Streamlit dashboard.

This module keeps business logic out of the page layer by coordinating ingestion, weather joins,
feature engineering, baseline estimation, diagnostics, recommendations, emissions, and compliance.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from auditcopilot.baselines import ElectricityBaselineModel, GasBaselineModel
from auditcopilot.compliance import (
    LL97Config,
    ComplianceResult,
    evaluate_generic_compliance,
    evaluate_ll97_compliance,
)
from auditcopilot.diagnostics import DiagnosticFinding, run_diagnostics
from auditcopilot.emissions import EmissionsFactorSet, EmissionsResult, calculate_annual_emissions
from auditcopilot.features import engineer_monthly_features
from auditcopilot.ingestion import UtilityBillIngestionResult, ingest_utility_bills
from auditcopilot.recommendations import (
    Recommendation,
    generate_recommendations,
)
from auditcopilot.weather import (
    DemoMonthlyWeatherProvider,
    OpenMeteoWeatherProvider,
    build_monthly_weather_dataframe,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_UTILITY_PATH = PROJECT_ROOT / "sample_data" / "utility_bills_mvp.csv"
DEFAULT_BUILDING_PATH = PROJECT_ROOT / "sample_data" / "buildings.csv"
DEFAULT_WEATHER_PATH = PROJECT_ROOT / "sample_data" / "monthly_weather.csv"
WEATHER_CACHE_DIR = PROJECT_ROOT / ".cache" / "open_meteo"
MIN_MODEL_TRAINING_ROWS = 18


@dataclass(frozen=True)
class DashboardResult:
    source_label: str
    building_metadata: dict[str, Any]
    weather_metadata: dict[str, Any]
    validation_messages: list[dict[str, Any]]
    kpis: dict[str, Any]
    electricity_chart_df: pd.DataFrame
    gas_chart_df: pd.DataFrame
    diagnostics: list[DiagnosticFinding]
    recommendations: list[Recommendation]
    emissions: EmissionsResult | None
    compliance: ComplianceResult | None
    narrative_summary: str
    monthly_analysis_df: pd.DataFrame
    model_details: dict[str, Any]


def run_dashboard_analysis(
    uploaded_file_bytes: bytes | None,
    building_metadata: dict[str, Any],
    weather_settings: dict[str, Any],
    emissions_factor_settings: dict[str, float],
    compliance_mode: str,
    compliance_settings: dict[str, float],
) -> DashboardResult:
    """Build the full dashboard data payload from user inputs and uploaded or sample data."""
    utility_df, source_label = _load_utility_source(uploaded_file_bytes)
    ingestion_result = ingest_utility_bills(utility_df)

    validation_messages = ingestion_result.message_dicts()
    validation_messages.insert(
        0,
        {
            "level": "info",
            "code": "data_source",
            "message": f"Using {source_label}.",
            "row": None,
            "column": None,
        },
    )

    resolved_building_metadata = _resolve_building_metadata(building_metadata)
    if ingestion_result.dataframe.empty:
        return DashboardResult(
            source_label=source_label,
            building_metadata=resolved_building_metadata,
            weather_metadata={"source": "unavailable", "location_query": None, "resolved_location": None},
            validation_messages=validation_messages,
            kpis={},
            electricity_chart_df=pd.DataFrame(),
            gas_chart_df=pd.DataFrame(),
            diagnostics=[],
            recommendations=[],
            emissions=None,
            compliance=None,
            narrative_summary="No dashboard summary is available because the uploaded utility data did not pass validation.",
            monthly_analysis_df=pd.DataFrame(),
            model_details={},
        )

    weather_df, weather_metadata, weather_source_message = _load_weather_dataframe(
        ingestion_result=ingestion_result,
        source_label=source_label,
        building_metadata=resolved_building_metadata,
        weather_settings=weather_settings,
    )
    validation_messages.append(weather_source_message)
    monthly_df = _prepare_monthly_analysis_dataframe(
        ingestion_result=ingestion_result,
        weather_df=weather_df,
        building_metadata=resolved_building_metadata,
    )

    predictions_df, model_metadata = _build_predictions(monthly_df)
    diagnostics = run_diagnostics(predictions_df, model_metadata=model_metadata)
    recommendations = generate_recommendations(diagnostics)

    factor_set = EmissionsFactorSet(
        electricity_mtco2e_per_kwh=float(emissions_factor_settings["electricity_mtco2e_per_kwh"]),
        gas_mtco2e_per_therm=float(emissions_factor_settings["gas_mtco2e_per_therm"]),
    )
    emissions = calculate_annual_emissions(
        ingestion_result.dataframe[["utility_type", "usage", "usage_unit"]],
        factors=factor_set,
    )
    compliance = _evaluate_compliance(
        compliance_mode=compliance_mode,
        annual_emissions=emissions.annual_emissions_mtco2e,
        compliance_settings=compliance_settings,
    )

    return DashboardResult(
        source_label=source_label,
        building_metadata=resolved_building_metadata,
        weather_metadata=weather_metadata,
        validation_messages=validation_messages,
        kpis=_build_kpis(predictions_df, emissions, compliance, diagnostics, recommendations),
        electricity_chart_df=_chart_dataframe(predictions_df, "electricity"),
        gas_chart_df=_chart_dataframe(predictions_df, "gas"),
        diagnostics=diagnostics,
        recommendations=recommendations,
        emissions=emissions,
        compliance=compliance,
        narrative_summary=_build_narrative_summary(
            source_label=source_label,
            building_metadata=resolved_building_metadata,
            diagnostics=diagnostics,
            recommendations=recommendations,
            emissions=emissions,
            compliance=compliance,
        ),
        monthly_analysis_df=predictions_df,
        model_details=_build_model_details(model_metadata),
    )


def _load_utility_source(uploaded_file_bytes: bytes | None) -> tuple[pd.DataFrame, str]:
    if uploaded_file_bytes:
        return pd.read_csv(BytesIO(uploaded_file_bytes)), "uploaded utility bill file"
    return pd.read_csv(DEFAULT_UTILITY_PATH), "sample utility data"


def _resolve_building_metadata(user_metadata: dict[str, Any]) -> dict[str, Any]:
    default_building = pd.read_csv(DEFAULT_BUILDING_PATH).iloc[0].to_dict()
    resolved = {
        "building_name": user_metadata.get("building_name") or default_building["building_name"],
        "building_type": user_metadata.get("building_type") or default_building["building_type"],
        "address": user_metadata.get("address") or default_building["address"],
        "floor_area_sqft": float(user_metadata.get("floor_area_sqft") or default_building["floor_area_sqft"]),
        "year_built": int(user_metadata.get("year_built") or default_building["year_built"]),
    }
    return resolved


def _load_weather_dataframe(
    ingestion_result: UtilityBillIngestionResult,
    source_label: str,
    building_metadata: dict[str, Any],
    weather_settings: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    if source_label == "sample utility data":
        return build_monthly_weather_dataframe(DemoMonthlyWeatherProvider(DEFAULT_WEATHER_PATH)), {
            "source": "sample",
            "location_query": None,
            "resolved_location": None,
        }, {
            "level": "info",
            "code": "weather_source",
            "message": "Using bundled sample monthly weather data.",
            "row": None,
            "column": None,
        }

    try:
        start_date = pd.to_datetime(ingestion_result.dataframe["billing_start"]).min().strftime("%Y-%m-%d")
        end_date = pd.to_datetime(ingestion_result.dataframe["billing_end"]).max().strftime("%Y-%m-%d")
        location_query = _resolve_weather_location_query(building_metadata, weather_settings)
        provider = OpenMeteoWeatherProvider(
            query=location_query,
            start_date=start_date,
            end_date=end_date,
            cache_dir=WEATHER_CACHE_DIR,
        )
        weather_df = build_monthly_weather_dataframe(provider)
        resolved_location = None
        if provider.last_location is not None:
            resolved_location = {
                "name": provider.last_location.name,
                "latitude": provider.last_location.latitude,
                "longitude": provider.last_location.longitude,
            }
        return weather_df, {
            "source": "open_meteo",
            "location_query": location_query,
            "resolved_location": resolved_location,
        }, {
            "level": "info",
            "code": "weather_source",
            "message": "Using cached historical weather from Open-Meteo for the uploaded billing period.",
            "row": None,
            "column": None,
        }
    except Exception as exc:
        return build_monthly_weather_dataframe(DemoMonthlyWeatherProvider(DEFAULT_WEATHER_PATH)), {
            "source": "sample_fallback",
            "location_query": _resolve_weather_location_query(building_metadata, weather_settings),
            "resolved_location": None,
        }, {
            "level": "warning",
            "code": "weather_fallback",
            "message": f"Open-Meteo weather lookup failed; falling back to sample weather data. Reason: {exc}",
            "row": None,
            "column": None,
        }


def _resolve_weather_location_query(
    building_metadata: dict[str, Any],
    weather_settings: dict[str, Any],
) -> str:
    use_building_address = bool(weather_settings.get("use_building_address", False))
    if use_building_address:
        return str(building_metadata["address"])

    zip_code = str(weather_settings.get("zip_code") or "").strip()
    if zip_code:
        return zip_code

    return str(building_metadata["address"])


def _prepare_monthly_analysis_dataframe(
    ingestion_result: UtilityBillIngestionResult,
    weather_df: pd.DataFrame,
    building_metadata: dict[str, Any],
) -> pd.DataFrame:
    monthly_df = ingestion_result.dataframe.copy()
    monthly_df = monthly_df.merge(weather_df, on="billing_month", how="left")
    monthly_df["floor_area_sqft"] = float(building_metadata["floor_area_sqft"])
    monthly_df["building_name"] = building_metadata["building_name"]
    monthly_df["building_type"] = building_metadata["building_type"]
    monthly_df["address"] = building_metadata["address"]
    monthly_df["year_built"] = int(building_metadata["year_built"])
    return engineer_monthly_features(monthly_df)


def _build_predictions(monthly_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    prediction_frames: list[pd.DataFrame] = []
    model_metadata: dict[str, dict[str, Any]] = {}

    for utility_type, model in (
        ("electricity", ElectricityBaselineModel(min_training_rows=MIN_MODEL_TRAINING_ROWS)),
        ("gas", GasBaselineModel(min_training_rows=MIN_MODEL_TRAINING_ROWS)),
    ):
        utility_df = monthly_df.loc[monthly_df["utility_type"] == utility_type].copy()
        if utility_df.empty:
            continue

        prediction_result = model.fit(utility_df).predict(utility_df)
        prediction_frames.append(prediction_result.dataframe)
        model_metadata[utility_type] = prediction_result.metadata()

    if not prediction_frames:
        return pd.DataFrame(), model_metadata

    prediction_df = pd.concat(prediction_frames, ignore_index=True)
    prediction_df["actual_vs_expected_ratio"] = prediction_df["usage"] / prediction_df["predicted_usage"]
    return prediction_df.sort_values(["billing_month", "utility_type"]).reset_index(drop=True), model_metadata


def _evaluate_compliance(
    compliance_mode: str,
    annual_emissions: float,
    compliance_settings: dict[str, float],
) -> ComplianceResult | None:
    mode = compliance_mode.lower()
    if mode == "none":
        return None
    if mode == "generic":
        return evaluate_generic_compliance(
            annual_emissions_mtco2e=annual_emissions,
            emissions_limit_mtco2e=float(compliance_settings["emissions_limit_mtco2e"]),
        )
    if mode == "nyc ll97":
        return evaluate_ll97_compliance(
            annual_emissions_mtco2e=annual_emissions,
            config=LL97Config(
                emissions_limit_mtco2e=float(compliance_settings["emissions_limit_mtco2e"]),
                penalty_rate_usd_per_mtco2e=float(compliance_settings.get("penalty_rate_usd_per_mtco2e", 268.0)),
            ),
        )
    raise ValueError(f"Unsupported compliance mode: {compliance_mode}")


def _chart_dataframe(prediction_df: pd.DataFrame, utility_type: str) -> pd.DataFrame:
    utility_df = prediction_df.loc[prediction_df["utility_type"] == utility_type].copy()
    if utility_df.empty:
        return pd.DataFrame()

    chart_df = utility_df[["billing_month", "usage", "predicted_usage"]].rename(
        columns={
            "usage": "Actual",
            "predicted_usage": "Expected",
        }
    )
    chart_df["billing_month"] = pd.to_datetime(chart_df["billing_month"])
    return chart_df.set_index("billing_month")


def _build_kpis(
    prediction_df: pd.DataFrame,
    emissions: EmissionsResult,
    compliance: ComplianceResult | None,
    diagnostics: list[DiagnosticFinding],
    recommendations: list[Recommendation],
) -> dict[str, Any]:
    electricity_actual = float(
        prediction_df.loc[prediction_df["utility_type"] == "electricity", "usage"].sum()
    )
    gas_actual = float(prediction_df.loc[prediction_df["utility_type"] == "gas", "usage"].sum())
    electricity_expected = float(
        prediction_df.loc[prediction_df["utility_type"] == "electricity", "predicted_usage"].sum()
    )
    gas_expected = float(
        prediction_df.loc[prediction_df["utility_type"] == "gas", "predicted_usage"].sum()
    )

    return {
        "annual_electricity_kwh": round(electricity_actual, 1),
        "annual_gas_therms": round(gas_actual, 1),
        "electricity_gap_kwh": round(electricity_actual - electricity_expected, 1),
        "gas_gap_therms": round(gas_actual - gas_expected, 1),
        "annual_emissions_mtco2e": emissions.annual_emissions_mtco2e,
        "diagnostic_count": len(diagnostics),
        "recommendation_count": len(recommendations),
        "penalty_estimate_usd": None if compliance is None else compliance.penalty_estimate_usd,
    }


def _build_narrative_summary(
    source_label: str,
    building_metadata: dict[str, Any],
    diagnostics: list[DiagnosticFinding],
    recommendations: list[Recommendation],
    emissions: EmissionsResult,
    compliance: ComplianceResult | None,
) -> str:
    top_diagnostics = ", ".join(finding.title for finding in diagnostics[:3]) or "no major diagnostic flags"
    top_recommendation = recommendations[0].title if recommendations else "no immediate recommendation"
    compliance_text = "Compliance mode is off."
    if compliance is not None:
        if compliance.compliant:
            compliance_text = (
                f"{compliance.mode} review shows emissions below the configured limit "
                f"({compliance.annual_emissions_mtco2e:.1f} mtCO2e vs {compliance.emissions_limit_mtco2e:.1f} mtCO2e)."
            )
        else:
            compliance_text = (
                f"{compliance.mode} review shows {compliance.excess_emissions_mtco2e:.1f} mtCO2e above the limit "
                f"with an estimated penalty of ${compliance.penalty_estimate_usd:,.0f}."
            )

    return (
        f"{building_metadata['building_name']} is being analyzed using {source_label}. "
        f"Annual emissions are estimated at {emissions.annual_emissions_mtco2e:.1f} mtCO2e. "
        f"The leading diagnostic signals are {top_diagnostics}. "
        f"The highest-ranked recommendation is {top_recommendation}. "
        f"{compliance_text}"
    )


def _build_model_details(model_metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "electricity": {
            "features": ["month_index", "CDD", "HDD", "is_summer", "is_winter"],
            "target": "electric_kwh_per_sqft",
            "driver": "Cooling degree days with seasonal month effects",
            "training_mode": model_metadata.get("electricity", {}).get("training_mode"),
            "model_type": model_metadata.get("electricity", {}).get("model_type"),
            "confidence": model_metadata.get("electricity", {}).get("confidence"),
            "fallback_formula": "avg_intensity * (1 + CDD_current) / (1 + CDD_average)",
        },
        "gas": {
            "features": ["month_index", "HDD", "CDD", "heating_season", "is_winter"],
            "target": "gas_therms_per_sqft",
            "driver": "Heating degree days with heating-season effects",
            "training_mode": model_metadata.get("gas", {}).get("training_mode"),
            "model_type": model_metadata.get("gas", {}).get("model_type"),
            "confidence": model_metadata.get("gas", {}).get("confidence"),
            "fallback_formula": "avg_intensity * (1 + HDD_current) / (1 + HDD_average)",
        },
    }
