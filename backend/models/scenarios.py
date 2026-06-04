"""Interest-rate scenario generation models."""

from __future__ import annotations

import numpy as np


class VasicekModel:
    """Vasicek short-rate model using Euler-Maruyama simulation.

    Parameters
    ----------
    kappa:
        Mean-reversion speed. Higher values pull rates toward ``theta`` faster.
    theta:
        Long-run mean short rate, expressed as a decimal.
    sigma:
        Short-rate volatility.
    r0:
        Initial short rate, expressed as a decimal.

    Notes
    -----
    The continuous-time model is:

    ``dr = kappa * (theta - r) * dt + sigma * dW``

    This implementation uses Euler-Maruyama discretization:

    ``r[t+1] = r[t] + kappa * (theta - r[t]) * dt + sigma * sqrt(dt) * Z``
    """

    BASIS_POINT: float = 0.0001

    def __init__(
        self,
        kappa: float,
        theta: float,
        sigma: float,
        r0: float,
    ) -> None:
        """Initialize and validate Vasicek model parameters."""
        self.kappa = kappa
        self.theta = theta
        self.sigma = sigma
        self.r0 = r0
        self._last_paths: np.ndarray | None = None
        self._validate_inputs()

    def simulate_path(self, years: float, dt: float) -> np.ndarray:
        """Simulate one short-rate path.

        Parameters
        ----------
        years:
            Simulation horizon in years.
        dt:
            Time step in years.

        Returns
        -------
        numpy.ndarray
            One-dimensional array of simulated rates with length
            ``n_steps + 1``. The first element is ``r0``.
        """
        return self.simulate_paths(years=years, dt=dt, n_paths=1)[0]

    def simulate_paths(
        self,
        years: float,
        dt: float,
        n_paths: int,
    ) -> np.ndarray:
        """Simulate multiple short-rate paths.

        Parameters
        ----------
        years:
            Simulation horizon in years.
        dt:
            Time step in years.
        n_paths:
            Number of Monte Carlo paths to simulate.

        Returns
        -------
        numpy.ndarray
            Array of shape ``(n_paths, n_steps + 1)``.
        """
        n_steps = self._validate_simulation_inputs(
            years=years,
            dt=dt,
            n_paths=n_paths,
        )

        paths = np.empty((n_paths, n_steps + 1), dtype=float)
        paths[:, 0] = self.r0

        random_shocks = np.random.normal(
            loc=0.0,
            scale=np.sqrt(dt),
            size=(n_paths, n_steps),
        )

        for step in range(n_steps):
            current_rates = paths[:, step]
            drift = self.kappa * (self.theta - current_rates) * dt
            diffusion = self.sigma * random_shocks[:, step]
            paths[:, step + 1] = current_rates + drift + diffusion

        self._last_paths = paths
        return paths

    def parallel_shift_scenarios(self) -> dict[str, float]:
        """Return standard parallel shifts applied to the initial short rate.

        Returns
        -------
        dict[str, float]
            Mapping from scenario label to shifted rate. Shifts include
            +/-25 bp, +/-50 bp, and +/-100 bp.
        """
        shifts_bps = (25, 50, 100, -25, -50, -100)
        return {
            self._format_shift_label(shift_bps): self.r0
            + shift_bps * self.BASIS_POINT
            for shift_bps in shifts_bps
        }

    def summarize_terminal_rates(self) -> dict[str, float]:
        """Summarize terminal rates from the most recent path simulation.

        Returns
        -------
        dict[str, float]
            Summary statistics for terminal rates: mean, standard deviation,
            and 5%, 50%, and 95% quantiles.

        Raises
        ------
        ValueError
            If no paths have been simulated yet.
        """
        if self._last_paths is None:
            raise ValueError("No simulated paths available to summarize.")

        terminal_rates = self._last_paths[:, -1]
        quantiles = np.quantile(terminal_rates, [0.05, 0.50, 0.95])

        return {
            "mean": float(np.mean(terminal_rates)),
            "std": float(np.std(terminal_rates)),
            "5%": float(quantiles[0]),
            "50%": float(quantiles[1]),
            "95%": float(quantiles[2]),
        }

    def _validate_inputs(self) -> None:
        """Validate Vasicek model parameters."""
        for field_name in ("kappa", "theta", "sigma", "r0"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric.")

        if self.kappa <= 0.0:
            raise ValueError("kappa must be positive.")
        if self.sigma < 0.0:
            raise ValueError("sigma must be non-negative.")

    @staticmethod
    def _validate_simulation_inputs(
        years: float,
        dt: float,
        n_paths: int,
    ) -> int:
        """Validate simulation settings and return the number of time steps."""
        if not isinstance(years, (int, float)):
            raise TypeError("years must be numeric.")
        if not isinstance(dt, (int, float)):
            raise TypeError("dt must be numeric.")
        if not isinstance(n_paths, int) or isinstance(n_paths, bool):
            raise TypeError("n_paths must be an integer.")

        if years <= 0.0:
            raise ValueError("years must be positive.")
        if dt <= 0.0:
            raise ValueError("dt must be positive.")
        if n_paths <= 0:
            raise ValueError("n_paths must be positive.")

        n_steps = int(np.ceil(years / dt))
        if n_steps <= 0:
            raise ValueError("simulation must contain at least one time step.")

        return n_steps

    @staticmethod
    def _format_shift_label(shift_bps: int) -> str:
        """Return a readable basis-point scenario label."""
        sign = "+" if shift_bps > 0 else ""
        return f"{sign}{shift_bps}bp"
