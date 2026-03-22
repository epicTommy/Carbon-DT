import pandas as pd

from auditcopilot.compliance import (
    LL97Config,
    evaluate_generic_compliance,
    evaluate_ll97_compliance,
)
from auditcopilot.emissions import EmissionsFactorSet, calculate_annual_emissions


def test_calculate_annual_emissions_uses_configurable_factors() -> None:
    utility_df = pd.DataFrame(
        [
            {"utility_type": "electricity", "usage": 12000.0, "usage_unit": "kwh"},
            {"utility_type": "gas", "usage": 800.0, "usage_unit": "therms"},
        ]
    )
    factors = EmissionsFactorSet(
        electricity_mtco2e_per_kwh=0.00025,
        gas_mtco2e_per_therm=0.005,
    )

    result = calculate_annual_emissions(utility_df, factors=factors)

    assert result.annual_electricity_kwh == 12000.0
    assert result.annual_gas_therms == 800.0
    assert result.electricity_emissions_mtco2e == 3.0
    assert result.gas_emissions_mtco2e == 4.0
    assert result.annual_emissions_mtco2e == 7.0


def test_generic_compliance_reports_excess_without_penalty() -> None:
    result = evaluate_generic_compliance(
        annual_emissions_mtco2e=55.0,
        emissions_limit_mtco2e=50.0,
    )

    assert result.mode == "generic"
    assert result.excess_emissions_mtco2e == 5.0
    assert result.penalty_estimate_usd == 0.0
    assert result.compliant is False


def test_ll97_compliance_calculates_excess_and_penalty() -> None:
    config = LL97Config(
        emissions_limit_mtco2e=40.0,
        penalty_rate_usd_per_mtco2e=268.0,
    )

    result = evaluate_ll97_compliance(
        annual_emissions_mtco2e=52.5,
        config=config,
    )

    assert result.mode == "nyc_ll97"
    assert result.annual_emissions_mtco2e == 52.5
    assert result.emissions_limit_mtco2e == 40.0
    assert result.excess_emissions_mtco2e == 12.5
    assert result.penalty_estimate_usd == 3350.0
    assert result.compliant is False


def test_ll97_compliance_reports_no_penalty_when_below_limit() -> None:
    config = LL97Config(emissions_limit_mtco2e=40.0)

    result = evaluate_ll97_compliance(
        annual_emissions_mtco2e=38.2,
        config=config,
    )

    assert result.excess_emissions_mtco2e == 0.0
    assert result.penalty_estimate_usd == 0.0
    assert result.compliant is True
