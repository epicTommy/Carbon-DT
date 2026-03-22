import pandas as pd

from auditcopilot.ingestion import ingest_utility_bills


def test_ingest_utility_bills_normalizes_units_and_monthly_splits() -> None:
    source_df = pd.DataFrame(
        [
            {
                "billing_start": "2025-01-15",
                "billing_end": "2025-02-14",
                "utility_type": "electricity",
                "usage": 1.5,
                "usage_unit": "MWh",
                "cost": 310.0,
            },
            {
                "billing_start": "2025-03-01",
                "billing_end": "2025-03-31",
                "utility_type": "gas",
                "usage": 2.0,
                "usage_unit": "MCF",
                "cost": 90.0,
            },
        ]
    )

    result = ingest_utility_bills(source_df)

    assert result.messages == []
    assert len(result.dataframe) == 3

    jan_row = result.dataframe[result.dataframe["billing_month"] == "2025-01"].iloc[0]
    feb_row = result.dataframe[result.dataframe["billing_month"] == "2025-02"].iloc[0]
    march_row = result.dataframe[result.dataframe["billing_month"] == "2025-03"].iloc[0]

    assert jan_row["usage_unit"] == "kwh"
    assert round(jan_row["usage"] + feb_row["usage"], 6) == 1500.0
    assert round(jan_row["cost"] + feb_row["cost"], 6) == 310.0
    assert round(jan_row["usage"], 6) == round(1500.0 * (17 / 31), 6)
    assert round(feb_row["usage"], 6) == round(1500.0 * (14 / 31), 6)

    assert march_row["usage_unit"] == "therms"
    assert round(march_row["usage"], 6) == 20.74
    assert march_row["cost"] == 90.0


def test_ingest_utility_bills_reports_missing_columns() -> None:
    source_df = pd.DataFrame(
        [
            {
                "billing_start": "2025-01-01",
                "billing_end": "2025-01-31",
                "utility_type": "electricity",
                "usage": 1000,
                "cost": 120.0,
            }
        ]
    )

    result = ingest_utility_bills(source_df)

    assert result.dataframe.empty
    assert len(result.messages) == 1
    message = result.messages[0]
    assert message.code == "missing_required_column"
    assert message.column == "usage_unit"


def test_ingest_utility_bills_rejects_unsupported_units() -> None:
    source_df = pd.DataFrame(
        [
            {
                "billing_start": "2025-01-01",
                "billing_end": "2025-01-31",
                "utility_type": "gas",
                "usage": 100.0,
                "usage_unit": "kwh",
                "cost": 80.0,
            }
        ]
    )

    result = ingest_utility_bills(source_df)

    assert result.dataframe.empty
    assert len(result.messages) == 1
    assert result.messages[0].code == "unsupported_usage_unit"
