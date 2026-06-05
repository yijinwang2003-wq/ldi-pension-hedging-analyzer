"""Portfolio aggregation model for LDI asset allocation."""

from __future__ import annotations


class PortfolioModel:
    """Represent a simple LDI portfolio split into growth and hedging assets.

    Parameters
    ----------
    equities:
        Market value of equity assets in the growth portfolio.
    credit:
        Market value of credit assets in the growth portfolio.
    long_bonds:
        Market value of long-duration bond assets in the hedging portfolio.
    irs_exposure:
        Market value or exposure proxy for interest rate swaps in the hedging
        portfolio.
    """

    def __init__(
        self,
        equities: float,
        credit: float,
        long_bonds: float,
        irs_exposure: float,
    ) -> None:
        """Initialize and validate portfolio component market values."""
        self.equities = equities
        self.credit = credit
        self.long_bonds = long_bonds
        self.irs_exposure = irs_exposure
        self._validate_inputs()

    def growth_portfolio(self) -> float:
        """Return total market value of the growth portfolio."""
        return self.equities + self.credit

    def hedging_portfolio(self) -> float:
        """Return total market value of the hedging portfolio."""
        return self.long_bonds + self.irs_exposure

    def total_assets(self) -> float:
        """Return combined growth and hedging portfolio market value."""
        return self.growth_portfolio() + self.hedging_portfolio()

    def growth_allocation(self) -> float:
        """Return growth portfolio share of total assets."""
        return self._allocation(self.growth_portfolio())

    def hedging_allocation(self) -> float:
        """Return hedging portfolio share of total assets."""
        return self._allocation(self.hedging_portfolio())

    def as_dict(self) -> dict[str, float]:
        """Return portfolio components, totals, and allocation weights."""
        return {
            "equities": self.equities,
            "credit": self.credit,
            "long_bonds": self.long_bonds,
            "irs_exposure": self.irs_exposure,
            "growth_portfolio": self.growth_portfolio(),
            "hedging_portfolio": self.hedging_portfolio(),
            "total_assets": self.total_assets(),
            "growth_allocation": self.growth_allocation(),
            "hedging_allocation": self.hedging_allocation(),
        }

    def _allocation(self, value: float) -> float:
        """Return allocation weight, or zero when total assets are zero."""
        total_assets = self.total_assets()
        if total_assets == 0.0:
            return 0.0
        return value / total_assets

    def _validate_inputs(self) -> None:
        """Validate portfolio component market values."""
        for field_name in ("equities", "credit", "long_bonds", "irs_exposure"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric.")
            if value < 0.0:
                raise ValueError(f"{field_name} must be non-negative.")
