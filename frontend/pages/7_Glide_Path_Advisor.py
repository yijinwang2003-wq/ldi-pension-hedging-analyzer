"""Streamlit page for pension de-risking glide path recommendations."""

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
    """Render the glide path advisor page."""
    st.set_page_config(
        page_title="Glide Path Advisor",
        layout="wide",
    )

    st.title("Glide Path Advisor")

    first, second = st.columns(2)
    with first:
        funding_ratio = st.number_input(
            "Current Funding Ratio",
            min_value=0.0,
            value=0.92,
            step=0.01,
            format="%.2f",
        )
        current_hedge_ratio = st.number_input(
            "Current Hedge Ratio",
            min_value=0.0,
            value=0.68,
            step=0.01,
            format="%.2f",
        )
    with second:
        liability_dv01 = st.number_input(
            "Liability DV01",
            min_value=0.0,
            value=1_000_000.0,
            step=50_000.0,
            format="%.2f",
        )
        current_hedge_portfolio_dv01 = st.number_input(
            "Current Hedge Portfolio DV01",
            min_value=0.0,
            value=680_000.0,
            step=50_000.0,
            format="%.2f",
        )
        dv01_per_notional = st.number_input(
            "DV01 per $1 Notional",
            min_value=0.0,
            value=0.0005,
            step=0.0001,
            format="%.6f",
        )

    if st.button("Calculate Glide Path Recommendation", type="primary"):
        payload = {
            "funding_ratio": funding_ratio,
            "current_hedge_ratio": current_hedge_ratio,
            "liability_dv01": liability_dv01,
            "current_hedge_portfolio_dv01": current_hedge_portfolio_dv01,
            "dv01_per_notional": dv01_per_notional,
        }
        try:
            warm_up_backend(API_BASE_URL)
            result = post_api_json(API_BASE_URL, "hedging/glide-path", payload)
        except requests.RequestException as exc:
            st.error(render_backend_error("calculate glide path", exc))
            return

        render_recommendation(result)


def render_recommendation(result: dict[str, object]) -> None:
    """Render glide path metrics, chart, and narrative."""
    st.header("Gap Analysis")
    columns = st.columns(5)
    columns[0].metric("Funding Ratio", f"{float(result['funding_ratio']):.0%}")
    columns[1].metric(
        "Current Hedge Ratio",
        f"{float(result['current_hedge_ratio']):.0%}",
    )
    columns[2].metric(
        "Target Hedge Ratio",
        f"{float(result['target_hedge_ratio']):.0%}",
    )
    columns[3].metric(
        "Additional DV01",
        f"${float(result['additional_dv01_needed']):,.0f}",
    )
    suggested_notional = result["suggested_notional_change"]
    columns[4].metric(
        "Notional Change",
        "N/A" if suggested_notional is None else f"${float(suggested_notional):,.0f}",
    )

    st.info(str(result["narrative"]))

    st.header("Funding Ratio to Target Hedge Ratio")
    policy_df = pd.DataFrame(result["policy_curve"])
    fig = px.line(
        policy_df,
        x="funding_ratio",
        y="target_hedge_ratio",
        markers=True,
        labels={
            "funding_ratio": "Funding Ratio",
            "target_hedge_ratio": "Target Hedge Ratio",
        },
    )
    fig.add_scatter(
        x=[float(result["funding_ratio"])],
        y=[float(result["target_hedge_ratio"])],
        mode="markers",
        marker={"size": 14},
        name="Current Policy Point",
    )
    fig.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
