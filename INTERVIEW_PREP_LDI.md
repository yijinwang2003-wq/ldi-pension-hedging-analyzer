# Interview Prep: LDI Pension Hedging Analyzer

## 1. Project Overview

### What Problem This Project Solves

This project is an interactive analytics platform for pension liability valuation, interest-rate hedging, funding status monitoring, scenario analysis, and client reporting. It lets a user input projected pension cash flows, discount curves, and asset portfolio values, then calculates core LDI metrics such as liability present value, duration, DV01, key-rate DV01, hedge notional, funding ratio, and surplus/deficit.

The core problem is the same one faced in LDI analytics: pension plans have long-dated liabilities whose value changes with interest rates. The platform helps quantify those liabilities, separate return-seeking assets from hedging assets, estimate interest-rate sensitivity, and communicate the plan's funded status through dashboards and downloadable reports.

### How It Maps To An LDI / Pension Analytics Workflow

The workflow in the code maps closely to a simplified institutional LDI process:

1. **Liability projection**: The user enters annual benefit cash flows in `frontend/pages/1_Liability_Analysis.py` and `frontend/pages/4_Funding_Status.py`.
2. **Curve-based valuation**: The backend discounts each cash flow using the year-specific spot rate in `backend/models/liability.py`.
3. **Risk measurement**: The system calculates duration, parallel DV01, and key-rate DV01 in `LiabilityModel`.
4. **Hedge design**: The hedge optimizer models a plain-vanilla interest-rate swap in `backend/models/hedging.py` and sizes a hedge notional against liability DV01.
5. **Asset-liability monitoring**: `frontend/pages/4_Funding_Status.py` combines growth assets, hedging assets, liability PV, funding ratio, and surplus/deficit.
6. **Scenario analysis**: `backend/models/scenarios.py` simulates short-rate paths using a Vasicek model, exposed through `/api/scenarios/vasicek`.
7. **Client reporting**: `frontend/pages/5_Client_Report.py` creates Streamlit dashboards plus downloadable CSV and PDF client reports.

### Strong 60-Second Interview Explanation

I built a full-stack LDI analytics platform for a pension plan. The user enters projected benefit cash flows, a discount curve, and asset portfolio values split between growth assets and hedging assets. The FastAPI backend values the liabilities by discounting each cash flow, then calculates Macaulay duration, modified duration, parallel DV01, and key-rate DV01. On the hedging side, I implemented a simplified interest-rate swap model that values fixed and floating legs, calculates signed swap DV01, and estimates the swap notional needed to offset liability DV01. The Streamlit frontend turns those analytics into dashboards for liability analysis, hedge optimization, funding status, scenario analysis, and client reporting. It is intentionally simplified, but it demonstrates the end-to-end LDI workflow: value the liability, measure rate risk, compare assets to liabilities, design a hedge, stress interest rates, and communicate the results in a client-ready format.

## 2. System Architecture

### Frontend Structure

The frontend is a Streamlit multi-page app:

- `frontend/app.py`: Landing page and Streamlit app entry point.
- `frontend/pages/1_Liability_Analysis.py`: Liability cash-flow inputs, discount curve inputs, PV/duration/DV01/key-rate DV01 display, and cash-flow chart.
- `frontend/pages/2_Hedge_Optimizer.py`: Liability DV01 and swap inputs, hedge notional API call, and before/after DV01 risk chart.
- `frontend/pages/3_Scenario_Analysis.py`: Vasicek parameter inputs, Monte Carlo API call, sample path chart, terminal rate histogram, and summary metrics.
- `frontend/pages/4_Funding_Status.py`: Growth and hedging portfolio inputs, liability valuation API calls, funding ratio, surplus/deficit, allocation charts, and asset-liability comparison.
- `frontend/pages/5_Client_Report.py`: Client/report inputs, liability API calls, portfolio summary, Plotly charts, CSV export, and PDF export using ReportLab.

The frontend uses:

- `requests` for API calls.
- `pandas` for table cleanup and chart data preparation.
- `plotly.express` for charts.
- `streamlit` for UI controls, metrics, charts, and downloads.
- `reportlab` for PDF report generation.

### Backend Structure

The backend is a FastAPI app:

- `backend/main.py`: Creates the FastAPI app and includes API routers under `/api`.
- `backend/api/liability.py`: Defines liability request/response schemas and routes.
- `backend/api/hedging.py`: Defines swap and hedge notional request/response schemas and routes.
- `backend/api/scenarios.py`: Defines Vasicek simulation schemas and route.
- `backend/models/liability.py`: Pure Python liability valuation and risk model.
- `backend/models/hedging.py`: Pure Python interest-rate swap valuation and hedge sizing model.
- `backend/models/scenarios.py`: Vasicek short-rate simulation model.
- `backend/models/portfolio.py`: Growth/hedging portfolio aggregation model.

The backend models are intentionally framework-independent, which makes them reusable from API routes, frontend pages, and tests.

### API Endpoints

Defined in `backend/main.py`, `backend/api/liability.py`, `backend/api/hedging.py`, and `backend/api/scenarios.py`:

| Route | Method | File | Purpose |
|---|---:|---|---|
| `/` | GET | `backend/main.py` | Health/project metadata |
| `/api/liability/pv` | POST | `backend/api/liability.py` | Liability present value |
| `/api/liability/duration` | POST | `backend/api/liability.py` | Macaulay and modified duration |
| `/api/liability/dv01` | POST | `backend/api/liability.py` | Parallel liability DV01 |
| `/api/liability/key-rate-dv01` | POST | `backend/api/liability.py` | Key-rate DV01 by selected maturities |
| `/api/hedging/swap-value` | POST | `backend/api/hedging.py` | Fixed leg PV, floating leg PV, swap value, swap DV01 |
| `/api/hedging/hedge-notional` | POST | `backend/api/hedging.py` | Swap notional needed to hedge liability DV01 |
| `/api/scenarios/vasicek` | POST | `backend/api/scenarios.py` | Monte Carlo short-rate paths and terminal-rate summary |

### Data Flow

Example: Liability Analysis page.

1. User edits the cash-flow and discount-curve tables in `render_liability_inputs()`.
2. `build_liability_payload()` cleans the tables, converts `year`, `cash_flow`, and `discount_rate` to numeric values, drops invalid rows, and builds JSON dictionaries.
3. `calculate_liability_analytics()` calls:
   - `POST /api/liability/pv`
   - `POST /api/liability/duration`
   - `POST /api/liability/dv01`
   - `POST /api/liability/key-rate-dv01`
4. `backend/api/liability.py` validates the request with Pydantic, builds a `LiabilityModel`, and calls model methods.
5. `backend/models/liability.py` performs the calculations.
6. Streamlit renders the results through `st.metric`, Plotly bar charts, and key-rate DV01 guidance.

Example: Funding Status page.

1. User enters equities, credit, long bonds, IRS exposure, cash flows, and discount curve in `frontend/pages/4_Funding_Status.py`.
2. `PortfolioModel` calculates growth portfolio, hedging portfolio, and total assets.
3. The page calls liability PV and DV01 endpoints.
4. It calculates:
   - `funding_ratio = asset_market_value / liability_pv`
   - `surplus = asset_market_value - liability_pv`
5. It renders total assets, liability PV, funding ratio, surplus/deficit, liability DV01, allocation charts, and asset-liability charts.

### Important Files

| File | Role |
|---|---|
| `README.md` | Project description, features, architecture, running instructions |
| `backend/main.py` | FastAPI app creation and router registration |
| `backend/api/liability.py` | Liability API schemas and routes |
| `backend/api/hedging.py` | Swap valuation and hedge notional API schemas/routes |
| `backend/api/scenarios.py` | Vasicek scenario API schemas/routes |
| `backend/models/liability.py` | Liability PV, duration, parallel DV01, key-rate DV01 |
| `backend/models/hedging.py` | Swap fixed leg PV, floating leg PV, swap value, swap DV01, hedge notional |
| `backend/models/scenarios.py` | Vasicek Monte Carlo paths and terminal-rate summaries |
| `backend/models/portfolio.py` | Growth/hedging portfolio totals and allocation weights |
| `frontend/pages/1_Liability_Analysis.py` | Liability dashboard and API orchestration |
| `frontend/pages/2_Hedge_Optimizer.py` | Swap hedge optimizer dashboard |
| `frontend/pages/3_Scenario_Analysis.py` | Scenario analysis dashboard |
| `frontend/pages/4_Funding_Status.py` | Asset-liability and funding status dashboard |
| `frontend/pages/5_Client_Report.py` | Client report dashboard, CSV export, PDF export |
| `tests/test_liability.py` | Unit tests for liability PV, duration, DV01, key-rate DV01, validation |
| `tests/test_hedging.py` | Unit tests for swap valuation, DV01, hedge notional, validation |
| `tests/test_portfolio.py` | Unit tests for portfolio aggregation and allocation |

## 3. Quant / Finance Logic

### Liability Present Value Calculation

**Implemented in:** `backend/models/liability.py`, `LiabilityModel.present_value()`, `_discounted_cash_flow()`.

**Formula:**

```text
PV = sum_t CF_t / (1 + r_t)^t
```

where `CF_t` is the projected pension payment in year `t`, and `r_t` is the discount rate for that year.

**Plain-English interview explanation:**

I treat the pension liability as a schedule of future benefit payments. For each year, I discount the expected payment back to today using the spot rate for that maturity, then sum all discounted payments. That gives the market-consistent present value of the liability under the input curve.

**Limitations:**

- Annual cash flows only.
- Annual compounding only.
- No mortality, salary growth, inflation indexation, retirement behavior, or actuarial decrements.
- Discount rates are user-entered, not bootstrapped from real market instruments.

### Discount Curve Usage

**Implemented in:** `backend/models/liability.py`, `LiabilityModel.__init__()`, `_validate_inputs()`, `_discounted_cash_flow()`, `_present_value_with_curve()`.

**Algorithm:**

- The discount curve is a dictionary mapping integer year to annual spot rate.
- Every cash-flow year must have a corresponding discount rate.
- Each cash flow uses the rate for its exact year.
- Parallel shifts add the same number of basis points to every curve node.
- Key-rate DV01 shifts only one selected curve maturity at a time.

**Plain-English interview explanation:**

The implementation uses a simple spot curve representation: year one cash flow uses the one-year rate, year five uses the five-year rate, and so on. That makes the valuation transparent and allows both parallel rate shocks and key-rate shocks.

**Limitations:**

- No interpolation for missing maturities.
- No curve bootstrapping from Treasuries, swaps, or corporate bond yields.
- No separate Treasury, swap, AA corporate, or accounting discount curves.

### Funding Ratio Calculation

**Implemented in:** `frontend/pages/4_Funding_Status.py`, `calculate_funding_status()`; also `frontend/pages/5_Client_Report.py`, `generate_client_report()`.

**Formula:**

```text
Funding Ratio = Total Assets / Liability PV
```

`Total Assets` comes from `PortfolioModel.total_assets()`.

**Plain-English interview explanation:**

After valuing the liability, I compare total plan assets against that liability value. A funding ratio above 1.0 means assets exceed discounted liabilities; below 1.0 means the plan is underfunded.

**Limitations:**

- Asset values are manually entered rather than loaded from custodial feeds.
- No return attribution over time.
- No accounting-specific funded status rules.

### Surplus / Deficit Calculation

**Implemented in:** `frontend/pages/4_Funding_Status.py`, `calculate_funding_status()`; also `frontend/pages/5_Client_Report.py`, `generate_client_report()`.

**Formula:**

```text
Surplus / Deficit = Total Assets - Liability PV
```

**Plain-English interview explanation:**

The surplus or deficit is the dollar gap between asset market value and the present value of liabilities. This is the economic funded status in currency terms, while the funding ratio is the same idea expressed as a ratio.

**Limitations:**

- No attribution of surplus changes to asset returns, discount-rate moves, contributions, or benefit payments.
- No projected surplus under future scenarios.

### Liability DV01 Calculation

**Implemented in:** `backend/models/liability.py`, `LiabilityModel.dv01()`, `pv_under_parallel_shift()`.

**Formula:**

```text
DV01 = (PV_down_1bp - PV_up_1bp) / 2
```

The model shifts all discount rates down 1 bp and up 1 bp, calculates both PVs, and uses a symmetric finite difference. The result is reported as a positive currency amount for liabilities because liabilities rise when rates fall.

**Plain-English interview explanation:**

DV01 tells me how many dollars the liability value changes for a one-basis-point move in rates. I calculate it by shocking the entire curve down 1 bp and up 1 bp, revaluing the cash flows under both curves, and taking half the difference. Because liabilities increase when rates fall, the liability DV01 is positive.

**Limitations:**

- Parallel DV01 only captures a uniform curve shift.
- Does not model convexity beyond the finite-difference revaluation.
- No curve interpolation or full key-rate hedge matrix.

### Key-Rate DV01

**Implemented in:** `backend/models/liability.py`, `LiabilityModel.key_rate_dv01()`; displayed in `frontend/pages/1_Liability_Analysis.py`, `render_key_rate_dv01_analysis()`.

**Formula:**

```text
KRDV01_k = (PV_with_key_k_down_1bp - PV_with_key_k_up_1bp) / 2
```

Only the selected maturity node is shocked. The frontend uses `KEY_RATES = [5, 10, 20, 30]`.

**Plain-English interview explanation:**

Key-rate DV01 decomposes the liability's interest-rate exposure by maturity bucket. Instead of shocking the whole curve, I shock only the 5-year, 10-year, 20-year, or 30-year point and revalue the liability. That helps identify which tenors would be most relevant for swaps or long bonds.

**Limitations:**

- If the exact key-rate year is not in the curve, the model returns zero.
- No interpolation or smoothing across adjacent maturities.
- Key-rate shocks are independent simple node shocks, not a production curve-risk framework.

### Growth vs Hedging Portfolio Attribution

**Implemented in:** `backend/models/portfolio.py`, `PortfolioModel`; used in `frontend/pages/4_Funding_Status.py` and `frontend/pages/5_Client_Report.py`.

**Formulas:**

```text
Growth Portfolio = Equities + Credit
Hedging Portfolio = Long Bonds + IRS Exposure
Total Assets = Growth Portfolio + Hedging Portfolio
Growth Allocation = Growth Portfolio / Total Assets
Hedging Allocation = Hedging Portfolio / Total Assets
```

**Plain-English interview explanation:**

I separate the asset portfolio into a growth portfolio, which is meant to generate excess return, and a hedging portfolio, which is meant to reduce liability interest-rate risk. The dashboard shows both dollar amounts and allocation percentages so a user can understand how much of the plan is return-seeking versus liability-hedging.

**Limitations:**

- This is allocation attribution, not performance attribution.
- Credit is grouped with growth assets, though in real LDI some credit can have both return-seeking and liability-hedging roles.
- IRS exposure is entered as a simple exposure/market-value proxy rather than modeled from trade-level derivatives data.

### Interest Rate Swap / IRS Exposure Logic

**Implemented in:** `backend/models/hedging.py`, `InterestRateSwap`; API routes in `backend/api/hedging.py`; frontend in `frontend/pages/2_Hedge_Optimizer.py`.

**Fixed leg PV:**

```text
Fixed Leg PV = sum_t Notional * Fixed Rate * DF_t
DF_t = 1 / (1 + r_t)^t
```

**Floating leg PV approximation:**

```text
Floating Leg PV = Notional * (1 - DF_T)
```

**Swap value convention:**

```text
Swap Value = Floating Leg PV - Fixed Leg PV
```

Under this convention, a positive value benefits a receive-floating/pay-fixed position.

**Swap DV01:**

```text
Swap DV01 = (Value_down_1bp - Value_up_1bp) / 2
```

**Hedge notional:**

```text
Hedge Notional = Liability DV01 * Input Swap Notional / Swap DV01
```

The sign indicates hedge direction under the model's value convention.

**Plain-English interview explanation:**

I model a plain-vanilla annual-pay interest-rate swap. The fixed leg is the present value of fixed coupons. The floating leg is approximated as par floating exposure using `Notional * (1 - DF_T)`. I then calculate signed swap DV01 by shocking the curve up and down one basis point. To size the hedge, I scale the swap notional so that the swap DV01 offsets the liability DV01.

**Limitations:**

- Annual-pay fixed leg only.
- Floating leg is approximate.
- No forward curve, reset schedule, day count, collateral discounting, OIS discounting, or swap curve bootstrapping.
- No trade-level receive-fixed/pay-fixed toggle in the UI; direction is inferred from signed DV01.
- No futures, swaptions, Treasury STRIPS, or long corporate bond hedge optimizer.

### Scenario Analysis Logic

**Implemented in:** `backend/models/scenarios.py`, `VasicekModel`; API route in `backend/api/scenarios.py`; frontend in `frontend/pages/3_Scenario_Analysis.py`.

**Continuous-time model:**

```text
dr = kappa * (theta - r) * dt + sigma * dW
```

**Euler-Maruyama discretization:**

```text
r[t+1] = r[t] + kappa * (theta - r[t]) * dt + sigma * sqrt(dt) * Z
```

The frontend uses `TIME_STEP = 0.25`, displays up to `MAX_DISPLAY_PATHS = 25`, and renders a terminal-rate histogram plus summary metrics.

**Plain-English interview explanation:**

I implemented a Vasicek short-rate simulation to show how interest rates could evolve under mean reversion and volatility. The model generates many paths, summarizes terminal rates, and displays the distribution. In an LDI context, this can support rate stress testing and future-funded-status analysis.

**Limitations:**

- Scenario output is currently rate-path focused; it does not automatically revalue assets and liabilities along every path.
- Vasicek allows negative rates and has constant volatility.
- No calibration to market curves, caps/floors, or historical data.
- `parallel_shift_scenarios()` exists in `VasicekModel`, but the current API/frontend mainly use Monte Carlo paths rather than a full stress testing dashboard.

## 4. Full-Stack Implementation Details

### How The Frontend Calls The Backend

Each Streamlit page defines:

```python
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")
```

The pages call backend endpoints with `requests.post(..., json=payload, timeout=10)` and then call `response.raise_for_status()`. Examples:

- `frontend/pages/1_Liability_Analysis.py`, `post_liability_endpoint()`
- `frontend/pages/2_Hedge_Optimizer.py`, `calculate_hedge()`
- `frontend/pages/3_Scenario_Analysis.py`, `run_scenario_analysis()`
- `frontend/pages/4_Funding_Status.py`, `post_liability_endpoint()`
- `frontend/pages/5_Client_Report.py`, `post_liability_endpoint()`

### How State / Input Data Is Managed

The app uses Streamlit's widget state:

- `st.number_input()` for portfolio values, swap terms, and scenario parameters.
- `st.data_editor()` for editable liability cash-flow and discount-curve tables.
- `st.text_input()` and `st.date_input()` for client report metadata.
- Button clicks trigger calculations, so analytics run on demand rather than continuously.

Data cleanup is handled by helper functions such as:

- `prepare_cash_flow_dataframe()`
- `prepare_discount_curve_dataframe()`
- `build_liability_payload()`

These functions convert user-edited table cells to numeric values, drop invalid rows, cast years to integers, sort by year, and package the payload for the API.

### How Charts And Tables Are Generated

Charts use Plotly Express in the Streamlit pages:

- Liability cash-flow chart: `render_cash_flow_chart()` in `1_Liability_Analysis.py`.
- Key-rate DV01 bar chart: `render_key_rate_dv01_analysis()`.
- Hedge risk before/after bar chart: `render_risk_chart()` in `2_Hedge_Optimizer.py`.
- Scenario sample paths and terminal histogram: `render_sample_paths_chart()` and `render_terminal_rate_histogram()` in `3_Scenario_Analysis.py`.
- Funding allocation pie chart, portfolio bar chart, asset-liability chart, and surplus chart: `4_Funding_Status.py`.
- Client report dashboard charts: `render_visualization()` in `5_Client_Report.py`.

The PDF report uses ReportLab charts:

- `create_funding_ratio_chart()`
- `create_asset_liability_chart()`
- `create_portfolio_allocation_chart()`

### How Errors Or Edge Cases Are Handled

Backend validation:

- `LiabilityModel._validate_inputs()` rejects empty cash flows, non-positive years, negative cash flows, missing curve points, non-numeric rates, and rates less than or equal to -100%.
- `InterestRateSwap._validate_inputs()` rejects non-positive notional, invalid fixed rates, non-positive maturity, missing curve years, and invalid rates.
- `VasicekModel._validate_inputs()` and `_validate_simulation_inputs()` validate model and simulation parameters.
- API layers catch `TypeError` and `ValueError` and convert them to HTTP 400 responses.

Frontend handling:

- API failures are caught as `requests.RequestException` and shown with `st.error()`.
- Empty cleaned cash-flow or curve tables trigger `st.error()`.
- Funding ratio calculations explicitly reject `liability_pv == 0.0`.
- Portfolio allocation handles zero total assets in `PortfolioModel._allocation()` and in the funding attribution view.

### Reporting / Export Feature

Implemented in `frontend/pages/5_Client_Report.py`.

The report page:

1. Collects client name, report date, portfolio inputs, cash flows, and discount curve.
2. Calls liability endpoints for PV, DV01, and duration.
3. Builds `report_data` with portfolio values, allocations, liability metrics, funding ratio, and surplus/deficit.
4. Displays dashboard metrics and charts.
5. Creates a CSV with `create_csv_report()`.
6. Creates a PDF with `create_pdf_report()`.
7. Exposes both via `st.download_button()`.

The PDF includes:

- Client metadata.
- Executive summary from `generate_executive_summary()`.
- Metric table.
- Portfolio allocation table.
- Funding interpretation from `funding_interpretation()`.
- Funding status, asset-liability, and allocation charts.
- Methodology section.

## 5. Interview Q&A

### Why did you build this project?

I built it to demonstrate the core workflow of institutional LDI analytics in a full-stack application: liability valuation, interest-rate risk measurement, hedge sizing, asset-liability funded status, scenario analysis, and client reporting. I wanted something that connects the finance logic to a usable dashboard rather than keeping the calculations in a notebook.

### What was the hardest technical part?

The hardest part was designing the calculation flow so the quant models stayed clean and testable while the frontend remained interactive. I separated pure finance logic into backend model classes, exposed it through FastAPI routes, and kept Streamlit focused on inputs, API orchestration, charts, and reporting.

### How did you model liabilities?

I modeled liabilities as annual projected pension cash flows. Each cash flow is discounted using the rate for that maturity, so the liability PV is the sum of `CF_t / (1 + r_t)^t`. I also calculate Macaulay duration, modified duration, parallel DV01, and key-rate DV01 from the same cash-flow and curve inputs.

### How did you calculate DV01?

I used a symmetric finite-difference approach. I revalue the liability after shifting the entire discount curve down one basis point and up one basis point, then calculate `(PV_down - PV_up) / 2`. That gives the dollar sensitivity of the liability to a one-basis-point rate move.

### How would you hedge the liabilities using swaps?

First I measure the liability DV01. Then I calculate the signed DV01 of a representative interest-rate swap by shocking the curve and revaluing the swap. The hedge notional scales the swap so its DV01 offsets the liability DV01. In production I would extend this to multiple swap tenors and solve a key-rate DV01 matching problem.

### How does this relate to ALM?

ALM is about managing assets relative to liabilities, not just optimizing asset returns in isolation. This project values the liabilities, measures their rate sensitivity, compares assets to liability PV through funding ratio and surplus/deficit, and separates the asset portfolio into growth and hedging components. That is the basic ALM lens.

### How does this support client reporting?

The client report page turns the analytics into a repeatable reporting workflow. It produces funding ratio, surplus/deficit, growth and hedging allocation, liability DV01, duration, charts, an executive summary, and downloadable CSV/PDF reports. That maps to quarterly client reporting where stakeholders need both numbers and interpretation.

### What would you improve if this were production-level?

I would add real market curve bootstrapping, curve interpolation, actuarial liability modeling, trade-level swaps with proper day count and forward curves, multi-tenor hedge optimization, historical performance attribution, database persistence, authentication, automated data ingestion, and production monitoring. The current version is an educational but end-to-end prototype.

### Why did you use FastAPI and Streamlit?

FastAPI gives a clean API boundary around the analytics and automatically documents request/response schemas. Streamlit is efficient for building internal analytics dashboards. Together they let me separate quant calculation services from user-facing reporting.

### How would you extend key-rate hedging?

I would compute liability key-rate DV01 across standard tenors, compute instrument key-rate DV01 for swaps or bonds at those tenors, then solve for hedge weights that minimize residual key-rate exposure subject to constraints such as notional limits, liquidity, duration target, and transaction cost.

## 6. JD Mapping

| Interview Requirement | Project Feature | Code File / Function | Finance Concept Demonstrated | Interview Talking Point |
|---|---|---|---|---|
| Analyze data for LDI investment solutions | Liability and funding dashboards | `frontend/pages/1_Liability_Analysis.py`, `frontend/pages/4_Funding_Status.py` | Liability valuation, funded status, rate sensitivity | I built dashboards that turn pension cash flows and asset values into LDI metrics. |
| Growth and hedging portfolios | Portfolio split and allocation metrics | `backend/models/portfolio.py`, `PortfolioModel.growth_portfolio()`, `PortfolioModel.hedging_portfolio()` | Return-seeking vs liability-hedging asset pools | I separated assets into growth and hedging portfolios and showed their funding impact. |
| Derivatives hedging solutions | IRS valuation and hedge notional | `backend/models/hedging.py`, `InterestRateSwap`, `/api/hedging/hedge-notional` | Swap PV, signed DV01, hedge sizing | I modeled swap DV01 and scaled notional to offset liability DV01. |
| Asset-liability modeling | Funding ratio and surplus/deficit | `frontend/pages/4_Funding_Status.py`, `calculate_funding_status()` | ALM, funded status, surplus risk | The system compares total assets to liability PV and tracks surplus/deficit. |
| Real-world hedging strategies | Key-rate DV01 and hedge maturity guidance | `LiabilityModel.key_rate_dv01()`, `render_key_rate_dv01_analysis()` | Curve bucket exposure and tenor selection | The dashboard identifies maturity buckets where liability rate exposure is concentrated. |
| Scenario analysis | Vasicek Monte Carlo engine | `backend/models/scenarios.py`, `VasicekModel.simulate_paths()` | Stochastic interest-rate modeling | I simulated interest-rate paths to support stress testing and future risk analysis. |
| Quarterly client reporting | Downloadable CSV/PDF report | `frontend/pages/5_Client_Report.py`, `create_csv_report()`, `create_pdf_report()` | Client-ready funded status reporting | I automated the conversion of analytics into a client report with charts and methodology. |
| Performance dashboards | Streamlit metrics and Plotly charts | All `frontend/pages/*.py` files | Dashboarding, data visualization | The frontend presents metrics, allocation charts, scenario distributions, and risk charts. |
| Full-stack software solutions | FastAPI + Streamlit architecture | `backend/main.py`, `backend/api/*.py`, `frontend/pages/*.py` | API design and analytics delivery | The project separates calculation logic, API services, and dashboard/reporting layers. |
| Testing and reliability | Unit tests for models | `tests/test_liability.py`, `tests/test_hedging.py`, `tests/test_portfolio.py` | Model correctness and validation | I added tests around PV, DV01, swap logic, portfolio totals, and input validation. |

## 7. Weaknesses / Limitations

### Honest Simplifications

- **No real market curve bootstrapping**: Discount curves are manually entered by year rather than bootstrapped from Treasury, swap, or AA corporate bond instruments.
- **Simplified swap model**: The IRS model uses annual payments and a simple floating leg approximation, not a full forward-curve, reset-date, collateralized swap valuation model.
- **Simplified pension cash flows**: Cash flows are entered directly and do not include actuarial assumptions such as mortality, salary growth, inflation, retirements, or lump-sum election behavior.
- **No production-grade risk engine**: The project calculates PV, duration, DV01, and basic key-rate DV01, but it does not include full curve scenario grids, factor models, Greeks, stress libraries, or trade-level risk aggregation.
- **Limited historical data**: There is no historical return, funded-status, or rate time series database.
- **No persistence layer**: Inputs and reports are generated interactively but not stored in a database.
- **No authentication or permissions**: It is an analytics prototype, not a secure client portal.
- **Limited ALM projection**: Scenario analysis simulates rates, but the current app does not project full asset-liability funded status through time under each path.
- **Simplified performance attribution**: Growth and hedging portfolios are shown by allocation and market value, not time-series return attribution.

### How To Frame These Positively

You can frame the limitations as scope decisions:

- The goal was to build an end-to-end prototype that demonstrates the core analytics workflow, not to recreate a commercial risk system.
- I intentionally kept the quant models transparent so the formulas are explainable in an interview and testable in unit tests.
- The architecture is extensible: production curve bootstrapping, trade-level swaps, actuarial cash-flow engines, and database persistence could be added behind the existing FastAPI layer.
- The project demonstrates that I understand both the finance concepts and how to deliver them through software: clean models, APIs, dashboards, reports, and tests.

Suggested interview wording:

> This is intentionally a simplified LDI analytics prototype. I focused on the core concepts: liability PV, duration, DV01, key-rate exposure, hedge notional, funding ratio, and client reporting. In production, I would replace the manual curve with bootstrapped market curves, add actuarial cash-flow modeling, extend the swap engine to trade-level valuation, and build a database-backed reporting workflow. The value of this project is that it shows the full analytical pipeline end to end.

## 8. Final Interview Script

## 9. Deep Technical Walkthrough Reference

For a deeper technical interview, use `CODE_WALKTHROUGH.md` as the function-by-function companion to this prep guide. It covers:

- `LiabilityModel`: every public method and helper, formulas, call paths, API routes, frontend displays, design rationale, and complexity.
- `InterestRateSwap`: fixed leg PV, floating leg PV, swap value, signed DV01, hedge notional sizing, and full UI-to-backend call path.
- `VasicekModel`: Euler-Maruyama simulation, random shock generation, terminal-rate statistics, API serialization, and complexity.
- `PortfolioModel`: growth/hedging aggregation, allocation weights, funding-ratio integration, report usage, and edge-case handling.

The shortest technical framing to memorize:

> The code separates quant logic from delivery. The model classes in `backend/models/` are pure Python and testable. FastAPI routes in `backend/api/` validate requests, instantiate models, catch domain errors, and return typed responses. Streamlit pages in `frontend/pages/` collect inputs, call the APIs, and render dashboards or reports. Liability and swap DV01 both use symmetric finite differences, which makes the hedge sizing logic consistent: measure liability DV01, measure swap DV01, then scale swap notional to offset the liability sensitivity.

### 30-Second Version

I built a full-stack LDI analytics dashboard for pension plans. It values projected pension liabilities using a discount curve, calculates duration and DV01, separates assets into growth and hedging portfolios, computes funding ratio and surplus/deficit, and estimates swap notional needed to hedge liability DV01. The backend is FastAPI with pure Python quant models, and the frontend is Streamlit with dashboards and downloadable client reports.

### 1-Minute Version

This project is an end-to-end LDI pension analytics platform. The user enters projected benefit cash flows, discount rates, and asset values split between growth assets and hedging assets. The backend values liabilities by discounting each cash flow, then calculates Macaulay duration, modified duration, parallel DV01, and key-rate DV01. I also implemented a simplified interest-rate swap model that calculates fixed leg PV, floating leg PV, signed swap DV01, and hedge notional required to offset liability DV01. On the frontend, Streamlit pages show liability analysis, hedge optimization, scenario analysis, funding status, and client reports. The project is simplified, but it demonstrates the core LDI workflow: value liabilities, measure rate risk, design hedges, monitor funded status, and communicate results.

### 2-Minute Version

I built this project to connect LDI finance concepts with a working full-stack analytics application. The backend is FastAPI, and the calculation layer is organized into pure Python models. `LiabilityModel` takes projected annual pension cash flows and a discount curve, calculates present value, Macaulay duration, modified duration, parallel DV01, and key-rate DV01. The DV01 is calculated by shifting the curve down and up one basis point and taking a symmetric finite difference. `InterestRateSwap` models a simplified annual-pay swap, values the fixed and floating legs, calculates signed swap DV01, and estimates the notional needed to hedge a liability DV01. `PortfolioModel` separates assets into growth assets, like equities and credit, and hedging assets, like long bonds and IRS exposure.

The Streamlit frontend turns those models into practical workflows. The liability page shows PV, duration, DV01, key-rate DV01, and cash-flow charts. The hedge optimizer uses the swap model to show before-and-after DV01 risk. The funding status page combines assets and liability PV to calculate funding ratio and surplus or deficit. The scenario page uses a Vasicek short-rate model to simulate interest-rate paths and terminal-rate distributions. The client report page generates dashboard metrics plus downloadable CSV and PDF reports with executive summary, allocation tables, funding charts, and methodology.

The implementation is intentionally simplified. It does not bootstrap real market curves, model full actuarial cash flows, or value swaps with full production conventions. But that was a deliberate scope choice: I wanted a transparent, testable prototype that demonstrates the end-to-end LDI analytics process. If I were taking it to production, I would add market data ingestion, bootstrapped curves, curve interpolation, trade-level derivatives valuation, multi-tenor hedge optimization, historical performance attribution, database persistence, authentication, and automated quarterly reporting.
