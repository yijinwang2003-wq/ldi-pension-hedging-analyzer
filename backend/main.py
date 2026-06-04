"""FastAPI application entry point for the LDI Pension Hedging Analyzer."""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.hedging import router as hedging_router
from backend.api.liability import router as liability_router
from backend.api.scenarios import router as scenarios_router


app = FastAPI(
    title="LDI Pension Hedging Analyzer",
    description=(
        "API for pension liability valuation, interest-rate hedging, and "
        "scenario analysis."
    ),
    version="0.1.0",
)

app.include_router(liability_router, prefix="/api")
app.include_router(hedging_router, prefix="/api")
app.include_router(scenarios_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    """Return application health and project metadata."""
    return {
        "project": "LDI Pension Hedging Analyzer",
        "status": "running",
    }
