"""CSV parsing helpers for liability, KRD, and asset upload workflows."""

from __future__ import annotations

from io import StringIO

import pandas as pd


class CSVValidationError(ValueError):
    """Raised when an uploaded CSV does not match the expected schema."""


def parse_liability_cash_flows(csv_data: bytes | str) -> dict[int, float]:
    """Parse liability cash-flow CSV into year-indexed cash flows.

    Expected columns: `Date`, `CashFlow`.
    """
    dataframe = _read_csv(csv_data)
    _require_columns(dataframe, ["Date", "CashFlow"])
    dataframe["Date"] = pd.to_datetime(dataframe["Date"], errors="coerce")
    dataframe["CashFlow"] = pd.to_numeric(dataframe["CashFlow"], errors="coerce")
    dataframe = dataframe.dropna(subset=["Date", "CashFlow"]).sort_values("Date")
    if dataframe.empty:
        raise CSVValidationError("Liability cash-flow CSV contains no valid rows.")
    if (dataframe["CashFlow"] < 0.0).any():
        raise CSVValidationError("CashFlow values must be non-negative.")

    first_year = int(dataframe["Date"].dt.year.min())
    dataframe["Year"] = dataframe["Date"].dt.year.astype(int) - first_year + 1
    grouped = dataframe.groupby("Year")["CashFlow"].sum()
    return {int(year): float(value) for year, value in grouped.items()}


def parse_liability_krd(csv_data: bytes | str) -> dict[str, float]:
    """Parse liability KRD CSV into bucket DV01 mapping.

    Expected columns: `Bucket`, `DV01`.
    """
    dataframe = _read_csv(csv_data)
    _require_columns(dataframe, ["Bucket", "DV01"])
    dataframe["Bucket"] = dataframe["Bucket"].astype(str).str.strip()
    dataframe["DV01"] = pd.to_numeric(dataframe["DV01"], errors="coerce")
    dataframe = dataframe.dropna(subset=["Bucket", "DV01"])
    dataframe = dataframe[dataframe["Bucket"] != ""]
    if dataframe.empty:
        raise CSVValidationError("Liability KRD CSV contains no valid rows.")
    if (dataframe["DV01"] < 0.0).any():
        raise CSVValidationError("DV01 values must be non-negative.")
    return {
        str(bucket): float(value)
        for bucket, value in dataframe.groupby("Bucket")["DV01"].sum().items()
    }


def parse_asset_holdings(csv_data: bytes | str) -> list[dict[str, float | str]]:
    """Parse asset holdings CSV into instrument market values.

    Expected columns: `Instrument`, `MarketValue`.
    """
    dataframe = _read_csv(csv_data)
    _require_columns(dataframe, ["Instrument", "MarketValue"])
    dataframe["Instrument"] = dataframe["Instrument"].astype(str).str.strip()
    dataframe["MarketValue"] = pd.to_numeric(
        dataframe["MarketValue"],
        errors="coerce",
    )
    dataframe = dataframe.dropna(subset=["Instrument", "MarketValue"])
    dataframe = dataframe[dataframe["Instrument"] != ""]
    if dataframe.empty:
        raise CSVValidationError("Asset holdings CSV contains no valid rows.")
    if (dataframe["MarketValue"] < 0.0).any():
        raise CSVValidationError("MarketValue values must be non-negative.")
    return [
        {"instrument": str(row.Instrument), "market_value": float(row.MarketValue)}
        for row in dataframe.itertuples(index=False)
    ]


def liability_cash_flow_template() -> str:
    """Return a downloadable liability cash-flow CSV template."""
    return "Date,CashFlow\n2027-01-01,1000000\n2028-01-01,1000000\n"


def liability_krd_template() -> str:
    """Return a downloadable liability KRD CSV template."""
    return "Bucket,DV01\n1Y,50000\n5Y,150000\n10Y,400000\n"


def asset_holdings_template() -> str:
    """Return a downloadable asset holdings CSV template."""
    return "Instrument,MarketValue\n10Y Treasury,50000000\n30Y Treasury,25000000\n"


def _read_csv(csv_data: bytes | str) -> pd.DataFrame:
    """Read CSV bytes or text into a dataframe."""
    if isinstance(csv_data, bytes):
        text = csv_data.decode("utf-8")
    elif isinstance(csv_data, str):
        text = csv_data
    else:
        raise TypeError("csv_data must be bytes or string.")

    try:
        return pd.read_csv(StringIO(text))
    except Exception as exc:
        raise CSVValidationError(f"Unable to read CSV: {exc}") from exc


def _require_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    """Raise when required columns are missing."""
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise CSVValidationError(f"Missing required columns: {', '.join(missing)}.")
