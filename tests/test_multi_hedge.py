from backend.models.multi_hedge import (
    MultiInstrumentHedgeOptimizer,
    default_instrument_universe,
)


def sample_liability_krd() -> dict[str, float]:
    return {
        "1Y": 50_000.0,
        "5Y": 150_000.0,
        "10Y": 400_000.0,
        "20Y": 350_000.0,
        "30Y": 250_000.0,
    }


def test_multi_hedge_optimization_converges_to_allocations() -> None:
    optimizer = MultiInstrumentHedgeOptimizer(
        liability_krd=sample_liability_krd(),
        selected_instruments=default_instrument_universe(),
    )

    result = optimizer.optimize()

    assert result["recommended_allocations"]
    assert result["hedge_ratio"] > 0.0
    assert all("recommended_notional" in row for row in result["recommended_allocations"])


def test_multi_hedge_residual_krd_decreases() -> None:
    liability_krd = sample_liability_krd()
    optimizer = MultiInstrumentHedgeOptimizer(liability_krd=liability_krd)

    result = optimizer.optimize()
    starting_score = sum(value**2 for value in liability_krd.values()) ** 0.5
    ending_score = result["comparison"]["multi_instrument_krd_hedge"][
        "residual_risk_score"
    ]

    assert ending_score < starting_score


def test_multi_hedge_outperforms_single_dv01_hedge() -> None:
    optimizer = MultiInstrumentHedgeOptimizer(liability_krd=sample_liability_krd())

    result = optimizer.optimize()
    single_score = result["comparison"]["single_dv01_hedge"]["residual_risk_score"]
    multi_score = result["comparison"]["multi_instrument_krd_hedge"][
        "residual_risk_score"
    ]

    assert multi_score < single_score


def test_multi_hedge_stress_scenarios_run_successfully() -> None:
    optimizer = MultiInstrumentHedgeOptimizer(
        liability_krd=sample_liability_krd(),
        asset_market_value=105_000_000.0,
        liability_pv=100_000_000.0,
    )

    result = optimizer.optimize()
    stress_results = result["stress_results"]

    assert set(stress_results) == {
        "single_dv01_hedge",
        "multi_instrument_krd_hedge",
    }
    assert len(stress_results["single_dv01_hedge"]) == 4
    assert len(stress_results["multi_instrument_krd_hedge"]) == 4
    assert all(
        "funding_ratio_change" in row
        for row in stress_results["multi_instrument_krd_hedge"]
    )
