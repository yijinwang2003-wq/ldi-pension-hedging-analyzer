"""Multi-instrument key-rate duration hedge optimization."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from itertools import combinations
from typing import Any

import numpy as np


STANDARD_BUCKETS = ("1Y", "5Y", "10Y", "20Y", "30Y")


@dataclass(frozen=True)
class HedgeInstrument:
    """A hedge instrument with total DV01 and key-rate DV01 profile."""

    name: str
    type: str
    notional: float
    dv01: float
    krd: dict[str, float]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HedgeInstrument":
        """Create an instrument from an API/UI dictionary."""
        return cls(
            name=str(data["name"]),
            type=str(data["type"]),
            notional=float(data["notional"]),
            dv01=float(data["dv01"]),
            krd={str(bucket): float(value) for bucket, value in data["krd"].items()},
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable instrument dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "notional": self.notional,
            "dv01": self.dv01,
            "krd": dict(self.krd),
        }


def default_instrument_universe() -> list[HedgeInstrument]:
    """Return an interview-friendly starter universe of LDI hedge instruments."""
    return [
        HedgeInstrument(
            name="10Y Interest Rate Swap",
            type="swap",
            notional=1_000_000.0,
            dv01=-850.0,
            krd={"1Y": 0.0, "5Y": -150.0, "10Y": -500.0, "20Y": -150.0, "30Y": -50.0},
        ),
        HedgeInstrument(
            name="30Y Interest Rate Swap",
            type="swap",
            notional=1_000_000.0,
            dv01=-1_950.0,
            krd={"1Y": 0.0, "5Y": -75.0, "10Y": -250.0, "20Y": -625.0, "30Y": -1_000.0},
        ),
        HedgeInstrument(
            name="10Y Treasury Bond",
            type="treasury",
            notional=1_000_000.0,
            dv01=-700.0,
            krd={"1Y": -25.0, "5Y": -175.0, "10Y": -425.0, "20Y": -60.0, "30Y": -15.0},
        ),
        HedgeInstrument(
            name="30Y Treasury Bond",
            type="treasury",
            notional=1_000_000.0,
            dv01=-1_650.0,
            krd={"1Y": -10.0, "5Y": -60.0, "10Y": -175.0, "20Y": -525.0, "30Y": -880.0},
        ),
    ]


class MultiInstrumentHedgeOptimizer:
    """Optimize hedge allocations against a liability KRD target."""

    def __init__(
        self,
        liability_krd: dict[str, float],
        selected_instruments: list[dict[str, Any] | HedgeInstrument] | None = None,
        asset_market_value: float = 100_000_000.0,
        liability_pv: float = 100_000_000.0,
    ) -> None:
        """Initialize optimizer inputs."""
        self.liability_krd = {str(bucket): float(value) for bucket, value in liability_krd.items()}
        self.instruments = self._coerce_instruments(selected_instruments)
        self.asset_market_value = asset_market_value
        self.liability_pv = liability_pv
        self.buckets = self._ordered_buckets()
        self._validate_inputs()

    def optimize(self) -> dict[str, Any]:
        """Run single-DV01 and multi-instrument KRD hedge analysis."""
        multi_multipliers = self._solve_multipliers()
        multi = self._build_hedge_result("Multi-Instrument KRD Hedge", multi_multipliers)
        single = self._single_dv01_hedge()
        stress_results = self._stress_results(single=single, multi=multi)

        return {
            "recommended_allocations": multi["allocations"],
            "hedge_ratio": multi["hedge_ratio"],
            "residual_krd": multi["residual_krd"],
            "portfolio_krd": multi["portfolio_krd"],
            "liability_krd": dict(self.liability_krd),
            "comparison": {
                "single_dv01_hedge": self._comparison_summary(single),
                "multi_instrument_krd_hedge": self._comparison_summary(multi),
            },
            "stress_results": stress_results,
            "recommendation": self._recommendation(single, multi),
        }

    def _solve_multipliers(self) -> np.ndarray:
        """Solve nonnegative instrument multipliers for KRD matching."""
        matrix = self._krd_matrix()
        target = -self._liability_vector()

        if os.getenv("LDI_USE_SCIPY_OPTIMIZER") == "1":
            try:
                from scipy.optimize import lsq_linear  # type: ignore

                result = lsq_linear(matrix, target, bounds=(0.0, np.inf))
                if result.success:
                    return np.array(result.x, dtype=float)
            except Exception:
                pass

        return self._nonnegative_least_squares_fallback(matrix, target)

    @staticmethod
    def _nonnegative_least_squares_fallback(
        matrix: np.ndarray,
        target: np.ndarray,
    ) -> np.ndarray:
        """Solve a small nonnegative least-squares problem by active subsets."""
        n_instruments = matrix.shape[1]
        if n_instruments > 12:
            multipliers, *_ = np.linalg.lstsq(matrix, target, rcond=None)
            return np.maximum(multipliers, 0.0)

        best_multipliers = np.zeros(n_instruments, dtype=float)
        best_error = float(np.sum((matrix @ best_multipliers - target) ** 2))

        for subset_size in range(1, n_instruments + 1):
            for subset in combinations(range(n_instruments), subset_size):
                subset_matrix = matrix[:, subset]
                subset_solution, *_ = np.linalg.lstsq(
                    subset_matrix,
                    target,
                    rcond=None,
                )
                if np.any(subset_solution < -1e-9):
                    continue

                multipliers = np.zeros(n_instruments, dtype=float)
                multipliers[list(subset)] = np.maximum(subset_solution, 0.0)
                error = float(np.sum((matrix @ multipliers - target) ** 2))
                if error < best_error:
                    best_error = error
                    best_multipliers = multipliers

        return best_multipliers

    def _single_dv01_hedge(self) -> dict[str, Any]:
        """Build a single-instrument hedge sized to total liability DV01."""
        instrument_index = self._single_instrument_index()
        instrument = self.instruments[instrument_index]
        liability_dv01 = self._liability_total_dv01()
        multiplier = 0.0 if instrument.dv01 == 0.0 else -liability_dv01 / instrument.dv01
        multipliers = np.zeros(len(self.instruments), dtype=float)
        multipliers[instrument_index] = max(multiplier, 0.0)
        return self._build_hedge_result("Single DV01 Hedge", multipliers)

    def _build_hedge_result(
        self,
        name: str,
        multipliers: np.ndarray,
    ) -> dict[str, Any]:
        """Return allocation, KRD, residual, and risk metrics for a hedge."""
        portfolio_krd = self._portfolio_krd(multipliers)
        residual_krd = {
            bucket: self.liability_krd[bucket] + portfolio_krd[bucket]
            for bucket in self.buckets
        }
        hedge_dv01 = sum(
            multiplier * instrument.dv01
            for multiplier, instrument in zip(multipliers, self.instruments)
        )
        liability_dv01 = self._liability_total_dv01()
        residual_total_dv01 = liability_dv01 + hedge_dv01
        residual_risk_score = math.sqrt(sum(value**2 for value in residual_krd.values()))

        return {
            "name": name,
            "allocations": self._allocations(multipliers),
            "portfolio_krd": portfolio_krd,
            "residual_krd": residual_krd,
            "hedge_dv01": hedge_dv01,
            "hedge_ratio": 0.0 if liability_dv01 == 0.0 else -hedge_dv01 / liability_dv01,
            "total_dv01_mismatch": residual_total_dv01,
            "residual_risk_score": residual_risk_score,
        }

    def _comparison_summary(self, result: dict[str, Any]) -> dict[str, Any]:
        """Return compact comparison metrics for one hedge approach."""
        return {
            "hedge_ratio": result["hedge_ratio"],
            "total_dv01_mismatch": result["total_dv01_mismatch"],
            "bucket_mismatch": result["residual_krd"],
            "residual_risk_score": result["residual_risk_score"],
            "allocations": result["allocations"],
        }

    def _stress_results(
        self,
        single: dict[str, Any],
        multi: dict[str, Any],
    ) -> dict[str, list[dict[str, float | str]]]:
        """Compare hedge approaches under standard curve scenarios."""
        scenarios = self._stress_scenarios()
        return {
            "single_dv01_hedge": [
                self._stress_row(scenario_name, shocks, single)
                for scenario_name, shocks in scenarios.items()
            ],
            "multi_instrument_krd_hedge": [
                self._stress_row(scenario_name, shocks, multi)
                for scenario_name, shocks in scenarios.items()
            ],
        }

    def _stress_row(
        self,
        scenario_name: str,
        shocks_bps: dict[str, float],
        hedge_result: dict[str, Any],
    ) -> dict[str, float | str]:
        """Return one funding-ratio stress row."""
        liability_pv_change = -sum(
            self.liability_krd[bucket] * shocks_bps[bucket]
            for bucket in self.buckets
        )
        hedge_portfolio_change = sum(
            hedge_result["portfolio_krd"][bucket] * shocks_bps[bucket]
            for bucket in self.buckets
        )
        stressed_liability_pv = self.liability_pv + liability_pv_change
        stressed_assets = self.asset_market_value + hedge_portfolio_change
        base_funding_ratio = self.asset_market_value / self.liability_pv
        stressed_funding_ratio = stressed_assets / stressed_liability_pv

        return {
            "scenario": scenario_name,
            "liability_pv_change": liability_pv_change,
            "hedge_portfolio_change": hedge_portfolio_change,
            "funding_ratio_change": stressed_funding_ratio - base_funding_ratio,
        }

    def _stress_scenarios(self) -> dict[str, dict[str, float]]:
        """Return standard KRD stress scenarios in basis points."""
        return {
            "Parallel +100bp": {bucket: 100.0 for bucket in self.buckets},
            "Parallel -100bp": {bucket: -100.0 for bucket in self.buckets},
            "Bear Steepener": self._slope_shock(short_bps=25.0, long_bps=100.0),
            "Bull Flattener": self._slope_shock(short_bps=-100.0, long_bps=-25.0),
        }

    def _recommendation(self, single: dict[str, Any], multi: dict[str, Any]) -> str:
        """Return a concise institutional LDI recommendation."""
        single_score = single["residual_risk_score"]
        multi_score = multi["residual_risk_score"]
        improvement = 0.0 if single_score == 0.0 else 1.0 - multi_score / single_score
        largest_bucket = max(self.liability_krd, key=lambda bucket: abs(self.liability_krd[bucket]))
        active_allocations = [
            allocation
            for allocation in multi["allocations"]
            if abs(allocation["recommended_notional"]) > 1.0
        ]
        instrument_names = ", ".join(
            allocation["name"] for allocation in active_allocations[:3]
        )

        return (
            f"The liability profile is most concentrated in the {largest_bucket} "
            f"bucket. A single DV01 hedge leaves residual curve risk because it "
            f"matches total duration but not the KRD shape. The optimized hedge "
            f"uses {instrument_names or 'the selected instruments'} and reduces "
            f"the KRD residual risk score by approximately {improvement:.0%}."
        )

    def _allocations(self, multipliers: np.ndarray) -> list[dict[str, float | str]]:
        """Return optimized instrument allocations."""
        rows = []
        for multiplier, instrument in zip(multipliers, self.instruments):
            rows.append(
                {
                    "name": instrument.name,
                    "type": instrument.type,
                    "base_notional": instrument.notional,
                    "allocation_multiplier": float(multiplier),
                    "recommended_notional": float(multiplier * instrument.notional),
                    "portfolio_dv01": float(multiplier * instrument.dv01),
                }
            )
        return rows

    def _portfolio_krd(self, multipliers: np.ndarray) -> dict[str, float]:
        """Return aggregate hedge KRD by bucket."""
        return {
            bucket: float(
                sum(
                    multiplier * instrument.krd.get(bucket, 0.0)
                    for multiplier, instrument in zip(multipliers, self.instruments)
                )
            )
            for bucket in self.buckets
        }

    def _krd_matrix(self) -> np.ndarray:
        """Return bucket-by-instrument KRD exposure matrix."""
        return np.array(
            [
                [instrument.krd.get(bucket, 0.0) for instrument in self.instruments]
                for bucket in self.buckets
            ],
            dtype=float,
        )

    def _liability_vector(self) -> np.ndarray:
        """Return liability KRD vector in bucket order."""
        return np.array([self.liability_krd[bucket] for bucket in self.buckets], dtype=float)

    def _ordered_buckets(self) -> list[str]:
        """Return standard buckets first, then any custom buckets."""
        custom_buckets = [
            bucket for bucket in self.liability_krd if bucket not in STANDARD_BUCKETS
        ]
        return [
            bucket
            for bucket in [*STANDARD_BUCKETS, *custom_buckets]
            if bucket in self.liability_krd
        ]

    def _single_instrument_index(self) -> int:
        """Choose the selected instrument with the largest absolute DV01."""
        return max(
            range(len(self.instruments)),
            key=lambda index: abs(self.instruments[index].dv01),
        )

    def _liability_total_dv01(self) -> float:
        """Return aggregate liability DV01 across KRD buckets."""
        return sum(self.liability_krd.values())

    def _slope_shock(self, short_bps: float, long_bps: float) -> dict[str, float]:
        """Return a simple maturity-ordered slope shock."""
        if len(self.buckets) == 1:
            return {self.buckets[0]: long_bps}
        return {
            bucket: short_bps
            + (long_bps - short_bps) * index / (len(self.buckets) - 1)
            for index, bucket in enumerate(self.buckets)
        }

    @staticmethod
    def _coerce_instruments(
        selected_instruments: list[dict[str, Any] | HedgeInstrument] | None,
    ) -> list[HedgeInstrument]:
        """Return selected instruments or the default universe."""
        raw_instruments = selected_instruments or default_instrument_universe()
        return [
            instrument
            if isinstance(instrument, HedgeInstrument)
            else HedgeInstrument.from_dict(instrument)
            for instrument in raw_instruments
        ]

    def _validate_inputs(self) -> None:
        """Validate optimizer inputs."""
        if not self.liability_krd:
            raise ValueError("liability_krd must contain at least one bucket.")
        if not self.instruments:
            raise ValueError("At least one hedge instrument is required.")
        if not isinstance(self.asset_market_value, (int, float)):
            raise TypeError("asset_market_value must be numeric.")
        if not isinstance(self.liability_pv, (int, float)):
            raise TypeError("liability_pv must be numeric.")
        if self.asset_market_value < 0.0:
            raise ValueError("asset_market_value must be non-negative.")
        if self.liability_pv <= 0.0:
            raise ValueError("liability_pv must be positive.")

        for bucket, value in self.liability_krd.items():
            if not isinstance(bucket, str):
                raise TypeError("liability_krd bucket names must be strings.")
            if value < 0.0:
                raise ValueError("liability_krd values must be non-negative.")

        for instrument in self.instruments:
            if instrument.notional <= 0.0:
                raise ValueError("Instrument notional must be positive.")
            if not instrument.krd:
                raise ValueError("Instrument krd must contain at least one bucket.")
