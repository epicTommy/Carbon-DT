import pandas as pd

from auditcopilot.dashboard import run_dashboard_analysis
from auditcopilot.reporting import export_audit_report_pdf


def test_export_audit_report_pdf_returns_pdf_bytes_with_expected_sections(monkeypatch) -> None:
    class _FakeLocation:
        name = "New York, NY, US"
        latitude = 40.75
        longitude = -73.99

    class _FakeOpenMeteoWeatherProvider:
        def __init__(self, *args, **kwargs) -> None:
            self.last_location = _FakeLocation()

        def get_monthly_weather(self) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "year": [2025] * 12,
                    "month": list(range(1, 13)),
                    "avg_temp": [30.0, 34.5, 45.2, 56.8, 66.1, 74.9, 79.3, 77.8, 70.4, 58.7, 46.5, 35.1],
                }
            )

    monkeypatch.setattr("auditcopilot.dashboard.service.OpenMeteoWeatherProvider", _FakeOpenMeteoWeatherProvider)

    uploaded_csv = b"""billing_start,billing_end,utility_type,usage,usage_unit,cost
2025-01-01,2025-01-31,electricity,32000,kwh,4320
2025-01-01,2025-01-31,gas,2300,therms,2530
2025-02-01,2025-02-28,electricity,31200,kwh,4212
2025-02-01,2025-02-28,gas,2100,therms,2310
2025-03-01,2025-03-31,electricity,30100,kwh,4063.5
2025-03-01,2025-03-31,gas,1700,therms,1870
2025-04-01,2025-04-30,electricity,29400,kwh,3969
2025-04-01,2025-04-30,gas,1200,therms,1320
2025-05-01,2025-05-31,electricity,31500,kwh,4252.5
2025-05-01,2025-05-31,gas,800,therms,880
2025-06-01,2025-06-30,electricity,36400,kwh,4914
2025-06-01,2025-06-30,gas,450,therms,495
2025-07-01,2025-07-31,electricity,43200,kwh,5832
2025-07-01,2025-07-31,gas,250,therms,275
2025-08-01,2025-08-31,electricity,42400,kwh,5724
2025-08-01,2025-08-31,gas,260,therms,286
2025-09-01,2025-09-30,electricity,35200,kwh,4752
2025-09-01,2025-09-30,gas,500,therms,550
2025-10-01,2025-10-31,electricity,33400,kwh,4509
2025-10-01,2025-10-31,gas,900,therms,990
2025-11-01,2025-11-30,electricity,34500,kwh,4657.5
2025-11-01,2025-11-30,gas,1500,therms,1650
2025-12-01,2025-12-31,electricity,36800,kwh,4968
2025-12-01,2025-12-31,gas,2200,therms,2420
"""

    result = run_dashboard_analysis(
        uploaded_file_bytes=uploaded_csv,
        building_metadata={
            "building_name": "North Office",
            "building_type": "Office",
            "address": "123 Main St",
            "floor_area_sqft": 25000,
            "year_built": 1998,
        },
        weather_settings={
            "use_building_address": False,
            "zip_code": "10001",
        },
        emissions_factor_settings={
            "electricity_mtco2e_per_kwh": 0.000288962,
            "gas_mtco2e_per_therm": 0.005302,
        },
        compliance_mode="NYC LL97",
        compliance_settings={
            "emissions_limit_mtco2e": 120.0,
            "penalty_rate_usd_per_mtco2e": 268.0,
        },
    )

    pdf_bytes = export_audit_report_pdf(result)

    assert pdf_bytes.startswith(b"%PDF")
    assert b"Energy Audit Copilot MVP" in pdf_bytes
    assert b"Building Summary" in pdf_bytes
    assert b"Carbon And Compliance Summary" in pdf_bytes
    assert b"Disclaimer" in pdf_bytes
