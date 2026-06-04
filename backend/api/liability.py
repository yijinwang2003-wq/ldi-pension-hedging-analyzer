"""FastAPI routes for liability analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.liability import LiabilityModel


router = APIRouter(prefix="/liability", tags=["liability"])


class LiabilityRequest(BaseModel):
    """Request payload for liability analytics."""

    cash_flows: dict[int, float] = Field(
        ...,
        description="Projected pension payments by year.",
        example={1: 1_000_000.0, 2: 1_050_000.0},
    )
    discount_curve: dict[int, float] = Field(
        ...,
        description="Annual spot discount rates by year, expressed as decimals.",
        example={1: 0.04, 2: 0.042},
    )


class PresentValueResponse(BaseModel):
    """Response payload for present value analytics."""

    present_value: float


class DurationResponse(BaseModel):
    """Response payload for duration analytics."""

    macaulay_duration: float
    modified_duration: float


class DV01Response(BaseModel):
    """Response payload for DV01 analytics."""

    dv01: float


@router.post("/pv", response_model=PresentValueResponse)
def calculate_present_value(request: LiabilityRequest) -> PresentValueResponse:
    """Calculate the present value of pension liability cash flows."""
    model = _build_liability_model(request)
    return PresentValueResponse(present_value=model.present_value())


@router.post("/duration", response_model=DurationResponse)
def calculate_duration(request: LiabilityRequest) -> DurationResponse:
    """Calculate Macaulay and modified duration for liability cash flows."""
    model = _build_liability_model(request)
    try:
        return DurationResponse(
            macaulay_duration=model.macaulay_duration(),
            modified_duration=model.modified_duration(),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/dv01", response_model=DV01Response)
def calculate_dv01(request: LiabilityRequest) -> DV01Response:
    """Calculate liability DV01 for a one-basis-point parallel rate move."""
    model = _build_liability_model(request)
    return DV01Response(dv01=model.dv01())


def _build_liability_model(request: LiabilityRequest) -> LiabilityModel:
    """Create a liability model and map domain validation errors to HTTP 400."""
    try:
        return LiabilityModel(
            cash_flows=request.cash_flows,
            discount_curve=request.discount_curve,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
