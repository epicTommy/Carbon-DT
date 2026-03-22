"""Streamlit MVP UI for the Energy Audit Copilot dashboard."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


SRC_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGO_PATH = PROJECT_ROOT / "image.png"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from auditcopilot.dashboard import run_dashboard_analysis
from auditcopilot.reporting import export_audit_report_pdf

LL97_PENALTY_RATE_USD_PER_MTCO2E = 268.0


def main() -> None:
    st.set_page_config(page_title="Energy Audit Copilot", layout="wide")
    _render_header()

    sidebar_inputs = _render_sidebar()
    result = run_dashboard_analysis(**sidebar_inputs)

    _render_validation_messages(result.validation_messages)
    _render_weather_summary(result.weather_metadata)
    _render_export_controls(result)
    _render_kpi_cards(result.kpis)
    _render_model_details(result.model_details)
    _render_charts(result.electricity_chart_df, result.gas_chart_df)
    _render_diagnostics_table(result.diagnostics)
    _render_recommendations(result.recommendations)
    _render_carbon_compliance_summary(result.emissions, result.compliance)
    _render_narrative_summary(result.narrative_summary)


def _render_sidebar() -> dict[str, object]:
    with st.sidebar:
        st.header("Inputs")
        uploaded_file = st.file_uploader("Upload utility bills CSV", type=["csv"])

        st.subheader("Building Metadata")
        building_name = st.text_input("Building name", value="North Office")
        building_type = st.text_input("Building type", value="Office")
        address = st.text_input("Address", value="123 Main St")
        floor_area_sqft = st.number_input("Floor area (sqft)", min_value=1.0, value=25000.0, step=500.0)
        year_built = st.number_input("Year built", min_value=1800, max_value=2100, value=1998, step=1)

        st.subheader("Weather Location")
        use_building_address = st.checkbox("Use building address for weather", value=False)
        zip_code = st.text_input(
            "ZIP code",
            value="10001",
            disabled=use_building_address,
            help="Used for historical weather lookup on uploaded utility files.",
        )
        if not use_building_address and zip_code and not re.fullmatch(r"\d{5}(?:-\d{4})?", zip_code):
            st.warning("ZIP code should be 5 digits or ZIP+4 format.")

        st.subheader("Emissions Factors")
        electricity_factor = st.number_input(
            "Electricity factor (mtCO2e/kWh)",
            min_value=0.0,
            value=0.000288962,
            format="%.9f",
        )
        gas_factor = st.number_input(
            "Gas factor (mtCO2e/therm)",
            min_value=0.0,
            value=0.005302,
            format="%.6f",
        )

        st.subheader("Compliance")
        compliance_mode = st.selectbox(
            "Compliance mode",
            options=["None", "Generic", "NYC LL97"],
            index=2,
        )
        emissions_limit = st.number_input(
            "Annual emissions limit (mtCO2e)",
            min_value=0.0,
            value=120.0,
            step=5.0,
        )
        if compliance_mode == "NYC LL97":
            st.caption(
                f"LL97 penalty rate is auto-applied at ${LL97_PENALTY_RATE_USD_PER_MTCO2E:,.0f}/mtCO2e."
            )

    return {
        "uploaded_file_bytes": None if uploaded_file is None else uploaded_file.getvalue(),
        "building_metadata": {
            "building_name": building_name,
            "building_type": building_type,
            "address": address,
            "floor_area_sqft": floor_area_sqft,
            "year_built": year_built,
        },
        "weather_settings": {
            "use_building_address": use_building_address,
            "zip_code": zip_code,
        },
        "emissions_factor_settings": {
            "electricity_mtco2e_per_kwh": electricity_factor,
            "gas_mtco2e_per_therm": gas_factor,
        },
        "compliance_mode": compliance_mode,
        "compliance_settings": {
            "emissions_limit_mtco2e": emissions_limit,
            "penalty_rate_usd_per_mtco2e": LL97_PENALTY_RATE_USD_PER_MTCO2E,
        },
    }


def _render_header() -> None:
    left_col, right_col = st.columns([1, 3])
    with left_col:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=220)
    with right_col:
        st.title("Energy Audit Copilot MVP")
        st.caption("Interactive utility, diagnostics, recommendations, and compliance dashboard.")


def _render_validation_messages(messages: list[dict[str, object]]) -> None:
    st.subheader("Validation Messages")
    if not messages:
        st.success("No validation issues were detected.")
        return

    messages_df = pd.DataFrame(messages)
    st.dataframe(messages_df, width="stretch", hide_index=True)


def _render_export_controls(result) -> None:
    st.subheader("Export")
    pdf_bytes = export_audit_report_pdf(result)
    file_stem = result.building_metadata["building_name"].lower().replace(" ", "_")
    st.download_button(
        label="Download Audit Report PDF",
        data=pdf_bytes,
        file_name=f"{file_stem}_audit_report.pdf",
        mime="application/pdf",
        width="stretch",
    )


def _render_weather_summary(weather_metadata: dict[str, object]) -> None:
    st.subheader("Weather Source")
    source = weather_metadata.get("source")
    location_query = weather_metadata.get("location_query")
    resolved_location = weather_metadata.get("resolved_location")

    if source == "sample":
        st.info("Using bundled sample monthly weather data.")
        return

    if source == "sample_fallback":
        st.warning(
            f"Using sample weather fallback. Requested weather query: {location_query or 'N/A'}"
        )
        return

    if source == "open_meteo":
        if isinstance(resolved_location, dict):
            st.success(
                f"Using Open-Meteo historical weather for {resolved_location.get('name')} "
                f"({resolved_location.get('latitude')}, {resolved_location.get('longitude')})"
            )
        else:
            st.success(f"Using Open-Meteo historical weather for query: {location_query}")
        return

    st.info("Weather source information is unavailable.")


def _render_kpi_cards(kpis: dict[str, object]) -> None:
    st.subheader("KPIs")
    if not kpis:
        st.info("KPI cards will appear after valid utility data is loaded.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Annual Electricity", f"{kpis['annual_electricity_kwh']:,.0f} kWh", f"{kpis['electricity_gap_kwh']:,.0f} vs expected")
    col2.metric("Annual Gas", f"{kpis['annual_gas_therms']:,.0f} therms", f"{kpis['gas_gap_therms']:,.0f} vs expected")
    col3.metric("Annual Emissions", f"{kpis['annual_emissions_mtco2e']:,.1f} mtCO2e", f"{kpis['diagnostic_count']} diagnostics")
    penalty_value = "N/A" if kpis["penalty_estimate_usd"] is None else f"${kpis['penalty_estimate_usd']:,.0f}"
    col4.metric("Compliance / Actions", penalty_value, f"{kpis['recommendation_count']} recommendations")


def _render_model_details(model_details: dict[str, object]) -> None:
    st.subheader("Model Details")
    if not model_details:
        st.info("Model details are unavailable until valid utility data is loaded.")
        return

    left_col, right_col = st.columns(2)
    for column, utility_key, label in (
        (left_col, "electricity", "Electricity Expected Usage"),
        (right_col, "gas", "Gas Expected Usage"),
    ):
        details = model_details.get(utility_key, {})
        with column:
            st.markdown(f"**{label}**")
            st.markdown(f"- Target: `{details.get('target')}`")
            st.markdown(f"- Features: {', '.join(details.get('features', []))}")
            st.markdown(f"- Main weather driver: {details.get('driver')}")
            st.markdown(f"- Model type: {details.get('model_type')}")
            st.markdown(f"- Training mode: {details.get('training_mode')}")
            st.markdown(f"- Confidence: {details.get('confidence')}")
            st.markdown(f"- Fallback formula: `{details.get('fallback_formula')}`")


def _render_charts(electricity_chart_df: pd.DataFrame, gas_chart_df: pd.DataFrame) -> None:
    st.subheader("Actual Vs Expected")
    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("**Electricity**")
        if electricity_chart_df.empty:
            st.info("No electricity records available.")
        else:
            st.line_chart(electricity_chart_df, width="stretch")

    with right_col:
        st.markdown("**Gas**")
        if gas_chart_df.empty:
            st.info("No gas records available.")
        else:
            st.line_chart(gas_chart_df, width="stretch")


def _render_diagnostics_table(diagnostics: list[object]) -> None:
    st.subheader("Diagnostics")
    if not diagnostics:
        st.info("No diagnostics were triggered for the current dataset.")
        return

    diagnostics_df = pd.DataFrame([finding.to_dict() for finding in diagnostics])
    st.dataframe(diagnostics_df, width="stretch", hide_index=True)


def _render_recommendations(recommendations: list[object]) -> None:
    st.subheader("Recommendations")
    if not recommendations:
        st.info("No recommendations are available for the current diagnostics.")
        return

    for recommendation in recommendations:
        with st.container(border=True):
            st.markdown(f"**{recommendation.title}**")
            st.caption(
                f"{recommendation.category.title()} | Difficulty: {recommendation.implementation_difficulty.title()} | Confidence: {recommendation.confidence.title()} | Score: {recommendation.ranking_score:.2f}"
            )
            st.write(recommendation.why_it_matters)
            metric_col1, metric_col2 = st.columns(2)
            metric_col1.markdown(f"**Estimated Savings:** {recommendation.estimated_savings_range_usd}")
            metric_col2.markdown(
                f"**Carbon Reduction:** {recommendation.estimated_carbon_reduction_range}"
            )
            st.markdown(f"**Payback Note:** {recommendation.payback_note}")
            with st.expander("Audit trace"):
                for trace_line in recommendation.audit_trace:
                    st.markdown(f"- {trace_line}")


def _render_carbon_compliance_summary(emissions, compliance) -> None:
    st.subheader("Carbon And Compliance Summary")
    left_col, right_col = st.columns(2)

    with left_col:
        if emissions is None:
            st.info("Emissions summary is unavailable.")
        else:
            st.markdown(
                f"""
                **Electricity Emissions:** {emissions.electricity_emissions_mtco2e:,.2f} mtCO2e  
                **Gas Emissions:** {emissions.gas_emissions_mtco2e:,.2f} mtCO2e  
                **Annual Total:** {emissions.annual_emissions_mtco2e:,.2f} mtCO2e
                """
            )

    with right_col:
        if compliance is None:
            st.info("Compliance mode is disabled.")
        else:
            st.markdown(
                f"""
                **Mode:** {compliance.mode}  
                **Emissions Limit:** {compliance.emissions_limit_mtco2e:,.2f} mtCO2e  
                **Excess Emissions:** {compliance.excess_emissions_mtco2e:,.2f} mtCO2e  
                **Penalty Estimate:** ${compliance.penalty_estimate_usd:,.2f}
                """
            )


def _render_narrative_summary(narrative_summary: str) -> None:
    st.subheader("Narrative Summary")
    st.write(narrative_summary)


if __name__ == "__main__":
    main()
