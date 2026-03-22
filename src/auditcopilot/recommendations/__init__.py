"""Recommendation mapping and ranking for audit diagnostics."""

from auditcopilot.recommendations.engine import (
    Recommendation,
    generate_recommendations,
)

__all__ = [
    "Recommendation",
    "generate_recommendations",
]
