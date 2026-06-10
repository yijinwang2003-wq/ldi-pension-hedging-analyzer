"""Streamlit page for multi-instrument KRD hedge optimization."""

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
KRD_BUCKETS = ["1Y", "5Y", "10Y", "20Y", "30Y"]


def main() -> None:
    """Render the multi-instrument hedge optimizer page."""
    st.set_page_config(
        page_title="Multi-Instrument Hedge Optimizer",
        layout="wide",
    )

    st.title("Multi-Instrument Hedge Optimizer")

    st.header("Liability KRD Profile")
    liability_krd_df = st.data_editor(
        default_liability_krd(),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="multi_hedge_liability_krd",
    )

    st.header("Available Hedge Instruments")
    instrument_df = st.data_editor(
        default_instruments(),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="multi_hedge_instruments",
    )

    left, right = st.columns(2)
    with left:
        asset_market_value = st.number_input(
            "Stress Test Assets",
            min_value=0.0,
            value=100_000_000.0,
            step=1_000_000.0,
            format="%.2f",
        )
    with right:
        liability_pv = st.number_input(
            "Stress Test Liability PV",
            min_value=1.0,
            value=100_000_000.0,
            step=1_000_000.0,
            format="%.2f",
        )

    if st.button("Optimize Multi-Instrument Hedge", type="primary"):
        optimize_hedge(
            liability_krd_df=liability_krd_df,
            instrument_df=instrument_df,
            asset_market_value=asset_market_value,
            liability_pv=liability_pv,
        )


def optimize_hedge(
    liability_krd_df: pd.DataFrame,
    instrument_df: pd.DataFrame,
    asset_market_value: float,
    liability_pv: float,
) -> None:
    """Call the backend optimizer and render results."""
    payload = {
        "liability_krd": liability_krd_from_dataframe(liability_krd_df),
        "selected_instruments": instruments_from_dataframe(instrument_df),
        "asset_market_value": asset_market_value,
        "liability_pv": liability_pv,
    }

    try:
        warm_up_backend(API_BASE_URL)
        result = post_api_json(API_BASE_URL, "hedging/multi-instrument", payload)
    except requests.RequestException as exc:
        st.error(render_backend_error("optimize multi-instrument hedge", exc))
        return

    render_optimized_allocations(result)
    render_krd_matching_visualization(result)
    render_stress_testing_comparison(result)
    render_recommendation_summary(result)


def render_optimized_allocations(result: dict[str, object]) -> None:
    """Render allocation and comparison metrics."""
    st.header("Optimized Allocations")
    allocations_df = pd.DataFrame(result["recommended_allocations"])
    st.dataframe(
        allocations_df,
        use_container_width=True,
        hide_index=True,
    )

    comparison = result["comparison"]
    single = comparison["single_dv01_hedge"]
    multi = comparison["multi_instrument_krd_hedge"]
    columns = st.columns(4)
    columns[0].metric("Multi Hedge Ratio", f"{multi['hedge_ratio']:.0%}")
    columns[1].metric(
        "Single Residual Score",
        f"{single['residual_risk_score']:,.0f}",
    )
    columns[2].metric(
        "Multi Residual Score",
        f"{multi['residual_risk_score']:,.0f}",
    )
    columns[3].metric(
        "DV01 Mismatch",
        f"{multi['total_dv01_mismatch']:,.0f}",
    )


def render_krd_matching_visualization(result: dict[str, object]) -> None:
    """Render liability, hedge, and residual KRD charts."""
    st.header("KRD Matching Visualization")
    liability_krd = result["liability_krd"]
    portfolio_krd = result["portfolio_krd"]
    residual_krd = result["residual_krd"]

    match_df = pd.DataFrame(
        {
            "Bucket": list(liability_krd.keys()),
            "Liability KRD": list(liability_krd.values()),
            "Hedge KRD": [portfolio_krd[bucket] for bucket in liability_krd],
        }
    ).melt(id_vars="Bucket", var_name="Series", value_name="KRD")
    fig = px.bar(match_df, x="Bucket", y="KRD", color="Series", barmode="group")
    fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)

    residual_df = pd.DataFrame(
        {
            "Bucket": list(residual_krd.keys()),
            "Residual KRD": list(residual_krd.values()),
        }
    )
    residual_fig = px.bar(residual_df, x="Bucket", y="Residual KRD")
    residual_fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(residual_fig, use_container_width=True)


def render_stress_testing_comparison(result: dict[str, object]) -> None:
    """Render funding-ratio stress comparison for single and multi hedges."""
    st.header("Stress Testing Comparison")
    stress_results = result["stress_results"]
    single_df = pd.DataFrame(stress_results["single_dv01_hedge"])
    single_df["Approach"] = "Single DV01 Hedge"
    multi_df = pd.DataFrame(stress_results["multi_instrument_krd_hedge"])
    multi_df["Approach"] = "Multi-Instrument KRD Hedge"
    stress_df = pd.concat([single_df, multi_df], ignore_index=True)

    st.dataframe(stress_df, use_container_width=True, hide_index=True)
    fig = px.bar(
        stress_df,
        x="scenario",
        y="funding_ratio_change",
        color="Approach",
        barmode="group",
        labels={
            "scenario": "Scenario",
            "funding_ratio_change": "Funding Ratio Change",
        },
    )
    fig.update_layout(yaxis_tickformat=".2%")
    st.plotly_chart(fig, use_container_width=True)


def render_recommendation_summary(result: dict[str, object]) -> None:
    """Render narrative hedge recommendation."""
    st.header("Hedge Recommendation Summary")
    st.info(str(result["recommendation"]))


def default_liability_krd() -> pd.DataFrame:
    """Return default liability KRD profile."""
    if "uploaded_liability_krd" in st.session_state:
        uploaded_krd = st.session_state["uploaded_liability_krd"]
        return pd.DataFrame(
            {
                "bucket": list(uploaded_krd.keys()),
                "liability_krd": list(uploaded_krd.values()),
            }
        )

    return pd.DataFrame(
        {
            "bucket": KRD_BUCKETS,
            "liability_krd": [
                50_000.0,
                150_000.0,
                400_000.0,
                350_000.0,
                250_000.0,
            ],
        }
    )


def default_instruments() -> pd.DataFrame:
    """Return default hedge instrument universe in editable table form."""
    return pd.DataFrame(
        [
            {
                "include": True,
                "name": "10Y Interest Rate Swap",
                "type": "swap",
                "notional": 1_000_000.0,
                "dv01": -850.0,
                "1Y": 0.0,
                "5Y": -150.0,
                "10Y": -500.0,
                "20Y": -150.0,
                "30Y": -50.0,
            },
            {
                "include": True,
                "name": "30Y Interest Rate Swap",
                "type": "swap",
                "notional": 1_000_000.0,
                "dv01": -1_950.0,
                "1Y": 0.0,
                "5Y": -75.0,
                "10Y": -250.0,
                "20Y": -625.0,
                "30Y": -1_000.0,
            },
            {
                "include": True,
                "name": "10Y Treasury Bond",
                "type": "treasury",
                "notional": 1_000_000.0,
                "dv01": -700.0,
                "1Y": -25.0,
                "5Y": -175.0,
                "10Y": -425.0,
                "20Y": -60.0,
                "30Y": -15.0,
            },
            {
                "include": True,
                "name": "30Y Treasury Bond",
                "type": "treasury",
                "notional": 1_000_000.0,
                "dv01": -1_650.0,
                "1Y": -10.0,
                "5Y": -60.0,
                "10Y": -175.0,
                "20Y": -525.0,
                "30Y": -880.0,
            },
        ]
    )


def liability_krd_from_dataframe(dataframe: pd.DataFrame) -> dict[str, float]:
    """Convert liability KRD table into API payload dictionary."""
    clean_df = dataframe.dropna(subset=["bucket", "liability_krd"]).copy()
    clean_df["liability_krd"] = pd.to_numeric(
        clean_df["liability_krd"],
        errors="coerce",
    )
    clean_df = clean_df.dropna(subset=["liability_krd"])
    return dict(zip(clean_df["bucket"].astype(str), clean_df["liability_krd"]))


def instruments_from_dataframe(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    """Convert editable instrument table into API payload rows."""
    clean_df = dataframe.copy()
    clean_df = clean_df[clean_df["include"].astype(bool)]
    instruments = []
    for row in clean_df.to_dict(orient="records"):
        instruments.append(
            {
                "name": str(row["name"]),
                "type": str(row["type"]),
                "notional": float(row["notional"]),
                "dv01": float(row["dv01"]),
                "krd": {
                    bucket: float(row.get(bucket, 0.0))
                    for bucket in KRD_BUCKETS
                },
            }
        )
    return instruments


if __name__ == "__main__":
    main()
