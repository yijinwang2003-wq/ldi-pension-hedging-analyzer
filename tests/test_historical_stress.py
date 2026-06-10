import pytest

from backend.models.historical_stress import (
    HISTORICAL_SCENARIOS,
    HistoricalStressTester,
)


def sample_liability_krd() -> dict[str, float]:
    return {
        "2Y": 50_000.0,
        "5Y": 150_000.0,
        "10Y": 400_000.0,
        "20Y": 350_000.0,
        "30Y": 250_000.0,
    }


def sample_hedge_krd() -> dict[str, float]:
    return {
        "2Y": -25_000.0,
        "5Y": -100_000.0,
        "10Y": -325_000.0,
        "20Y": -275_000.0,
        "30Y": -200_000.0,
    }


def test_historical_scenarios_run_successfully() -> None:
    tester = HistoricalStressTester(
        liability_krd=sample_liability_krd(),
        hedge_krd=sample_hedge_krd(),
        asset_market_value=1_000_000_000.0,
        liability_pv=1_000_000_000.0,
    )

    results = tester.run()

    assert len(results) == len(HISTORICAL_SCENARIOS)
    assert all("funding_ratio_after_hedged" in row for row in results)


def test_historical_stress_funding_ratio_calculation_is_correct() -> None:
    tester = HistoricalStressTester(
        liability_krd={"10Y": 100.0},
        hedge_krd={"10Y": -50.0},
        asset_market_value=1_000_000.0,
        liability_pv=1_000_000.0,
    )

    covid = next(
        row for row in tester.run() if row["scenario"] == "2020 COVID Shock (Feb-Mar 2020)"
    )

    assert covid["liability_change"] == pytest.approx(12_500.0)
    assert covid["hedge_change"] == pytest.approx(6_250.0)
    assert covid["funding_ratio_before"] == pytest.approx(1.0)
    assert covid["funding_ratio_after_hedged"] == pytest.approx(
        1_006_250.0 / 1_012_500.0
    )


def test_hedged_result_reduces_covid_downrate_damage() -> None:
    tester = HistoricalStressTester(
        liability_krd=sample_liability_krd(),
        hedge_krd=sample_hedge_krd(),
        asset_market_value=1_000_000_000.0,
        liability_pv=1_000_000_000.0,
    )

    covid = next(
        row for row in tester.run() if row["scenario"] == "2020 COVID Shock (Feb-Mar 2020)"
    )

    assert covid["funding_ratio_after_hedged"] > covid["funding_ratio_after_unhedged"]


def test_invalid_liability_pv_raises_value_error() -> None:
    with pytest.raises(ValueError):
        HistoricalStressTester(
            liability_krd=sample_liability_krd(),
            liability_pv=0.0,
        )
