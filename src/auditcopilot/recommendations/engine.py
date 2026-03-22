"""Recommendation engine that maps diagnostics to ranked actions.

Assumptions:
- Diagnostics are already generated and carry severity and confidence labels.
- Recommendation ranking should be transparent and stable, not opaque or model-driven.
- Savings and carbon ranges are heuristic placeholders for MVP triage, not investment-grade estimates.

Limitations:
- Estimated ranges are broad and should be refined with project-specific data.
- Ranking favors explainable operational actions slightly ahead of harder capital measures when scores are similar.
- Recommendations are deterministic but intentionally conservative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from auditcopilot.diagnostics.engine import DiagnosticFinding
from auditcopilot.recommendations.heuristics import (
    CONFIDENCE_WEIGHTS,
    IMPLEMENTATION_DIFFICULTY_WEIGHTS,
    RECOMMENDATION_LIBRARY,
    RECOMMENDATION_TYPE_WEIGHTS,
    SEVERITY_WEIGHTS,
)


@dataclass(frozen=True)
class Recommendation:
    title: str
    why_it_matters: str
    estimated_savings_range_usd: str
    estimated_carbon_reduction_range: str
    implementation_difficulty: str
    payback_note: str
    confidence: str
    category: str
    source_diagnostic_code: str
    ranking_score: float
    audit_trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_recommendations(
    diagnostics: list[DiagnosticFinding],
) -> list[Recommendation]:
    """Map diagnostics to ranked recommendations using a transparent scoring formula."""
    recommendation_rows: list[tuple[float, str, Recommendation]] = []

    for finding in diagnostics:
        for template in RECOMMENDATION_LIBRARY.get(finding.code, []):
            score = _compute_ranking_score(
                diagnostic_severity=finding.severity,
                diagnostic_confidence=finding.confidence,
                implementation_difficulty=template["implementation_difficulty"],
                recommendation_category=template["category"],
                base_score=float(template["base_score"]),
            )
            recommendation = Recommendation(
                title=template["title"],
                why_it_matters=template["why_it_matters"],
                estimated_savings_range_usd=template["estimated_savings_range_usd"],
                estimated_carbon_reduction_range=template["estimated_carbon_reduction_range"],
                implementation_difficulty=template["implementation_difficulty"],
                payback_note=template["payback_note"],
                confidence=finding.confidence,
                category=template["category"],
                source_diagnostic_code=finding.code,
                ranking_score=round(score, 3),
                audit_trace=_build_audit_trace(finding),
            )
            recommendation_rows.append(
                (
                    recommendation.ranking_score,
                    template["recommendation_code"],
                    recommendation,
                )
            )

    recommendation_rows.sort(
        key=lambda row: (
            -row[0],
            row[2].title.lower(),
            row[1],
            row[2].source_diagnostic_code,
        )
    )
    return [row[2] for row in recommendation_rows]


def _compute_ranking_score(
    diagnostic_severity: str,
    diagnostic_confidence: str,
    implementation_difficulty: str,
    recommendation_category: str,
    base_score: float,
) -> float:
    """Return a transparent weighted score for recommendation ordering.

    Formula:
    `score = base_score * severity_weight * confidence_weight * category_weight * difficulty_weight / 6`

    This keeps the score interpretable and easy to tune from the centralized heuristics module.
    """
    severity_weight = SEVERITY_WEIGHTS[diagnostic_severity]
    confidence_weight = CONFIDENCE_WEIGHTS[diagnostic_confidence]
    difficulty_weight = IMPLEMENTATION_DIFFICULTY_WEIGHTS[implementation_difficulty]
    category_weight = RECOMMENDATION_TYPE_WEIGHTS[recommendation_category]

    return (
        base_score
        * severity_weight
        * confidence_weight
        * difficulty_weight
        * category_weight
        / 6.0
    )


def _build_audit_trace(finding: DiagnosticFinding) -> list[str]:
    trace = [
        f"Diagnostic code: {finding.code}",
        f"Diagnostic severity: {finding.severity}",
        f"Diagnostic confidence: {finding.confidence}",
    ]
    for key, value in finding.evidence.items():
        trace.append(f"Evidence - {key}: {value}")
    return trace
