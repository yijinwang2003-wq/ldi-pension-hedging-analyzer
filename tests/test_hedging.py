import pytest

from backend.models.hedging import InterestRateSwap


def sample_swap() -> InterestRateSwap:
    return InterestRateSwap(
        notional=1_000_000.0,
        fixed_rate=0.04,
        maturity_years=5,
        discount_curve={1: 0.035, 2: 0.037, 3: 0.039, 4: 0.041, 5: 0.043},
    )


def test_fixed_leg_pv_is_positive() -> None:
    assert sample_swap().fixed_leg_pv() > 0.0


def test_floating_leg_pv_is_positive() -> None:
    assert sample_swap().floating_leg_pv() > 0.0


def test_swap_value_returns_float() -> None:
    assert isinstance(sample_swap().swap_value(), float)


def test_dv01_is_non_zero() -> None:
    assert abs(sample_swap().dv01()) > 0.0


def test_hedge_notional_preserves_direction() -> None:
    swap = sample_swap()
    liability_dv01 = 1_000.0
    expected_notional = liability_dv01 * swap.notional / swap.dv01()

    assert swap.hedge_notional(liability_dv01) == pytest.approx(expected_notional)


@pytest.mark.parametrize(
    ("notional", "fixed_rate", "maturity_years", "discount_curve"),
    [
        (0.0, 0.04, 5, {1: 0.035, 2: 0.037, 3: 0.039, 4: 0.041, 5: 0.043}),
        (1_000_000.0, -1.0, 5, {1: 0.035, 2: 0.037, 3: 0.039, 4: 0.041, 5: 0.043}),
        (1_000_000.0, 0.04, 0, {}),
        (1_000_000.0, 0.04, 5, {1: 0.035, 2: 0.037}),
        (1_000_000.0, 0.04, 5, {1: 0.035, 2: 0.037, 3: 0.039, 4: 0.041, 5: -1.0}),
    ],
)
def test_invalid_inputs_raise_value_error(
    notional: float,
    fixed_rate: float,
    maturity_years: int,
    discount_curve: dict[int, float],
) -> None:
    with pytest.raises(ValueError):
        InterestRateSwap(
            notional=notional,
            fixed_rate=fixed_rate,
            maturity_years=maturity_years,
            discount_curve=discount_curve,
        )
