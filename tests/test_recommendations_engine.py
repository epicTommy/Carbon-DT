from auditcopilot.diagnostics.engine import DiagnosticFinding
from auditcopilot.recommendations import generate_recommendations


def test_recommendations_are_ranked_by_transparent_score() -> None:
    diagnostics = [
        DiagnosticFinding(
            code="elevated_baseload",
            title="Elevated Baseload",
            description="Baseload is high.",
            evidence={"non_summer_mean_usage_ratio": 1.2},
            severity="high",
            confidence="high",
        ),
        DiagnosticFinding(
            code="poor_data_quality_or_low_confidence",
            title="Poor Data Quality Or Low Confidence",
            description="Confidence is limited.",
            evidence={"row_count": 4},
            severity="low",
            confidence="high",
        ),
    ]

    recommendations = generate_recommendations(diagnostics)

    assert len(recommendations) >= 2
    assert recommendations[0].title == "Reduce After-Hours Baseload"
    assert recommendations[0].ranking_score > recommendations[-1].ranking_score


def test_recommendation_ordering_is_deterministic_for_ties() -> None:
    diagnostics = [
        DiagnosticFinding(
            code="high_gas_relative_to_expected",
            title="Consistently High Gas Relative To Expected",
            description="Gas is high.",
            evidence={"mean_usage_ratio": 1.22},
            severity="medium",
            confidence="medium",
        ),
        DiagnosticFinding(
            code="negative_trend_over_time",
            title="Negative Trend Over Time",
            description="Trend is worsening.",
            evidence={"ratio_delta": 0.18},
            severity="medium",
            confidence="medium",
        ),
    ]

    first = [recommendation.to_dict() for recommendation in generate_recommendations(diagnostics)]
    second = [recommendation.to_dict() for recommendation in generate_recommendations(diagnostics)]

    assert first == second
    assert [item["title"] for item in first] == [
        "Review Boiler Reset Strategy And Heating Schedules",
        "Investigate Performance Drift Over Time",
        "Perform Combustion Tuning And Heating System Maintenance",
    ]
