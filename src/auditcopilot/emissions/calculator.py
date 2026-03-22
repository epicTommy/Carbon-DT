"""Annual emissions calculations with configurable utility emission factors.

Assumptions:
- Electricity usage is expressed in kWh and gas usage is expressed in therms.
- Emission factors are provided in metric tons CO2e per unit of utility consumption.
- Inputs are annual totals or monthly records that can be summed to annual totals.

Limitations:
- The module does not attempt temporal grid-mix adjustments or hourly marginal emissions.
- Other fuels are excluded from the MVP and can be added later by extending the factor set.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EmissionsFactorSet:
    """Configurable emissions factors in metric tons CO2e per utility unit."""

    electricity_mtco2e_per_kwh: float = 0.000288962
    gas_mtco2e_per_therm: float = 0.005302


@dataclass(frozen=True)
class EmissionsResult:
    annual_electricity_kwh: float
    annual_gas_therms: float
    electricity_emissions_mtco2e: float
    gas_emissions_mtco2e: float
    annual_emissions_mtco2e: float
    factors: EmissionsFactorSet

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["factors"] = asdict(self.factors)
        return payload


def calculate_annual_emissions(
    utility_df: pd.DataFrame,
    factors: EmissionsFactorSet | None = None,
) -> EmissionsResult:
    """Compute annual electricity, gas, and total emissions from utility records."""
    factor_set = factors or EmissionsFactorSet()
    prepared_df = _prepare_utility_dataframe(utility_df)

    electricity_usage = float(
        prepared_df.loc[
            (prepared_df["utility_type"] == "electricity")
            & (prepared_df["usage_unit"] == "kwh"),
            "usage",
        ].sum()
    )
    gas_usage = float(
        prepared_df.loc[
            (prepared_df["utility_type"] == "gas")
            & (prepared_df["usage_unit"] == "therms"),
            "usage",
        ].sum()
    )

    electricity_emissions = electricity_usage * factor_set.electricity_mtco2e_per_kwh
    gas_emissions = gas_usage * factor_set.gas_mtco2e_per_therm
    total_emissions = electricity_emissions + gas_emissions

    return EmissionsResult(
        annual_electricity_kwh=round(electricity_usage, 6),
        annual_gas_therms=round(gas_usage, 6),
        electricity_emissions_mtco2e=round(electricity_emissions, 6),
        gas_emissions_mtco2e=round(gas_emissions, 6),
        annual_emissions_mtco2e=round(total_emissions, 6),
        factors=factor_set,
    )


def _prepare_utility_dataframe(utility_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"utility_type", "usage", "usage_unit"}
    missing_columns = sorted(required_columns.difference(utility_df.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Emissions input is missing required columns: {missing}")

    working_df = utility_df.copy()
    working_df["utility_type"] = working_df["utility_type"].astype("string").str.lower()
    working_df["usage_unit"] = working_df["usage_unit"].astype("string").str.lower()
    working_df["usage"] = pd.to_numeric(working_df["usage"], errors="raise")
    return working_df
