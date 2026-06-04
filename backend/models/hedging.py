"""Interest-rate hedging instruments for liability-driven investing."""

from __future__ import annotations


class InterestRateSwap:
    """Plain-vanilla annual-pay fixed-for-floating interest rate swap.

    Parameters
    ----------
    notional:
        Swap notional amount.
    fixed_rate:
        Annual fixed coupon rate, expressed as a decimal. For example,
        ``0.035`` represents 3.5%.
    maturity_years:
        Swap maturity in whole years.
    discount_curve:
        Mapping from year to annual spot discount rate, expressed as a decimal.

    Notes
    -----
    This model assumes annual fixed payments and annual compounding:

    ``discount_factor_t = 1 / (1 + discount_rate_t) ** t``

    The floating leg is approximated as ``notional * (1 - DF_T)``, which is
    standard for a par floating leg between reset dates in a simple interview
    project setting.
    """

    BASIS_POINT: float = 0.0001

    def __init__(
        self,
        notional: float,
        fixed_rate: float,
        maturity_years: int,
        discount_curve: dict[int, float],
    ) -> None:
        """Initialize and validate an interest rate swap."""
        self.notional = notional
        self.fixed_rate = fixed_rate
        self.maturity_years = maturity_years
        self.discount_curve = dict(discount_curve)
        self._validate_inputs()

    def fixed_leg_pv(self) -> float:
        """Return the present value of annual fixed coupon payments."""
        return self._fixed_leg_pv(self.discount_curve)

    def floating_leg_pv(self) -> float:
        """Return the approximate present value of the floating leg."""
        return self._floating_leg_pv(self.discount_curve)

    def swap_value(self) -> float:
        """Return swap value as floating leg PV minus fixed leg PV.

        A positive value benefits a receive-floating/pay-fixed position.
        """
        return self.floating_leg_pv() - self.fixed_leg_pv()

    def dv01(self) -> float:
        """Return swap DV01 for a one-basis-point parallel rate move.

        DV01 is signed and computed with a symmetric finite difference:

        ``DV01 = (value(-1 bp) - value(+1 bp)) / 2``

        The sign follows the swap value convention. Under ``floating - fixed``,
        a receive-floating/pay-fixed swap will typically have negative DV01.
        """
        value_down = self._swap_value_under_parallel_shift(-1.0)
        value_up = self._swap_value_under_parallel_shift(1.0)
        return (value_down - value_up) / 2.0

    def hedge_notional(self, liability_dv01: float) -> float:
        """Return the swap notional required to hedge a liability DV01.

        Parameters
        ----------
        liability_dv01:
            Liability DV01 in currency terms.

        Returns
        -------
        float
            Notional of the same swap structure needed to offset the liability
            DV01. The sign indicates hedge direction under this swap's value
            convention.

        Raises
        ------
        ValueError
            If the current swap DV01 is zero.
        """
        if not isinstance(liability_dv01, (int, float)):
            raise TypeError("liability_dv01 must be numeric.")

        swap_dv01 = self.dv01()
        if swap_dv01 == 0.0:
            raise ValueError("Cannot hedge with a swap whose DV01 is zero.")

        return liability_dv01 * self.notional / swap_dv01

    def _swap_value_under_parallel_shift(self, shift_bps: float) -> float:
        """Return swap value after shifting all discount rates in parallel."""
        shifted_curve = {
            year: rate + shift_bps * self.BASIS_POINT
            for year, rate in self.discount_curve.items()
        }
        return self._floating_leg_pv(shifted_curve) - self._fixed_leg_pv(
            shifted_curve
        )

    def _fixed_leg_pv(self, discount_curve: dict[int, float]) -> float:
        """Return fixed leg PV using the supplied discount curve."""
        annual_coupon = self.notional * self.fixed_rate
        return sum(
            annual_coupon * self._discount_factor(year, discount_curve)
            for year in range(1, self.maturity_years + 1)
        )

    def _floating_leg_pv(self, discount_curve: dict[int, float]) -> float:
        """Return approximate floating leg PV using the supplied curve."""
        maturity_discount_factor = self._discount_factor(
            self.maturity_years,
            discount_curve,
        )
        return self.notional * (1.0 - maturity_discount_factor)

    @staticmethod
    def _discount_factor(year: int, discount_curve: dict[int, float]) -> float:
        """Return the annual-compounded discount factor for a year."""
        return 1.0 / (1.0 + discount_curve[year]) ** year

    def _validate_inputs(self) -> None:
        """Validate swap terms and required discount-curve points."""
        if not isinstance(self.notional, (int, float)):
            raise TypeError("notional must be numeric.")
        if self.notional <= 0.0:
            raise ValueError("notional must be positive.")

        if not isinstance(self.fixed_rate, (int, float)):
            raise TypeError("fixed_rate must be numeric.")
        if self.fixed_rate <= -1.0:
            raise ValueError("fixed_rate must be greater than -100%.")

        if not isinstance(self.maturity_years, int) or isinstance(
            self.maturity_years, bool
        ):
            raise TypeError("maturity_years must be an integer.")
        if self.maturity_years <= 0:
            raise ValueError("maturity_years must be positive.")

        for year in range(1, self.maturity_years + 1):
            if year not in self.discount_curve:
                raise ValueError(f"Missing discount rate for year {year}.")

        for year, rate in self.discount_curve.items():
            if not isinstance(year, int) or isinstance(year, bool):
                raise TypeError("discount_curve years must be integers.")
            if year <= 0:
                raise ValueError("discount_curve years must be positive.")
            if not isinstance(rate, (int, float)):
                raise TypeError("discount rates must be numeric.")
            if rate <= -1.0:
                raise ValueError("discount rates must be greater than -100%.")
