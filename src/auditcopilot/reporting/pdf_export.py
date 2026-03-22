"""PDF export for the audit report.

The layout is intentionally simple and professional for local report generation:
- title page
- building and data quality summary
- KPI summary
- diagnostics and recommendations
- carbon/compliance section
- disclaimer

This module expects a fully prepared dashboard result and does not perform business calculations.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from auditcopilot.dashboard import DashboardResult


def export_audit_report_pdf(result: DashboardResult) -> bytes:
    """Build a PDF audit report from the dashboard analysis result."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        pageCompression=0,
    )
    styles = _build_styles()

    story = []
    story.extend(_title_page(result, styles))
    story.append(PageBreak())
    story.extend(_building_summary(result, styles))
    story.extend(_data_quality_note(result, styles))
    story.extend(_kpi_section(result, styles))
    story.extend(_diagnostics_section(result, styles))
    story.extend(_recommendations_section(result, styles))
    story.extend(_carbon_compliance_section(result, styles))
    story.extend(_disclaimer_section(styles))

    document.build(story)
    return buffer.getvalue()


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            spaceAfter=8,
            textColor=colors.HexColor("#17324d"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=13,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TitleLarge",
            parent=styles["Title"],
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#17324d"),
        )
    )
    return styles


def _title_page(result: DashboardResult, styles):
    metadata = result.building_metadata
    return [
        Spacer(1, 1.1 * inch),
        Paragraph("Energy Audit Copilot MVP", styles["TitleLarge"]),
        Spacer(1, 0.25 * inch),
        Paragraph(f"Audit Report for {metadata['building_name']}", styles["Heading2"]),
        Spacer(1, 0.15 * inch),
        Paragraph(f"{metadata['address']}", styles["BodyText"]),
        Paragraph(
            f"{metadata['building_type']} | {metadata['floor_area_sqft']:,.0f} sqft | Built {metadata['year_built']}",
            styles["BodyText"],
        ),
        Spacer(1, 0.5 * inch),
        Paragraph(f"Data Source: {result.source_label}", styles["BodyText"]),
        Spacer(1, 3.5 * inch),
        Paragraph(
            "This report summarizes utility data quality, modeled baseline comparisons, diagnostics, recommendations, and carbon/compliance indicators.",
            styles["BodySmall"],
        ),
    ]


def _building_summary(result: DashboardResult, styles):
    metadata = result.building_metadata
    rows = [
        ["Building", metadata["building_name"]],
        ["Type", metadata["building_type"]],
        ["Address", metadata["address"]],
        ["Floor Area", f"{metadata['floor_area_sqft']:,.0f} sqft"],
        ["Year Built", str(metadata["year_built"])],
        ["Input Source", result.source_label],
    ]
    return [
        Paragraph("Building Summary", styles["SectionHeading"]),
        _styled_table(rows, col_widths=[1.6 * inch, 4.9 * inch]),
        Spacer(1, 0.2 * inch),
    ]


def _data_quality_note(result: DashboardResult, styles):
    messages_df = pd.DataFrame(result.validation_messages)
    if messages_df.empty:
        quality_text = "No validation issues were detected."
    else:
        issue_count = len(messages_df.loc[messages_df["level"] != "info"])
        quality_text = (
            f"{issue_count} validation issues were identified. "
            "See the dashboard for row-level details."
            if issue_count
            else "Input data passed validation checks aside from informational source notes."
        )

    return [
        Paragraph("Data Quality Note", styles["SectionHeading"]),
        Paragraph(quality_text, styles["BodyText"]),
        Spacer(1, 0.18 * inch),
    ]


def _kpi_section(result: DashboardResult, styles):
    kpis = result.kpis
    if not kpis:
        return [
            Paragraph("Key KPIs", styles["SectionHeading"]),
            Paragraph("KPI summary is unavailable because the input data did not pass validation.", styles["BodyText"]),
            Spacer(1, 0.2 * inch),
        ]

    rows = [
        ["Annual Electricity", f"{kpis['annual_electricity_kwh']:,.0f} kWh"],
        ["Annual Gas", f"{kpis['annual_gas_therms']:,.0f} therms"],
        ["Electricity Gap vs Expected", f"{kpis['electricity_gap_kwh']:,.0f} kWh"],
        ["Gas Gap vs Expected", f"{kpis['gas_gap_therms']:,.0f} therms"],
        ["Annual Emissions", f"{kpis['annual_emissions_mtco2e']:,.2f} mtCO2e"],
        ["Diagnostics", str(kpis["diagnostic_count"])],
        ["Recommendations", str(kpis["recommendation_count"])],
    ]
    return [
        Paragraph("Key KPIs", styles["SectionHeading"]),
        _styled_table(rows, col_widths=[2.4 * inch, 3.6 * inch]),
        Spacer(1, 0.2 * inch),
    ]


def _diagnostics_section(result: DashboardResult, styles):
    story = [Paragraph("Diagnostics", styles["SectionHeading"])]
    if not result.diagnostics:
        story.append(Paragraph("No diagnostics were triggered.", styles["BodyText"]))
        story.append(Spacer(1, 0.2 * inch))
        return story

    rows = [["Title", "Severity", "Confidence", "Evidence"]]
    for finding in result.diagnostics:
        evidence_summary = ", ".join(f"{key}: {value}" for key, value in list(finding.evidence.items())[:3])
        rows.append(
            [
                finding.title,
                finding.severity.title(),
                finding.confidence.title(),
                evidence_summary,
            ]
        )
    story.append(_styled_table(rows, header=True, col_widths=[2.0 * inch, 0.9 * inch, 1.0 * inch, 2.3 * inch]))
    story.append(Spacer(1, 0.2 * inch))
    return story


def _recommendations_section(result: DashboardResult, styles):
    story = [Paragraph("Recommendations", styles["SectionHeading"])]
    if not result.recommendations:
        story.append(Paragraph("No recommendations were generated.", styles["BodyText"]))
        story.append(Spacer(1, 0.2 * inch))
        return story

    for recommendation in result.recommendations[:6]:
        story.append(Paragraph(recommendation.title, styles["Heading4"]))
        story.append(
            Paragraph(
                f"{recommendation.category.title()} | Difficulty: {recommendation.implementation_difficulty.title()} | Confidence: {recommendation.confidence.title()}",
                styles["BodySmall"],
            )
        )
        story.append(Paragraph(recommendation.why_it_matters, styles["BodyText"]))
        story.append(
            Paragraph(
                f"Savings: {recommendation.estimated_savings_range_usd} | Carbon: {recommendation.estimated_carbon_reduction_range}",
                styles["BodySmall"],
            )
        )
        story.append(Paragraph(f"Payback Note: {recommendation.payback_note}", styles["BodySmall"]))
        if recommendation.audit_trace:
            story.append(
                Paragraph(
                    "Audit Trace: " + "; ".join(recommendation.audit_trace[:5]),
                    styles["BodySmall"],
                )
            )
        story.append(Spacer(1, 0.12 * inch))
    story.append(Spacer(1, 0.12 * inch))
    return story


def _carbon_compliance_section(result: DashboardResult, styles):
    story = [Paragraph("Carbon And Compliance Summary", styles["SectionHeading"])]
    if result.emissions is None:
        story.append(Paragraph("Carbon summary is unavailable.", styles["BodyText"]))
        story.append(Spacer(1, 0.2 * inch))
        return story

    emissions_rows = [
        ["Electricity Emissions", f"{result.emissions.electricity_emissions_mtco2e:,.2f} mtCO2e"],
        ["Gas Emissions", f"{result.emissions.gas_emissions_mtco2e:,.2f} mtCO2e"],
        ["Annual Total", f"{result.emissions.annual_emissions_mtco2e:,.2f} mtCO2e"],
    ]
    story.append(_styled_table(emissions_rows, col_widths=[2.4 * inch, 3.1 * inch]))
    story.append(Spacer(1, 0.12 * inch))

    if result.compliance is None:
        story.append(Paragraph("Compliance mode was not enabled for this export.", styles["BodyText"]))
    else:
        compliance_rows = [
            ["Mode", result.compliance.mode],
            ["Limit", f"{result.compliance.emissions_limit_mtco2e:,.2f} mtCO2e"],
            ["Excess Emissions", f"{result.compliance.excess_emissions_mtco2e:,.2f} mtCO2e"],
            ["Penalty Estimate", f"${result.compliance.penalty_estimate_usd:,.2f}"],
            ["Compliant", "Yes" if result.compliance.compliant else "No"],
        ]
        story.append(_styled_table(compliance_rows, col_widths=[2.4 * inch, 3.1 * inch]))
    story.append(Spacer(1, 0.2 * inch))
    return story


def _disclaimer_section(styles):
    return [
        Paragraph("Disclaimer", styles["SectionHeading"]),
        Paragraph(
            "This MVP report is intended for preliminary screening only. Expected usage, emissions, recommendations, and compliance indicators are based on configurable heuristics and simplified assumptions. They should be reviewed and validated before any engineering, financial, or regulatory decision is made.",
            styles["BodySmall"],
        ),
    ]


def _styled_table(rows, header: bool = False, col_widths=None):
    table = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#95a5b3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c7d1db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    else:
        style.extend(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(style))
    return table
