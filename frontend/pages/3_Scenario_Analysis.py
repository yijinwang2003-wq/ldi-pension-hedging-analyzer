"""Streamlit page for Vasicek interest-rate scenario analysis."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from frontend.api_client import post_api_json, render_backend_error, warm_up_backend


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

    st.header("Inputs")
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


if __name__ == "__main__":
    main()
