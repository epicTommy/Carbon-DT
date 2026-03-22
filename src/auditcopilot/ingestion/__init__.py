"""Ingestion interfaces for Energy Audit Copilot."""

from auditcopilot.ingestion.utility_bills import (
    UtilityBillIngestionResult,
    ValidationMessage,
    ingest_utility_bills,
)

__all__ = [
    "UtilityBillIngestionResult",
    "ValidationMessage",
    "ingest_utility_bills",
]
