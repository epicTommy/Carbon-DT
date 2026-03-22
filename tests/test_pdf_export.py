from auditcopilot.dashboard import run_dashboard_analysis
from auditcopilot.reporting import export_audit_report_pdf


def test_export_audit_report_pdf_returns_pdf_bytes_with_expected_sections() -> None:
    result = run_dashboard_analysis(
        uploaded_file_bytes=None,
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
