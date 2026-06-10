import pytest

from backend.models.glide_path import GlidePathAdvisor


@pytest.mark.parametrize(
    ("funding_ratio", "target"),
    [
        (0.75, 0.40),
        (0.85, 0.65),
        (0.92, 0.80),
        (1.05, 0.95),
    ],
)
def test_glide_path_policy_rules_match_funding_bands(
    funding_ratio: float,
    target: float,
) -> None:
    assert GlidePathAdvisor.target_hedge_ratio(funding_ratio) == pytest.approx(target)


def test_glide_path_recommends_increase_when_below_target() -> None:
    advisor = GlidePathAdvisor(
        funding_ratio=0.92,
        current_hedge_ratio=0.68,
        liability_dv01=1_000_000.0,
        current_hedge_portfolio_dv01=680_000.0,
        dv01_per_notional=0.0005,
    )

    result = advisor.recommendation()

    assert result["target_hedge_ratio"] == pytest.approx(0.80)
    assert result["additional_dv01_needed"] == pytest.approx(120_000.0)
    assert result["suggested_notional_change"] == pytest.approx(240_000_000.0)
    assert result["recommended_action"] == "Increase hedge allocation"


def test_glide_path_recommends_decrease_when_above_target() -> None:
    advisor = GlidePathAdvisor(
        funding_ratio=0.85,
        current_hedge_ratio=0.80,
        liability_dv01=1_000_000.0,
        current_hedge_portfolio_dv01=800_000.0,
    )

    result = advisor.recommendation()

    assert result["target_hedge_ratio"] == pytest.approx(0.65)
    assert result["additional_dv01_needed"] == pytest.approx(-150_000.0)
    assert result["recommended_action"] == "Decrease hedge allocation"


def test_invalid_negative_funding_ratio_raises_value_error() -> None:
    with pytest.raises(ValueError):
        GlidePathAdvisor(
            funding_ratio=-0.01,
            current_hedge_ratio=0.50,
            liability_dv01=1_000_000.0,
            current_hedge_portfolio_dv01=500_000.0,
        )
