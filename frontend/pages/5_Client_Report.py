"""Streamlit page for downloadable client LDI reports."""

from __future__ import annotations

from datetime import date
from io import BytesIO
import os
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import requests
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from backend.models.portfolio import PortfolioModel
from api_client import post_api_json, render_backend_error, warm_up_backend


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")


def main() -> None:
    """Render the client reporting page."""
    st.set_page_config(
        page_title="Client Report",
        layout="wide",
    )

    st.title("Client Report")

    st.header("Inputs")
    (
        client_name,
        report_date,
        portfolio,
        cash_flow_df,
        discount_curve_df,
        attribution_inputs,
    ) = render_inputs()

    st.header("Report")
    if st.button("Generate Client Report", type="primary"):
        generate_client_report(
            client_name=client_name,
            report_date=report_date,
            portfolio=portfolio,
            cash_flow_df=cash_flow_df,
            discount_curve_df=discount_curve_df,
            attribution_inputs=attribution_inputs,
        )


def render_inputs() -> tuple[
    str,
    date,
    PortfolioModel,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, float],
]:
    """Render client report inputs and editable liability tables."""
    left, right = st.columns(2)
    with left:
        client_name = st.text_input("Client Name", value="Sample Pension Plan")
    with right:
        report_date = st.date_input("Report Date", value=date.today())

    growth_col, hedging_col = st.columns(2)
    with growth_col:
        st.subheader("Growth Portfolio")
        equities = st.number_input(
            "Equities",
            min_value=0.0,
            value=3_000_000.0,
            step=100_000.0,
            format="%.2f",
        )
        credit = st.number_input(
            "Credit",
            min_value=0.0,
            value=1_000_000.0,
            step=100_000.0,
            format="%.2f",
        )

    with hedging_col:
        st.subheader("Hedging Portfolio")
        long_bonds = st.number_input(
            "Long Bonds",
            min_value=0.0,
            value=500_000.0,
            step=50_000.0,
            format="%.2f",
        )
        irs_exposure = st.number_input(
            "IRS Exposure",
            min_value=0.0,
            value=700_000.0,
            step=50_000.0,
            format="%.2f",
        )

    portfolio = PortfolioModel(
        equities=equities,
        credit=credit,
        long_bonds=long_bonds,
        irs_exposure=irs_exposure,
    )
    render_portfolio_summary_metrics(portfolio)

    default_cash_flows = pd.DataFrame(
        {
            "year": [1, 2, 3, 4, 5],
            "cash_flow": [
                1_000_000.0,
                1_050_000.0,
                1_100_000.0,
                1_150_000.0,
                1_200_000.0,
            ],
        }
    )
    default_discount_curve = pd.DataFrame(
        {
            "year": [1, 2, 3, 4, 5],
            "discount_rate": [0.040, 0.041, 0.042, 0.043, 0.044],
        }
    )

    table_left, table_right = st.columns(2)
    with table_left:
        st.subheader("Cash Flow Table")
        cash_flow_df = st.data_editor(
            default_cash_flows,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
        )

    with table_right:
        st.subheader("Discount Curve Table")
        discount_curve_df = st.data_editor(
            default_discount_curve,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
        )

    attribution_inputs = render_attribution_inputs(
        beginning_assets=portfolio.total_assets() * 0.97,
        ending_assets=portfolio.total_assets(),
    )

    return (
        client_name,
        report_date,
        portfolio,
        cash_flow_df,
        discount_curve_df,
        attribution_inputs,
    )


def render_attribution_inputs(
    beginning_assets: float,
    ending_assets: float,
) -> dict[str, float]:
    """Render attribution inputs for client report downloads."""
    st.subheader("Period Attribution")
    first, second, third = st.columns(3)
    with first:
        beginning_assets = st.number_input(
            "Report Beginning Assets",
            min_value=0.0,
            value=beginning_assets,
            step=100_000.0,
            format="%.2f",
        )
        ending_assets = st.number_input(
            "Report Ending Assets",
            min_value=0.0,
            value=ending_assets,
            step=100_000.0,
            format="%.2f",
        )
    with second:
        beginning_liability_pv = st.number_input(
            "Report Beginning Liability PV",
            min_value=1.0,
            value=5_500_000.0,
            step=100_000.0,
            format="%.2f",
        )
        ending_liability_pv = st.number_input(
            "Report Ending Liability PV",
            min_value=1.0,
            value=5_650_000.0,
            step=100_000.0,
            format="%.2f",
        )
    with third:
        asset_return = st.number_input(
            "Report Asset Return",
            value=225_000.0,
            step=25_000.0,
            format="%.2f",
        )
        liability_discount_rate_change = st.number_input(
            "Report Liability Discount-Rate Change",
            value=125_000.0,
            step=25_000.0,
            format="%.2f",
        )
        benefit_payments = st.number_input(
            "Report Benefit Payments",
            value=100_000.0,
            step=25_000.0,
            format="%.2f",
        )
        hedge_return = st.number_input(
            "Report Hedge Return",
            value=75_000.0,
            step=25_000.0,
            format="%.2f",
        )

    return {
        "beginning_assets": beginning_assets,
        "ending_assets": ending_assets,
        "beginning_liability_pv": beginning_liability_pv,
        "ending_liability_pv": ending_liability_pv,
        "asset_return": asset_return,
        "liability_discount_rate_change": liability_discount_rate_change,
        "benefit_payments": benefit_payments,
        "hedge_return": hedge_return,
    }


def render_portfolio_summary_metrics(portfolio: PortfolioModel) -> None:
    """Render portfolio totals and allocation weights before report generation."""
    portfolio_data = portfolio.as_dict()
    columns = st.columns(3)
    columns[0].metric(
        "Growth Portfolio",
        f"${portfolio_data['growth_portfolio']:,.2f}",
    )
    columns[1].metric(
        "Hedging Portfolio",
        f"${portfolio_data['hedging_portfolio']:,.2f}",
    )
    columns[2].metric("Total Assets", f"${portfolio_data['total_assets']:,.2f}")

    allocation_columns = st.columns(2)
    allocation_columns[0].metric(
        "Growth Allocation",
        f"{portfolio_data['growth_allocation']:.1%}",
    )
    allocation_columns[1].metric(
        "Hedging Allocation",
        f"{portfolio_data['hedging_allocation']:.1%}",
    )


def generate_client_report(
    client_name: str,
    report_date: date,
    portfolio: PortfolioModel,
    cash_flow_df: pd.DataFrame,
    discount_curve_df: pd.DataFrame,
    attribution_inputs: dict[str, float],
) -> None:
    """Generate analytics, display metrics, and create report downloads."""
    payload = build_liability_payload(cash_flow_df, discount_curve_df)
    if payload is None:
        return

    try:
        warm_up_backend(API_BASE_URL)
        present_value = post_liability_endpoint("pv", payload)
        dv01 = post_liability_endpoint("dv01", payload)
        duration = post_liability_endpoint("duration", payload)
        attribution = post_api_json(
            API_BASE_URL,
            "reporting/funding-attribution",
            attribution_inputs,
        )
        multi_hedge = post_api_json(
            API_BASE_URL,
            "hedging/multi-instrument",
            default_multi_hedge_payload(
                asset_market_value=asset_market_value,
                liability_pv=liability_pv,
            ),
        )
    except requests.RequestException as exc:
        st.error(render_backend_error("generate client report", exc))
        return

    liability_pv = present_value["present_value"]
    if liability_pv == 0.0:
        st.error("Funding ratio is undefined when liability PV is zero.")
        return

    portfolio_data = portfolio.as_dict()
    asset_market_value = portfolio.total_assets()
    report_data = {
        "client_name": client_name,
        "report_date": report_date.isoformat(),
        **portfolio_data,
        "asset_market_value": asset_market_value,
        "liability_pv": liability_pv,
        "funding_ratio": asset_market_value / liability_pv,
        "surplus_deficit": asset_market_value - liability_pv,
        "liability_dv01": dv01["dv01"],
        "macaulay_duration": duration["macaulay_duration"],
        "modified_duration": duration["modified_duration"],
        **prefix_keys(attribution, "attribution"),
        "multi_hedge_recommendation": multi_hedge["recommendation"],
        "multi_hedge_hedge_ratio": multi_hedge["hedge_ratio"],
        "multi_hedge_residual_risk_score": multi_hedge["comparison"][
            "multi_instrument_krd_hedge"
        ]["residual_risk_score"],
        "single_hedge_residual_risk_score": multi_hedge["comparison"][
            "single_dv01_hedge"
        ]["residual_risk_score"],
        "multi_hedge_allocations": multi_hedge["recommended_allocations"],
        "multi_hedge_residual_krd": multi_hedge["residual_krd"],
        "multi_hedge_stress_results": multi_hedge["stress_results"],
    }

    render_metrics(report_data)
    render_attribution_summary(report_data)
    render_multi_hedge_summary(report_data)
    render_visualization(report_data)
    render_downloads(report_data)


def post_liability_endpoint(
    endpoint: str,
    payload: dict[str, dict[int, float]],
) -> dict[str, float]:
    """POST a liability payload to an API endpoint and return JSON data."""
    return post_api_json(API_BASE_URL, f"liability/{endpoint}", payload)


def render_metrics(report_data: dict[str, float | str]) -> None:
    """Render report metrics in columns."""
    columns = st.columns(6)
    columns[0].metric(
        "Total Assets",
        f"${float(report_data['total_assets']):,.2f}",
    )
    columns[1].metric("Liability PV", f"${float(report_data['liability_pv']):,.2f}")
    columns[2].metric("Funding Ratio", f"{float(report_data['funding_ratio']):.2f}")
    columns[3].metric(
        "Surplus / Deficit",
        f"${float(report_data['surplus_deficit']):,.2f}",
    )
    columns[4].metric(
        "Liability DV01",
        f"${float(report_data['liability_dv01']):,.2f}",
    )
    columns[5].metric(
        "Modified Duration",
        f"{float(report_data['modified_duration']):.2f}",
    )


def render_visualization(report_data: dict[str, float | str]) -> None:
    """Render a compact report summary chart."""
    chart_df = pd.DataFrame(
        {
            "Measure": ["Total Assets", "Liability PV", "Surplus / Deficit"],
            "Value": [
                float(report_data["total_assets"]),
                float(report_data["liability_pv"]),
                float(report_data["surplus_deficit"]),
            ],
        }
    )
    fig = px.bar(
        chart_df,
        x="Measure",
        y="Value",
        labels={"Value": "Value"},
    )
    fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)

    allocation_df = pd.DataFrame(
        {
            "Portfolio": ["Growth Portfolio", "Hedging Portfolio"],
            "Value": [
                float(report_data["growth_portfolio"]),
                float(report_data["hedging_portfolio"]),
            ],
        }
    )
    allocation_fig = px.pie(
        allocation_df,
        names="Portfolio",
        values="Value",
        title="Portfolio Allocation",
        hole=0.35,
    )
    allocation_fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(allocation_fig, use_container_width=True)


def render_attribution_summary(report_data: dict[str, float | str]) -> None:
    """Render period-over-period attribution included in client report."""
    st.subheader("Attribution Report")
    columns = st.columns(3)
    columns[0].metric(
        "Beginning Funding Ratio",
        f"{float(report_data['attribution_beginning_funding_ratio']):.2f}",
    )
    columns[1].metric(
        "Ending Funding Ratio",
        f"{float(report_data['attribution_ending_funding_ratio']):.2f}",
    )
    columns[2].metric(
        "Total Change",
        f"{float(report_data['attribution_total_change']):.2%}",
    )

    attribution_df = build_attribution_dataframe(report_data)
    st.dataframe(attribution_df, use_container_width=True, hide_index=True)


def render_multi_hedge_summary(report_data: dict[str, object]) -> None:
    """Render multi-instrument hedge recommendation in the client report page."""
    st.subheader("Multi-Instrument Hedge Recommendation")
    columns = st.columns(3)
    columns[0].metric(
        "Optimized Hedge Ratio",
        f"{float(report_data['multi_hedge_hedge_ratio']):.0%}",
    )
    columns[1].metric(
        "Single Hedge Residual Score",
        f"{float(report_data['single_hedge_residual_risk_score']):,.0f}",
    )
    columns[2].metric(
        "KRD Hedge Residual Score",
        f"{float(report_data['multi_hedge_residual_risk_score']):,.0f}",
    )
    st.info(str(report_data["multi_hedge_recommendation"]))
    st.dataframe(
        build_multi_hedge_allocation_dataframe(report_data),
        use_container_width=True,
        hide_index=True,
    )
    st.dataframe(
        build_multi_hedge_residual_dataframe(report_data),
        use_container_width=True,
        hide_index=True,
    )
    st.dataframe(
        build_multi_hedge_stress_dataframe(report_data),
        use_container_width=True,
        hide_index=True,
    )


def render_downloads(report_data: dict[str, float | str]) -> None:
    """Render CSV and PDF download buttons."""
    csv_bytes = create_csv_report(report_data)
    pdf_bytes = create_pdf_report(report_data)

    left, right = st.columns(2)
    with left:
        st.download_button(
            "Download CSV Report",
            data=csv_bytes,
            file_name="ldi_client_report.csv",
            mime="text/csv",
        )
    with right:
        st.download_button(
            "Download PDF Report",
            data=pdf_bytes,
            file_name="ldi_client_report.pdf",
            mime="application/pdf",
        )


def create_csv_report(report_data: dict[str, float | str]) -> bytes:
    """Create a downloadable one-row CSV summary."""
    summary_df = pd.DataFrame([report_data])
    return summary_df.to_csv(index=False).encode("utf-8")


def create_pdf_report(report_data: dict[str, float | str]) -> bytes:
    """Create a downloadable PDF client report using ReportLab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("LDI Pension Hedging Analyzer", styles["Heading1"]))
    elements.append(Paragraph("Client Report", styles["Title"]))
    elements.append(Spacer(1, 16))
    elements.append(
        Table(
            [
                ["Prepared for:", report_data["client_name"]],
                ["Prepared on:", report_data["report_date"]],
            ],
            colWidths=[1.4 * inch, 4.8 * inch],
        )
    )
    elements.append(Spacer(1, 18))

    elements.append(Paragraph("Executive Summary", styles["Heading2"]))
    for paragraph in generate_executive_summary(report_data):
        elements.append(Paragraph(paragraph, styles["Normal"]))
        elements.append(Spacer(1, 8))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Metric Table", styles["Heading2"]))
    metric_table = Table(
        [
            ["Metric", "Value"],
            ["Growth Portfolio", format_currency(float(report_data["growth_portfolio"]))],
            ["Hedging Portfolio", format_currency(float(report_data["hedging_portfolio"]))],
            ["Total Assets", format_currency(float(report_data["total_assets"]))],
            ["Liability PV", format_currency(float(report_data["liability_pv"]))],
            ["Funding Ratio", f"{float(report_data['funding_ratio']):.2f}"],
            ["Surplus / Deficit", format_currency(float(report_data["surplus_deficit"]))],
            ["Liability DV01", format_currency(float(report_data["liability_dv01"]))],
            ["Macaulay Duration", f"{float(report_data['macaulay_duration']):.2f}"],
            ["Modified Duration", f"{float(report_data['modified_duration']):.2f}"],
        ]
    )
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(metric_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Portfolio Allocation", styles["Heading2"]))
    allocation_table = Table(
        [
            ["Portfolio", "Market Value", "Allocation"],
            [
                "Growth Portfolio",
                format_currency(float(report_data["growth_portfolio"])),
                f"{float(report_data['growth_allocation']):.1%}",
            ],
            [
                "Hedging Portfolio",
                format_currency(float(report_data["hedging_portfolio"])),
                f"{float(report_data['hedging_allocation']):.1%}",
            ],
        ]
    )
    allocation_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(allocation_table)
    elements.append(Spacer(1, 12))

    residual_rows = [["Bucket", "Residual KRD"]]
    for row in build_multi_hedge_residual_dataframe(report_data).itertuples(index=False):
        residual_rows.append([row.Bucket, format_currency(float(row.Residual_KRD))])
    residual_table = Table(residual_rows)
    residual_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(residual_table)
    elements.append(Spacer(1, 12))

    stress_rows = [["Approach", "Scenario", "Funding Ratio Change"]]
    for row in build_multi_hedge_stress_dataframe(report_data).itertuples(index=False):
        stress_rows.append(
            [
                row.Approach,
                row.Scenario,
                f"{float(row.Funding_Ratio_Change):.2%}",
            ]
        )
    stress_table = Table(stress_rows)
    stress_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(stress_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Funding Ratio Attribution", styles["Heading2"]))
    attribution_rows = [["Driver", "Funding Ratio Contribution"]]
    for row in build_attribution_dataframe(report_data).itertuples(index=False):
        attribution_rows.append([row.Driver, f"{row.Contribution:.2%}"])
    attribution_table = Table(attribution_rows)
    attribution_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(attribution_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Multi-Instrument Hedge Recommendation", styles["Heading2"]))
    elements.append(Paragraph(str(report_data["multi_hedge_recommendation"]), styles["Normal"]))
    elements.append(Spacer(1, 8))
    allocation_rows = [["Instrument", "Recommended Notional", "Portfolio DV01"]]
    for row in build_multi_hedge_allocation_dataframe(report_data).itertuples(index=False):
        allocation_rows.append(
            [
                row.Instrument,
                format_currency(float(row.Notional)),
                format_currency(float(row.DV01)),
            ]
        )
    allocation_table = Table(allocation_rows)
    allocation_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(allocation_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Interpretation", styles["Heading2"]))
    elements.append(Paragraph(funding_interpretation(float(report_data["funding_ratio"])), styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(PageBreak())
    elements.append(Paragraph("Funding Status Chart", styles["Heading2"]))
    elements.append(create_funding_ratio_chart(float(report_data["funding_ratio"])))
    elements.append(Spacer(1, 18))

    elements.append(Paragraph("Asset vs Liability Chart", styles["Heading2"]))
    elements.append(create_asset_liability_chart(report_data))
    elements.append(Spacer(1, 18))

    elements.append(Paragraph("Portfolio Allocation Chart", styles["Heading2"]))
    elements.append(create_portfolio_allocation_chart(report_data))
    elements.append(Spacer(1, 18))

    elements.append(Paragraph("Methodology", styles["Heading2"]))
    methodology = [
        "Liability PV is calculated by discounting projected pension cash flows.",
        "DV01 measures sensitivity to a 1bp interest-rate move.",
        "Funding Ratio equals Total Assets divided by Liability PV.",
        "Total Assets equal Growth Portfolio plus Hedging Portfolio market value.",
    ]
    for item in methodology:
        elements.append(Paragraph(f"- {item}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_executive_summary(report_data: dict[str, float | str]) -> list[str]:
    """Generate client-facing key takeaways for the PDF report."""
    funding_ratio = float(report_data["funding_ratio"])
    liability_pv = float(report_data["liability_pv"])
    liability_dv01 = float(report_data["liability_dv01"])
    surplus_deficit = float(report_data["surplus_deficit"])
    growth_portfolio = float(report_data["growth_portfolio"])
    hedging_portfolio = float(report_data["hedging_portfolio"])
    growth_allocation = float(report_data["growth_allocation"])
    hedging_allocation = float(report_data["hedging_allocation"])

    funding_text = (
        f"The pension plan is currently {funding_ratio:.1%} funded, "
        f"with liabilities valued at {format_currency(liability_pv)}."
    )
    allocation_text = (
        f"Assets are split between a growth portfolio of "
        f"{format_currency(growth_portfolio)} ({growth_allocation:.1%}) and a "
        f"hedging portfolio of {format_currency(hedging_portfolio)} "
        f"({hedging_allocation:.1%})."
    )
    dv01_text = (
        f"The plan exhibits a liability DV01 of {format_currency(liability_dv01)}, "
        "indicating sensitivity to interest-rate movements."
    )
    if surplus_deficit >= 0.0:
        surplus_text = (
            f"A surplus of {format_currency(surplus_deficit)} is currently available, "
            "providing a cushion relative to discounted liabilities."
        )
    else:
        surplus_text = (
            f"A deficit of {format_currency(abs(surplus_deficit))} remains and may "
            "require additional hedging or asset growth to achieve full funding."
        )

    return [funding_text, allocation_text, dv01_text, surplus_text]


def create_funding_ratio_chart(funding_ratio: float) -> Drawing:
    """Create a ReportLab funding ratio bar chart."""
    drawing = Drawing(440, 220)
    chart = VerticalBarChart()
    chart.x = 70
    chart.y = 45
    chart.height = 125
    chart.width = 300
    chart.data = [[funding_ratio], [1.0]]
    chart.categoryAxis.categoryNames = ["Funding Ratio"]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(1.2, funding_ratio * 1.15)
    chart.valueAxis.valueStep = 0.2
    chart.bars[0].fillColor = funding_ratio_report_color(funding_ratio)
    chart.bars[1].fillColor = colors.lightgrey
    drawing.add(chart)
    drawing.add(String(82, 180, "Current Funding Ratio", fontSize=9))
    drawing.add(String(223, 180, "Full Funding Target", fontSize=9))
    drawing.add(String(185, 15, f"{funding_ratio:.1%} funded", fontSize=11))
    return drawing


def create_asset_liability_chart(report_data: dict[str, float | str]) -> Drawing:
    """Create a ReportLab bar chart comparing assets, liabilities, and surplus."""
    asset_market_value = float(report_data["total_assets"])
    liability_pv = float(report_data["liability_pv"])
    surplus_deficit = float(report_data["surplus_deficit"])
    max_value = max(abs(asset_market_value), abs(liability_pv), abs(surplus_deficit))

    drawing = Drawing(440, 240)
    chart = VerticalBarChart()
    chart.x = 55
    chart.y = 55
    chart.height = 140
    chart.width = 330
    chart.data = [[asset_market_value, liability_pv, surplus_deficit]]
    chart.categoryAxis.categoryNames = ["Assets", "Liabilities", "Surplus"]
    chart.valueAxis.valueMin = min(0, surplus_deficit * 1.2)
    chart.valueAxis.valueMax = max_value * 1.2
    chart.valueAxis.valueStep = max_value / 4 if max_value else 1
    chart.bars[0].fillColor = colors.HexColor("#2563eb")
    drawing.add(chart)
    drawing.add(String(142, 20, "Total Assets vs Liability PV", fontSize=11))
    return drawing


def create_portfolio_allocation_chart(report_data: dict[str, float | str]) -> Drawing:
    """Create a ReportLab pie chart for growth and hedging allocation."""
    drawing = Drawing(440, 220)
    pie = Pie()
    pie.x = 145
    pie.y = 40
    pie.width = 150
    pie.height = 150
    pie.data = [
        float(report_data["growth_portfolio"]),
        float(report_data["hedging_portfolio"]),
    ]
    pie.labels = ["Growth", "Hedging"]
    pie.slices[0].fillColor = colors.HexColor("#2563eb")
    pie.slices[1].fillColor = colors.HexColor("#16a34a")
    drawing.add(pie)
    drawing.add(String(115, 18, "Growth and Hedging Portfolio Allocation", fontSize=11))
    return drawing


def funding_interpretation(funding_ratio: float) -> str:
    """Return funding status interpretation text."""
    if funding_ratio >= 1.0:
        return "Plan is fully funded."
    if funding_ratio >= 0.9:
        return "Plan is modestly underfunded."
    return "Plan is materially underfunded."


def format_currency(value: float) -> str:
    """Format a number as US currency."""
    return f"${value:,.2f}"


def build_attribution_dataframe(report_data: dict[str, float | str]) -> pd.DataFrame:
    """Return attribution report data in display order."""
    return pd.DataFrame(
        {
            "Driver": [
                "Asset return",
                "Liability discount-rate",
                "Cash flow / benefits",
                "Hedge",
                "Residual",
            ],
            "Contribution": [
                float(report_data["attribution_asset_return_contribution"]),
                float(report_data["attribution_liability_discount_rate_contribution"]),
                float(report_data["attribution_cash_flow_contribution"]),
                float(report_data["attribution_hedge_contribution"]),
                float(report_data["attribution_residual_contribution"]),
            ],
        }
    )


def build_multi_hedge_allocation_dataframe(report_data: dict[str, object]) -> pd.DataFrame:
    """Return nonzero recommended multi-hedge allocations for reporting."""
    allocations = list(report_data["multi_hedge_allocations"])
    rows = [
        {
            "Instrument": allocation["name"],
            "Notional": float(allocation["recommended_notional"]),
            "DV01": float(allocation["portfolio_dv01"]),
        }
        for allocation in allocations
        if abs(float(allocation["recommended_notional"])) > 1.0
    ]
    return pd.DataFrame(rows)


def build_multi_hedge_residual_dataframe(report_data: dict[str, object]) -> pd.DataFrame:
    """Return residual KRD by bucket for reporting."""
    residual_krd = dict(report_data["multi_hedge_residual_krd"])
    return pd.DataFrame(
        {
            "Bucket": list(residual_krd.keys()),
            "Residual_KRD": [float(value) for value in residual_krd.values()],
        }
    )


def build_multi_hedge_stress_dataframe(report_data: dict[str, object]) -> pd.DataFrame:
    """Return single-vs-multi stress comparison for reporting."""
    stress_results = dict(report_data["multi_hedge_stress_results"])
    rows = []
    for approach_key, approach_label in (
        ("single_dv01_hedge", "Single DV01 Hedge"),
        ("multi_instrument_krd_hedge", "Multi-Instrument KRD Hedge"),
    ):
        for row in stress_results[approach_key]:
            rows.append(
                {
                    "Approach": approach_label,
                    "Scenario": row["scenario"],
                    "Funding_Ratio_Change": float(row["funding_ratio_change"]),
                }
            )
    return pd.DataFrame(rows)


def default_multi_hedge_payload(
    asset_market_value: float,
    liability_pv: float,
) -> dict[str, object]:
    """Return report-ready default KRD optimization inputs."""
    return {
        "liability_krd": {
            "1Y": 50_000.0,
            "5Y": 150_000.0,
            "10Y": 400_000.0,
            "20Y": 350_000.0,
            "30Y": 250_000.0,
        },
        "asset_market_value": asset_market_value,
        "liability_pv": liability_pv,
    }


def prefix_keys(data: dict[str, float], prefix: str) -> dict[str, float]:
    """Prefix dictionary keys for flat report export."""
    return {f"{prefix}_{key}": value for key, value in data.items()}


def funding_ratio_report_color(funding_ratio: float) -> colors.Color:
    """Return ReportLab color for funding ratio status."""
    if funding_ratio >= 1.0:
        return colors.HexColor("#15803d")
    if funding_ratio >= 0.9:
        return colors.HexColor("#ca8a04")
    return colors.HexColor("#dc2626")


def build_liability_payload(
    cash_flow_df: pd.DataFrame,
    discount_curve_df: pd.DataFrame,
) -> dict[str, dict[int, float]] | None:
    """Convert Streamlit table data into the liability API payload."""
    clean_cash_flows = prepare_cash_flow_dataframe(cash_flow_df)
    clean_discount_curve = prepare_discount_curve_dataframe(discount_curve_df)

    if clean_cash_flows.empty:
        st.error("Cash flow table must contain at least one valid row.")
        return None
    if clean_discount_curve.empty:
        st.error("Discount curve table must contain at least one valid row.")
        return None

    return {
        "cash_flows": dict(
            zip(clean_cash_flows["year"], clean_cash_flows["cash_flow"])
        ),
        "discount_curve": dict(
            zip(clean_discount_curve["year"], clean_discount_curve["discount_rate"])
        ),
    }


def prepare_cash_flow_dataframe(cash_flow_df: pd.DataFrame) -> pd.DataFrame:
    """Return normalized cash-flow table rows for API calls."""
    clean_df = cash_flow_df.copy()
    clean_df["year"] = pd.to_numeric(clean_df["year"], errors="coerce")
    clean_df["cash_flow"] = pd.to_numeric(clean_df["cash_flow"], errors="coerce")
    clean_df = clean_df.dropna(subset=["year", "cash_flow"])
    clean_df["year"] = clean_df["year"].astype(int)
    return clean_df.sort_values("year")


def prepare_discount_curve_dataframe(discount_curve_df: pd.DataFrame) -> pd.DataFrame:
    """Return normalized discount-curve rows for API calls."""
    clean_df = discount_curve_df.copy()
    clean_df["year"] = pd.to_numeric(clean_df["year"], errors="coerce")
    clean_df["discount_rate"] = pd.to_numeric(
        clean_df["discount_rate"],
        errors="coerce",
    )
    clean_df = clean_df.dropna(subset=["year", "discount_rate"])
    clean_df["year"] = clean_df["year"].astype(int)
    return clean_df.sort_values("year")


if __name__ == "__main__":
    main()
