"""FastAPI routes for multi-instrument KRD hedge optimization."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.multi_hedge import (
    MultiInstrumentHedgeOptimizer,
    default_instrument_universe,
)


router = APIRouter(prefix="/hedging", tags=["hedging"])


class HedgeInstrumentPayload(BaseModel):
    """API payload for one hedge instrument."""

    name: str
    type: str
    notional: float
    dv01: float
    krd: dict[str, float]


class MultiInstrumentHedgeRequest(BaseModel):
    """Request payload for multi-instrument KRD hedge optimization."""

    liability_krd: dict[str, float] = Field(
        ...,
        example={
            "1Y": 50_000.0,
            "5Y": 150_000.0,
            "10Y": 400_000.0,
            "20Y": 350_000.0,
            "30Y": 250_000.0,
        },
    )
    selected_instruments: list[HedgeInstrumentPayload] | None = Field(
        None,
        description="Optional instrument list. Defaults to the starter universe.",
    )
    asset_market_value: float = Field(
        100_000_000.0,
        description="Asset value used for funding-ratio stress tests.",
    )
    liability_pv: float = Field(
        100_000_000.0,
        description="Liability PV used for funding-ratio stress tests.",
    )


class MultiInstrumentHedgeResponse(BaseModel):
    """Response payload for multi-instrument KRD hedge optimization."""

    recommended_allocations: list[dict[str, float | str]]
    hedge_ratio: float
    residual_krd: dict[str, float]
    portfolio_krd: dict[str, float]
    liability_krd: dict[str, float]
    comparison: dict[str, Any]
    stress_results: dict[str, list[dict[str, float | str]]]
    recommendation: str


@router.get("/multi-instrument/universe")
def get_default_instrument_universe() -> dict[str, list[dict[str, Any]]]:
    """Return the default hedge instrument universe for frontend demos."""
    return {
        "instruments": [
            instrument.as_dict() for instrument in default_instrument_universe()
        ]
    }


@router.post("/multi-instrument", response_model=MultiInstrumentHedgeResponse)
def optimize_multi_instrument_hedge(
    request: MultiInstrumentHedgeRequest,
) -> MultiInstrumentHedgeResponse:
    """Optimize a multi-instrument hedge against liability key-rate DV01."""
    try:
        optimizer = MultiInstrumentHedgeOptimizer(
            liability_krd=request.liability_krd,
            selected_instruments=[
                instrument.model_dump()
                if hasattr(instrument, "model_dump")
                else instrument.dict()
                for instrument in request.selected_instruments
            ]
            if request.selected_instruments is not None
            else None,
            asset_market_value=request.asset_market_value,
            liability_pv=request.liability_pv,
        )
        result = optimizer.optimize()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiInstrumentHedgeResponse(**result)
