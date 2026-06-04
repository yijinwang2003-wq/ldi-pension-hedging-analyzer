import pytest

from backend.models.liability import LiabilityModel


def test_present_value_is_correct_for_simple_cash_flows() -> None:
    model = LiabilityModel(
        cash_flows={1: 100.0, 2: 100.0},
        discount_curve={1: 0.05, 2: 0.05},
    )

    expected_pv = 100.0 / 1.05 + 100.0 / 1.05**2

    assert model.present_value() == pytest.approx(expected_pv)


def test_duration_is_positive() -> None:
    model = LiabilityModel(
        cash_flows={1: 100.0, 5: 250.0, 10: 500.0},
        discount_curve={1: 0.04, 5: 0.045, 10: 0.05},
    )

    assert model.macaulay_duration() > 0.0
    assert model.modified_duration() > 0.0


def test_dv01_is_positive() -> None:
    model = LiabilityModel(
        cash_flows={1: 100.0, 5: 250.0, 10: 500.0},
        discount_curve={1: 0.04, 5: 0.045, 10: 0.05},
    )

    assert model.dv01() > 0.0


def test_present_value_decreases_when_rates_shift_upward() -> None:
    model = LiabilityModel(
        cash_flows={1: 100.0, 5: 250.0, 10: 500.0},
        discount_curve={1: 0.04, 5: 0.045, 10: 0.05},
    )

    assert model.pv_under_parallel_shift(25.0) < model.present_value()


@pytest.mark.parametrize(
    ("cash_flows", "discount_curve"),
    [
        ({}, {}),
        ({0: 100.0}, {0: 0.05}),
        ({1: -100.0}, {1: 0.05}),
        ({1: 100.0}, {}),
        ({1: 100.0}, {1: -1.0}),
    ],
)
def test_invalid_inputs_raise_value_error(
    cash_flows: dict[int, float],
    discount_curve: dict[int, float],
) -> None:
    with pytest.raises(ValueError):
        LiabilityModel(cash_flows=cash_flows, discount_curve=discount_curve)
