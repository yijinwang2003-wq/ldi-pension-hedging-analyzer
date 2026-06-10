import pytest

from backend.models.effectiveness import HedgeEffectivenessAnalyzer


def test_hedge_effectiveness_metrics_are_calculated() -> None:
    analyzer = HedgeEffectivenessAnalyzer(
        liability_dv01=5_000.0,
        hedge_dv01=3_900.0,
        asset_market_value=5_200_000.0,
        liability_pv=5_600_000.0,
        target_hedge_ratio=0.90,
    )

    metrics = analyzer.metrics()

    assert metrics["hedge_ratio"] == pytest.approx(0.78)
    assert metrics["percent_hedged"] == pytest.approx(0.78)
    assert metrics["residual_dv01"] == pytest.approx(1_100.0)
    assert metrics["required_incremental_dv01"] == pytest.approx(600.0)
    assert "Current hedge ratio is 78%" in str(metrics["recommendation"])


def test_hedged_funding_ratio_is_less_rate_sensitive_than_unhedged() -> None:
    analyzer = HedgeEffectivenessAnalyzer(
        liability_dv01=5_000.0,
        hedge_dv01=4_500.0,
        asset_market_value=5_200_000.0,
        liability_pv=5_600_000.0,
    )

    shock = analyzer.funding_ratio_shock(100.0)

    assert abs(shock["hedged_change"]) < abs(shock["unhedged_change"])


def test_required_notional_uses_swap_dv01_per_notional() -> None:
    analyzer = HedgeEffectivenessAnalyzer(
        liability_dv01=5_000.0,
        hedge_dv01=3_900.0,
        asset_market_value=5_200_000.0,
        liability_pv=5_600_000.0,
        target_hedge_ratio=0.90,
        swap_dv01_per_notional=0.0005,
    )

    metrics = analyzer.metrics()

    assert metrics["required_incremental_notional"] == pytest.approx(1_200_000.0)


def test_invalid_liability_pv_raises_value_error() -> None:
    with pytest.raises(ValueError):
        HedgeEffectivenessAnalyzer(
            liability_dv01=5_000.0,
            hedge_dv01=3_900.0,
            asset_market_value=5_200_000.0,
            liability_pv=0.0,
        )
