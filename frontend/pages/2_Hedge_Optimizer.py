"""Streamlit page for swap-based liability DV01 hedging."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]

if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from api_client import post_api_json, render_backend_error, warm_up_backend


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")


def main() -> None:
    """Render the hedge optimizer page."""
    st.set_page_config(
        page_title="Hedge Optimizer",
        layout="wide",
    )

    st.title("Hedge Optimizer")

    st.header("Inputs")
    liability_dv01, swap_notional, fixed_rate, maturity_years = render_inputs()

    st.header("Analytics")
    if st.button("Calculate Hedge", type="primary"):
        calculate_hedge(
            liability_dv01=liability_dv01,
            swap_notional=swap_notional,
            fixed_rate=fixed_rate,
            maturity_years=maturity_years,
        )

    st.divider()
    st.header("Hedge Effectiveness Summary")
    render_hedge_effectiveness_section(liability_dv01=liability_dv01)


def render_inputs() -> tuple[float, float, float, int]:
    """Render hedge optimizer input controls."""
    left, right = st.columns(2)

    with left:
        liability_dv01 = st.number_input(
            "Liability DV01",
            min_value=0.0,
            value=5_000.0,
            step=100.0,
            format="%.2f",
        )
        swap_notional = st.number_input(
            "Swap Notional",
            min_value=1.0,
            value=1_000_000.0,
            step=100_000.0,
            format="%.2f",
        )

    with right:
        fixed_rate = st.number_input(
            "Fixed Rate",
            min_value=0.0,
            value=0.04,
            step=0.001,
            format="%.4f",
        )
        maturity_years = st.number_input(
            "Maturity Years",
            min_value=1,
            value=10,
            step=1,
        )

    return liability_dv01, swap_notional, fixed_rate, int(maturity_years)


def calculate_hedge(
    liability_dv01: float,
    swap_notional: float,
    fixed_rate: float,
    maturity_years: int,
) -> None:
    """Call the backend hedge endpoint and display hedge analytics."""
    payload = {
        "notional": swap_notional,
        "fixed_rate": fixed_rate,
        "maturity_years": maturity_years,
        "discount_curve": build_flat_discount_curve(
            rate=fixed_rate,
            maturity_years=maturity_years,
        ),
        "liability_dv01": liability_dv01,
    }

    try:
        warm_up_backend(API_BASE_URL)
        result = post_api_json(
            API_BASE_URL,
            "hedging/hedge-notional",
            payload,
        )
    except requests.RequestException as exc:
        st.error(render_backend_error("calculate hedge", exc))
        return

    swap_dv01 = result["swap_dv01"]
    hedge_notional = result["hedge_notional"]
    hedge_dv01 = hedge_notional / swap_notional * swap_dv01
    before_hedge_risk = liability_dv01
    after_hedge_risk = liability_dv01 - hedge_dv01

    render_metrics(
        liability_dv01=liability_dv01,
        swap_dv01=swap_dv01,
        hedge_notional=hedge_notional,
    )

    st.header("Visualization")
    render_risk_chart(
        before_hedge_risk=before_hedge_risk,
        after_hedge_risk=after_hedge_risk,
    )


def build_flat_discount_curve(rate: float, maturity_years: int) -> dict[int, float]:
    """Build a flat annual discount curve for the swap maturity."""
    return {year: rate for year in range(1, maturity_years + 1)}


def render_metrics(
    liability_dv01: float,
    swap_dv01: float,
    hedge_notional: float,
) -> None:
    """Render hedge analytics in metric columns."""
    columns = st.columns(3)
    columns[0].metric("Liability DV01", f"${liability_dv01:,.2f}")
    columns[1].metric("Swap DV01", f"${swap_dv01:,.2f}")
    columns[2].metric("Hedge Notional", f"${hedge_notional:,.2f}")


def render_risk_chart(before_hedge_risk: float, after_hedge_risk: float) -> None:
    """Render a bar chart comparing DV01 risk before and after hedging."""
    risk_df = pd.DataFrame(
        {
            "Scenario": ["Before Hedge Risk", "After Hedge Risk"],
            "DV01 Risk": [before_hedge_risk, after_hedge_risk],
        }
    )

    fig = px.bar(
        risk_df,
        x="Scenario",
        y="DV01 Risk",
        labels={"DV01 Risk": "DV01 Risk"},
    )
    fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)


def render_hedge_effectiveness_section(liability_dv01: float) -> None:
    """Render hedge effectiveness controls and metrics."""
    left, right = st.columns(2)
    with left:
        hedge_dv01 = st.number_input(
            "Hedging Portfolio DV01",
            min_value=0.0,
            value=3_900.0,
            step=100.0,
            format="%.2f",
        )
        asset_market_value = st.number_input(
            "Total Assets",
            min_value=0.0,
            value=5_200_000.0,
            step=100_000.0,
            format="%.2f",
        )
    with right:
        liability_pv = st.number_input(
            "Liability PV",
            min_value=1.0,
            value=5_600_000.0,
            step=100_000.0,
            format="%.2f",
        )
        target_hedge_ratio = st.number_input(
            "Target Hedge Ratio",
            min_value=0.0,
            value=0.90,
            step=0.05,
            format="%.2f",
        )
        swap_dv01_per_notional = st.number_input(
            "Swap DV01 per $1 Notional",
            min_value=0.0,
            value=0.0005,
            step=0.0001,
            format="%.6f",
        )

    if st.button("Calculate Hedge Effectiveness"):
        payload = {
            "liability_dv01": liability_dv01,
            "hedge_dv01": hedge_dv01,
            "asset_market_value": asset_market_value,
            "liability_pv": liability_pv,
            "target_hedge_ratio": target_hedge_ratio,
            "swap_dv01_per_notional": swap_dv01_per_notional,
        }
        try:
            warm_up_backend(API_BASE_URL)
            result = post_api_json(API_BASE_URL, "hedging/effectiveness", payload)
        except requests.RequestException as exc:
            st.error(render_backend_error("calculate hedge effectiveness", exc))
            return

        columns = st.columns(4)
        columns[0].metric("Hedge Ratio", f"{result['hedge_ratio']:.0%}")
        columns[1].metric("Percent Hedged", f"{result['percent_hedged']:.0%}")
        columns[2].metric("Residual DV01", f"${result['residual_dv01']:,.2f}")
        required_notional = result["required_incremental_notional"]
        columns[3].metric(
            "IRS Notional to Target",
            "N/A" if required_notional is None else f"${required_notional:,.2f}",
        )
        st.info(result["recommendation"])

        sensitivity_df = pd.DataFrame(result["funding_ratio_sensitivity"]).T
        st.dataframe(sensitivity_df, use_container_width=True)
        chart_df = sensitivity_df.reset_index(names="Shock")[
            ["Shock", "unhedged_change", "hedged_change"]
        ].melt(
            id_vars="Shock",
            var_name="Measure",
            value_name="Funding Ratio Change",
        )
        fig = px.bar(
            chart_df,
            x="Shock",
            y="Funding Ratio Change",
            color="Measure",
            barmode="group",
        )
        fig.update_layout(yaxis_tickformat=".2%")
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
