"""Liability valuation model for pension cash-flow schedules.

This module intentionally contains only core liability analytics. It has no
framework dependencies and can be reused by an API layer, UI layer, or tests.
"""

from __future__ import annotations


class LiabilityModel:
    """Model pension liabilities from projected annual cash flows.

    Parameters
    ----------
    cash_flows:
        Mapping from payment year to pension payment amount. Years are treated
        as annual periods from valuation date, so year ``1`` is paid one year
        from today.
    discount_curve:
        Mapping from year to annual spot discount rate, expressed as a decimal.
        For example, ``0.045`` represents 4.5%.

    Notes
    -----
    Present values use annual compounding:

    ``PV_t = cash_flow_t / (1 + discount_rate_t) ** t``
    """

    BASIS_POINT: float = 0.0001

    def __init__(
        self,
        cash_flows: dict[int, float],
        discount_curve: dict[int, float],
    ) -> None:
        """Initialize and validate a liability model."""
        self.cash_flows = dict(cash_flows)
        self.discount_curve = dict(discount_curve)
        self._validate_inputs()

    def present_value(self) -> float:
        """Return the present value of all projected liability cash flows."""
        return sum(
            self._discounted_cash_flow(year, cash_flow)
            for year, cash_flow in self.cash_flows.items()
        )

    def macaulay_duration(self) -> float:
        """Return the Macaulay duration in years.

        Macaulay duration is the present-value-weighted average payment time.

        Raises
        ------
        ValueError
            If present value is zero, because duration is undefined.
        """
        pv = self.present_value()
        self._ensure_positive_present_value(pv)

        weighted_time = sum(
            year * self._discounted_cash_flow(year, cash_flow)
            for year, cash_flow in self.cash_flows.items()
        )
        return weighted_time / pv

    def modified_duration(self) -> float:
        """Return modified duration for a parallel shift in spot rates.

        With a full discount curve, this is the first-order percentage price
        sensitivity to a parallel rate shift under annual compounding:

        ``modified_duration = -1 / PV * dPV / dy``

        For a flat curve this reduces to ``macaulay_duration / (1 + rate)``.

        Raises
        ------
        ValueError
            If present value is zero, because duration is undefined.
        """
        pv = self.present_value()
        self._ensure_positive_present_value(pv)

        sensitivity = sum(
            year
            * cash_flow
            / (1.0 + self.discount_curve[year]) ** (year + 1)
            for year, cash_flow in self.cash_flows.items()
        )
        return sensitivity / pv

    def dv01(self) -> float:
        """Return the liability DV01 for a one-basis-point rate move.

        DV01 is reported as a positive currency amount for liabilities whose
        value increases when rates fall. It is computed with a symmetric
        finite difference around the current discount curve:

        ``DV01 = (PV(-1 bp) - PV(+1 bp)) / 2``
        """
        pv_down = self.pv_under_parallel_shift(-1.0)
        pv_up = self.pv_under_parallel_shift(1.0)
        return (pv_down - pv_up) / 2.0

    def pv_under_parallel_shift(self, shift_bps: float) -> float:
        """Return present value after a parallel shift to all discount rates.

        Parameters
        ----------
        shift_bps:
            Parallel shift in basis points. Positive values increase rates;
            negative values decrease rates.
        """
        shift = shift_bps * self.BASIS_POINT
        return sum(
            cash_flow / (1.0 + self.discount_curve[year] + shift) ** year
            for year, cash_flow in self.cash_flows.items()
        )

    def key_rate_dv01(self, key_rates: list[int]) -> dict[int, float]:
        """Return key-rate DV01 for selected maturity points.

        For each key rate, only that discount-curve maturity is shifted up and
        down by one basis point. Missing key rates return ``0.0`` because they
        do not affect the current curve representation.

        Parameters
        ----------
        key_rates:
            Maturity points to shock, expressed as positive integer years.

        Returns
        -------
        dict[int, float]
            Mapping from key-rate year to key-rate DV01.
        """
        key_rate_dv01s: dict[int, float] = {}

        for key_rate in key_rates:
            if key_rate not in self.discount_curve:
                key_rate_dv01s[key_rate] = 0.0
                continue

            up_curve = dict(self.discount_curve)
            down_curve = dict(self.discount_curve)
            up_curve[key_rate] += self.BASIS_POINT
            down_curve[key_rate] -= self.BASIS_POINT

            pv_down = self._present_value_with_curve(down_curve)
            pv_up = self._present_value_with_curve(up_curve)
            key_rate_dv01s[key_rate] = (pv_down - pv_up) / 2.0

        return key_rate_dv01s

    def _present_value_with_curve(self, discount_curve: dict[int, float]) -> float:
        """Return present value using a supplied discount curve."""
        return sum(
            cash_flow / (1.0 + discount_curve[year]) ** year
            for year, cash_flow in self.cash_flows.items()
        )

    def _discounted_cash_flow(self, year: int, cash_flow: float) -> float:
        """Return the present value contribution of one cash flow."""
        rate = self.discount_curve[year]
        return cash_flow / (1.0 + rate) ** year

    def _validate_inputs(self) -> None:
        """Validate cash-flow and discount-curve inputs."""
        if not self.cash_flows:
            raise ValueError("cash_flows must contain at least one cash flow.")

        for year, cash_flow in self.cash_flows.items():
            self._validate_year(year, field_name="cash_flows")

            if not isinstance(cash_flow, (int, float)):
                raise TypeError("Cash flow amounts must be numeric.")
            if cash_flow < 0:
                raise ValueError("Cash flow amounts must be non-negative.")

            if year not in self.discount_curve:
                raise ValueError(
                    f"Missing discount rate for cash flow year {year}."
                )

        for year, rate in self.discount_curve.items():
            self._validate_year(year, field_name="discount_curve")

            if not isinstance(rate, (int, float)):
                raise TypeError("Discount rates must be numeric.")
            if rate <= -1.0:
                raise ValueError("Discount rates must be greater than -100%.")

    @staticmethod
    def _validate_year(year: int, field_name: str) -> None:
        """Validate that a year key is a positive integer."""
        if not isinstance(year, int) or isinstance(year, bool):
            raise TypeError(f"{field_name} years must be integers.")
        if year <= 0:
            raise ValueError(f"{field_name} years must be positive integers.")

    @staticmethod
    def _ensure_positive_present_value(present_value: float) -> None:
        """Raise if present value is zero and duration is undefined."""
        if present_value == 0.0:
            raise ValueError("Duration is undefined when present value is zero.")
