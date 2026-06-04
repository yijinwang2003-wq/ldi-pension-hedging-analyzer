"""FastAPI routes for hedge analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.hedging import InterestRateSwap


router = APIRouter(prefix="/hedging", tags=["hedging"])


class SwapRequest(BaseModel):
    """Request payload for interest rate swap analytics."""

    notional: float = Field(..., description="Swap notional amount.", example=1_000_000.0)
    fixed_rate: float = Field(
        ...,
        description="Annual fixed coupon rate, expressed as a decimal.",
        example=0.04,
    )
    maturity_years: int = Field(..., description="Swap maturity in years.", example=5)
    discount_curve: dict[int, float] = Field(
        ...,
        description="Annual spot discount rates by year, expressed as decimals.",
        example={1: 0.035, 2: 0.037, 3: 0.039, 4: 0.041, 5: 0.043},
    )


class HedgeNotionalRequest(SwapRequest):
    """Request payload for hedge notional analytics."""

    liability_dv01: float = Field(
        ...,
        description="Liability DV01 in currency terms.",
        example=5_000.0,
    )


class SwapValueResponse(BaseModel):
    """Response payload for swap valuation analytics."""

    fixed_leg_pv: float
    floating_leg_pv: float
    swap_value: float
    swap_dv01: float


class HedgeNotionalResponse(BaseModel):
    """Response payload for hedge notional analytics."""

    liability_dv01: float
    swap_dv01: float
    hedge_notional: float


@router.post("/swap-value", response_model=SwapValueResponse)
def calculate_swap_value(request: SwapRequest) -> SwapValueResponse:
    """Calculate swap leg PVs, market value, and signed DV01."""
    swap = _build_interest_rate_swap(request)
    return SwapValueResponse(
        fixed_leg_pv=swap.fixed_leg_pv(),
        floating_leg_pv=swap.floating_leg_pv(),
        swap_value=swap.swap_value(),
        swap_dv01=swap.dv01(),
    )


@router.post("/hedge-notional", response_model=HedgeNotionalResponse)
def calculate_hedge_notional(
    request: HedgeNotionalRequest,
) -> HedgeNotionalResponse:
    """Calculate required hedge notional for a liability DV01."""
    swap = _build_interest_rate_swap(request)
    try:
        swap_dv01 = swap.dv01()
        hedge_notional = swap.hedge_notional(request.liability_dv01)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return HedgeNotionalResponse(
        liability_dv01=request.liability_dv01,
        swap_dv01=swap_dv01,
        hedge_notional=hedge_notional,
    )


def _build_interest_rate_swap(request: SwapRequest) -> InterestRateSwap:
    """Create an interest rate swap and map domain errors to HTTP 400."""
    try:
        return InterestRateSwap(
            notional=request.notional,
            fixed_rate=request.fixed_rate,
            maturity_years=request.maturity_years,
            discount_curve=request.discount_curve,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
