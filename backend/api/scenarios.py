"""FastAPI routes for scenario analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.curve import CurveScenario, CurveScenarioAnalyzer, NelsonSiegelCurve
from backend.models.historical_stress import HistoricalStressTester
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


class CurveTwistRequest(BaseModel):
    """Request payload for curve twist scenario analytics."""

    cash_flows: dict[int, float] = Field(
        ...,
        description="Projected pension payments by year.",
        example={1: 1_000_000.0, 5: 1_250_000.0, 10: 1_500_000.0},
    )
    discount_curve: dict[int, float] = Field(
        ...,
        description="Annual spot discount rates by year, expressed as decimals.",
        example={1: 0.04, 5: 0.043, 10: 0.047},
    )
    asset_market_value: float = Field(
        ...,
        description="Total plan asset market value.",
        example=4_800_000.0,
    )
    hedge_dv01: float = Field(
        0.0,
        description="Hedge portfolio DV01 used when key-rate hedge DV01 is absent.",
        example=3_000.0,
    )
    hedge_key_rate_dv01: dict[int, float] | None = Field(
        None,
        description="Optional hedge DV01 by maturity bucket.",
        example={1: 200.0, 5: 1_000.0, 10: 1_800.0},
    )
    custom_shocks_bps: dict[int, float] | None = Field(
        None,
        description="Optional custom key-rate shocks in basis points.",
        example={1: -25.0, 5: 50.0, 10: 90.0},
    )


class CurveTwistResponse(BaseModel):
    """Response payload for curve twist scenario analytics."""

    results: list[dict[str, float | str | dict[int, float]]]


class NelsonSiegelRequest(BaseModel):
    """Request payload for Nelson-Siegel curve fitting."""

    maturities: list[float] = Field(
        ...,
        description="Market maturity points in years.",
        example=[1.0, 2.0, 5.0, 10.0, 30.0],
    )
    rates: list[float] = Field(
        ...,
        description="Market spot rates, expressed as decimals.",
        example=[0.038, 0.039, 0.041, 0.044, 0.047],
    )
    tau: float | None = Field(
        None,
        description="Optional fixed Nelson-Siegel tau.",
        example=2.5,
    )
    output_years: list[int] = Field(
        ...,
        description="Annual maturities to generate.",
        example=[1, 2, 3, 4, 5, 10, 20, 30],
    )


class NelsonSiegelResponse(BaseModel):
    """Response payload for Nelson-Siegel curve fitting."""

    parameters: dict[str, float]
    discount_curve: dict[int, float]


class HistoricalStressRequest(BaseModel):
    """Request payload for historical funded-status stress testing."""

    liability_krd: dict[str, float] = Field(
        ...,
        example={"2Y": 50_000.0, "5Y": 150_000.0, "10Y": 400_000.0},
    )
    hedge_krd: dict[str, float] | None = Field(
        None,
        example={"2Y": -20_000.0, "5Y": -100_000.0, "10Y": -300_000.0},
    )
    asset_market_value: float = Field(100_000_000.0, example=100_000_000.0)
    liability_pv: float = Field(100_000_000.0, example=100_000_000.0)
    asset_return_shocks: dict[str, float] | None = Field(
        None,
        description="Optional non-hedging asset return shock by scenario name.",
    )


class HistoricalStressResponse(BaseModel):
    """Response payload for historical funded-status stress testing."""

    results: list[dict[str, float | str]]
    ranked_by_severity: list[dict[str, float | str]]


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


@router.post("/curve-twists", response_model=CurveTwistResponse)
def analyze_curve_twists(request: CurveTwistRequest) -> CurveTwistResponse:
    """Analyze liability and funding sensitivity under curve-shape shocks."""
    try:
        analyzer = CurveScenarioAnalyzer(
            cash_flows=request.cash_flows,
            discount_curve=request.discount_curve,
            asset_market_value=request.asset_market_value,
            hedge_dv01=request.hedge_dv01,
            hedge_key_rate_dv01=request.hedge_key_rate_dv01,
        )
        custom_scenario = (
            CurveScenario("Custom key-rate shock", request.custom_shocks_bps)
            if request.custom_shocks_bps
            else None
        )
        results = analyzer.analyze(custom_scenario=custom_scenario)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CurveTwistResponse(results=results)


@router.post("/nelson-siegel", response_model=NelsonSiegelResponse)
def fit_nelson_siegel(request: NelsonSiegelRequest) -> NelsonSiegelResponse:
    """Fit a Nelson-Siegel curve and generate a smooth annual spot curve."""
    try:
        curve = NelsonSiegelCurve(
            maturities=request.maturities,
            rates=request.rates,
            tau=request.tau,
        )
        parameters = curve.fit()
        discount_curve = curve.generate_curve(request.output_years)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return NelsonSiegelResponse(
        parameters=parameters,
        discount_curve=discount_curve,
    )


@router.post("/historical-stress", response_model=HistoricalStressResponse)
def run_historical_stress(
    request: HistoricalStressRequest,
) -> HistoricalStressResponse:
    """Run hardcoded historical rate scenarios against funded status."""
    try:
        tester = HistoricalStressTester(
            liability_krd=request.liability_krd,
            hedge_krd=request.hedge_krd,
            asset_market_value=request.asset_market_value,
            liability_pv=request.liability_pv,
            asset_return_shocks=request.asset_return_shocks,
        )
        results = tester.run()
        ranked_by_severity = tester.ranked_by_severity()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return HistoricalStressResponse(
        results=results,
        ranked_by_severity=ranked_by_severity,
    )
