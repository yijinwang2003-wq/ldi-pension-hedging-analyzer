import pytest

from backend.models.attribution import FundingAttribution


def test_funding_attribution_contributions_bridge_to_total_change() -> None:
    attribution = FundingAttribution(
        beginning_assets=5_000_000.0,
        ending_assets=5_250_000.0,
        beginning_liability_pv=5_500_000.0,
        ending_liability_pv=5_650_000.0,
        asset_return=225_000.0,
        liability_discount_rate_change=125_000.0,
        benefit_payments=100_000.0,
        hedge_return=75_000.0,
    )

    result = attribution.decompose()
    explained_total = (
        result["asset_return_contribution"]
        + result["liability_discount_rate_contribution"]
        + result["cash_flow_contribution"]
        + result["hedge_contribution"]
        + result["residual_contribution"]
    )

    assert explained_total == pytest.approx(result["total_change"])


def test_discount_rate_liability_increase_reduces_funding_ratio() -> None:
    attribution = FundingAttribution(
        beginning_assets=5_000_000.0,
        ending_assets=5_000_000.0,
        beginning_liability_pv=5_500_000.0,
        ending_liability_pv=5_650_000.0,
        liability_discount_rate_change=150_000.0,
    )

    result = attribution.decompose()

    assert result["liability_discount_rate_contribution"] < 0.0


def test_invalid_beginning_liability_raises_value_error() -> None:
    with pytest.raises(ValueError):
        FundingAttribution(
            beginning_assets=5_000_000.0,
            ending_assets=5_250_000.0,
            beginning_liability_pv=0.0,
            ending_liability_pv=5_650_000.0,
        )
