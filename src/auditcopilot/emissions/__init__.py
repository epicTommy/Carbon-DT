"""Emissions calculations for annual electricity and gas usage."""

from auditcopilot.emissions.calculator import (
    EmissionsFactorSet,
    EmissionsResult,
    calculate_annual_emissions,
)

__all__ = [
    "EmissionsFactorSet",
    "EmissionsResult",
    "calculate_annual_emissions",
]
