"""Streamlit dashboard for the LDI Pension Hedging Analyzer."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


API_BASE_URL = "http://127.0.0.1:8000/api"


def main() -> None:
    """Render the Streamlit dashboard."""
    st.set_page_config(
        page_title="LDI Pension Hedging Analyzer",
        layout="wide",
    )

    st.title("LDI Pension Hedging Analyzer")

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
            "cash_flow": [1_000_000.0, 1_050_000.0, 1_100_000.0, 1_150_000.0, 1_200_000.0],
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
        present_value = post_liability_endpoint("pv", payload)
        duration = post_liability_endpoint("duration", payload)
        dv01 = post_liability_endpoint("dv01", payload)
    except requests.RequestException as exc:
        st.error(f"Unable to calculate liability analytics: {exc}")
        return

    render_liability_metrics(
        present_value=present_value["present_value"],
        macaulay_duration=duration["macaulay_duration"],
        modified_duration=duration["modified_duration"],
        dv01=dv01["dv01"],
    )


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
