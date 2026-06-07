# Code Walkthrough: LDI Pension Hedging Analyzer

This document is designed for a deep technical interview. It explains the major quant models and how they connect to FastAPI endpoints and Streamlit pages, so you can discuss the code without opening the repository.

## Mental Model Of The App

The project has three layers:

1. **Pure quant/domain models** in `backend/models/`
   - `LiabilityModel`: liability PV, duration, DV01, key-rate DV01.
   - `InterestRateSwap`: swap fixed leg PV, floating leg PV, value, DV01, hedge notional.
   - `VasicekModel`: stochastic short-rate simulation.
   - `PortfolioModel`: growth/hedging asset aggregation and allocation.

2. **FastAPI routes** in `backend/api/`
   - Convert JSON requests into model objects.
   - Catch domain validation errors.
   - Return typed Pydantic responses.

3. **Streamlit pages** in `frontend/pages/`
   - Collect user inputs.
   - Call backend endpoints with `requests.post`.
   - Render metrics, charts, tables, and exports.

The key design decision is separation of concerns: financial formulas live in pure Python classes without FastAPI or Streamlit dependencies. The API layer handles HTTP. The frontend handles user interaction and visualization.

## Call Graph Summary

### Liability Analytics

```text
Streamlit page
  frontend/pages/1_Liability_Analysis.py
  frontend/pages/4_Funding_Status.py
  frontend/pages/5_Client_Report.py
        |
        | requests.post(...)
        v
FastAPI route
  backend/api/liability.py
        |
        | _build_liability_model(...)
        v
Quant model
  backend/models/liability.py::LiabilityModel
```

Routes:

- `/api/liability/pv` calls `LiabilityModel.present_value()`.
- `/api/liability/duration` calls `LiabilityModel.macaulay_duration()` and `LiabilityModel.modified_duration()`.
- `/api/liability/dv01` calls `LiabilityModel.dv01()`.
- `/api/liability/key-rate-dv01` calls `LiabilityModel.key_rate_dv01()`.

Frontend displays:

- `1_Liability_Analysis.py`: PV, Macaulay duration, modified duration, DV01, key-rate DV01, cash-flow chart.
- `4_Funding_Status.py`: liability PV and liability DV01 as part of funding status.
- `5_Client_Report.py`: liability PV, DV01, duration, funding ratio, surplus/deficit, CSV/PDF report.

### Hedge Analytics

```text
frontend/pages/2_Hedge_Optimizer.py
        |
        | POST /api/hedging/hedge-notional
        v
backend/api/hedging.py
        |
        | _build_interest_rate_swap(...)
        v
backend/models/hedging.py::InterestRateSwap
```

Routes:

- `/api/hedging/swap-value` calls `fixed_leg_pv()`, `floating_leg_pv()`, `swap_value()`, `dv01()`.
- `/api/hedging/hedge-notional` calls `dv01()` and `hedge_notional()`.

Frontend displays:

- `2_Hedge_Optimizer.py`: liability DV01, swap DV01, hedge notional, before/after hedge DV01 chart.

### Scenario Analytics

```text
frontend/pages/3_Scenario_Analysis.py
        |
        | POST /api/scenarios/vasicek
        v
backend/api/scenarios.py
        |
        | VasicekModel(...).simulate_paths(...)
        v
backend/models/scenarios.py::VasicekModel
```

Route:

- `/api/scenarios/vasicek` calls `simulate_paths()` and `summarize_terminal_rates()`.

Frontend displays:

- `3_Scenario_Analysis.py`: sample rate paths, terminal rate histogram, mean/std/5%/50%/95% terminal-rate metrics.

### Portfolio And Funding

```text
frontend/pages/4_Funding_Status.py
frontend/pages/5_Client_Report.py
        |
        | direct Python import
        v
backend/models/portfolio.py::PortfolioModel
        |
        | plus API calls to liability endpoints
        v
Funding ratio and surplus/deficit calculations in frontend page
```

There is no dedicated portfolio API endpoint. The Streamlit pages instantiate `PortfolioModel` directly.

## 1. LiabilityModel

File: `backend/models/liability.py`

Purpose: model pension liabilities as a dictionary of future annual cash flows and a dictionary of annual spot discount rates.

### Module Header And Class Design

Lines 1-5 state that this module contains only core liability analytics and intentionally has no framework dependencies. That matters in an interview because it means the model can be used from FastAPI, Streamlit, tests, or another batch/reporting process.

Line 7 imports `annotations` from `__future__` so type hints can be evaluated more flexibly.

Line 10 defines `class LiabilityModel`.

Lines 11-28 document the assumptions:

- `cash_flows` maps year to pension payment amount.
- `discount_curve` maps year to annual spot discount rate.
- Year `1` means one year from valuation date.
- Discounting uses annual compounding:

```text
PV_t = cash_flow_t / (1 + discount_rate_t)^t
```

Line 30 defines `BASIS_POINT = 0.0001`, which is 1 bp in decimal rate terms.

Design rationale:

- A class is used because several calculations share the same cash flows and curve.
- Dictionaries make the input easy to serialize through JSON and Pydantic.
- Copying inputs protects the model from accidental external mutation.
- Validation happens once during initialization, so calculation methods can assume clean inputs.

### `__init__(cash_flows, discount_curve)`

Lines: 32-40

Inputs:

- `cash_flows: dict[int, float]`
- `discount_curve: dict[int, float]`

Output:

- No return value. Initializes the object or raises an exception.

Called from:

- `backend/api/liability.py::_build_liability_model()`.
- Unit tests in `tests/test_liability.py`.

API endpoint usage:

- Indirectly used by all liability endpoints:
  - `/api/liability/pv`
  - `/api/liability/duration`
  - `/api/liability/dv01`
  - `/api/liability/key-rate-dv01`

Frontend usage:

- Indirectly displayed by:
  - `frontend/pages/1_Liability_Analysis.py`
  - `frontend/pages/4_Funding_Status.py`
  - `frontend/pages/5_Client_Report.py`

Line-by-line:

- Line 38 copies `cash_flows` into `self.cash_flows`.
- Line 39 copies `discount_curve` into `self.discount_curve`.
- Line 40 calls `_validate_inputs()` immediately.

Why copy dictionaries?

- If the caller mutates the original dictionary after constructing the model, the model remains stable.
- This is especially useful in tests and API handlers.

Complexity:

- Time: `O(n + m)` due to validation, where `n` is number of cash flows and `m` is number of curve points.
- Space: `O(n + m)` due to copying dictionaries.

### `present_value()`

Lines: 42-47

Inputs:

- No method arguments.
- Uses `self.cash_flows` and `self.discount_curve`.

Output:

- `float`: total present value of all liability cash flows.

Called from:

- `backend/api/liability.py::calculate_present_value()`.
- `macaulay_duration()`.
- `modified_duration()`.
- Unit tests in `tests/test_liability.py`.

API endpoint:

- `/api/liability/pv`

Frontend displays:

- `1_Liability_Analysis.py`: "Present Value" metric.
- `4_Funding_Status.py`: "Liability PV" metric and funding ratio.
- `5_Client_Report.py`: "Liability PV" metric and CSV/PDF report.

Formula:

```text
PV = sum_t CF_t / (1 + r_t)^t
```

Line-by-line:

- Line 44 starts a `sum(...)`.
- Lines 45-46 iterate over each `(year, cash_flow)` pair.
- For each pair, `_discounted_cash_flow(year, cash_flow)` returns that cash flow's present value.
- Line 47 closes the generator expression and returns the sum.

Design rationale:

- Delegating one cash-flow discounting calculation to `_discounted_cash_flow()` avoids duplicating formula code.
- A generator expression avoids building an intermediate list.

Complexity:

- Time: `O(n)`.
- Space: `O(1)` beyond the iterator, because it streams values into `sum`.

Interview explanation:

I value the liability as the sum of discounted projected pension benefit payments. Each cash flow uses its matching maturity rate, so the 5-year cash flow is discounted at the 5-year curve point.

### `macaulay_duration()`

Lines: 49-66

Inputs:

- No method arguments.
- Uses validated cash flows and discount curve.

Output:

- `float`: PV-weighted average payment time in years.

Called from:

- `backend/api/liability.py::calculate_duration()`.
- Unit tests in `tests/test_liability.py`.

API endpoint:

- `/api/liability/duration`

Frontend displays:

- `1_Liability_Analysis.py`: "Macaulay Duration" metric.
- `5_Client_Report.py`: "Macaulay Duration" in report data and PDF table.

Formula:

```text
Macaulay Duration = sum_t t * PV(CF_t) / Total PV
```

Line-by-line:

- Line 59 calculates total PV by calling `present_value()`.
- Line 60 calls `_ensure_positive_present_value(pv)` because duration is undefined when PV is zero.
- Lines 62-65 calculate `weighted_time`, which is the sum of each year multiplied by that year's discounted cash-flow contribution.
- Line 66 divides weighted time by total PV.

Design rationale:

- Calling `present_value()` reuses the same discounting logic.
- The zero-PV guard avoids a divide-by-zero error and gives a domain-specific message.

Complexity:

- Time: `O(n)` for `present_value()` plus `O(n)` for `weighted_time`, so `O(n)`.
- Space: `O(1)`.

Interview explanation:

Macaulay duration is the weighted average timing of the liability payments, where the weights are present value contributions. Long-dated liabilities have longer duration because more of the PV is concentrated in later years.

### `modified_duration()`

Lines: 68-92

Inputs:

- No method arguments.

Output:

- `float`: first-order percentage sensitivity of liability PV to a parallel rate move under annual compounding.

Called from:

- `backend/api/liability.py::calculate_duration()`.
- Unit tests in `tests/test_liability.py`.

API endpoint:

- `/api/liability/duration`

Frontend displays:

- `1_Liability_Analysis.py`: "Modified Duration" metric.
- `5_Client_Report.py`: "Modified Duration" metric and PDF table.

Formula:

For each cash flow:

```text
PV_t = CF_t / (1 + r_t)^t
dPV_t/dy = -t * CF_t / (1 + r_t)^(t + 1)
Modified Duration = -1 / PV * dPV/dy
```

Because the derivative is negative, the implementation calculates the positive sensitivity:

```text
sensitivity = sum_t t * CF_t / (1 + r_t)^(t + 1)
modified_duration = sensitivity / PV
```

Line-by-line:

- Line 83 calculates total present value.
- Line 84 checks that PV is not zero.
- Lines 86-91 compute the positive part of the derivative magnitude for each cash flow.
- Line 92 divides the sensitivity by total PV.

Design rationale:

- For a flat curve, this reduces to Macaulay duration divided by `(1 + rate)`.
- With a non-flat curve, it applies the same derivative idea using each maturity's spot rate.

Complexity:

- Time: `O(n)` for PV plus `O(n)` for sensitivity, so `O(n)`.
- Space: `O(1)`.

Interview explanation:

Modified duration translates the timing of cash flows into first-order price sensitivity. It answers: approximately what percentage does the liability PV change for a 1.00 rate move? DV01 then turns that into dollars per basis point.

### `dv01()`

Lines: 94-105

Inputs:

- No method arguments.

Output:

- `float`: dollar sensitivity of liability PV to a 1 bp parallel rate move.

Called from:

- `backend/api/liability.py::calculate_dv01()`.
- Unit tests in `tests/test_liability.py`.

API endpoint:

- `/api/liability/dv01`

Frontend displays:

- `1_Liability_Analysis.py`: "DV01" metric.
- `4_Funding_Status.py`: "Liability DV01" metric.
- `5_Client_Report.py`: "Liability DV01" metric and PDF table.

Formula:

```text
DV01 = (PV(-1 bp) - PV(+1 bp)) / 2
```

Line-by-line:

- Line 103 calls `pv_under_parallel_shift(-1.0)`.
- Line 104 calls `pv_under_parallel_shift(1.0)`.
- Line 105 returns half the difference.

Why half the difference?

- The model uses a symmetric finite difference around the current curve.
- It is more balanced than using only a one-sided shock.

Why positive for liabilities?

- Liability PV increases when discount rates fall.
- Therefore `PV_down` is usually greater than `PV_up`, making liability DV01 positive.

Complexity:

- Time: `O(n)` for the down valuation plus `O(n)` for the up valuation, so `O(n)`.
- Space: `O(1)`.

Interview explanation:

I calculate liability DV01 by shocking the entire discount curve down 1 bp and up 1 bp, revaluing the liability, and taking half the difference. This gives dollar sensitivity to a basis-point move.

### `pv_under_parallel_shift(shift_bps)`

Lines: 107-120

Inputs:

- `shift_bps: float`: rate shock in basis points.

Output:

- `float`: liability PV after shifting every discount curve point.

Called from:

- `dv01()`.
- Unit test `test_present_value_decreases_when_rates_shift_upward()`.

API endpoint:

- Not directly exposed.
- Indirectly used by `/api/liability/dv01`.

Frontend displays:

- Not directly displayed.
- Its output feeds liability DV01 displayed on liability, funding, and report pages.

Formula:

```text
shift = shift_bps * 0.0001
PV_shifted = sum_t CF_t / (1 + r_t + shift)^t
```

Line-by-line:

- Line 116 converts bps to decimal rate terms.
- Lines 117-120 loop through all cash flows and discount them with shifted rates.

Design rationale:

- Keeping this as a separate method makes DV01 easy to read.
- It is also useful for tests and potential future stress scenario pages.

Complexity:

- Time: `O(n)`.
- Space: `O(1)`.

Interview explanation:

This method applies a parallel shift to the full curve and revalues all liability cash flows. It is the building block for parallel DV01 and rate stress testing.

### `key_rate_dv01(key_rates)`

Lines: 122-155

Inputs:

- `key_rates: list[int]`: maturity nodes to shock, such as `[5, 10, 20, 30]`.

Output:

- `dict[int, float]`: mapping from key-rate year to key-rate DV01.

Called from:

- `backend/api/liability.py::calculate_key_rate_dv01()`.
- Unit tests in `tests/test_liability.py`.

API endpoint:

- `/api/liability/key-rate-dv01`

Frontend displays:

- `1_Liability_Analysis.py`: key-rate DV01 metric cards and bar chart in `render_key_rate_dv01_analysis()`.

Formula:

```text
KRDV01_k = (PV(curve with node k down 1 bp) - PV(curve with node k up 1 bp)) / 2
```

Line-by-line:

- Line 139 initializes the output dictionary.
- Line 141 loops over requested key rates.
- Lines 142-144 return `0.0` for missing key-rate nodes and continue. This avoids failing just because a selected tenor is absent.
- Lines 146-147 copy the original curve into separate up and down curves.
- Line 148 shifts only the selected key-rate node up 1 bp.
- Line 149 shifts only the selected key-rate node down 1 bp.
- Lines 151-152 revalue liabilities under the down and up curves.
- Line 153 stores the symmetric finite-difference key-rate DV01.
- Line 155 returns the dictionary.

Design rationale:

- Copying the curve avoids mutating the model's original curve.
- Missing key rates return zero because, under this exact-node curve representation, a missing node has no modeled effect.
- The same finite-difference logic as parallel DV01 makes the risk measure easy to explain.

Complexity:

- Let `n` be cash flows, `m` be discount curve points, and `k` be requested key rates.
- Each key rate copies two curves: `O(m)`.
- Each key rate revalues two PVs: `O(n)`.
- Time: `O(k * (m + n))`.
- Space: `O(m)` per loop iteration for copied curves, plus `O(k)` output.

Interview explanation:

Key-rate DV01 decomposes rate sensitivity by tenor. I shock one maturity node at a time, revalue the liability, and report the dollar sensitivity for that node. This helps identify which swap or bond maturities are most relevant for hedging.

### `_present_value_with_curve(discount_curve)`

Lines: 157-162

Inputs:

- `discount_curve: dict[int, float]`: supplied curve, often a shocked curve.

Output:

- `float`: PV using the supplied curve.

Called from:

- `key_rate_dv01()`.

API endpoint:

- Not directly exposed.
- Indirectly used by `/api/liability/key-rate-dv01`.

Frontend displays:

- Indirectly used by the key-rate DV01 section in `1_Liability_Analysis.py`.

Line-by-line:

- Lines 159-162 calculate the same PV formula as `present_value()`, but using the supplied curve argument rather than `self.discount_curve`.

Design rationale:

- This helper allows key-rate shocks to use temporary curve copies.
- It avoids overwriting `self.discount_curve`.

Complexity:

- Time: `O(n)`.
- Space: `O(1)`.

### `_discounted_cash_flow(year, cash_flow)`

Lines: 164-167

Inputs:

- `year: int`
- `cash_flow: float`

Output:

- `float`: PV contribution of one cash flow.

Called from:

- `present_value()`.
- `macaulay_duration()`.

API endpoint:

- Not directly exposed.
- Indirectly used by `/api/liability/pv` and `/api/liability/duration`.

Frontend displays:

- Indirectly contributes to liability PV and duration metrics.

Line-by-line:

- Line 166 retrieves the rate for that payment year.
- Line 167 applies annual-compounded discounting.

Formula:

```text
PV_t = CF_t / (1 + r_t)^t
```

Complexity:

- Time: `O(1)` dictionary lookup and arithmetic.
- Space: `O(1)`.

### `_validate_inputs()`

Lines: 169-193

Inputs:

- No arguments.
- Reads `self.cash_flows` and `self.discount_curve`.

Output:

- `None`, or raises `TypeError`/`ValueError`.

Called from:

- `__init__()`.

API endpoint:

- Indirectly used by all liability endpoints through model construction.

Frontend displays:

- Errors surface through FastAPI HTTP 400 and Streamlit `st.error()` handling.

Line-by-line:

- Lines 171-172 reject empty cash-flow dictionaries.
- Lines 174-185 validate each cash-flow entry:
  - Line 175 validates the year key.
  - Lines 177-178 require numeric cash-flow values.
  - Lines 179-180 reject negative cash flows.
  - Lines 182-185 require a discount rate for every cash-flow year.
- Lines 187-193 validate each curve entry:
  - Line 188 validates the curve year.
  - Lines 190-191 require numeric rates.
  - Lines 192-193 reject rates less than or equal to -100%, because `(1 + rate)` would be zero or negative.

Design rationale:

- Validate at construction so financial methods stay focused on formulas.
- Missing curve points fail early rather than producing a `KeyError` later.
- Non-negative cash flows match the simplified pension benefit payment assumption.

Complexity:

- Time: `O(n + m)`.
- Space: `O(1)`.

### `_validate_year(year, field_name)`

Lines: 195-201

Inputs:

- `year: int`
- `field_name: str`

Output:

- `None`, or raises.

Called from:

- `_validate_inputs()`.

Line-by-line:

- Lines 198-199 require years to be integers and explicitly reject booleans. In Python, `bool` is a subclass of `int`, so the `isinstance(year, bool)` guard is intentional.
- Lines 200-201 require positive years.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `_ensure_positive_present_value(present_value)`

Lines: 203-207

Inputs:

- `present_value: float`

Output:

- `None`, or raises.

Called from:

- `macaulay_duration()`.
- `modified_duration()`.

Line-by-line:

- Lines 206-207 raise a `ValueError` if PV is zero.

Design rationale:

- Duration divides by PV.
- A zero PV makes duration mathematically undefined.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

## 2. InterestRateSwap

File: `backend/models/hedging.py`

Purpose: model a simplified plain-vanilla annual-pay fixed-for-floating interest-rate swap for LDI hedge sizing.

### Module Header And Class Design

Lines 1-3 define this as an interest-rate hedging model with no framework dependency.

Line 6 defines `class InterestRateSwap`.

Lines 7-30 document the instrument:

- `notional`: swap notional.
- `fixed_rate`: annual fixed coupon rate.
- `maturity_years`: integer maturity.
- `discount_curve`: annual spot curve.
- Annual fixed payments.
- Annual compounding.
- Floating leg approximation:

```text
Floating Leg PV = Notional * (1 - DF_T)
```

Line 32 defines one basis point as `0.0001`.

Design rationale:

- The model is simple enough to explain in an interview but still contains the key hedge-sizing concept: match liability DV01 with instrument DV01.
- The signed swap value convention is explicit: `floating leg - fixed leg`.

### `__init__(notional, fixed_rate, maturity_years, discount_curve)`

Lines: 34-46

Inputs:

- `notional: float`
- `fixed_rate: float`
- `maturity_years: int`
- `discount_curve: dict[int, float]`

Output:

- No return value. Initializes the swap or raises.

Called from:

- `backend/api/hedging.py::_build_interest_rate_swap()`.
- Unit tests in `tests/test_hedging.py`.

API endpoint usage:

- Indirectly used by:
  - `/api/hedging/swap-value`
  - `/api/hedging/hedge-notional`

Frontend displays:

- `2_Hedge_Optimizer.py` indirectly displays swap DV01 and hedge notional.

Line-by-line:

- Lines 42-45 store swap terms and copy the curve.
- Line 46 validates all terms.

Complexity:

- Time: `O(maturity_years + m)` due to validation.
- Space: `O(m)` for curve copy.

### `fixed_leg_pv()`

Lines: 48-50

Inputs:

- No method arguments.

Output:

- `float`: PV of annual fixed coupons.

Called from:

- `swap_value()`.
- `backend/api/hedging.py::calculate_swap_value()`.
- Unit tests.

API endpoint:

- `/api/hedging/swap-value`

Frontend displays:

- No current Streamlit page displays fixed leg PV directly.
- It is returned by the API and could be shown in an expanded hedge diagnostics view.

Formula:

```text
Fixed Leg PV = sum_t Notional * Fixed Rate * DF_t
DF_t = 1 / (1 + r_t)^t
```

Line-by-line:

- Line 50 delegates to `_fixed_leg_pv(self.discount_curve)`.

Design rationale:

- Public method is a clean API.
- Private helper accepts arbitrary curves, which is useful for shocked DV01 valuations.

Complexity:

- Time: `O(T)`, where `T` is maturity in years.
- Space: `O(1)`.

### `floating_leg_pv()`

Lines: 52-54

Inputs:

- No method arguments.

Output:

- `float`: approximate PV of floating leg.

Called from:

- `swap_value()`.
- `backend/api/hedging.py::calculate_swap_value()`.
- Unit tests.

API endpoint:

- `/api/hedging/swap-value`

Frontend displays:

- No current Streamlit page displays floating leg PV directly.

Formula:

```text
Floating Leg PV = Notional * (1 - DF_T)
```

Line-by-line:

- Line 54 delegates to `_floating_leg_pv(self.discount_curve)`.

Design rationale:

- Uses a standard simplified par floating leg approximation.
- Keeps the educational model transparent.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `swap_value()`

Lines: 56-61

Inputs:

- No method arguments.

Output:

- `float`: swap market value under the model convention.

Called from:

- `backend/api/hedging.py::calculate_swap_value()`.
- Unit tests.

API endpoint:

- `/api/hedging/swap-value`

Frontend displays:

- Not currently displayed directly in Streamlit.

Formula:

```text
Swap Value = Floating Leg PV - Fixed Leg PV
```

Line-by-line:

- Line 61 calls `floating_leg_pv()`.
- Line 61 calls `fixed_leg_pv()`.
- Line 61 subtracts fixed from floating.

Design rationale:

- The sign convention is explicit. Positive value benefits receive-floating/pay-fixed.
- This convention also determines the sign of swap DV01 and hedge notional.

Complexity:

- Time: `O(T)` because fixed leg loops through all payment years.
- Space: `O(1)`.

### `dv01()`

Lines: 63-75

Inputs:

- No method arguments.

Output:

- `float`: signed swap DV01.

Called from:

- `backend/api/hedging.py::calculate_swap_value()`.
- `backend/api/hedging.py::calculate_hedge_notional()`.
- `hedge_notional()`.
- Unit tests.

API endpoints:

- `/api/hedging/swap-value`
- `/api/hedging/hedge-notional`

Frontend displays:

- `2_Hedge_Optimizer.py`: "Swap DV01" metric.

Formula:

```text
Swap DV01 = (Value(-1 bp) - Value(+1 bp)) / 2
```

Line-by-line:

- Line 73 calculates swap value under a 1 bp lower curve.
- Line 74 calculates swap value under a 1 bp higher curve.
- Line 75 returns the symmetric finite difference.

Design rationale:

- Same finite-difference style as liability DV01.
- The result is signed because a swap can offset or add to liability rate risk depending on direction.

Complexity:

- `_swap_value_under_parallel_shift()` runs a fixed leg PV of `O(T)` and floating leg PV of `O(1)`.
- `dv01()` calls it twice.
- Time: `O(T)`.
- Space: `O(m)` inside the shifted curve helper.

Interview explanation:

Swap DV01 is the dollar change in swap value for a 1 bp curve move. I calculate it by revaluing the swap under down-1-bp and up-1-bp curves. The sign matters because the hedge direction depends on whether the swap gains or loses value when rates move.

### `hedge_notional(liability_dv01)`

Lines: 77-104

Inputs:

- `liability_dv01: float`

Output:

- `float`: required notional of this swap structure to offset liability DV01. The sign indicates hedge direction under the model's convention.

Called from:

- `backend/api/hedging.py::calculate_hedge_notional()`.
- Unit tests.

API endpoint:

- `/api/hedging/hedge-notional`

Frontend displays:

- `2_Hedge_Optimizer.py`: "Hedge Notional" metric and before/after hedge risk chart.

Formula:

```text
Hedge Notional = Liability DV01 * Base Swap Notional / Base Swap DV01
```

Line-by-line:

- Lines 97-98 require `liability_dv01` to be numeric.
- Line 100 calls `self.dv01()` to calculate the DV01 of the base swap.
- Lines 101-102 reject zero swap DV01 because hedge notional would divide by zero.
- Line 104 scales the swap notional by the ratio of liability DV01 to swap DV01.

Design rationale:

- The model takes a base swap notional and computes DV01 for that notional. It then scales linearly because DV01 is approximately proportional to notional.
- Returning signed notional is useful because hedge direction matters.

Complexity:

- Time: `O(T)` because it calls `dv01()`.
- Space: `O(m)` inside shifted curve construction.

Function call path from UI:

```text
2_Hedge_Optimizer.py::calculate_hedge()
  POST /api/hedging/hedge-notional
    hedging.py::calculate_hedge_notional()
      _build_interest_rate_swap()
        InterestRateSwap.__init__()
      InterestRateSwap.dv01()
      InterestRateSwap.hedge_notional()
        InterestRateSwap.dv01()
```

Note: the route calculates `swap.dv01()` once for the response and `hedge_notional()` calls `dv01()` again internally. That is simple and clear, though a production version could avoid recalculating.

### `_swap_value_under_parallel_shift(shift_bps)`

Lines: 106-114

Inputs:

- `shift_bps: float`

Output:

- `float`: swap value after shifting all curve points.

Called from:

- `dv01()`.

API endpoint:

- Indirectly used by `/api/hedging/swap-value` and `/api/hedging/hedge-notional`.

Frontend displays:

- Indirectly feeds swap DV01 and hedge notional on `2_Hedge_Optimizer.py`.

Line-by-line:

- Lines 108-111 build a new `shifted_curve` dictionary by adding `shift_bps * BASIS_POINT` to each rate.
- Lines 112-114 calculate `floating leg PV - fixed leg PV` using the shifted curve.

Design rationale:

- Uses a copied shifted curve so original swap curve is not mutated.
- Centralizes shocked swap valuation for DV01.

Complexity:

- Time: `O(m + T)`.
- Space: `O(m)`.

### `_fixed_leg_pv(discount_curve)`

Lines: 116-122

Inputs:

- `discount_curve: dict[int, float]`

Output:

- `float`: fixed leg PV using supplied curve.

Called from:

- `fixed_leg_pv()`.
- `_swap_value_under_parallel_shift()`.

Formula:

```text
annual_coupon = notional * fixed_rate
fixed_leg_pv = sum_t annual_coupon * DF_t
```

Line-by-line:

- Line 118 calculates the annual fixed coupon.
- Lines 119-122 sum coupon times discount factor for years `1` through `maturity_years`.

Design rationale:

- The helper accepts a curve parameter so both current and shocked valuations reuse one implementation.

Complexity:

- Time: `O(T)`.
- Space: `O(1)`.

### `_floating_leg_pv(discount_curve)`

Lines: 124-130

Inputs:

- `discount_curve: dict[int, float]`

Output:

- `float`: approximate floating leg PV.

Called from:

- `floating_leg_pv()`.
- `_swap_value_under_parallel_shift()`.

Formula:

```text
floating_leg_pv = notional * (1 - DF_T)
```

Line-by-line:

- Lines 126-129 get the maturity discount factor.
- Line 130 returns notional times one minus that discount factor.

Design rationale:

- This is a compact approximation for a par floating leg between reset dates.
- It avoids building a full projected floating cash-flow schedule.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `_discount_factor(year, discount_curve)`

Lines: 132-135

Inputs:

- `year: int`
- `discount_curve: dict[int, float]`

Output:

- `float`: annual-compounded discount factor.

Called from:

- `_fixed_leg_pv()`.
- `_floating_leg_pv()`.

Formula:

```text
DF_t = 1 / (1 + r_t)^t
```

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `_validate_inputs()`

Lines: 137-168

Inputs:

- No method arguments.

Output:

- `None`, or raises.

Called from:

- `__init__()`.

Line-by-line:

- Lines 139-142 validate notional is numeric and positive.
- Lines 144-147 validate fixed rate is numeric and greater than -100%.
- Lines 149-154 validate maturity is a positive integer and reject bool.
- Lines 156-158 require a curve point for every payment year from 1 to maturity.
- Lines 160-168 validate every curve year and rate.

Design rationale:

- The swap valuation loops from year 1 to maturity, so every year must exist in the curve.
- Rejecting rates at or below -100% avoids division by zero or invalid annual compounding.

Complexity:

- Time: `O(T + m)`.
- Space: `O(1)`.

## 3. VasicekModel

File: `backend/models/scenarios.py`

Purpose: generate stochastic interest-rate scenarios with a one-factor mean-reverting short-rate model.

### Module Header And Class Design

Line 5 imports NumPy because path simulation is vectorized across paths.

Line 8 defines `class VasicekModel`.

Lines 9-31 document:

- `kappa`: mean reversion speed.
- `theta`: long-run mean rate.
- `sigma`: rate volatility.
- `r0`: initial short rate.
- Continuous-time model:

```text
dr = kappa * (theta - r) * dt + sigma * dW
```

- Discrete approximation:

```text
r[t+1] = r[t] + kappa * (theta - r[t]) * dt + sigma * sqrt(dt) * Z
```

Line 33 defines `BASIS_POINT = 0.0001`.

Design rationale:

- Vasicek is mathematically simple and easy to explain.
- Euler-Maruyama lets the app simulate paths using a clear step-by-step formula.
- The class stores `_last_paths` so `summarize_terminal_rates()` can summarize the most recent simulation.

### `__init__(kappa, theta, sigma, r0)`

Lines: 35-48

Inputs:

- `kappa: float`
- `theta: float`
- `sigma: float`
- `r0: float`

Output:

- Initializes the model or raises.

Called from:

- `backend/api/scenarios.py::simulate_vasicek()`.

API endpoint:

- `/api/scenarios/vasicek`

Frontend displays:

- `3_Scenario_Analysis.py` displays simulated paths and terminal-rate metrics from this model.

Line-by-line:

- Lines 43-46 store model parameters.
- Line 47 initializes `_last_paths` to `None`.
- Line 48 validates model parameters.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `simulate_path(years, dt)`

Lines: 50-66

Inputs:

- `years: float`
- `dt: float`

Output:

- `np.ndarray`: one-dimensional rate path.

Called from:

- Not used by current API or frontend.
- Useful convenience wrapper for tests or future single-path views.

API endpoint:

- Not directly used.

Frontend displays:

- Not directly used.

Line-by-line:

- Line 66 calls `simulate_paths(years=years, dt=dt, n_paths=1)` and returns the first path.

Design rationale:

- Avoids duplicating simulation logic.
- Single-path simulation is a special case of multi-path simulation.

Complexity:

- Time: `O(S)`, where `S = ceil(years / dt)`.
- Space: `O(S)`.

### `simulate_paths(years, dt, n_paths)`

Lines: 68-112

Inputs:

- `years: float`: horizon.
- `dt: float`: time step in years.
- `n_paths: int`: number of Monte Carlo paths.

Output:

- `np.ndarray` of shape `(n_paths, n_steps + 1)`.

Called from:

- `backend/api/scenarios.py::simulate_vasicek()`.
- `simulate_path()`.

API endpoint:

- `/api/scenarios/vasicek`

Frontend displays:

- `3_Scenario_Analysis.py`:
  - `render_sample_paths_chart()` displays up to 25 paths.
  - `render_terminal_rate_histogram()` displays terminal distribution.
  - `render_summary_metrics()` displays summary statistics calculated after simulation.

Euler formula:

```text
r_next = r_current + drift + diffusion
drift = kappa * (theta - r_current) * dt
diffusion = sigma * sqrt(dt) * Z
Z ~ N(0, 1)
```

Implementation detail:

The code draws `random_shocks` with `scale=np.sqrt(dt)`, so each shock is already `sqrt(dt) * Z`. Then it multiplies by `sigma`.

Line-by-line:

- Lines 90-94 validate simulation inputs and calculate `n_steps`.
- Line 96 allocates an empty NumPy array of shape `(n_paths, n_steps + 1)`.
- Line 97 sets the first column of every path equal to `r0`.
- Lines 99-103 generate random normal shocks:
  - Mean `0.0`.
  - Standard deviation `sqrt(dt)`.
  - Shape `(n_paths, n_steps)`, one shock per path per step.
- Line 105 loops over time steps.
- Line 106 reads current rates for all paths at that step.
- Line 107 calculates the mean-reversion drift vector.
- Line 108 calculates the stochastic diffusion vector.
- Line 109 writes the next rates for all paths.
- Line 111 stores the paths in `_last_paths`.
- Line 112 returns the paths.

Design rationale:

- Vectorizes across paths at each time step, which is much faster than nested Python loops over paths and steps.
- Keeps a loop over time because each next rate depends on the previous rate.
- Stores `_last_paths` so a separate summary method can operate on the same simulation.

Random number generation:

- Uses `np.random.normal`.
- No explicit random seed is set, so each API call produces different scenarios.
- In production or tests, a seed or random generator object would improve reproducibility.

Complexity:

- Let `P = n_paths` and `S = ceil(years / dt)`.
- Time: `O(P * S)`.
- Space: `O(P * S)` for the full path matrix plus random shocks.

Interview explanation:

The scenario engine simulates a mean-reverting short rate. Each step pulls rates toward the long-run mean through the drift term and adds randomness through the diffusion term. The implementation vectorizes all paths for each time step, stores the full path matrix, and summarizes terminal rates.

### `parallel_shift_scenarios()`

Lines: 114-128

Inputs:

- No method arguments.

Output:

- `dict[str, float]`: shifted initial-rate scenarios.

Called from:

- Not called by the current API or frontend.

API endpoint:

- Not exposed.

Frontend displays:

- Not displayed.

Line-by-line:

- Line 123 defines shifts of `+25`, `+50`, `+100`, `-25`, `-50`, and `-100` bps.
- Lines 124-128 return a dictionary where each key is a formatted label and each value is `r0 + shift`.

Design rationale:

- This is a useful future hook for deterministic stress scenarios.
- It complements Monte Carlo by providing named rate shocks.

Complexity:

- Time: `O(1)` because there are always six shifts.
- Space: `O(1)`.

### `summarize_terminal_rates()`

Lines: 130-156

Inputs:

- No method arguments.
- Uses `self._last_paths`.

Output:

- `dict[str, float]` with:
  - `mean`
  - `std`
  - `5%`
  - `50%`
  - `95%`

Called from:

- `backend/api/scenarios.py::simulate_vasicek()`.

API endpoint:

- `/api/scenarios/vasicek`

Frontend displays:

- `3_Scenario_Analysis.py::render_summary_metrics()` displays mean, standard deviation, 5th percentile, median, and 95th percentile.

Line-by-line:

- Lines 144-145 raise if no paths have been simulated yet.
- Line 147 extracts the final column of the path matrix, which is the terminal rate for each path.
- Line 148 calculates the 5%, 50%, and 95% quantiles.
- Lines 150-156 return summary statistics as plain floats, which are JSON serializable.

Design rationale:

- Terminal-rate statistics are the most compact way to describe the future rate distribution.
- Casting NumPy values to Python floats prevents serialization issues in FastAPI responses.

Complexity:

- Let `P = n_paths`.
- Time: `O(P)` for mean/std plus roughly `O(P log P)` or implementation-dependent quantile cost.
- Space: `O(P)` for terminal rates view/reference and quantile work.

### `_validate_inputs()`

Lines: 158-168

Inputs:

- No method arguments.

Output:

- `None`, or raises.

Called from:

- `__init__()`.

Line-by-line:

- Lines 160-163 ensure `kappa`, `theta`, `sigma`, and `r0` are numeric.
- Lines 165-166 require positive mean-reversion speed.
- Lines 167-168 require non-negative volatility.

Design rationale:

- `kappa <= 0` would not be a valid mean-reversion speed for this model.
- Negative volatility is not meaningful.
- `theta` and `r0` can be negative because rate models may allow negative rates.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `_validate_simulation_inputs(years, dt, n_paths)`

Lines: 170-195

Inputs:

- `years: float`
- `dt: float`
- `n_paths: int`

Output:

- `int`: number of simulation steps.

Called from:

- `simulate_paths()`.

Line-by-line:

- Lines 177-182 validate types and reject bool for `n_paths`.
- Lines 184-189 require positive years, positive `dt`, and positive path count.
- Line 191 calculates `n_steps = ceil(years / dt)`.
- Lines 192-193 guard against zero-step simulations.
- Line 195 returns `n_steps`.

Design rationale:

- Using `ceil` ensures the simulation covers at least the requested horizon.
- Returning `n_steps` keeps validation and step-count calculation in one place.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `_format_shift_label(shift_bps)`

Lines: 197-201

Inputs:

- `shift_bps: int`

Output:

- `str`: formatted label such as `+25bp` or `-50bp`.

Called from:

- `parallel_shift_scenarios()`.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

## 4. PortfolioModel And Funding

File: `backend/models/portfolio.py`

Purpose: aggregate asset values into growth and hedging portfolios and compute allocation weights.

### Class Design

Lines 6-20 define the model:

- Growth assets:
  - `equities`
  - `credit`
- Hedging assets:
  - `long_bonds`
  - `irs_exposure`

Design rationale:

- The model mirrors common LDI language: growth portfolio seeks returns; hedging portfolio manages liability interest-rate risk.
- The model is intentionally simple and directly imported by Streamlit pages rather than exposed through a separate API.

### `__init__(equities, credit, long_bonds, irs_exposure)`

Lines: 22-34

Inputs:

- `equities: float`
- `credit: float`
- `long_bonds: float`
- `irs_exposure: float`

Output:

- Initializes the object or raises.

Called from:

- `frontend/pages/4_Funding_Status.py::render_inputs()`.
- `frontend/pages/5_Client_Report.py::render_inputs()`.
- Unit tests in `tests/test_portfolio.py`.

API endpoint:

- None. This model is used directly in the frontend.

Frontend displays:

- `4_Funding_Status.py`: growth portfolio, hedging portfolio, total assets, allocation charts.
- `5_Client_Report.py`: portfolio metrics, CSV/PDF allocation tables, allocation chart.

Line-by-line:

- Lines 30-33 store the four asset values.
- Line 34 validates them.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `growth_portfolio()`

Lines: 36-38

Inputs:

- No method arguments.

Output:

- `float`: equities plus credit.

Called from:

- `total_assets()`.
- `growth_allocation()`.
- `as_dict()`.
- `4_Funding_Status.py::render_inputs()`.

Frontend displays:

- `4_Funding_Status.py`: "Growth Portfolio" metric and allocation charts.
- `5_Client_Report.py`: "Growth Portfolio" metric and PDF/CSV.

Formula:

```text
Growth Portfolio = Equities + Credit
```

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `hedging_portfolio()`

Lines: 40-42

Inputs:

- No method arguments.

Output:

- `float`: long bonds plus IRS exposure.

Called from:

- `total_assets()`.
- `hedging_allocation()`.
- `as_dict()`.
- `4_Funding_Status.py::render_inputs()`.

Frontend displays:

- `4_Funding_Status.py`: "Hedging Portfolio" metric and allocation charts.
- `5_Client_Report.py`: "Hedging Portfolio" metric and PDF/CSV.

Formula:

```text
Hedging Portfolio = Long Bonds + IRS Exposure
```

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `total_assets()`

Lines: 44-46

Inputs:

- No method arguments.

Output:

- `float`: total assets.

Called from:

- `_allocation()`.
- `as_dict()`.
- `4_Funding_Status.py::render_inputs()`.
- `5_Client_Report.py::generate_client_report()`.

Frontend displays:

- `4_Funding_Status.py`: "Total Assets" metric and asset-liability chart.
- `5_Client_Report.py`: "Total Assets" metric, CSV, PDF.

Formula:

```text
Total Assets = Growth Portfolio + Hedging Portfolio
```

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `growth_allocation()`

Lines: 48-50

Inputs:

- No method arguments.

Output:

- `float`: growth share of total assets.

Called from:

- `as_dict()`.

Frontend displays:

- `5_Client_Report.py`: "Growth Allocation" metric and allocation table.
- `4_Funding_Status.py` computes allocation directly in `render_funding_ratio_attribution()` rather than calling this method.

Formula:

```text
Growth Allocation = Growth Portfolio / Total Assets
```

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `hedging_allocation()`

Lines: 52-54

Inputs:

- No method arguments.

Output:

- `float`: hedging share of total assets.

Called from:

- `as_dict()`.

Frontend displays:

- `5_Client_Report.py`: "Hedging Allocation" metric and allocation table.

Formula:

```text
Hedging Allocation = Hedging Portfolio / Total Assets
```

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `as_dict()`

Lines: 56-68

Inputs:

- No method arguments.

Output:

- `dict[str, float]`: all input components, totals, and allocations.

Called from:

- `5_Client_Report.py::render_portfolio_summary_metrics()`.
- `5_Client_Report.py::generate_client_report()`.

Frontend displays:

- Client report metrics, charts, CSV, and PDF.

Line-by-line:

- Lines 58-68 build a dictionary with:
  - raw inputs: equities, credit, long bonds, IRS exposure.
  - derived totals: growth, hedging, total assets.
  - derived weights: growth allocation, hedging allocation.

Design rationale:

- `as_dict()` creates a single object that can be merged into `report_data`.
- That makes CSV/PDF export straightforward.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `_allocation(value)`

Lines: 70-75

Inputs:

- `value: float`: portfolio sleeve value.

Output:

- `float`: allocation weight.

Called from:

- `growth_allocation()`.
- `hedging_allocation()`.

Formula:

```text
Allocation = value / total_assets
```

Line-by-line:

- Line 72 calculates total assets.
- Lines 73-74 return zero if total assets are zero.
- Line 75 returns the allocation ratio.

Design rationale:

- Avoids division by zero.
- Returning zero allocations for a zero-asset plan is a pragmatic dashboard behavior.

Complexity:

- Time: `O(1)`.
- Space: `O(1)`.

### `_validate_inputs()`

Lines: 77-84

Inputs:

- No method arguments.

Output:

- `None`, or raises.

Called from:

- `__init__()`.

Line-by-line:

- Line 79 loops over the four portfolio fields.
- Line 80 reads each value dynamically using `getattr`.
- Lines 81-82 require numeric values.
- Lines 83-84 reject negative market values.

Design rationale:

- All four asset fields share the same validation rules, so a loop avoids repetition.
- Negative asset values are not allowed in this simplified market-value model.

Complexity:

- Time: `O(1)` because there are always four fields.
- Space: `O(1)`.

## Funding Ratio And Surplus Calculations

Funding ratio is not inside `PortfolioModel`; it is calculated in the Streamlit pages because it combines portfolio assets with liability PV returned by the backend.

### Funding Status Page

File: `frontend/pages/4_Funding_Status.py`

Call path:

```text
render_inputs()
  PortfolioModel(...)
  growth_portfolio()
  hedging_portfolio()
  total_assets()

calculate_funding_status()
  build_liability_payload()
  POST /api/liability/pv
  POST /api/liability/dv01
  liability_pv = present_value["present_value"]
  liability_dv01 = dv01["dv01"]
  funding_ratio = asset_market_value / liability_pv
  surplus = asset_market_value - liability_pv
```

Formulas:

```text
Funding Ratio = Total Assets / Liability PV
Surplus / Deficit = Total Assets - Liability PV
```

Displayed in:

- `render_metrics()`: total assets, liability PV, funding ratio, surplus/deficit, liability DV01.
- `render_funding_ratio_attribution()`: growth and hedging allocation.
- `render_portfolio_allocation_pie_chart()`.
- `render_portfolio_type_chart()`.
- `render_asset_liability_chart()`.
- `render_surplus_chart()`.

Design rationale:

- Funding status is a cross-model result: assets come from `PortfolioModel`; liabilities come from the liability API.
- Keeping the final ratio in the page makes it easy to display and report without adding a separate backend endpoint.

Complexity:

- Portfolio aggregation: `O(1)`.
- Liability PV API call: `O(n)` in backend.
- Liability DV01 API call: `O(n)` in backend.
- Chart DataFrame creation: `O(1)` because chart categories are fixed.

### Client Report Page

File: `frontend/pages/5_Client_Report.py`

Call path:

```text
generate_client_report()
  build_liability_payload()
  POST /api/liability/pv
  POST /api/liability/dv01
  POST /api/liability/duration
  portfolio.as_dict()
  asset_market_value = portfolio.total_assets()
  report_data = {
    funding_ratio = asset_market_value / liability_pv
    surplus_deficit = asset_market_value - liability_pv
    ...
  }
  render_metrics()
  render_visualization()
  render_downloads()
    create_csv_report()
    create_pdf_report()
```

Displayed in:

- Streamlit metrics.
- Plotly dashboard charts.
- CSV download.
- PDF metric table, executive summary, allocation table, charts, and methodology.

## API Layer Walkthrough

### Liability API

File: `backend/api/liability.py`

Core request classes:

- `LiabilityRequest`: `cash_flows`, `discount_curve`.
- `KeyRateDV01Request`: extends `LiabilityRequest` with `key_rates`.

Response classes:

- `PresentValueResponse`: `present_value`.
- `DurationResponse`: `macaulay_duration`, `modified_duration`.
- `DV01Response`: `dv01`.
- `KeyRateDV01Response`: `key_rate_dv01`.

Route call paths:

```text
POST /api/liability/pv
  calculate_present_value()
    _build_liability_model()
      LiabilityModel.__init__()
    model.present_value()
```

```text
POST /api/liability/duration
  calculate_duration()
    _build_liability_model()
      LiabilityModel.__init__()
    model.macaulay_duration()
    model.modified_duration()
```

```text
POST /api/liability/dv01
  calculate_dv01()
    _build_liability_model()
      LiabilityModel.__init__()
    model.dv01()
```

```text
POST /api/liability/key-rate-dv01
  calculate_key_rate_dv01()
    _build_liability_model()
      LiabilityModel.__init__()
    model.key_rate_dv01(request.key_rates)
```

Design rationale:

- Pydantic validates request shape and response shape.
- `_build_liability_model()` centralizes model construction and maps finance validation errors to HTTP 400.
- Separate endpoints keep frontend calls explicit and modular.

### Hedging API

File: `backend/api/hedging.py`

Core request classes:

- `SwapRequest`: notional, fixed rate, maturity, discount curve.
- `HedgeNotionalRequest`: extends `SwapRequest` with liability DV01.

Response classes:

- `SwapValueResponse`: fixed leg PV, floating leg PV, swap value, swap DV01.
- `HedgeNotionalResponse`: liability DV01, swap DV01, hedge notional.

Route call paths:

```text
POST /api/hedging/swap-value
  calculate_swap_value()
    _build_interest_rate_swap()
      InterestRateSwap.__init__()
    swap.fixed_leg_pv()
    swap.floating_leg_pv()
    swap.swap_value()
    swap.dv01()
```

```text
POST /api/hedging/hedge-notional
  calculate_hedge_notional()
    _build_interest_rate_swap()
      InterestRateSwap.__init__()
    swap.dv01()
    swap.hedge_notional(request.liability_dv01)
```

Design rationale:

- Swap valuation and hedge sizing are separate use cases.
- The hedge endpoint returns enough information for the frontend to show both the instrument sensitivity and the resulting notional.

### Scenario API

File: `backend/api/scenarios.py`

Request:

- `VasicekRequest`: kappa, theta, sigma, r0, years, dt, n_paths.

Response:

- `VasicekResponse`: paths, terminal rates, summary.

Route call path:

```text
POST /api/scenarios/vasicek
  simulate_vasicek()
    VasicekModel(...)
    model.simulate_paths(...)
    model.summarize_terminal_rates()
    return paths.tolist(), terminal_rates, summary
```

Design rationale:

- NumPy arrays are converted to lists so they can be returned as JSON.
- The API returns both full paths and terminal rates because the frontend needs line charts and histograms.

## Frontend Page Walkthrough

### `1_Liability_Analysis.py`

Purpose: standalone liability analytics dashboard.

Major functions:

- `main()`: sets page config, renders inputs, button, and chart.
- `render_liability_inputs()`: creates editable cash-flow and discount-curve tables.
- `calculate_liability_analytics()`: builds payload and calls four liability endpoints.
- `post_liability_endpoint()`: shared POST helper for liability routes.
- `render_liability_metrics()`: displays PV, durations, and DV01.
- `render_key_rate_dv01_analysis()`: displays key-rate DV01 metrics, bar chart, and largest exposure guidance.
- `render_cash_flow_chart()`: displays projected cash flows.
- `build_liability_payload()`: converts editable tables into JSON-ready dictionaries.
- `prepare_cash_flow_dataframe()` and `prepare_discount_curve_dataframe()`: numeric cleanup and sorting.

Interview point:

This page is the clearest example of full data flow: table inputs -> JSON payload -> FastAPI -> `LiabilityModel` -> response JSON -> Streamlit metrics and charts.

### `2_Hedge_Optimizer.py`

Purpose: liability DV01 hedge sizing with a simplified interest-rate swap.

Major functions:

- `main()`: renders page and calculate button.
- `render_inputs()`: collects liability DV01, swap notional, fixed rate, and maturity.
- `calculate_hedge()`: builds flat curve, calls `/api/hedging/hedge-notional`, and calculates before/after hedge risk.
- `build_flat_discount_curve()`: creates `{year: fixed_rate}` for all swap years.
- `render_metrics()`: displays liability DV01, swap DV01, hedge notional.
- `render_risk_chart()`: bar chart of pre-hedge and post-hedge DV01.

Key implementation detail:

The frontend calculates:

```text
hedge_dv01 = hedge_notional / swap_notional * swap_dv01
after_hedge_risk = liability_dv01 - hedge_dv01
```

Because `hedge_notional` is signed under the backend convention, the displayed residual risk depends on that sign. In a production version, the sign convention would need careful UX labeling.

### `3_Scenario_Analysis.py`

Purpose: stochastic interest-rate scenario dashboard.

Major functions:

- `main()`: renders inputs and run button.
- `render_inputs()`: collects Vasicek parameters.
- `run_scenario_analysis()`: calls `/api/scenarios/vasicek`.
- `render_sample_paths_chart()`: melts the path matrix into long format and plots up to 25 sample paths.
- `render_terminal_rate_histogram()`: plots terminal distribution.
- `render_summary_metrics()`: displays mean, std, 5%, median, 95%.

Key constants:

- `TIME_STEP = 0.25`: quarterly time step.
- `MAX_DISPLAY_PATHS = 25`: prevents unreadable charts when many paths are simulated.

### `4_Funding_Status.py`

Purpose: asset-liability funded status dashboard.

Major functions:

- `render_inputs()`: collects growth and hedging assets, builds `PortfolioModel`, and collects liability tables.
- `calculate_funding_status()`: calls liability PV and DV01 endpoints, computes funding ratio and surplus.
- `render_funding_ratio_attribution()`: shows growth/hedging allocation.
- `render_metrics()`: displays core funded status metrics.
- `render_funding_ratio_card()` and `funding_ratio_color()`: color-coded funded status.
- Chart helpers: allocation pie, portfolio type bar, asset-liability bar, surplus bar.

Key finance formulas:

```text
Funding Ratio = Total Assets / Liability PV
Surplus = Total Assets - Liability PV
```

### `5_Client_Report.py`

Purpose: quarterly-style reporting and export.

Major functions:

- `render_inputs()`: collects client metadata, portfolio, and liability inputs.
- `generate_client_report()`: calls liability endpoints, builds `report_data`, renders metrics/charts/downloads.
- `create_csv_report()`: one-row CSV from `report_data`.
- `create_pdf_report()`: ReportLab PDF with summary, tables, charts, and methodology.
- `generate_executive_summary()`: client-facing interpretation.
- `funding_interpretation()`: concise status label based on funding ratio.
- `funding_ratio_report_color()`: status color for PDF chart.

Interview point:

This page demonstrates the client-reporting requirement: it turns raw analytics into repeatable output that could resemble a quarterly LDI report.

## Tests And What They Prove

### `tests/test_liability.py`

Covers:

- PV formula correctness on simple cash flows.
- Duration is positive.
- DV01 is positive for normal liability cash flows.
- PV decreases when rates rise.
- Key-rate DV01 returns requested keys.
- Missing key-rate node returns zero.
- Key-rate DV01 does not mutate the original curve.
- Invalid inputs raise errors.

Interview point:

The tests focus on finance invariants, not just code execution.

### `tests/test_hedging.py`

Covers:

- Fixed leg PV is positive.
- Floating leg PV is positive.
- Swap value returns a float.
- Swap DV01 is nonzero.
- Hedge notional formula preserves direction.
- Invalid swap terms raise errors.

### `tests/test_portfolio.py`

Covers:

- Growth, hedging, and total assets.
- Allocation weights.
- Zero total assets returns zero allocations.
- Negative inputs are rejected.

## Complexity Cheat Sheet

| Component | Main Operation | Time Complexity | Space Complexity |
|---|---|---:|---:|
| `LiabilityModel.present_value()` | Discount all cash flows | `O(n)` | `O(1)` |
| `LiabilityModel.macaulay_duration()` | PV plus weighted PV | `O(n)` | `O(1)` |
| `LiabilityModel.modified_duration()` | PV plus derivative sum | `O(n)` | `O(1)` |
| `LiabilityModel.dv01()` | Two parallel shifted PVs | `O(n)` | `O(1)` |
| `LiabilityModel.key_rate_dv01()` | Two PVs per key rate plus curve copies | `O(k * (n + m))` | `O(m + k)` |
| `InterestRateSwap.fixed_leg_pv()` | Sum fixed coupons | `O(T)` | `O(1)` |
| `InterestRateSwap.floating_leg_pv()` | Maturity discount factor | `O(1)` | `O(1)` |
| `InterestRateSwap.swap_value()` | Floating minus fixed | `O(T)` | `O(1)` |
| `InterestRateSwap.dv01()` | Two shocked swap valuations | `O(T + m)` | `O(m)` |
| `InterestRateSwap.hedge_notional()` | Swap DV01 plus scaling | `O(T + m)` | `O(m)` |
| `VasicekModel.simulate_paths()` | Simulate path matrix | `O(P * S)` | `O(P * S)` |
| `VasicekModel.summarize_terminal_rates()` | Terminal statistics | `O(P)` to `O(P log P)` | `O(P)` |
| `PortfolioModel` totals/allocations | Arithmetic | `O(1)` | `O(1)` |

Definitions:

- `n`: number of liability cash flows.
- `m`: number of discount curve points.
- `k`: number of key-rate tenors requested.
- `T`: swap maturity in years.
- `P`: number of Monte Carlo paths.
- `S`: number of simulation steps.

## Deep Interview Talking Points

### Why pure model classes?

The quant logic is reusable and testable. `LiabilityModel`, `InterestRateSwap`, `VasicekModel`, and `PortfolioModel` do not import FastAPI or Streamlit. That makes the formulas easier to unit test and avoids mixing UI concerns with finance logic.

### Why finite-difference DV01?

Finite-difference DV01 is easy to explain and works consistently across liabilities and swaps. It also naturally captures some nonlinearity from revaluing under shocked curves, even though the interpretation is still first-order rate sensitivity.

### Why symmetric shocks?

Symmetric shocks reduce one-sided approximation bias:

```text
DV01 = (Value_down - Value_up) / 2
```

This centers the sensitivity around the current curve.

### What would change in production?

- Add market curve bootstrapping and interpolation.
- Add actuarial liability cash-flow generation.
- Add trade-level swap conventions, forward curves, OIS discounting, and day counts.
- Add multi-instrument key-rate hedge optimization.
- Add persistent data storage.
- Add deterministic stress scenarios that revalue assets and liabilities.
- Add authentication, observability, and audit trails.

