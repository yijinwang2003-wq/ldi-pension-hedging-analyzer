"""Pension de-risking glide path policy recommendations."""

from __future__ import annotations


class GlidePathAdvisor:
    """Apply a simple funded-status-based hedge-ratio glide path."""

    POLICY_POINTS = [
        {"min": 0.0, "max": 0.80, "target": 0.40},
        {"min": 0.80, "max": 0.90, "target": 0.65},
        {"min": 0.90, "max": 1.00, "target": 0.80},
        {"min": 1.00, "max": float("inf"), "target": 0.95},
    ]

    def __init__(
        self,
        funding_ratio: float,
        current_hedge_ratio: float,
        liability_dv01: float,
        current_hedge_portfolio_dv01: float,
        dv01_per_notional: float | None = None,
    ) -> None:
        """Initialize glide path inputs."""
        self.funding_ratio = funding_ratio
        self.current_hedge_ratio = current_hedge_ratio
        self.liability_dv01 = liability_dv01
        self.current_hedge_portfolio_dv01 = current_hedge_portfolio_dv01
        self.dv01_per_notional = dv01_per_notional
        self._validate_inputs()

    def recommendation(self) -> dict[str, float | str | list[dict[str, float]]]:
        """Return target hedge ratio, gap analysis, and action narrative."""
        target_hedge_ratio = self.target_hedge_ratio(self.funding_ratio)
        target_hedge_dv01 = target_hedge_ratio * self.liability_dv01
        additional_dv01_needed = (
            target_hedge_dv01 - self.current_hedge_portfolio_dv01
        )
        suggested_notional_change = self._suggested_notional_change(
            additional_dv01_needed
        )
        recommended_action = self._action(additional_dv01_needed)

        return {
            "funding_ratio": self.funding_ratio,
            "current_hedge_ratio": self.current_hedge_ratio,
            "target_hedge_ratio": target_hedge_ratio,
            "hedge_ratio_gap": target_hedge_ratio - self.current_hedge_ratio,
            "current_hedge_portfolio_dv01": self.current_hedge_portfolio_dv01,
            "target_hedge_dv01": target_hedge_dv01,
            "additional_dv01_needed": additional_dv01_needed,
            "suggested_notional_change": suggested_notional_change,
            "recommended_action": recommended_action,
            "policy_curve": self.policy_curve(),
            "narrative": self._narrative(
                target_hedge_ratio=target_hedge_ratio,
                additional_dv01_needed=additional_dv01_needed,
                recommended_action=recommended_action,
            ),
        }

    @classmethod
    def target_hedge_ratio(cls, funding_ratio: float) -> float:
        """Return policy target hedge ratio for a funding ratio."""
        for point in cls.POLICY_POINTS:
            if point["min"] <= funding_ratio < point["max"]:
                return point["target"]
        return cls.POLICY_POINTS[-1]["target"]

    @classmethod
    def policy_curve(cls) -> list[dict[str, float]]:
        """Return display points for the glide path curve."""
        return [
            {"funding_ratio": 0.75, "target_hedge_ratio": 0.40},
            {"funding_ratio": 0.80, "target_hedge_ratio": 0.65},
            {"funding_ratio": 0.90, "target_hedge_ratio": 0.80},
            {"funding_ratio": 1.00, "target_hedge_ratio": 0.95},
            {"funding_ratio": 1.10, "target_hedge_ratio": 0.95},
        ]

    def _suggested_notional_change(self, additional_dv01_needed: float) -> float | None:
        """Convert DV01 gap to notional when a DV01 scale is supplied."""
        if self.dv01_per_notional is None or self.dv01_per_notional == 0.0:
            return None
        return additional_dv01_needed / self.dv01_per_notional

    @staticmethod
    def _action(additional_dv01_needed: float) -> str:
        """Return a short action label."""
        if additional_dv01_needed > 0.0:
            return "Increase hedge allocation"
        if additional_dv01_needed < 0.0:
            return "Decrease hedge allocation"
        return "Maintain hedge allocation"

    def _narrative(
        self,
        target_hedge_ratio: float,
        additional_dv01_needed: float,
        recommended_action: str,
    ) -> str:
        """Return an interview-friendly glide path explanation."""
        return (
            f"The plan is {self.funding_ratio:.0%} funded. Under the glide path "
            f"policy, this maps to a {target_hedge_ratio:.0%} target hedge ratio "
            f"versus the current {self.current_hedge_ratio:.0%}. The recommended "
            f"action is to {recommended_action.lower()} by approximately "
            f"${abs(additional_dv01_needed):,.2f} of DV01. This simulates an "
            "institutional de-risking policy that increases hedge allocations as "
            "funded status improves and helps lock in gains."
        )

    def _validate_inputs(self) -> None:
        """Validate glide path inputs."""
        for field_name in (
            "funding_ratio",
            "current_hedge_ratio",
            "liability_dv01",
            "current_hedge_portfolio_dv01",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric.")

        if self.funding_ratio < 0.0:
            raise ValueError("funding_ratio must be non-negative.")
        if self.current_hedge_ratio < 0.0:
            raise ValueError("current_hedge_ratio must be non-negative.")
        if self.liability_dv01 < 0.0:
            raise ValueError("liability_dv01 must be non-negative.")
        if self.current_hedge_portfolio_dv01 < 0.0:
            raise ValueError("current_hedge_portfolio_dv01 must be non-negative.")
        if self.dv01_per_notional is not None and not isinstance(
            self.dv01_per_notional,
            (int, float),
        ):
            raise TypeError("dv01_per_notional must be numeric.")
