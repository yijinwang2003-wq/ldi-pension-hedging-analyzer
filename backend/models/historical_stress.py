"""Historical interest-rate stress testing for LDI portfolios."""

from __future__ import annotations


HISTORICAL_SCENARIOS: dict[str, dict[str, float]] = {
    "2008 Financial Crisis (Oct 2008)": {
        "2Y": -150.0,
        "5Y": -180.0,
        "10Y": -160.0,
        "20Y": -120.0,
        "30Y": -100.0,
    },
    "2020 COVID Shock (Feb-Mar 2020)": {
        "2Y": -140.0,
        "5Y": -130.0,
        "10Y": -125.0,
        "20Y": -110.0,
        "30Y": -95.0,
    },
    "2022 Fed Hiking Cycle (Jan-Dec 2022)": {
        "2Y": 370.0,
        "5Y": 320.0,
        "10Y": 236.0,
        "20Y": 200.0,
        "30Y": 178.0,
    },
}


class HistoricalStressTester:
    """Evaluate funded-status sensitivity to historical rate regimes."""

    def __init__(
        self,
        liability_krd: dict[str, float],
        hedge_krd: dict[str, float] | None = None,
        asset_market_value: float = 100_000_000.0,
        liability_pv: float = 100_000_000.0,
        asset_return_shocks: dict[str, float] | None = None,
    ) -> None:
        """Initialize stress inputs.

        `asset_return_shocks` maps scenario name to non-hedging asset return in
        decimal form. For example, `-0.08` is an 8% decline. Missing scenarios
        default to zero non-hedging asset movement.
        """
        self.liability_krd = {
            str(bucket): float(value) for bucket, value in liability_krd.items()
        }
        self.hedge_krd = {
            str(bucket): float(value) for bucket, value in (hedge_krd or {}).items()
        }
        self.asset_market_value = asset_market_value
        self.liability_pv = liability_pv
        self.asset_return_shocks = dict(asset_return_shocks or {})
        self._validate_inputs()

    def run(self) -> list[dict[str, float | str]]:
        """Return historical stress results for each hardcoded scenario."""
        return [
            self._scenario_result(scenario_name, shocks_bps)
            for scenario_name, shocks_bps in HISTORICAL_SCENARIOS.items()
        ]

    def ranked_by_severity(self) -> list[dict[str, float | str]]:
        """Return scenarios ranked by worst hedged funding-ratio change."""
        return sorted(
            self.run(),
            key=lambda row: float(row["funding_ratio_after_hedged"])
            - float(row["funding_ratio_before"]),
        )

    def _scenario_result(
        self,
        scenario_name: str,
        shocks_bps: dict[str, float],
    ) -> dict[str, float | str]:
        """Calculate one historical stress scenario."""
        funding_ratio_before = self.asset_market_value / self.liability_pv
        liability_change = self._krd_change(self.liability_krd, shocks_bps, sign=-1.0)
        hedge_change = self._krd_change(self.hedge_krd, shocks_bps, sign=1.0)
        asset_value_change = self.asset_market_value * self.asset_return_shocks.get(
            scenario_name,
            0.0,
        )

        stressed_liability_pv = self.liability_pv + liability_change
        if stressed_liability_pv <= 0.0:
            raise ValueError("Stressed liability PV must remain positive.")

        funding_ratio_after_unhedged = (
            self.asset_market_value + asset_value_change
        ) / stressed_liability_pv
        funding_ratio_after_hedged = (
            self.asset_market_value + asset_value_change + hedge_change
        ) / stressed_liability_pv

        return {
            "scenario": scenario_name,
            "funding_ratio_before": funding_ratio_before,
            "funding_ratio_after_hedged": funding_ratio_after_hedged,
            "funding_ratio_after_unhedged": funding_ratio_after_unhedged,
            "liability_change": liability_change,
            "asset_value_change": asset_value_change,
            "hedge_change": hedge_change,
            "hedged_funding_ratio_change": (
                funding_ratio_after_hedged - funding_ratio_before
            ),
            "unhedged_funding_ratio_change": (
                funding_ratio_after_unhedged - funding_ratio_before
            ),
        }

    @staticmethod
    def _krd_change(
        krd: dict[str, float],
        shocks_bps: dict[str, float],
        sign: float,
    ) -> float:
        """Return value change from KRD exposures and rate shocks."""
        return sign * sum(
            krd.get(bucket, 0.0) * shock_bps
            for bucket, shock_bps in shocks_bps.items()
        )

    def _validate_inputs(self) -> None:
        """Validate historical stress inputs."""
        if not self.liability_krd:
            raise ValueError("liability_krd must contain at least one bucket.")
        for field_name in ("asset_market_value", "liability_pv"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric.")
        if self.asset_market_value < 0.0:
            raise ValueError("asset_market_value must be non-negative.")
        if self.liability_pv <= 0.0:
            raise ValueError("liability_pv must be positive.")

        for mapping_name in ("liability_krd", "hedge_krd"):
            mapping = getattr(self, mapping_name)
            for bucket, value in mapping.items():
                if not isinstance(bucket, str):
                    raise TypeError(f"{mapping_name} bucket names must be strings.")
                if not isinstance(value, (int, float)):
                    raise TypeError(f"{mapping_name} values must be numeric.")
