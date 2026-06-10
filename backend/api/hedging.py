"""FastAPI routes for hedge analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.effectiveness import HedgeEffectivenessAnalyzer
from backend.models.glide_path import GlidePathAdvisor
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


class HedgeEffectivenessRequest(BaseModel):
    """Request payload for hedge effectiveness reporting."""

    liability_dv01: float = Field(..., description="Liability DV01.", example=5_000.0)
    hedge_dv01: float = Field(
        ...,
        description="Hedging portfolio DV01.",
        example=3_900.0,
    )
    asset_market_value: float = Field(
        ...,
        description="Total plan asset market value.",
        example=5_200_000.0,
    )
    liability_pv: float = Field(
        ...,
        description="Present value of plan liabilities.",
        example=5_600_000.0,
    )
    target_hedge_ratio: float = Field(
        0.90,
        description="Target DV01 hedge ratio.",
        example=0.90,
    )
    swap_dv01_per_notional: float | None = Field(
        None,
        description="Optional swap DV01 per one dollar of notional.",
        example=0.00045,
    )


class HedgeEffectivenessResponse(BaseModel):
    """Response payload for hedge effectiveness reporting."""

    hedge_ratio: float
    percent_hedged: float
    residual_dv01: float
    target_hedge_ratio: float
    required_incremental_dv01: float
    required_incremental_notional: float | None
    funding_ratio_sensitivity: dict[str, dict[str, float]]
    recommendation: str


class GlidePathRequest(BaseModel):
    """Request payload for glide path policy recommendation."""

    funding_ratio: float = Field(..., example=0.92)
    current_hedge_ratio: float = Field(..., example=0.68)
    liability_dv01: float = Field(..., example=1_000_000.0)
    current_hedge_portfolio_dv01: float = Field(..., example=680_000.0)
    dv01_per_notional: float | None = Field(
        None,
        description="Optional DV01 per one dollar of hedge notional.",
        example=0.0005,
    )


class GlidePathResponse(BaseModel):
    """Response payload for glide path policy recommendation."""

    funding_ratio: float
    current_hedge_ratio: float
    target_hedge_ratio: float
    hedge_ratio_gap: float
    current_hedge_portfolio_dv01: float
    target_hedge_dv01: float
    additional_dv01_needed: float
    suggested_notional_change: float | None
    recommended_action: str
    policy_curve: list[dict[str, float]]
    narrative: str


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


@router.post("/effectiveness", response_model=HedgeEffectivenessResponse)
def calculate_hedge_effectiveness(
    request: HedgeEffectivenessRequest,
) -> HedgeEffectivenessResponse:
    """Calculate hedge ratio, residual DV01, and funding-ratio sensitivity."""
    try:
        analyzer = HedgeEffectivenessAnalyzer(
            liability_dv01=request.liability_dv01,
            hedge_dv01=request.hedge_dv01,
            asset_market_value=request.asset_market_value,
            liability_pv=request.liability_pv,
            target_hedge_ratio=request.target_hedge_ratio,
            swap_dv01_per_notional=request.swap_dv01_per_notional,
        )
        metrics = analyzer.metrics()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return HedgeEffectivenessResponse(**metrics)


@router.post("/glide-path", response_model=GlidePathResponse)
def calculate_glide_path(request: GlidePathRequest) -> GlidePathResponse:
    """Apply funded-status glide path policy to hedge allocation."""
    try:
        advisor = GlidePathAdvisor(
            funding_ratio=request.funding_ratio,
            current_hedge_ratio=request.current_hedge_ratio,
            liability_dv01=request.liability_dv01,
            current_hedge_portfolio_dv01=request.current_hedge_portfolio_dv01,
            dv01_per_notional=request.dv01_per_notional,
        )
        recommendation = advisor.recommendation()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GlidePathResponse(**recommendation)


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
