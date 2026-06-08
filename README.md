# LDI Pension Hedging Analyzer

[![CI](https://github.com/yijinwang2003-wq/ldi-pension-hedging-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/yijinwang2003-wq/ldi-pension-hedging-analyzer/actions/workflows/ci.yml)

Live Demo:
https://ldi-pension-frontend.onrender.com

API Documentation:
https://ldi-pension-hedging-analyzer.onrender.com/docs

## Overview

LDI Pension Hedging Analyzer is a full-stack Liability-Driven Investment
(LDI) analytics platform designed for defined-benefit pension plans.

The platform helps pension sponsors and investment teams evaluate pension
liabilities, measure interest-rate risk, construct hedging portfolios,
monitor funding status, and generate client-facing reports.

The platform combines clean Python quant models, a FastAPI backend, and a
Streamlit dashboard for interactive analytics.

Built with:

- Python
- FastAPI
- Streamlit
- Plotly
- NumPy
- Pandas
- Pytest

---

## Features

### Liability Analytics

- Present Value
- Macaulay Duration
- Modified Duration
- Parallel DV01
- Key-rate DV01 by maturity bucket
- Hedge maturity suggestion

### Hedge Optimizer

- Interest Rate Swap valuation
- Fixed leg present value
- Floating leg present value approximation
- Signed Swap DV01 calculation
- Hedge notional estimation
- Before/after hedge DV01 risk visualization

### Scenario Analysis

- Vasicek short-rate model
- Euler-Maruyama discretization
- Monte Carlo simulation
- Sample rate-path visualization
- Terminal rate distribution
- Summary statistics for terminal rates
- Parallel shift stress scenarios

### Funding Status

- Growth Portfolio and Hedging Portfolio separation
- Total asset calculation
- Funding ratio calculation
- Surplus / deficit monitoring
- Asset-vs-liability visualization

### Client Report

- Downloadable PDF client report
- Downloadable CSV summary
- Executive summary generation
- Growth/Hedging portfolio allocation reporting
- Funding status charts
- Methodology section

---

## Architecture

```text
Streamlit Frontend
        ↓
FastAPI Backend
        ↓
Quant Models
```

Current implementation:

- All Streamlit pages communicate with the FastAPI backend.
- The FastAPI layer orchestrates the underlying quant model classes.

---

## Project Structure

```text
ldi-pension-analyzer/
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── api/
│   │   ├── liability.py
│   │   ├── hedging.py
│   │   └── scenarios.py
│   └── models/
│       ├── liability.py
│       ├── hedging.py
│       ├── scenarios.py
│       └── portfolio.py
├── frontend/
│   ├── Dockerfile
│   ├── app.py
│   └── pages/
│       ├── 1_Liability_Analysis.py   # Liability PV, Duration, DV01, Key-Rate DV01
│       ├── 2_Hedge_Optimizer.py      # IRS valuation, hedge notional, DV01 risk
│       ├── 3_Scenario_Analysis.py    # Vasicek Monte Carlo, stress scenarios
│       ├── 4_Funding_Status.py       # Growth/Hedging split, funding ratio, surplus
│       └── 5_Client_Report.py        # PDF/CSV quarterly report generation
├── tests/
│   ├── test_liability.py
│   └── test_hedging.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Installation

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Backend

Start the FastAPI backend:

```bash
uvicorn backend.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

Root health endpoint:

```http
GET /
```

Response:

```json
{
  "project": "LDI Pension Hedging Analyzer",
  "status": "running"
}
```

---

## Running the Frontend

In a separate terminal, start Streamlit:

```bash
streamlit run frontend/app.py
```

The dashboard will open at:

```text
http://localhost:8501
```

If port `8501` is already in use:

```bash
streamlit run frontend/app.py --server.port 8502
```

The frontend reads the backend API location from:

```text
API_BASE_URL
```

For local development, it defaults to:

```text
http://127.0.0.1:8000/api
```

---

## Docker Deployment

Run:

```bash
docker compose up --build
```

Frontend:

```text
http://localhost:8501
```

Backend:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

The Docker Compose configuration sets:

```text
API_BASE_URL=http://backend:8000/api
```

To stop the services:

```bash
docker compose down
```

---

## API Endpoints

### Liability Present Value

```http
POST /api/liability/pv
```

Request:

```json
{
  "cash_flows": {
    "1": 1000000,
    "2": 1050000,
    "3": 1100000
  },
  "discount_curve": {
    "1": 0.04,
    "2": 0.041,
    "3": 0.042
  }
}
```

Response:

```json
{
  "present_value": 2912384.12
}
```

### Liability Duration

```http
POST /api/liability/duration
```

Response:

```json
{
  "macaulay_duration": 1.98,
  "modified_duration": 1.90
}
```

### Liability DV01

```http
POST /api/liability/dv01
```

Response:

```json
{
  "dv01": 553.42
}
```

### Liability Key-Rate DV01

```http
POST /api/liability/key-rate-dv01
```

Request:

```json
{
  "cash_flows": {
    "5": 1000000,
    "10": 1250000,
    "20": 1500000,
    "30": 1750000
  },
  "discount_curve": {
    "5": 0.04,
    "10": 0.042,
    "20": 0.045,
    "30": 0.047
  },
  "key_rates": [5, 10, 20, 30]
}
```

Response:

```json
{
  "key_rate_dv01": {
    "5": 421.18,
    "10": 932.45,
    "20": 1884.71,
    "30": 2910.33
  }
}
```

---

## Quant Models

### LiabilityModel

Located in:

```text
backend/models/liability.py
```

Inputs:

- `cash_flows: dict[int, float]`
- `discount_curve: dict[int, float]`

Methods:

- `present_value()`
- `macaulay_duration()`
- `modified_duration()`
- `dv01()`
- `pv_under_parallel_shift(shift_bps)`

Valuation uses annual compounding:

```text
PV_t = CF_t / (1 + r_t)^t
```

The liability DV01 is reported as a positive currency sensitivity:

```text
DV01 = (PV(-1 bp) - PV(+1 bp)) / 2
```

### InterestRateSwap

Located in:

```text
backend/models/hedging.py
```

Inputs:

- `notional`
- `fixed_rate`
- `maturity_years`
- `discount_curve`

Methods:

- `fixed_leg_pv()`
- `floating_leg_pv()`
- `swap_value()`
- `dv01()`
- `hedge_notional(liability_dv01)`

Fixed leg valuation uses annual fixed coupon payments:

```text
PV_fixed = sum(N * fixed_rate * DF_t)
```

Floating leg valuation is approximated using:

```text
PV_float ~= N * (1 - DF(T))
```

This simplification is intentional for the educational implementation. It keeps
the swap module focused on hedge mechanics rather than full forward-curve
construction, reset schedules, accrual conventions, and curve bootstrapping.

Swap value convention:

```text
swap_value = floating_leg_pv - fixed_leg_pv
```

Swap DV01 is signed:

```text
DV01 = (value(-1 bp) - value(+1 bp)) / 2
```

The sign is important. For example, a liability may have positive DV01, while a
receive-floating/pay-fixed swap can have negative DV01. The hedge notional keeps
this direction:

```text
hedge_notional = liability_dv01 * swap_notional / swap_dv01
```

### VasicekModel

Located in:

```text
backend/models/scenarios.py
```

Inputs:

- `kappa`
- `theta`
- `sigma`
- `r0`

Methods:

- `simulate_path(years, dt)`
- `simulate_paths(years, dt, n_paths)`
- `parallel_shift_scenarios()`
- `summarize_terminal_rates()`

Vasicek short-rate dynamics:

```text
dr = kappa * (theta - r) * dt + sigma * dW
```

Euler-Maruyama discretization:

```text
r[t+1] = r[t] + kappa * (theta - r[t]) * dt + sigma * sqrt(dt) * Z
```

---

## Frontend Pages

### Landing Page

```text
frontend/app.py
```

Features:

- Project title
- Sidebar page selection prompt

### Liability Analysis

```text
frontend/pages/1_Liability_Analysis.py
```

Features:

- Editable cash-flow table
- Editable discount-curve table
- Calls FastAPI liability endpoints
- Displays Present Value, Macaulay Duration, Modified Duration, and DV01
- Displays Key-Rate DV01 by maturity bucket
- Suggests a hedge maturity bucket based on largest absolute Key-Rate DV01
- Plots liability cash flows by year

### Hedge Optimizer

```text
frontend/pages/2_Hedge_Optimizer.py
```

Features:

- Inputs for Liability DV01, Swap Notional, Fixed Rate, and Maturity Years
- Computes signed Swap DV01
- Computes required hedge notional
- Plots before/after hedge DV01 risk

### Scenario Analysis

```text
frontend/pages/3_Scenario_Analysis.py
```

Features:

- Vasicek parameter inputs
- Monte Carlo short-rate simulation
- Sample path chart
- Terminal rate histogram
- Mean, standard deviation, 5%, median, and 95% terminal-rate metrics

### Funding Status

```text
frontend/pages/4_Funding_Status.py
```

Features:

- Growth Portfolio and Hedging Portfolio inputs
- Total asset calculation from equities, credit, long bonds, and IRS exposure
- Editable cash-flow table
- Editable discount-curve table
- Calls FastAPI liability PV and DV01 endpoints
- Computes Liability PV, Funding Ratio, Surplus / Deficit, and Liability DV01
- Shows Growth/Hedging allocation attribution
- Color-coded Funding Ratio metric
- Asset-versus-liability, surplus/deficit, and portfolio allocation charts

### Client Report

```text
frontend/pages/5_Client_Report.py
```

Features:

- Client name and report date inputs
- Growth Portfolio and Hedging Portfolio inputs
- Calls FastAPI liability PV, DV01, and duration endpoints
- Generates downloadable CSV summary
- Generates downloadable PDF client report
- Includes portfolio allocation, branded executive summary, metric table, interpretation, charts, and methodology

---

## Screenshots

### Liability Analysis

![Liability](docs/liability.png)

### Key-Rate DV01 Analysis

![Key-Rate DV01](docs/key_rate_dv01.png)

### Hedge Optimizer

![Hedge](docs/hedge.png)

### Scenario Analysis

![Scenario](docs/scenario.png)

### Funding Status

![Funding](docs/funding.png)

### Funding Ratio Attribution

![Funding Attribution](docs/funding_attribution.png)

### Client Report

![Client Report](docs/client_report.png)

---

## Testing

Run the test suite:

```bash
python3 -m pytest
```

GitHub Actions runs the same pytest suite on pushes and pull requests to `main`.

Current test coverage includes:

- Liability present value
- Liability duration positivity
- Liability DV01 positivity
- Liability key-rate DV01 behavior
- Liability parallel shift behavior
- Liability input validation
- Swap fixed leg PV
- Swap floating leg PV
- Swap value type
- Signed swap DV01 non-zero check
- Hedge notional direction
- Swap input validation

---

## Modeling Assumptions

- Annual compounding is used throughout the core liability and swap models.
- Pension cash-flow years are interpreted as annual periods from valuation date.
- Discount curves are represented as year-to-rate dictionaries.
- Liability cash flows must be non-negative.
- Interest-rate swap payments are annual.
- The swap floating leg uses a simplified par floating-leg approximation.
- Vasicek paths are simulated with Euler-Maruyama discretization.
- Scenario Analysis uses a quarterly time step in the Streamlit page.

---

## Roadmap

Potential next improvements:

- Add richer hedge and scenario API outputs for production-style workflows.
- Add tests for the Vasicek model.
- Add end-to-end tests for FastAPI routes.
- Support user-entered swap discount curves in the Hedge Optimizer.
- Add key-rate duration and curve twist scenarios.
- Add asset portfolio modeling and hedge effectiveness reporting.
- Add CSV upload/export for liability cash flows.
- Add cloud deployment configuration for a hosted demo.

---

## Disclaimer

This project is for educational and demonstration purposes only. It is not
investment advice, actuarial advice, or a production risk system.
