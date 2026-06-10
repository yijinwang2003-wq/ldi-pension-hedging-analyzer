"""Streamlit page for reusable CSV uploads and templates."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.csv_loader import (
    CSVValidationError,
    asset_holdings_template,
    liability_cash_flow_template,
    liability_krd_template,
    parse_asset_holdings,
    parse_liability_cash_flows,
    parse_liability_krd,
)


def main() -> None:
    """Render CSV upload center."""
    st.set_page_config(
        page_title="CSV Upload Center",
        layout="wide",
    )

    st.title("CSV Upload Center")

    render_template_downloads()
    st.divider()

    first, second, third = st.columns(3)
    with first:
        render_cash_flow_upload()
    with second:
        render_krd_upload()
    with third:
        render_asset_holdings_upload()


def render_template_downloads() -> None:
    """Render downloadable CSV templates."""
    st.header("Download Templates")
    columns = st.columns(3)
    columns[0].download_button(
        "Liability Cash Flows",
        data=liability_cash_flow_template(),
        file_name="liability_cash_flows_template.csv",
        mime="text/csv",
    )
    columns[1].download_button(
        "Liability KRD Profile",
        data=liability_krd_template(),
        file_name="liability_krd_template.csv",
        mime="text/csv",
    )
    columns[2].download_button(
        "Asset Holdings",
        data=asset_holdings_template(),
        file_name="asset_holdings_template.csv",
        mime="text/csv",
    )


def render_cash_flow_upload() -> None:
    """Render liability cash-flow CSV upload."""
    st.subheader("Liability Cash Flows")
    uploaded_file = st.file_uploader(
        "Upload cash flows",
        type=["csv"],
        key="cash_flow_upload",
    )
    if uploaded_file is None:
        return

    try:
        parsed = parse_liability_cash_flows(uploaded_file.getvalue())
    except (CSVValidationError, UnicodeDecodeError) as exc:
        st.error(str(exc))
        return

    st.session_state["uploaded_liability_cash_flows"] = parsed
    st.success("Liability cash flows uploaded.")
    st.dataframe(
        pd.DataFrame(
            {"year": list(parsed.keys()), "cash_flow": list(parsed.values())}
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_krd_upload() -> None:
    """Render liability KRD CSV upload."""
    st.subheader("Liability KRD Profile")
    uploaded_file = st.file_uploader(
        "Upload KRD profile",
        type=["csv"],
        key="krd_upload",
    )
    if uploaded_file is None:
        return

    try:
        parsed = parse_liability_krd(uploaded_file.getvalue())
    except (CSVValidationError, UnicodeDecodeError) as exc:
        st.error(str(exc))
        return

    st.session_state["uploaded_liability_krd"] = parsed
    st.success("Liability KRD profile uploaded.")
    st.dataframe(
        pd.DataFrame({"bucket": list(parsed.keys()), "dv01": list(parsed.values())}),
        use_container_width=True,
        hide_index=True,
    )


def render_asset_holdings_upload() -> None:
    """Render asset holdings CSV upload."""
    st.subheader("Asset Holdings")
    uploaded_file = st.file_uploader(
        "Upload asset holdings",
        type=["csv"],
        key="asset_holdings_upload",
    )
    if uploaded_file is None:
        return

    try:
        parsed = parse_asset_holdings(uploaded_file.getvalue())
    except (CSVValidationError, UnicodeDecodeError) as exc:
        st.error(str(exc))
        return

    st.session_state["uploaded_asset_holdings"] = parsed
    st.success("Asset holdings uploaded.")
    st.dataframe(pd.DataFrame(parsed), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
