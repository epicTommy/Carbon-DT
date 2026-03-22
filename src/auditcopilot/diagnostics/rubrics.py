"""Severity and confidence rubrics for diagnostics output.

The rubrics intentionally use simple score bands so findings remain explainable:
- Severity reflects potential impact if the signal is real.
- Confidence reflects how consistent the pattern is and how strong the supporting data appears.
"""


def severity_from_score(score: float) -> str:
    """Map a normalized impact score to a simple severity label."""
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def confidence_from_score(score: float) -> str:
    """Map a normalized evidence score to a simple confidence label."""
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"
