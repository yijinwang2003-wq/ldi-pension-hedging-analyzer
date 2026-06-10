"""FastAPI routes for LDI reporting analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.attribution import FundingAttribution


router = APIRouter(prefix="/reporting", tags=["reporting"])


class FundingAttributionRequest(BaseModel):
    """Request payload for period-over-period funding attribution."""

    beginning_assets: float = Field(..., example=5_000_000.0)
    ending_assets: float = Field(..., example=5_250_000.0)
    beginning_liability_pv: float = Field(..., example=5_500_000.0)
    ending_liability_pv: float = Field(..., example=5_650_000.0)
    asset_return: float = Field(0.0, example=225_000.0)
    liability_discount_rate_change: float = Field(0.0, example=125_000.0)
    benefit_payments: float = Field(0.0, example=100_000.0)
    hedge_return: float = Field(0.0, example=75_000.0)


class FundingAttributionResponse(BaseModel):
    """Response payload for period-over-period funding attribution."""

    beginning_funding_ratio: float
    ending_funding_ratio: float
    total_change: float
    asset_return_contribution: float
    liability_discount_rate_contribution: float
    cash_flow_contribution: float
    hedge_contribution: float
    residual_contribution: float


@router.post("/funding-attribution", response_model=FundingAttributionResponse)
def calculate_funding_attribution(
    request: FundingAttributionRequest,
) -> FundingAttributionResponse:
    """Decompose funding-ratio change into explainable LDI drivers."""
    try:
        attribution = FundingAttribution(
            beginning_assets=request.beginning_assets,
            ending_assets=request.ending_assets,
            beginning_liability_pv=request.beginning_liability_pv,
            ending_liability_pv=request.ending_liability_pv,
            asset_return=request.asset_return,
            liability_discount_rate_change=request.liability_discount_rate_change,
            benefit_payments=request.benefit_payments,
            hedge_return=request.hedge_return,
        )
        result = attribution.decompose()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FundingAttributionResponse(**result)
