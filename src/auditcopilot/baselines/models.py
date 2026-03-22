"""Explainable monthly baseline models with heuristic fallback behavior.

Assumptions:
- Inputs are already monthly and contain weather and building-area context.
- Electricity and gas are modeled separately because their dominant weather drivers differ.
- Baselines are intended for MVP explainability, not for high-stakes forecasting or M&V.

Limitations:
- The sklearn path uses a simple linear model for interpretability rather than maximum accuracy.
- The heuristic fallback is weather-normalized but intentionally conservative when history is sparse.
- Confidence is a lightweight score derived from training mode and available history, not a calibrated
  probability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


MIN_TRAINING_ROWS = 6


@dataclass(frozen=True)
class BaselinePredictionResult:
    """Predictions plus model metadata for downstream audit workflows."""

    dataframe: pd.DataFrame
    model_type: str
    training_mode: str
    confidence: float

    def metadata(self) -> dict[str, Any]:
        return {
            "model_type": self.model_type,
            "training_mode": self.training_mode,
            "confidence": self.confidence,
        }


class _BaseUsageModel:
    """Shared baseline-model behavior for separate utility-specific estimators."""

    utility_type: str
    feature_columns: list[str]
    weather_column: str
    intensity_column: str

    def __init__(self, min_training_rows: int = MIN_TRAINING_ROWS) -> None:
        self.min_training_rows = min_training_rows
        self._pipeline = None
        self._fitted = False
        self._model_type = "weather_normalized_heuristic"
        self._training_mode = "heuristic_fallback"
        self._confidence = 0.25
        self._heuristic_stats: dict[str, float] = {}

    def fit(self, training_df: pd.DataFrame) -> "_BaseUsageModel":
        """Fit an explainable baseline or store heuristic statistics when history is sparse."""
        utility_df = self._prepare_dataframe(training_df)

        if len(utility_df) < self.min_training_rows:
            self._fit_heuristic(utility_df)
            return self

        pipeline = _build_linear_pipeline(self.feature_columns)
        if pipeline is None:
            self._fit_heuristic(utility_df)
            return self

        features = utility_df[self.feature_columns]
        target = utility_df[self.intensity_column]
        pipeline.fit(features, target)

        self._pipeline = pipeline
        self._fitted = True
        self._model_type = "linear_regression"
        self._training_mode = "sklearn_pipeline"
        self._confidence = min(0.9, 0.45 + (0.03 * len(utility_df)))
        return self

    def predict(self, prediction_df: pd.DataFrame) -> BaselinePredictionResult:
        """Predict expected utility intensity and usage for monthly records.

        The model expects monthly rows with:
        - `billing_month`
        - `floor_area_sqft`
        - `month_index`
        - seasonal flags used by the chosen utility type
        - `hdd` and/or `cdd` when weather normalization is desired
        """
        if not self._fitted:
            raise ValueError("The baseline model must be fitted before prediction.")

        prepared_df = self._prepare_dataframe(prediction_df, require_target=False)

        if self._training_mode == "sklearn_pipeline":
            predicted_intensity = self._pipeline.predict(prepared_df[self.feature_columns])
        else:
            predicted_intensity = self._predict_with_heuristic(prepared_df)

        predicted_intensity_series = pd.Series(predicted_intensity, index=prepared_df.index).clip(
            lower=0.0
        )
        prediction_column = self._prediction_column_name()

        result_df = prepared_df.copy()
        result_df[prediction_column] = predicted_intensity_series
        result_df["predicted_usage"] = predicted_intensity_series * result_df["floor_area_sqft"]

        return BaselinePredictionResult(
            dataframe=result_df,
            model_type=self._model_type,
            training_mode=self._training_mode,
            confidence=round(self._confidence, 3),
        )

    def _fit_heuristic(self, utility_df: pd.DataFrame) -> None:
        weather_values = utility_df[self.weather_column].fillna(0.0)
        avg_weather = max(weather_values.mean(), 0.0)
        avg_intensity = max(utility_df[self.intensity_column].mean(), 0.0)

        self._heuristic_stats = {
            "avg_weather": avg_weather,
            "avg_intensity": avg_intensity,
        }
        self._model_type = "weather_normalized_heuristic"
        self._training_mode = "heuristic_fallback"
        self._confidence = min(0.6, 0.2 + (0.04 * len(utility_df)))
        self._fitted = True

    def _predict_with_heuristic(self, prediction_df: pd.DataFrame) -> pd.Series:
        weather_values = prediction_df[self.weather_column].fillna(0.0)
        avg_weather = self._heuristic_stats["avg_weather"]
        avg_intensity = self._heuristic_stats["avg_intensity"]
        weather_ratio = (1.0 + weather_values) / (1.0 + avg_weather)
        return avg_intensity * weather_ratio

    def _prepare_dataframe(
        self,
        input_df: pd.DataFrame,
        require_target: bool = True,
    ) -> pd.DataFrame:
        working_df = input_df.copy()

        if "utility_type" in working_df.columns:
            utility_mask = (
                working_df["utility_type"].astype("string").str.lower() == self.utility_type
            )
            working_df = working_df.loc[utility_mask].copy()

        if working_df.empty:
            raise ValueError(f"No rows available for utility_type '{self.utility_type}'.")

        required_columns = {"billing_month", "floor_area_sqft", *self.feature_columns}
        if require_target:
            required_columns.add(self.intensity_column)

        missing_columns = sorted(required_columns.difference(working_df.columns))
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"Missing required columns for {self.utility_type} model: {missing}")

        working_df["billing_month"] = pd.to_datetime(working_df["billing_month"], format="%Y-%m")
        numeric_columns = {"floor_area_sqft", *self.feature_columns}
        if require_target:
            numeric_columns.add(self.intensity_column)

        for column in numeric_columns:
            working_df[column] = pd.to_numeric(working_df[column], errors="raise")

        if (working_df["floor_area_sqft"] <= 0).any():
            raise ValueError("floor_area_sqft must be greater than zero.")

        return working_df.sort_values("billing_month").reset_index(drop=True)

    def _prediction_column_name(self) -> str:
        return f"predicted_{self.intensity_column}"


class ElectricityBaselineModel(_BaseUsageModel):
    """Monthly electricity baseline using cooling-sensitive explainable features.

    Assumptions:
    - Electricity intensity is primarily associated with cooling load and seasonal occupancy effects.
    - The target should be `electric_kwh_per_sqft`, typically created by feature engineering.
    """

    utility_type = "electricity"
    feature_columns = ["month_index", "cdd", "hdd", "is_summer", "is_winter"]
    weather_column = "cdd"
    intensity_column = "electric_kwh_per_sqft"


class GasBaselineModel(_BaseUsageModel):
    """Monthly gas baseline using heating-sensitive explainable features.

    Assumptions:
    - Gas intensity is primarily associated with heating load and winter-season operations.
    - The target should be `gas_therms_per_sqft`, typically created by feature engineering.
    """

    utility_type = "gas"
    feature_columns = ["month_index", "hdd", "cdd", "heating_season", "is_winter"]
    weather_column = "hdd"
    intensity_column = "gas_therms_per_sqft"


def _build_linear_pipeline(feature_columns: list[str]):
    """Return an explainable sklearn pipeline when sklearn is available.

    The import is intentionally local so the module can still be imported in environments that have
    not installed sklearn yet; in those cases, the model falls back to heuristics.
    """
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline
    except ModuleNotFoundError:
        return None

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                    ]
                ),
                feature_columns,
            )
        ],
        remainder="drop",
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", LinearRegression()),
        ]
    )
