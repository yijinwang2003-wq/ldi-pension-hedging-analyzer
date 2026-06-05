import pytest

from backend.models.portfolio import PortfolioModel


def sample_portfolio() -> PortfolioModel:
    return PortfolioModel(
        equities=3_000_000.0,
        credit=1_000_000.0,
        long_bonds=500_000.0,
        irs_exposure=700_000.0,
    )


def test_portfolio_totals_are_calculated() -> None:
    portfolio = sample_portfolio()

    assert portfolio.growth_portfolio() == pytest.approx(4_000_000.0)
    assert portfolio.hedging_portfolio() == pytest.approx(1_200_000.0)
    assert portfolio.total_assets() == pytest.approx(5_200_000.0)


def test_portfolio_allocations_are_calculated() -> None:
    portfolio = sample_portfolio()

    assert portfolio.growth_allocation() == pytest.approx(4_000_000.0 / 5_200_000.0)
    assert portfolio.hedging_allocation() == pytest.approx(1_200_000.0 / 5_200_000.0)


def test_zero_total_assets_returns_zero_allocations() -> None:
    portfolio = PortfolioModel(
        equities=0.0,
        credit=0.0,
        long_bonds=0.0,
        irs_exposure=0.0,
    )

    assert portfolio.growth_allocation() == 0.0
    assert portfolio.hedging_allocation() == 0.0


@pytest.mark.parametrize(
    ("equities", "credit", "long_bonds", "irs_exposure"),
    [
        (-1.0, 0.0, 0.0, 0.0),
        (0.0, -1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0, 0.0),
        (0.0, 0.0, 0.0, -1.0),
    ],
)
def test_negative_portfolio_inputs_raise_value_error(
    equities: float,
    credit: float,
    long_bonds: float,
    irs_exposure: float,
) -> None:
    with pytest.raises(ValueError):
        PortfolioModel(
            equities=equities,
            credit=credit,
            long_bonds=long_bonds,
            irs_exposure=irs_exposure,
        )
