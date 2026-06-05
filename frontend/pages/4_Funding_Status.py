"""Streamlit page for pension funding status analytics."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models.portfolio import PortfolioModel


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")


def main() -> None:
    """Render the funding status page."""
    st.set_page_config(
        page_title="Funding Status",
        layout="wide",
    )

    st.title("Funding Status")

    st.header("Inputs")
    (
        growth_portfolio,
        hedging_portfolio,
        asset_market_value,
        cash_flow_df,
        discount_curve_df,
    ) = render_inputs()

    st.header("Analytics")
    if st.button("Calculate Funding Status", type="primary"):
        calculate_funding_status(
            growth_portfolio=growth_portfolio,
            hedging_portfolio=hedging_portfolio,
            asset_market_value=asset_market_value,
            cash_flow_df=cash_flow_df,
            discount_curve_df=discount_curve_df,
        )


def render_inputs() -> tuple[float, float, float, pd.DataFrame, pd.DataFrame]:
    """Render funding status inputs and editable liability tables."""
    left, right = st.columns(2)

    with left:
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

    with right:
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
    growth_portfolio = portfolio.growth_portfolio()
    hedging_portfolio = portfolio.hedging_portfolio()
    asset_market_value = portfolio.total_assets()
    render_portfolio_summary_metrics(
        growth_portfolio=growth_portfolio,
        hedging_portfolio=hedging_portfolio,
        asset_market_value=asset_market_value,
    )

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

    return (
        growth_portfolio,
        hedging_portfolio,
        asset_market_value,
        cash_flow_df,
        discount_curve_df,
    )


def calculate_funding_status(
    growth_portfolio: float,
    hedging_portfolio: float,
    asset_market_value: float,
    cash_flow_df: pd.DataFrame,
    discount_curve_df: pd.DataFrame,
) -> None:
    """Calculate funding status using liability analytics API endpoints."""
    payload = build_liability_payload(cash_flow_df, discount_curve_df)
    if payload is None:
        return

    try:
        present_value = post_liability_endpoint("pv", payload)
        dv01 = post_liability_endpoint("dv01", payload)
    except requests.RequestException as exc:
        st.error(f"Unable to calculate funding status: {exc}")
        return

    liability_pv = present_value["present_value"]
    liability_dv01 = dv01["dv01"]
    if liability_pv == 0.0:
        st.error("Funding ratio is undefined when liability PV is zero.")
        return

    funding_ratio = asset_market_value / liability_pv
    surplus = asset_market_value - liability_pv

    render_metrics(
        asset_market_value=asset_market_value,
        liability_pv=liability_pv,
        funding_ratio=funding_ratio,
        surplus=surplus,
        liability_dv01=liability_dv01,
    )

    st.header("Funding Ratio Attribution")
    render_funding_ratio_attribution(
        growth_portfolio=growth_portfolio,
        hedging_portfolio=hedging_portfolio,
        asset_market_value=asset_market_value,
    )

    st.header("Visualization")
    render_portfolio_allocation_pie_chart(
        growth_portfolio=growth_portfolio,
        hedging_portfolio=hedging_portfolio,
    )
    render_portfolio_type_chart(
        growth_portfolio=growth_portfolio,
        hedging_portfolio=hedging_portfolio,
    )
    render_asset_liability_chart(
        asset_market_value=asset_market_value,
        liability_pv=liability_pv,
    )
    render_surplus_chart(surplus=surplus)


def post_liability_endpoint(
    endpoint: str,
    payload: dict[str, dict[int, float]],
) -> dict[str, float]:
    """POST a liability payload to an API endpoint and return JSON data."""
    response = requests.post(
        f"{API_BASE_URL}/liability/{endpoint}",
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def render_portfolio_summary_metrics(
    growth_portfolio: float,
    hedging_portfolio: float,
    asset_market_value: float,
) -> None:
    """Render top-level portfolio allocation metrics."""
    columns = st.columns(3)
    columns[0].metric("Growth Portfolio", f"${growth_portfolio:,.0f}")
    columns[1].metric("Hedging Portfolio", f"${hedging_portfolio:,.0f}")
    columns[2].metric("Total Assets", f"${asset_market_value:,.0f}")


def render_funding_ratio_attribution(
    growth_portfolio: float,
    hedging_portfolio: float,
    asset_market_value: float,
) -> None:
    """Render growth and hedging allocation attribution metrics."""
    if asset_market_value == 0.0:
        st.error("Portfolio allocation is undefined when total assets are zero.")
        return

    growth_allocation = growth_portfolio / asset_market_value
    hedging_allocation = hedging_portfolio / asset_market_value

    columns = st.columns(2)
    columns[0].metric("Growth Portfolio", f"{growth_allocation:.0%}")
    columns[1].metric("Hedging Portfolio", f"{hedging_allocation:.0%}")


def render_metrics(
    asset_market_value: float,
    liability_pv: float,
    funding_ratio: float,
    surplus: float,
    liability_dv01: float,
) -> None:
    """Render funding status metrics in columns."""
    columns = st.columns(5)
    columns[0].metric("Total Assets", f"${asset_market_value:,.2f}")
    columns[1].metric("Liability PV", f"${liability_pv:,.2f}")
    render_funding_ratio_card(columns[2], funding_ratio)
    columns[3].metric("Surplus / Deficit", f"${surplus:,.2f}")
    columns[4].metric("Liability DV01", f"${liability_dv01:,.2f}")


def render_funding_ratio_card(column: st.delta_generator.DeltaGenerator, funding_ratio: float) -> None:
    """Render a color-coded funding ratio card."""
    color = funding_ratio_color(funding_ratio)
    column.markdown(
        f"""
        <div style="
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.75rem 1rem;
            min-height: 96px;
            background: white;
        ">
            <div style="font-size: 0.875rem; color: #6b7280;">
                Funding Ratio
            </div>
            <div style="font-size: 2rem; font-weight: 600; color: {color};">
                {funding_ratio:.2f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def funding_ratio_color(funding_ratio: float) -> str:
    """Return status color for a funding ratio."""
    if funding_ratio >= 1.00:
        return "#15803d"
    if funding_ratio >= 0.90:
        return "#ca8a04"
    return "#dc2626"


def render_portfolio_allocation_pie_chart(
    growth_portfolio: float,
    hedging_portfolio: float,
) -> None:
    """Render a pie chart of growth versus hedging portfolio allocation."""
    allocation_df = pd.DataFrame(
        {
            "Portfolio Type": ["Growth", "Hedging"],
            "Value": [growth_portfolio, hedging_portfolio],
        }
    )
    fig = px.pie(
        allocation_df,
        names="Portfolio Type",
        values="Value",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_portfolio_type_chart(
    growth_portfolio: float,
    hedging_portfolio: float,
) -> None:
    """Render a bar chart comparing growth and hedging portfolios."""
    portfolio_df = pd.DataFrame(
        {
            "Portfolio Type": ["Growth", "Hedging"],
            "Value": [growth_portfolio, hedging_portfolio],
        }
    )
    fig = px.bar(
        portfolio_df,
        x="Portfolio Type",
        y="Value",
        labels={"Value": "Market Value"},
    )
    fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)


def render_asset_liability_chart(
    asset_market_value: float,
    liability_pv: float,
) -> None:
    """Render a bar chart comparing assets and liabilities."""
    comparison_df = pd.DataFrame(
        {
            "Measure": ["Total Assets", "Liability PV"],
            "Value": [asset_market_value, liability_pv],
        }
    )
    fig = px.bar(
        comparison_df,
        x="Measure",
        y="Value",
        labels={"Value": "Market Value"},
    )
    fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)


def render_surplus_chart(surplus: float) -> None:
    """Render a bar chart for surplus or deficit."""
    surplus_df = pd.DataFrame(
        {
            "Measure": ["Surplus / Deficit"],
            "Value": [surplus],
        }
    )
    fig = px.bar(
        surplus_df,
        x="Measure",
        y="Value",
        labels={"Value": "Surplus / Deficit"},
    )
    fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)


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
