import numpy as np
import pytest

from backend.models.scenarios import VasicekModel


def test_vasicek_simulate_paths_returns_expected_shape() -> None:
    np.random.seed(1)
    model = VasicekModel(kappa=0.30, theta=0.04, sigma=0.01, r0=0.035)

    paths = model.simulate_paths(years=1.0, dt=0.25, n_paths=3)

    assert paths.shape == (3, 5)
    assert np.all(paths[:, 0] == pytest.approx(0.035))


def test_vasicek_summary_requires_simulation() -> None:
    model = VasicekModel(kappa=0.30, theta=0.04, sigma=0.01, r0=0.035)

    with pytest.raises(ValueError):
        model.summarize_terminal_rates()


def test_vasicek_parallel_shift_scenarios_include_100bp() -> None:
    model = VasicekModel(kappa=0.30, theta=0.04, sigma=0.01, r0=0.035)

    scenarios = model.parallel_shift_scenarios()

    assert scenarios["+100bp"] == pytest.approx(0.045)
    assert scenarios["-100bp"] == pytest.approx(0.025)


@pytest.mark.parametrize(
    ("kappa", "sigma"),
    [
        (0.0, 0.01),
        (0.30, -0.01),
    ],
)
def test_vasicek_invalid_parameters_raise_value_error(
    kappa: float,
    sigma: float,
) -> None:
    with pytest.raises(ValueError):
        VasicekModel(kappa=kappa, theta=0.04, sigma=sigma, r0=0.035)
