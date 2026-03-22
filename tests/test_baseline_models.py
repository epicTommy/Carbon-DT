import pandas as pd

from auditcopilot.baselines import ElectricityBaselineModel, GasBaselineModel


def test_electricity_baseline_falls_back_to_heuristic_when_history_is_small() -> None:
    training_df = pd.DataFrame(
        [
            {
                "billing_month": "2025-01",
                "floor_area_sqft": 10000,
                "utility_type": "electricity",
                "month_index": 1,
                "hdd": 30,
                "cdd": 0,
                "is_summer": False,
                "is_winter": True,
                "electric_kwh_per_sqft": 1.2,
            },
            {
                "billing_month": "2025-02",
                "floor_area_sqft": 10000,
                "utility_type": "electricity",
                "month_index": 2,
                "hdd": 25,
                "cdd": 0,
                "is_summer": False,
                "is_winter": True,
                "electric_kwh_per_sqft": 1.1,
            },
        ]
    )
    prediction_df = pd.DataFrame(
        [
            {
                "billing_month": "2025-07",
                "floor_area_sqft": 10000,
                "utility_type": "electricity",
                "month_index": 7,
                "hdd": 0,
                "cdd": 18,
                "is_summer": True,
                "is_winter": False,
            }
        ]
    )

    result = ElectricityBaselineModel(min_training_rows=6).fit(training_df).predict(prediction_df)

    assert result.model_type == "weather_normalized_heuristic"
    assert result.training_mode == "heuristic_fallback"
    assert 0.0 < result.confidence <= 0.6
    assert "predicted_electric_kwh_per_sqft" in result.dataframe.columns
    assert result.dataframe.iloc[0]["predicted_usage"] > 0.0


def test_gas_baseline_falls_back_to_heuristic_when_history_is_small() -> None:
    training_df = pd.DataFrame(
        [
            {
                "billing_month": "2025-01",
                "floor_area_sqft": 20000,
                "utility_type": "gas",
                "month_index": 1,
                "hdd": 40,
                "cdd": 0,
                "heating_season": True,
                "is_winter": True,
                "gas_therms_per_sqft": 0.08,
            },
            {
                "billing_month": "2025-02",
                "floor_area_sqft": 20000,
                "utility_type": "gas",
                "month_index": 2,
                "hdd": 32,
                "cdd": 0,
                "heating_season": True,
                "is_winter": True,
                "gas_therms_per_sqft": 0.07,
            },
        ]
    )
    prediction_df = pd.DataFrame(
        [
            {
                "billing_month": "2025-12",
                "floor_area_sqft": 20000,
                "utility_type": "gas",
                "month_index": 12,
                "hdd": 45,
                "cdd": 0,
                "heating_season": True,
                "is_winter": True,
            }
        ]
    )

    result = GasBaselineModel(min_training_rows=6).fit(training_df).predict(prediction_df)

    assert result.model_type == "weather_normalized_heuristic"
    assert result.training_mode == "heuristic_fallback"
    assert 0.0 < result.confidence <= 0.6
    assert "predicted_gas_therms_per_sqft" in result.dataframe.columns
    assert result.dataframe.iloc[0]["predicted_usage"] > 0.0
