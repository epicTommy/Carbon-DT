"""Generic and NYC LL97 compliance evaluations.

Assumptions:
- Compliance operates on annual building emissions in metric tons CO2e.
- Limits and penalty rates are configurable so the module remains jurisdiction-agnostic by default.
- LL97 mode is a simplified annual estimate, not a legal interpretation or filing tool.

Limitations:
- This MVP does not encode occupancy-class lookup tables or filing exemptions.
- Penalty calculations assume a simple per-ton excess penalty rate.
- Users are expected to supply the correct annual emissions limit for the building being analyzed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ComplianceResult:
    mode: str
    annual_emissions_mtco2e: float
    emissions_limit_mtco2e: float
    excess_emissions_mtco2e: float
    penalty_estimate_usd: float
    compliant: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LL97Config:
    emissions_limit_mtco2e: float
    penalty_rate_usd_per_mtco2e: float = 268.0


def evaluate_generic_compliance(
    annual_emissions_mtco2e: float,
    emissions_limit_mtco2e: float,
) -> ComplianceResult:
    """Evaluate annual emissions against a configurable generic limit."""
    excess_emissions = max(float(annual_emissions_mtco2e) - float(emissions_limit_mtco2e), 0.0)
    return ComplianceResult(
        mode="generic",
        annual_emissions_mtco2e=round(float(annual_emissions_mtco2e), 6),
        emissions_limit_mtco2e=round(float(emissions_limit_mtco2e), 6),
        excess_emissions_mtco2e=round(excess_emissions, 6),
        penalty_estimate_usd=0.0,
        compliant=excess_emissions == 0.0,
    )


def evaluate_ll97_compliance(
    annual_emissions_mtco2e: float,
    config: LL97Config,
) -> ComplianceResult:
    """Evaluate annual emissions using a configurable NYC LL97-style limit and penalty."""
    excess_emissions = max(
        float(annual_emissions_mtco2e) - float(config.emissions_limit_mtco2e),
        0.0,
    )
    penalty_estimate = excess_emissions * float(config.penalty_rate_usd_per_mtco2e)

    return ComplianceResult(
        mode="nyc_ll97",
        annual_emissions_mtco2e=round(float(annual_emissions_mtco2e), 6),
        emissions_limit_mtco2e=round(float(config.emissions_limit_mtco2e), 6),
        excess_emissions_mtco2e=round(excess_emissions, 6),
        penalty_estimate_usd=round(penalty_estimate, 2),
        compliant=excess_emissions == 0.0,
    )
