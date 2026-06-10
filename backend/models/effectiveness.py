"""Hedge effectiveness metrics for LDI interest-rate risk reporting."""

from __future__ import annotations


class HedgeEffectivenessAnalyzer:
    """Calculate DV01 hedge coverage and funding-ratio rate sensitivity."""

    def __init__(
        self,
        liability_dv01: float,
        hedge_dv01: float,
        asset_market_value: float,
        liability_pv: float,
        target_hedge_ratio: float = 0.90,
        swap_dv01_per_notional: float | None = None,
    ) -> None:
        """Initialize hedge effectiveness inputs."""
        self.liability_dv01 = liability_dv01
        self.hedge_dv01 = hedge_dv01
        self.asset_market_value = asset_market_value
        self.liability_pv = liability_pv
        self.target_hedge_ratio = target_hedge_ratio
        self.swap_dv01_per_notional = swap_dv01_per_notional
        self._validate_inputs()

    def metrics(self) -> dict[str, float | str | dict[str, float]]:
        """Return hedge effectiveness metrics and short recommendation text."""
        hedge_ratio = self.hedge_ratio()
        residual_dv01 = self.residual_dv01()
        shock_results = {
            "+100bp": self.funding_ratio_shock(100.0),
            "-100bp": self.funding_ratio_shock(-100.0),
        }
        required_incremental_dv01 = (
            self.target_hedge_ratio * self.liability_dv01 - self.hedge_dv01
        )
        required_notional = self._required_notional(required_incremental_dv01)

        return {
            "hedge_ratio": hedge_ratio,
            "percent_hedged": hedge_ratio,
            "residual_dv01": residual_dv01,
            "target_hedge_ratio": self.target_hedge_ratio,
            "required_incremental_dv01": required_incremental_dv01,
            "required_incremental_notional": required_notional,
            "funding_ratio_sensitivity": shock_results,
            "recommendation": self.recommendation(
                required_incremental_dv01=required_incremental_dv01,
                required_notional=required_notional,
            ),
        }

    def hedge_ratio(self) -> float:
        """Return hedge portfolio DV01 divided by liability DV01."""
        if self.liability_dv01 == 0.0:
            return 0.0
        return self.hedge_dv01 / self.liability_dv01

    def residual_dv01(self) -> float:
        """Return remaining liability DV01 after hedge coverage."""
        return self.liability_dv01 - self.hedge_dv01

    def funding_ratio_shock(self, shock_bps: float) -> dict[str, float]:
        """Compare unhedged and hedged funding ratios for a rate shock."""
        base_funding_ratio = self.asset_market_value / self.liability_pv
        liability_pv_change = -self.liability_dv01 * shock_bps
        hedge_impact = -self.hedge_dv01 * shock_bps
        shocked_liability_pv = self.liability_pv + liability_pv_change
        if shocked_liability_pv <= 0.0:
            raise ValueError("Shocked liability PV must remain positive.")

        unhedged_funding_ratio = self.asset_market_value / shocked_liability_pv
        hedged_funding_ratio = (
            self.asset_market_value + hedge_impact
        ) / shocked_liability_pv

        return {
            "shock_bps": shock_bps,
            "base_funding_ratio": base_funding_ratio,
            "unhedged_funding_ratio": unhedged_funding_ratio,
            "hedged_funding_ratio": hedged_funding_ratio,
            "unhedged_change": unhedged_funding_ratio - base_funding_ratio,
            "hedged_change": hedged_funding_ratio - base_funding_ratio,
        }

    def recommendation(
        self,
        required_incremental_dv01: float | None = None,
        required_notional: float | None = None,
    ) -> str:
        """Return a concise hedge action narrative."""
        required_dv01 = (
            self.target_hedge_ratio * self.liability_dv01 - self.hedge_dv01
            if required_incremental_dv01 is None
            else required_incremental_dv01
        )
        notional = (
            self._required_notional(required_dv01)
            if required_notional is None
            else required_notional
        )
        ratio = self.hedge_ratio()

        if required_dv01 <= 0.0:
            return (
                f"Current hedge ratio is {ratio:.0%}. The portfolio meets the "
                f"{self.target_hedge_ratio:.0%} hedge target."
            )
        if notional is None:
            return (
                f"Current hedge ratio is {ratio:.0%}. To reach "
                f"{self.target_hedge_ratio:.0%}, add approximately "
                f"${required_dv01:,.2f} of DV01 through swaps or long bonds."
            )
        return (
            f"Current hedge ratio is {ratio:.0%}. To reach "
            f"{self.target_hedge_ratio:.0%}, increase IRS notional by "
            f"approximately ${notional:,.2f}."
        )

    def _required_notional(self, required_incremental_dv01: float) -> float | None:
        """Translate required DV01 into notional when a swap DV01 scale exists."""
        if self.swap_dv01_per_notional is None:
            return None
        if self.swap_dv01_per_notional == 0.0:
            return None
        return required_incremental_dv01 / self.swap_dv01_per_notional

    def _validate_inputs(self) -> None:
        """Validate hedge effectiveness inputs."""
        for field_name in (
            "liability_dv01",
            "hedge_dv01",
            "asset_market_value",
            "liability_pv",
            "target_hedge_ratio",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric.")

        if self.liability_dv01 < 0.0:
            raise ValueError("liability_dv01 must be non-negative.")
        if self.asset_market_value < 0.0:
            raise ValueError("asset_market_value must be non-negative.")
        if self.liability_pv <= 0.0:
            raise ValueError("liability_pv must be positive.")
        if self.target_hedge_ratio < 0.0:
            raise ValueError("target_hedge_ratio must be non-negative.")
        if self.swap_dv01_per_notional is not None and not isinstance(
            self.swap_dv01_per_notional,
            (int, float),
        ):
            raise TypeError("swap_dv01_per_notional must be numeric.")
