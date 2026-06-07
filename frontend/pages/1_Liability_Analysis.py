"""Streamlit page for liability analytics."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from frontend.api_client import post_api_json, render_backend_error, warm_up_backend


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")
KEY_RATES = [5, 10, 20, 30]


def main() -> None:
    """Render the liability analysis page."""
    st.set_page_config(
        page_title="Liability Analysis",
        layout="wide",
    )

    st.title("Liability Analysis")

    st.header("Liability Inputs")
    cash_flow_df, discount_curve_df = render_liability_inputs()

    st.header("Analytics")
    if st.button("Calculate", type="primary"):
        calculate_liability_analytics(cash_flow_df, discount_curve_df)

    st.header("Visualization")
    render_cash_flow_chart(cash_flow_df)


def render_liability_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Render editable cash-flow and discount-curve input tables."""
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

    left, right = st.columns(2)
    with left:
        st.subheader("Cash Flow Table")
        cash_flow_df = st.data_editor(
            default_cash_flows,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
        )

    with right:
        st.subheader("Discount Curve Table")
        discount_curve_df = st.data_editor(
            default_discount_curve,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
        )

    return cash_flow_df, discount_curve_df


def calculate_liability_analytics(
    cash_flow_df: pd.DataFrame,
    discount_curve_df: pd.DataFrame,
) -> None:
    """Call liability analytics endpoints and display metric cards."""
    payload = build_liability_payload(cash_flow_df, discount_curve_df)
    if payload is None:
        return

    try:
        warm_up_backend(API_BASE_URL)
        present_value = post_liability_endpoint("pv", payload)
        duration = post_liability_endpoint("duration", payload)
        dv01 = post_liability_endpoint("dv01", payload)
        key_rate_dv01 = post_liability_endpoint(
            "key-rate-dv01",
            {
                **payload,
                "key_rates": KEY_RATES,
            },
        )
    except requests.RequestException as exc:
        st.error(render_backend_error("calculate liability analytics", exc))
        return

    render_liability_metrics(
        present_value=present_value["present_value"],
        macaulay_duration=duration["macaulay_duration"],
        modified_duration=duration["modified_duration"],
        dv01=dv01["dv01"],
    )
    render_key_rate_dv01_analysis(key_rate_dv01["key_rate_dv01"])


def post_liability_endpoint(
    endpoint: str,
    payload: dict[str, object],
) -> dict[str, float]:
    """POST a liability payload to an API endpoint and return JSON data."""
    return post_api_json(API_BASE_URL, f"liability/{endpoint}", payload)


def render_liability_metrics(
    present_value: float,
    macaulay_duration: float,
    modified_duration: float,
    dv01: float,
) -> None:
    """Render liability analytics in Streamlit metric columns."""
    columns = st.columns(4)
    columns[0].metric("Present Value", f"${present_value:,.2f}")
    columns[1].metric("Macaulay Duration", f"{macaulay_duration:.2f}")
    columns[2].metric("Modified Duration", f"{modified_duration:.2f}")
    columns[3].metric("DV01", f"${dv01:,.2f}")


def render_key_rate_dv01_analysis(key_rate_dv01: dict[str, float]) -> None:
    """Render key-rate DV01 metrics, chart, and hedge guidance."""
    st.header("Key-Rate DV01 Analysis")

    normalized_dv01 = {
        key_rate: float(key_rate_dv01.get(str(key_rate), 0.0))
        for key_rate in KEY_RATES
    }

    columns = st.columns(4)
    for column, key_rate in zip(columns, KEY_RATES):
        column.metric(f"{key_rate}Y DV01", f"${normalized_dv01[key_rate]:,.2f}")

    chart_df = pd.DataFrame(
        {
            "Key Rate": [f"{key_rate}Y" for key_rate in KEY_RATES],
            "DV01": [normalized_dv01[key_rate] for key_rate in KEY_RATES],
        }
    )
    fig = px.bar(
        chart_df,
        x="Key Rate",
        y="DV01",
        labels={"DV01": "DV01"},
    )
    fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.2f")
    st.plotly_chart(fig, use_container_width=True)

    largest_key_rate = max(
        normalized_dv01,
        key=lambda key_rate: abs(normalized_dv01[key_rate]),
    )
    st.info(
        f"Largest exposure is at the {largest_key_rate}Y maturity bucket. "
        "Consider IRS or long-duration fixed income exposure around this tenor."
    )


def render_cash_flow_chart(cash_flow_df: pd.DataFrame) -> None:
    """Render a bar chart of liability cash flows by year."""
    chart_df = prepare_cash_flow_dataframe(cash_flow_df)
    if chart_df.empty:
        st.info("Enter at least one cash flow to display the chart.")
        return

    fig = px.bar(
        chart_df,
        x="year",
        y="cash_flow",
        labels={"year": "Year", "cash_flow": "Cash Flow"},
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
    """Return normalized cash-flow table rows for API calls and charting."""
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
