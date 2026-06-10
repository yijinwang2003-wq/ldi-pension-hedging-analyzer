"""Yield-curve construction and curve-shock scenario analytics."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from backend.models.liability import LiabilityModel


BASIS_POINT = 0.0001


@dataclass(frozen=True)
class CurveScenario:
    """Named maturity-specific interest-rate scenario."""

    name: str
    shocks_bps: dict[int, float]


class CurveScenarioAnalyzer:
    """Analyze liability and funding sensitivity under curve-shape shocks."""

    def __init__(
        self,
        cash_flows: dict[int, float],
        discount_curve: dict[int, float],
        asset_market_value: float,
        hedge_dv01: float = 0.0,
        hedge_key_rate_dv01: dict[int, float] | None = None,
    ) -> None:
        """Initialize scenario inputs."""
        self.liability = LiabilityModel(cash_flows, discount_curve)
        self.asset_market_value = asset_market_value
        self.hedge_dv01 = hedge_dv01
        self.hedge_key_rate_dv01 = dict(hedge_key_rate_dv01 or {})
        self._validate_inputs()

    def standard_scenarios(self) -> list[CurveScenario]:
        """Return standard parallel and curve-shape shocks."""
        maturities = sorted(self.liability.discount_curve)
        return [
            CurveScenario("Parallel +100bp", {year: 100.0 for year in maturities}),
            CurveScenario("Parallel -100bp", {year: -100.0 for year in maturities}),
            CurveScenario("Bear steepener", self._slope_shock(short_bps=25.0, long_bps=100.0)),
            CurveScenario("Bull flattener", self._slope_shock(short_bps=-100.0, long_bps=-25.0)),
        ]

    def analyze(
        self,
        custom_scenario: CurveScenario | None = None,
    ) -> list[dict[str, float | str | dict[int, float]]]:
        """Return funding and DV01 impact for standard plus optional scenarios."""
        scenarios = self.standard_scenarios()
        if custom_scenario is not None:
            scenarios.append(custom_scenario)

        base_liability_pv = self.liability.present_value()
        if base_liability_pv == 0.0:
            raise ValueError("Funding ratio is undefined when liability PV is zero.")

        base_funding_ratio = self.asset_market_value / base_liability_pv
        results = []
        for scenario in scenarios:
            shocked_pv = self.liability.pv_under_curve_shock(scenario.shocks_bps)
            liability_pv_change = shocked_pv - base_liability_pv
            liability_rate_pnl = -liability_pv_change
            hedge_impact = self._estimate_hedge_impact(scenario.shocks_bps)
            unhedged_assets = self.asset_market_value
            hedged_assets = self.asset_market_value + hedge_impact

            unhedged_funding_ratio = unhedged_assets / shocked_pv
            hedged_funding_ratio = hedged_assets / shocked_pv

            results.append(
                {
                    "scenario": scenario.name,
                    "liability_pv": shocked_pv,
                    "liability_pv_change": liability_pv_change,
                    "liability_rate_pnl": liability_rate_pnl,
                    "liability_dv01_impact": self._estimate_dv01_impact(
                        scenario.shocks_bps
                    ),
                    "hedge_impact": hedge_impact,
                    "funding_ratio_unhedged": unhedged_funding_ratio,
                    "funding_ratio_hedged": hedged_funding_ratio,
                    "funding_ratio_change_unhedged": (
                        unhedged_funding_ratio - base_funding_ratio
                    ),
                    "funding_ratio_change_hedged": hedged_funding_ratio
                    - base_funding_ratio,
                    "shocks_bps": scenario.shocks_bps,
                }
            )

        return results

    def _estimate_hedge_impact(self, shocks_bps: dict[int, float]) -> float:
        """Estimate hedge P&L from parallel or key-rate DV01 inputs."""
        if self.hedge_key_rate_dv01:
            return sum(
                self.hedge_key_rate_dv01.get(year, 0.0) * shock_bps
                for year, shock_bps in shocks_bps.items()
            )

        if not shocks_bps:
            return 0.0
        average_shock = sum(shocks_bps.values()) / len(shocks_bps)
        return -self.hedge_dv01 * average_shock

    def _estimate_dv01_impact(self, shocks_bps: dict[int, float]) -> float:
        """Estimate liability value impact using key-rate DV01 exposures."""
        key_rate_dv01 = self.liability.key_rate_dv01(sorted(shocks_bps))
        return sum(
            key_rate_dv01.get(year, 0.0) * shock_bps
            for year, shock_bps in shocks_bps.items()
        )

    def _slope_shock(self, short_bps: float, long_bps: float) -> dict[int, float]:
        """Interpolate a slope shock across available curve maturities."""
        maturities = sorted(self.liability.discount_curve)
        first = maturities[0]
        last = maturities[-1]
        if first == last:
            return {first: long_bps}

        return {
            year: short_bps
            + (long_bps - short_bps) * (year - first) / (last - first)
            for year in maturities
        }

    def _validate_inputs(self) -> None:
        """Validate scenario-level inputs."""
        if not isinstance(self.asset_market_value, (int, float)):
            raise TypeError("asset_market_value must be numeric.")
        if self.asset_market_value < 0.0:
            raise ValueError("asset_market_value must be non-negative.")
        if not isinstance(self.hedge_dv01, (int, float)):
            raise TypeError("hedge_dv01 must be numeric.")
        for year, dv01 in self.hedge_key_rate_dv01.items():
            LiabilityModel._validate_year(year, field_name="hedge_key_rate_dv01")
            if not isinstance(dv01, (int, float)):
                raise TypeError("Hedge key-rate DV01 amounts must be numeric.")


class NelsonSiegelCurve:
    """Fit and generate annual spot curves using the Nelson-Siegel form."""

    def __init__(
        self,
        maturities: list[float],
        rates: list[float],
        tau: float | None = None,
    ) -> None:
        """Initialize market curve points and optional fixed tau."""
        self.maturities = [float(maturity) for maturity in maturities]
        self.rates = [float(rate) for rate in rates]
        self.tau = tau
        self._validate_inputs()

    def fit(self) -> dict[str, float]:
        """Fit beta0, beta1, beta2, and tau to market points."""
        tau = float(self.tau) if self.tau is not None else self._fit_tau()
        beta0, beta1, beta2 = self._fit_betas(tau)
        return {
            "beta0": beta0,
            "beta1": beta1,
            "beta2": beta2,
            "tau": tau,
        }

    def generate_curve(self, years: list[int]) -> dict[int, float]:
        """Generate annual spot rates for requested maturities."""
        params = self.fit()
        return {
            int(year): nelson_siegel_rate(
                maturity=float(year),
                beta0=params["beta0"],
                beta1=params["beta1"],
                beta2=params["beta2"],
                tau=params["tau"],
            )
            for year in years
        }

    def _fit_tau(self) -> float:
        """Fit tau by coarse grid search for stable, dependency-light behavior."""
        candidate_taus = np.linspace(0.5, 15.0, 146)
        best_tau = float(candidate_taus[0])
        best_error = math.inf

        y = np.array(self.rates, dtype=float)
        for tau in candidate_taus:
            betas = self._fit_betas(float(tau))
            fitted = self._design_matrix(float(tau)) @ np.array(betas)
            error = float(np.mean((fitted - y) ** 2))
            if error < best_error:
                best_error = error
                best_tau = float(tau)

        return best_tau

    def _fit_betas(self, tau: float) -> tuple[float, float, float]:
        """Fit beta coefficients by least squares for a fixed tau."""
        x = self._design_matrix(tau)
        y = np.array(self.rates, dtype=float)
        betas, *_ = np.linalg.lstsq(x, y, rcond=None)
        return tuple(float(beta) for beta in betas)

    def _design_matrix(self, tau: float) -> np.ndarray:
        """Return Nelson-Siegel factor loadings for market maturities."""
        return np.array(
            [
                [
                    1.0,
                    _level_slope_loading(maturity, tau),
                    _curvature_loading(maturity, tau),
                ]
                for maturity in self.maturities
            ],
            dtype=float,
        )

    def _validate_inputs(self) -> None:
        """Validate market curve points."""
        if len(self.maturities) != len(self.rates):
            raise ValueError("maturities and rates must have the same length.")
        if len(self.maturities) < 3:
            raise ValueError("At least three market points are required.")
        if len(set(self.maturities)) != len(self.maturities):
            raise ValueError("maturities must be unique.")
        for maturity in self.maturities:
            if maturity <= 0.0:
                raise ValueError("maturities must be positive.")
        for rate in self.rates:
            if rate <= -1.0:
                raise ValueError("rates must be greater than -100%.")
        if self.tau is not None and self.tau <= 0.0:
            raise ValueError("tau must be positive.")


def nelson_siegel_rate(
    maturity: float,
    beta0: float,
    beta1: float,
    beta2: float,
    tau: float,
) -> float:
    """Return the Nelson-Siegel spot rate at one maturity."""
    if maturity <= 0.0:
        raise ValueError("maturity must be positive.")
    if tau <= 0.0:
        raise ValueError("tau must be positive.")

    slope_loading = _level_slope_loading(maturity, tau)
    curvature_loading = _curvature_loading(maturity, tau)
    return beta0 + beta1 * slope_loading + beta2 * curvature_loading


def _level_slope_loading(maturity: float, tau: float) -> float:
    scaled_maturity = maturity / tau
    return (1.0 - math.exp(-scaled_maturity)) / scaled_maturity


def _curvature_loading(maturity: float, tau: float) -> float:
    scaled_maturity = maturity / tau
    return _level_slope_loading(maturity, tau) - math.exp(-scaled_maturity)
