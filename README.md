# LDI Pension Hedging Analyzer

Educational analytics for liability-driven investment (LDI) pension hedging.

## Implemented Models

- `LiabilityModel`: present value, duration, DV01, and parallel rate shifts for
  annual pension cash flows.
- `InterestRateSwap`: annual-pay fixed-for-floating swap valuation and hedge
  notional sizing.

## Modeling Notes

All discounting currently uses annual compounding.

Floating leg valuation is approximated using:

```text
PV_float ~= N * (1 - DF(T))
```

This simplification is intentional for the first educational implementation.
It keeps the swap module focused on core hedge mechanics rather than full
forward-curve construction, reset schedules, accrual conventions, and curve
bootstrapping.
