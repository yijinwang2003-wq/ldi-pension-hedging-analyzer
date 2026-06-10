import pytest

from backend.utils.csv_loader import (
    CSVValidationError,
    asset_holdings_template,
    liability_cash_flow_template,
    liability_krd_template,
    parse_asset_holdings,
    parse_liability_cash_flows,
    parse_liability_krd,
)


def test_parse_liability_cash_flows() -> None:
    csv_data = "Date,CashFlow\n2027-01-01,1000000\n2028-01-01,1250000\n"

    result = parse_liability_cash_flows(csv_data)

    assert result == {1: 1_000_000.0, 2: 1_250_000.0}


def test_parse_liability_krd() -> None:
    csv_data = "Bucket,DV01\n1Y,50000\n5Y,150000\n10Y,400000\n"

    result = parse_liability_krd(csv_data)

    assert result == {"1Y": 50_000.0, "5Y": 150_000.0, "10Y": 400_000.0}


def test_parse_asset_holdings() -> None:
    csv_data = "Instrument,MarketValue\n10Y Treasury,50000000\n30Y Treasury,25000000\n"

    result = parse_asset_holdings(csv_data)

    assert result == [
        {"instrument": "10Y Treasury", "market_value": 50_000_000.0},
        {"instrument": "30Y Treasury", "market_value": 25_000_000.0},
    ]


def test_missing_required_columns_raise_validation_error() -> None:
    with pytest.raises(CSVValidationError):
        parse_liability_krd("Bucket,Value\n1Y,50000\n")


def test_negative_cash_flow_raises_validation_error() -> None:
    with pytest.raises(CSVValidationError):
        parse_liability_cash_flows("Date,CashFlow\n2027-01-01,-1\n")


def test_templates_are_downloadable_csv_text() -> None:
    assert "Date,CashFlow" in liability_cash_flow_template()
    assert "Bucket,DV01" in liability_krd_template()
    assert "Instrument,MarketValue" in asset_holdings_template()
