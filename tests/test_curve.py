import pytest

from backend.models.curve import (
    CurveScenario,
    CurveScenarioAnalyzer,
    NelsonSiegelCurve,
    nelson_siegel_rate,
)


def sample_cash_flows() -> dict[int, float]:
    return {1: 1_000_000.0, 5: 1_250_000.0, 10: 1_500_000.0}


def sample_curve() -> dict[int, float]:
    return {1: 0.040, 5: 0.043, 10: 0.047}


def test_curve_twist_scenarios_include_required_shapes() -> None:
    analyzer = CurveScenarioAnalyzer(
        cash_flows=sample_cash_flows(),
        discount_curve=sample_curve(),
        asset_market_value=3_600_000.0,
        hedge_dv01=2_000.0,
    )

    results = analyzer.analyze()
    scenario_names = {result["scenario"] for result in results}

    assert {
        "Parallel +100bp",
        "Parallel -100bp",
        "Bear steepener",
        "Bull flattener",
    }.issubset(scenario_names)


def test_parallel_up_scenario_reduces_liability_pv() -> None:
    analyzer = CurveScenarioAnalyzer(
        cash_flows=sample_cash_flows(),
        discount_curve=sample_curve(),
        asset_market_value=3_600_000.0,
    )

    results = analyzer.analyze()
    parallel_up = next(
        result for result in results if result["scenario"] == "Parallel +100bp"
    )

    assert parallel_up["liability_pv_change"] < 0.0
    assert parallel_up["funding_ratio_change_unhedged"] > 0.0


def test_custom_key_rate_shock_is_included() -> None:
    analyzer = CurveScenarioAnalyzer(
        cash_flows=sample_cash_flows(),
        discount_curve=sample_curve(),
        asset_market_value=3_600_000.0,
    )

    results = analyzer.analyze(
        custom_scenario=CurveScenario("Custom key-rate shock", {1: 10.0, 10: 90.0})
    )

    assert results[-1]["scenario"] == "Custom key-rate shock"
    assert results[-1]["shocks_bps"] == {1: 10.0, 10: 90.0}


def test_nelson_siegel_generates_smooth_curve_with_fixed_tau() -> None:
    curve = NelsonSiegelCurve(
        maturities=[1.0, 2.0, 5.0, 10.0, 30.0],
        rates=[0.038, 0.039, 0.041, 0.044, 0.047],
        tau=2.5,
    )

    fitted = curve.generate_curve([1, 2, 3, 5, 10, 30])

    assert set(fitted) == {1, 2, 3, 5, 10, 30}
    assert all(rate > 0.0 for rate in fitted.values())
    assert fitted[30] > fitted[1]


def test_nelson_siegel_rate_formula_matches_expected_value() -> None:
    rate = nelson_siegel_rate(
        maturity=5.0,
        beta0=0.05,
        beta1=-0.02,
        beta2=0.01,
        tau=2.0,
    )

    assert rate == pytest.approx(0.045507, rel=1e-4)


def test_nelson_siegel_requires_three_market_points() -> None:
    with pytest.raises(ValueError):
        NelsonSiegelCurve(maturities=[1.0, 2.0], rates=[0.04, 0.041])
