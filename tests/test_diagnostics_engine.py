import pandas as pd

from auditcopilot.diagnostics import run_diagnostics


def test_diagnostics_detect_consistently_high_electricity_and_baseload() -> None:
    monthly_df = pd.DataFrame(
        [
            {"billing_month": "2025-01", "utility_type": "electricity", "usage": 1300, "predicted_usage": 1000, "is_summer": False, "is_winter": True},
            {"billing_month": "2025-02", "utility_type": "electricity", "usage": 1280, "predicted_usage": 1000, "is_summer": False, "is_winter": True},
            {"billing_month": "2025-03", "utility_type": "electricity", "usage": 1250, "predicted_usage": 1000, "is_summer": False, "is_winter": False},
            {"billing_month": "2025-04", "utility_type": "electricity", "usage": 1220, "predicted_usage": 1000, "is_summer": False, "is_winter": False},
            {"billing_month": "2025-05", "utility_type": "electricity", "usage": 1240, "predicted_usage": 1000, "is_summer": False, "is_winter": False},
        ]
    )

    findings = run_diagnostics(monthly_df)
    finding_codes = {finding.code for finding in findings}

    assert "high_electricity_relative_to_expected" in finding_codes
    assert "elevated_baseload" in finding_codes


def test_diagnostics_detect_summer_electric_spike() -> None:
    monthly_df = pd.DataFrame(
        [
            {"billing_month": "2025-01", "utility_type": "electricity", "usage": 980, "predicted_usage": 1000, "is_summer": False, "is_winter": True},
            {"billing_month": "2025-04", "utility_type": "electricity", "usage": 1005, "predicted_usage": 1000, "is_summer": False, "is_winter": False},
            {"billing_month": "2025-07", "utility_type": "electricity", "usage": 1500, "predicted_usage": 1000, "is_summer": True, "is_winter": False},
            {"billing_month": "2025-08", "utility_type": "electricity", "usage": 1480, "predicted_usage": 1000, "is_summer": True, "is_winter": False},
            {"billing_month": "2025-10", "utility_type": "electricity", "usage": 990, "predicted_usage": 1000, "is_summer": False, "is_winter": False},
        ]
    )

    findings = run_diagnostics(monthly_df)
    matching = [finding for finding in findings if finding.code == "summer_electric_spike"]

    assert len(matching) == 1
    assert matching[0].severity in {"medium", "high"}


def test_diagnostics_detect_negative_trend_over_time() -> None:
    monthly_df = pd.DataFrame(
        [
            {"billing_month": "2025-01", "utility_type": "electricity", "usage": 980, "predicted_usage": 1000},
            {"billing_month": "2025-02", "utility_type": "electricity", "usage": 1020, "predicted_usage": 1000},
            {"billing_month": "2025-03", "utility_type": "electricity", "usage": 1100, "predicted_usage": 1000},
            {"billing_month": "2025-04", "utility_type": "electricity", "usage": 1175, "predicted_usage": 1000},
            {"billing_month": "2025-05", "utility_type": "electricity", "usage": 1240, "predicted_usage": 1000},
            {"billing_month": "2025-06", "utility_type": "electricity", "usage": 1310, "predicted_usage": 1000},
        ]
    )

    findings = run_diagnostics(monthly_df)
    matching = [finding for finding in findings if finding.code == "negative_trend_over_time"]

    assert len(matching) == 1
    assert matching[0].confidence in {"medium", "high"}


def test_diagnostics_detect_low_confidence_context() -> None:
    monthly_df = pd.DataFrame(
        [
            {"billing_month": "2025-01", "utility_type": "gas", "usage": 500, "predicted_usage": 480},
            {"billing_month": "2025-02", "utility_type": "gas", "usage": 530, "predicted_usage": 500},
            {"billing_month": "2025-03", "utility_type": "gas", "usage": 400, "predicted_usage": 390},
        ]
    )
    model_metadata = {
        "gas": {
            "model_type": "weather_normalized_heuristic",
            "training_mode": "heuristic_fallback",
            "confidence": 0.32,
        }
    }

    findings = run_diagnostics(monthly_df, model_metadata=model_metadata)
    matching = [finding for finding in findings if finding.code == "poor_data_quality_or_low_confidence"]

    assert len(matching) == 1
    assert matching[0].confidence == "high"
