"""Streamlit page for Vasicek interest-rate scenario analysis."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]

if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from api_client import post_api_json, render_backend_error, warm_up_backend


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")
TIME_STEP = 0.25
MAX_DISPLAY_PATHS = 25


def main() -> None:
    """Render the scenario analysis page."""
    st.set_page_config(
        page_title="Scenario Analysis",
        layout="wide",
    )

    st.title("Scenario Analysis")

    st.header("Vasicek Monte Carlo Inputs")
    kappa, theta, sigma, r0, years, n_paths = render_inputs()

    if st.button("Generate Monte Carlo Paths", type="primary"):
        run_scenario_analysis(
            kappa=kappa,
            theta=theta,
            sigma=sigma,
            r0=r0,
            years=years,
            n_paths=n_paths,
        )

    st.divider()
    st.header("Curve Twist Scenarios")
    render_curve_twist_section()

    st.divider()
    st.header("Historical Stress Testing")
    render_historical_stress_section()

    st.divider()
    st.header("Nelson-Siegel Curve Builder")
    render_nelson_siegel_section()


def render_inputs() -> tuple[float, float, float, float, float, int]:
    """Render Vasicek model input controls."""
    left, middle, right = st.columns(3)

    with left:
        kappa = st.number_input(
            "Kappa",
            min_value=0.0001,
            value=0.30,
            step=0.05,
            format="%.4f",
        )
        theta = st.number_input(
            "Theta",
            value=0.04,
            step=0.005,
            format="%.4f",
        )

    with middle:
        sigma = st.number_input(
            "Sigma",
            min_value=0.0,
            value=0.01,
            step=0.0025,
            format="%.4f",
        )
        r0 = st.number_input(
            "Initial Rate",
            value=0.035,
            step=0.005,
            format="%.4f",
        )

    with right:
        years = st.number_input(
            "Years",
            min_value=0.25,
            value=10.0,
            step=0.25,
            format="%.2f",
        )
        n_paths = st.number_input(
            "Number of Paths",
            min_value=1,
            value=500,
            step=100,
        )

    return kappa, theta, sigma, r0, years, int(n_paths)


def run_scenario_analysis(
    kappa: float,
    theta: float,
    sigma: float,
    r0: float,
    years: float,
    n_paths: int,
) -> None:
    """Call the backend Vasicek endpoint and render scenario analytics."""
    payload = {
        "kappa": kappa,
        "theta": theta,
        "sigma": sigma,
        "r0": r0,
        "years": years,
        "dt": TIME_STEP,
        "n_paths": n_paths,
    }

    try:
        warm_up_backend(API_BASE_URL)
        result = post_api_json(
            API_BASE_URL,
            "scenarios/vasicek",
            payload,
        )
    except requests.RequestException as exc:
        st.error(render_backend_error("generate scenarios", exc))
        return

    paths = np.array(result["paths"], dtype=float)
    terminal_rates = np.array(result["terminal_rates"], dtype=float)
    summary = result["summary"]
    time_grid = np.arange(paths.shape[1]) * TIME_STEP

    st.header("Sample Paths Chart")
    render_sample_paths_chart(paths=paths, time_grid=time_grid)

    st.header("Terminal Rate Histogram")
    render_terminal_rate_histogram(terminal_rates=terminal_rates)

    st.header("Summary Metrics")
    render_summary_metrics(summary)


def render_sample_paths_chart(paths: np.ndarray, time_grid: np.ndarray) -> None:
    """Render a line chart for a readable subset of simulated paths."""
    n_display_paths = min(paths.shape[0], MAX_DISPLAY_PATHS)
    sample_paths = paths[:n_display_paths]

    chart_df = pd.DataFrame(sample_paths.T, index=time_grid)
    chart_df.index.name = "Year"
    chart_df.columns = [f"Path {index + 1}" for index in range(n_display_paths)]
    long_df = chart_df.reset_index().melt(
        id_vars="Year",
        var_name="Path",
        value_name="Rate",
    )

    fig = px.line(
        long_df,
        x="Year",
        y="Rate",
        color="Path",
        labels={"Rate": "Short Rate"},
    )
    fig.update_layout(showlegend=False, yaxis_tickformat=".2%")
    st.plotly_chart(fig, use_container_width=True)


def render_terminal_rate_histogram(terminal_rates: np.ndarray) -> None:
    """Render a histogram of terminal simulated short rates."""
    histogram_df = pd.DataFrame({"Terminal Rate": terminal_rates})
    fig = px.histogram(
        histogram_df,
        x="Terminal Rate",
        nbins=40,
        labels={"Terminal Rate": "Terminal Rate"},
    )
    fig.update_layout(yaxis_title="Path Count", xaxis_tickformat=".2%")
    st.plotly_chart(fig, use_container_width=True)


def render_summary_metrics(summary: dict[str, float]) -> None:
    """Render terminal-rate summary statistics in metric columns."""
    columns = st.columns(5)
    columns[0].metric("Mean", f"{summary['mean']:.2%}")
    columns[1].metric("Std", f"{summary['std']:.2%}")
    columns[2].metric("5%", f"{summary['5%']:.2%}")
    columns[3].metric("Median", f"{summary['50%']:.2%}")
    columns[4].metric("95%", f"{summary['95%']:.2%}")


def render_curve_twist_section() -> None:
    """Render curve-shape scenario inputs and results."""
    default_cash_flows = pd.DataFrame(
        {
            "year": [1, 5, 10],
            "cash_flow": [1_000_000.0, 1_250_000.0, 1_500_000.0],
        }
    )
    default_curve = pd.DataFrame(
        {
            "year": [1, 5, 10],
            "discount_rate": [0.040, 0.043, 0.047],
        }
    )
    default_custom_shocks = pd.DataFrame(
        {"year": [1, 5, 10], "shock_bps": [0.0, 50.0, 100.0]}
    )

    top_left, top_right = st.columns(2)
    with top_left:
        asset_market_value = st.number_input(
            "Scenario Total Assets",
            min_value=0.0,
            value=3_600_000.0,
            step=100_000.0,
            format="%.2f",
        )
        hedge_dv01 = st.number_input(
            "Scenario Hedge DV01",
            value=2_000.0,
            step=100.0,
            format="%.2f",
        )
    with top_right:
        use_custom_shock = st.checkbox("Include custom key-rate shock", value=True)

    left, middle, right = st.columns(3)
    with left:
        st.subheader("Cash Flows")
        cash_flow_df = st.data_editor(
            default_cash_flows,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="curve_twist_cash_flows",
        )
    with middle:
        st.subheader("Discount Curve")
        curve_df = st.data_editor(
            default_curve,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="curve_twist_curve",
        )
    with right:
        st.subheader("Custom Shock")
        custom_shock_df = st.data_editor(
            default_custom_shocks,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            disabled=not use_custom_shock,
            key="curve_twist_custom",
        )

    if st.button("Run Curve Twists"):
        payload = {
            "cash_flows": dataframe_to_dict(cash_flow_df, "cash_flow"),
            "discount_curve": dataframe_to_dict(curve_df, "discount_rate"),
            "asset_market_value": asset_market_value,
            "hedge_dv01": hedge_dv01,
        }
        if use_custom_shock:
            payload["custom_shocks_bps"] = dataframe_to_dict(
                custom_shock_df,
                "shock_bps",
            )

        try:
            warm_up_backend(API_BASE_URL)
            result = post_api_json(API_BASE_URL, "scenarios/curve-twists", payload)
        except requests.RequestException as exc:
            st.error(render_backend_error("run curve twist scenarios", exc))
            return

        results_df = pd.DataFrame(result["results"]).drop(columns=["shocks_bps"])
        st.dataframe(
            results_df,
            use_container_width=True,
            hide_index=True,
        )
        chart_df = results_df[
            [
                "scenario",
                "funding_ratio_change_unhedged",
                "funding_ratio_change_hedged",
            ]
        ].melt(
            id_vars="scenario",
            var_name="Measure",
            value_name="Funding Ratio Change",
        )
        fig = px.bar(
            chart_df,
            x="scenario",
            y="Funding Ratio Change",
            color="Measure",
            barmode="group",
        )
        fig.update_layout(yaxis_tickformat=".2%")
        st.plotly_chart(fig, use_container_width=True)


def render_nelson_siegel_section() -> None:
    """Render Nelson-Siegel market-point fitting controls."""
    default_market_points = pd.DataFrame(
        {
            "maturity": [1.0, 2.0, 5.0, 10.0, 30.0],
            "rate": [0.038, 0.039, 0.041, 0.044, 0.047],
        }
    )
    left, right = st.columns([2, 1])
    with left:
        market_df = st.data_editor(
            default_market_points,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="nelson_siegel_market",
        )
    with right:
        use_fixed_tau = st.checkbox("Use fixed tau", value=True)
        tau = st.number_input(
            "Tau",
            min_value=0.1,
            value=2.5,
            step=0.1,
            format="%.2f",
            disabled=not use_fixed_tau,
        )
        max_year = st.number_input("Output Years", min_value=1, value=30, step=1)

    if st.button("Build Nelson-Siegel Curve"):
        clean_df = market_df.dropna(subset=["maturity", "rate"]).copy()
        payload = {
            "maturities": clean_df["maturity"].astype(float).tolist(),
            "rates": clean_df["rate"].astype(float).tolist(),
            "tau": tau if use_fixed_tau else None,
            "output_years": list(range(1, int(max_year) + 1)),
        }
        try:
            warm_up_backend(API_BASE_URL)
            result = post_api_json(API_BASE_URL, "scenarios/nelson-siegel", payload)
        except requests.RequestException as exc:
            st.error(render_backend_error("build Nelson-Siegel curve", exc))
            return

        params = result["parameters"]
        columns = st.columns(4)
        columns[0].metric("Beta 0", f"{params['beta0']:.4f}")
        columns[1].metric("Beta 1", f"{params['beta1']:.4f}")
        columns[2].metric("Beta 2", f"{params['beta2']:.4f}")
        columns[3].metric("Tau", f"{params['tau']:.2f}")

        curve_df = pd.DataFrame(
            {
                "Year": [int(year) for year in result["discount_curve"].keys()],
                "Rate": [float(rate) for rate in result["discount_curve"].values()],
            }
        )
        fig = px.line(curve_df, x="Year", y="Rate", markers=True)
        fig.update_layout(yaxis_tickformat=".2%")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(curve_df, use_container_width=True, hide_index=True)


def render_historical_stress_section() -> None:
    """Render historical stress test inputs and charts."""
    default_liability_krd = pd.DataFrame(
        {
            "bucket": ["2Y", "5Y", "10Y", "20Y", "30Y"],
            "liability_krd": [50_000.0, 150_000.0, 400_000.0, 350_000.0, 250_000.0],
        }
    )
    default_hedge_krd = pd.DataFrame(
        {
            "bucket": ["2Y", "5Y", "10Y", "20Y", "30Y"],
            "hedge_krd": [-25_000.0, -100_000.0, -325_000.0, -275_000.0, -200_000.0],
        }
    )

    first, second = st.columns(2)
    with first:
        asset_market_value = st.number_input(
            "Historical Stress Assets",
            min_value=0.0,
            value=1_000_000_000.0,
            step=10_000_000.0,
            format="%.2f",
        )
    with second:
        liability_pv = st.number_input(
            "Historical Stress Liability PV",
            min_value=1.0,
            value=1_000_000_000.0,
            step=10_000_000.0,
            format="%.2f",
        )

    left, right = st.columns(2)
    with left:
        st.subheader("Liability KRD")
        liability_krd_df = st.data_editor(
            default_liability_krd,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="historical_liability_krd",
        )
    with right:
        st.subheader("Hedge KRD")
        hedge_krd_df = st.data_editor(
            default_hedge_krd,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="historical_hedge_krd",
        )

    if st.button("Run Historical Stress Tests"):
        payload = {
            "liability_krd": bucket_dataframe_to_dict(
                liability_krd_df,
                "liability_krd",
            ),
            "hedge_krd": bucket_dataframe_to_dict(hedge_krd_df, "hedge_krd"),
            "asset_market_value": asset_market_value,
            "liability_pv": liability_pv,
        }
        try:
            warm_up_backend(API_BASE_URL)
            result = post_api_json(API_BASE_URL, "scenarios/historical-stress", payload)
        except requests.RequestException as exc:
            st.error(render_backend_error("run historical stress tests", exc))
            return

        results_df = pd.DataFrame(result["results"])
        st.dataframe(results_df, use_container_width=True, hide_index=True)

        comparison_df = results_df[
            [
                "scenario",
                "funding_ratio_before",
                "funding_ratio_after_unhedged",
                "funding_ratio_after_hedged",
            ]
        ].melt(
            id_vars="scenario",
            var_name="Measure",
            value_name="Funding Ratio",
        )
        comparison_fig = px.bar(
            comparison_df,
            x="scenario",
            y="Funding Ratio",
            color="Measure",
            barmode="group",
        )
        comparison_fig.update_layout(yaxis_tickformat=".2%")
        st.plotly_chart(comparison_fig, use_container_width=True)

        severity_df = pd.DataFrame(result["ranked_by_severity"])
        severity_fig = px.bar(
            severity_df,
            x="scenario",
            y="hedged_funding_ratio_change",
            labels={"hedged_funding_ratio_change": "Hedged Funding Ratio Change"},
        )
        severity_fig.update_layout(yaxis_tickformat=".2%")
        st.plotly_chart(severity_fig, use_container_width=True)


def dataframe_to_dict(dataframe: pd.DataFrame, value_column: str) -> dict[int, float]:
    """Convert a year/value Streamlit table into an API dictionary."""
    clean_df = dataframe.dropna(subset=["year", value_column]).copy()
    clean_df["year"] = pd.to_numeric(clean_df["year"], errors="coerce")
    clean_df[value_column] = pd.to_numeric(clean_df[value_column], errors="coerce")
    clean_df = clean_df.dropna(subset=["year", value_column])
    return dict(zip(clean_df["year"].astype(int), clean_df[value_column].astype(float)))


def bucket_dataframe_to_dict(
    dataframe: pd.DataFrame,
    value_column: str,
) -> dict[str, float]:
    """Convert a bucket/value table into an API dictionary."""
    clean_df = dataframe.dropna(subset=["bucket", value_column]).copy()
    clean_df[value_column] = pd.to_numeric(clean_df[value_column], errors="coerce")
    clean_df = clean_df.dropna(subset=[value_column])
    return dict(zip(clean_df["bucket"].astype(str), clean_df[value_column].astype(float)))


if __name__ == "__main__":
    main()
