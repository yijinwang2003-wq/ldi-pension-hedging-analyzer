"""FastAPI routes for scenario analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.scenarios import VasicekModel


router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class VasicekRequest(BaseModel):
    """Request payload for Vasicek Monte Carlo simulation."""

    kappa: float = Field(..., description="Mean-reversion speed.", example=0.30)
    theta: float = Field(..., description="Long-run mean short rate.", example=0.04)
    sigma: float = Field(..., description="Short-rate volatility.", example=0.01)
    r0: float = Field(..., description="Initial short rate.", example=0.035)
    years: float = Field(..., description="Simulation horizon in years.", example=10.0)
    dt: float = Field(
        0.25,
        description="Simulation time step in years.",
        example=0.25,
    )
    n_paths: int = Field(..., description="Number of Monte Carlo paths.", example=500)


class VasicekResponse(BaseModel):
    """Response payload for Vasicek Monte Carlo simulation."""

    paths: list[list[float]]
    terminal_rates: list[float]
    summary: dict[str, float]


@router.post("/vasicek", response_model=VasicekResponse)
def simulate_vasicek(request: VasicekRequest) -> VasicekResponse:
    """Simulate Vasicek short-rate paths and summarize terminal rates."""
    try:
        model = VasicekModel(
            kappa=request.kappa,
            theta=request.theta,
            sigma=request.sigma,
            r0=request.r0,
        )
        paths = model.simulate_paths(
            years=request.years,
            dt=request.dt,
            n_paths=request.n_paths,
        )
        summary = model.summarize_terminal_rates()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return VasicekResponse(
        paths=paths.tolist(),
        terminal_rates=paths[:, -1].tolist(),
        summary=summary,
    )
