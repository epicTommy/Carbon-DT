"""Centralized recommendation heuristics and scoring weights.

This module is the single edit point for:
- mapping diagnostics to recommendation templates
- translating severity and confidence labels into numeric weights
- defining the transparent ranking formula inputs
"""

from __future__ import annotations


SEVERITY_WEIGHTS = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
}

CONFIDENCE_WEIGHTS = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
}

IMPLEMENTATION_DIFFICULTY_WEIGHTS = {
    "low": 3.0,
    "medium": 2.0,
    "high": 1.0,
}

RECOMMENDATION_TYPE_WEIGHTS = {
    "operational": 1.15,
    "maintenance": 1.0,
    "capital": 0.9,
}

RECOMMENDATION_LIBRARY = {
    "high_electricity_relative_to_expected": [
        {
            "recommendation_code": "electric_schedule_optimization",
            "category": "operational",
            "title": "Optimize Equipment Scheduling And Setpoints",
            "why_it_matters": "Persistent excess electric use often comes from extended runtimes, override conditions, or inefficient setpoints.",
            "estimated_savings_range_usd": "$2,000-$8,000 per year",
            "estimated_carbon_reduction_range": "5-20 tCO2e per year",
            "implementation_difficulty": "low",
            "payback_note": "Typically fast payback because changes are operational rather than capital-intensive.",
            "base_score": 8.5,
        },
        {
            "recommendation_code": "electric_system_tuning",
            "category": "maintenance",
            "title": "Tune Controls And Investigate High-Run-Time Equipment",
            "why_it_matters": "Control drift, failed sensors, or short-cycling equipment can keep electric demand above baseline.",
            "estimated_savings_range_usd": "$3,000-$12,000 per year",
            "estimated_carbon_reduction_range": "8-28 tCO2e per year",
            "implementation_difficulty": "medium",
            "payback_note": "Payback is usually favorable if corrective maintenance resolves hidden control issues.",
            "base_score": 8.0,
        },
    ],
    "high_gas_relative_to_expected": [
        {
            "recommendation_code": "boiler_reset_review",
            "category": "operational",
            "title": "Review Boiler Reset Strategy And Heating Schedules",
            "why_it_matters": "Gas overruns often reflect aggressive heating schedules, high hot-water temperatures, or disabled reset logic.",
            "estimated_savings_range_usd": "$1,500-$6,000 per year",
            "estimated_carbon_reduction_range": "10-35 tCO2e per year",
            "implementation_difficulty": "low",
            "payback_note": "Often low-cost to implement and can produce savings within a single heating season.",
            "base_score": 8.3,
        },
        {
            "recommendation_code": "combustion_tune_up",
            "category": "maintenance",
            "title": "Perform Combustion Tuning And Heating System Maintenance",
            "why_it_matters": "Poor burner tuning, valve issues, and distribution imbalances can drive excess gas consumption.",
            "estimated_savings_range_usd": "$2,500-$9,000 per year",
            "estimated_carbon_reduction_range": "15-45 tCO2e per year",
            "implementation_difficulty": "medium",
            "payback_note": "Payback is usually attractive when deferred maintenance is the main driver.",
            "base_score": 8.1,
        },
    ],
    "summer_electric_spike": [
        {
            "recommendation_code": "cooling_plant_optimization",
            "category": "maintenance",
            "title": "Inspect Cooling Equipment And Optimize Summer Controls",
            "why_it_matters": "Summer spikes often point to cooling inefficiency, economizer faults, or excessive ventilation during hot periods.",
            "estimated_savings_range_usd": "$3,000-$15,000 per year",
            "estimated_carbon_reduction_range": "10-40 tCO2e per year",
            "implementation_difficulty": "medium",
            "payback_note": "Moderate payback, especially when the issue is resolved through tuning rather than replacement.",
            "base_score": 8.4,
        },
        {
            "recommendation_code": "cooling_upgrade_screen",
            "category": "capital",
            "title": "Screen Major Cooling Retrofits Or Controls Upgrades",
            "why_it_matters": "If summer performance remains poor after tuning, aging cooling assets or controls may need targeted upgrades.",
            "estimated_savings_range_usd": "$8,000-$30,000 per year",
            "estimated_carbon_reduction_range": "20-75 tCO2e per year",
            "implementation_difficulty": "high",
            "payback_note": "Payback depends on asset age and replacement timing; best evaluated alongside capital planning.",
            "base_score": 7.2,
        },
    ],
    "winter_gas_spike": [
        {
            "recommendation_code": "heating_distribution_review",
            "category": "maintenance",
            "title": "Review Heating Distribution And Envelope Leakage Drivers",
            "why_it_matters": "Winter gas spikes can reflect distribution losses, simultaneous heating, or avoidable envelope-driven loads.",
            "estimated_savings_range_usd": "$2,000-$10,000 per year",
            "estimated_carbon_reduction_range": "18-55 tCO2e per year",
            "implementation_difficulty": "medium",
            "payback_note": "Payback varies with whether fixes are control-based, maintenance-based, or envelope-related.",
            "base_score": 8.2,
        }
    ],
    "elevated_baseload": [
        {
            "recommendation_code": "after_hours_load_reduction",
            "category": "operational",
            "title": "Reduce After-Hours Baseload",
            "why_it_matters": "Elevated baseload often indicates lights, plug loads, fans, or process equipment running when the building is lightly occupied.",
            "estimated_savings_range_usd": "$2,500-$9,500 per year",
            "estimated_carbon_reduction_range": "6-24 tCO2e per year",
            "implementation_difficulty": "low",
            "payback_note": "Usually fast payback because improvements focus on scheduling, shutoff, and occupancy alignment.",
            "base_score": 9.0,
        },
        {
            "recommendation_code": "plug_load_controls",
            "category": "capital",
            "title": "Add Automated Plug Load Or Lighting Controls",
            "why_it_matters": "Persistent off-hour load may justify targeted controls where operational changes are not enough.",
            "estimated_savings_range_usd": "$3,000-$11,000 per year",
            "estimated_carbon_reduction_range": "8-26 tCO2e per year",
            "implementation_difficulty": "medium",
            "payback_note": "Payback depends on control scope and the share of unmanaged plug or lighting load.",
            "base_score": 7.0,
        },
    ],
    "negative_trend_over_time": [
        {
            "recommendation_code": "performance_drift_investigation",
            "category": "maintenance",
            "title": "Investigate Performance Drift Over Time",
            "why_it_matters": "Worsening performance can indicate controls drift, failing components, or gradual operational changes that are not visible in a single month.",
            "estimated_savings_range_usd": "$2,000-$10,000 per year",
            "estimated_carbon_reduction_range": "8-30 tCO2e per year",
            "implementation_difficulty": "medium",
            "payback_note": "Payback is usually favorable when the root cause is found early and corrected before a major failure.",
            "base_score": 8.6,
        }
    ],
    "poor_data_quality_or_low_confidence": [
        {
            "recommendation_code": "improve_metering_and_data_quality",
            "category": "operational",
            "title": "Improve Metering Coverage And Data Quality",
            "why_it_matters": "Low-confidence analytics limit prioritization accuracy and can hide the true drivers of waste.",
            "estimated_savings_range_usd": "$0-$3,000 indirect annual value",
            "estimated_carbon_reduction_range": "0-5 tCO2e indirect impact",
            "implementation_difficulty": "low",
            "payback_note": "Indirect payback through better targeting of future operational and capital actions.",
            "base_score": 6.5,
        }
    ],
}
