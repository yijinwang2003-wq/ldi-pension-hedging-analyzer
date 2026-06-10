"""Period-over-period funding-ratio attribution for LDI reporting."""

from __future__ import annotations


class FundingAttribution:
    """Decompose funding-ratio change into explainable LDI drivers."""

    def __init__(
        self,
        beginning_assets: float,
        ending_assets: float,
        beginning_liability_pv: float,
        ending_liability_pv: float,
        asset_return: float = 0.0,
        liability_discount_rate_change: float = 0.0,
        benefit_payments: float = 0.0,
        hedge_return: float = 0.0,
    ) -> None:
        """Initialize beginning/end values and period drivers."""
        self.beginning_assets = beginning_assets
        self.ending_assets = ending_assets
        self.beginning_liability_pv = beginning_liability_pv
        self.ending_liability_pv = ending_liability_pv
        self.asset_return = asset_return
        self.liability_discount_rate_change = liability_discount_rate_change
        self.benefit_payments = benefit_payments
        self.hedge_return = hedge_return
        self._validate_inputs()

    def decompose(self) -> dict[str, float]:
        """Return funding-ratio bridge contributions."""
        beginning_funding_ratio = self.beginning_assets / self.beginning_liability_pv
        ending_funding_ratio = self.ending_assets / self.ending_liability_pv
        total_change = ending_funding_ratio - beginning_funding_ratio

        asset_return_contribution = self.asset_return / self.beginning_liability_pv
        liability_discount_rate_contribution = (
            -self.beginning_assets
            * self.liability_discount_rate_change
            / self.beginning_liability_pv**2
        )
        cash_flow_contribution = self.benefit_payments / self.beginning_liability_pv
        hedge_contribution = self.hedge_return / self.beginning_liability_pv
        explained = (
            asset_return_contribution
            + liability_discount_rate_contribution
            + cash_flow_contribution
            + hedge_contribution
        )

        return {
            "beginning_funding_ratio": beginning_funding_ratio,
            "ending_funding_ratio": ending_funding_ratio,
            "total_change": total_change,
            "asset_return_contribution": asset_return_contribution,
            "liability_discount_rate_contribution": (
                liability_discount_rate_contribution
            ),
            "cash_flow_contribution": cash_flow_contribution,
            "hedge_contribution": hedge_contribution,
            "residual_contribution": total_change - explained,
        }

    def _validate_inputs(self) -> None:
        """Validate attribution inputs."""
        for field_name in (
            "beginning_assets",
            "ending_assets",
            "beginning_liability_pv",
            "ending_liability_pv",
            "asset_return",
            "liability_discount_rate_change",
            "benefit_payments",
            "hedge_return",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric.")

        if self.beginning_assets < 0.0:
            raise ValueError("beginning_assets must be non-negative.")
        if self.ending_assets < 0.0:
            raise ValueError("ending_assets must be non-negative.")
        if self.beginning_liability_pv <= 0.0:
            raise ValueError("beginning_liability_pv must be positive.")
        if self.ending_liability_pv <= 0.0:
            raise ValueError("ending_liability_pv must be positive.")
