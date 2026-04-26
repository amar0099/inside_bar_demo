# Inside Bar Terminal — v2 Specification

This is `inside_bar_terminal_V4.py`, an update of V3 implementing the v2 strategy
spec from the backtest analysis (Jan 2021 – Apr 2026 on BankNifty 1-min).

## Run locally
```bash
pip install -r requirements.txt
streamlit run inside_bar_terminal_V4.py
```

## Strategy changes from V3

### Trade-management changes
| | V3 | V4 (v2 spec) |
|---|---|---|
| RR target | 1:2 | **1:1** |
| Mother range minimum | none | **≥ 100 pts** |
| Mother range maximum | none | **≤ 0.40% of entry** |
| Force-close time | 15:10 | **15:15** |
| Daily SL circuit breaker | none | **stop after 2 consecutive SLs** |
| Position concurrency | unlimited | **one trade at a time** |

### New: Regime gate
- Computes 10-day rolling avg daily range from prior days only
- Skips the entire day if avg > 1.5%
- Surfaces a green/red status pill in the sidebar

## Tunable constants
All v2 parameters are at the top of the file in the `CONSTANTS & TIME RULES` section:

```python
RR_TARGET_MULTIPLE     = 1.0
MIN_MOTHER_RANGE_PTS   = 100
MAX_MOTHER_RANGE_PCT   = 0.40
CONSEC_SL_LIMIT        = 2
REGIME_FILTER_ENABLED  = True
REGIME_LOOKBACK_DAYS   = 10
REGIME_MAX_AVG_RANGE   = 1.50
```

To revert to "no regime filter", set `REGIME_FILTER_ENABLED = False`.

## What's preserved from V3
- Fyers TOTP-based auto-auth (no manual token paste)
- Same Streamlit secrets format
- Same UI layout, chart builder, sim engine, demo flow
- Same data-loading flow for live and sim modes

## Important caveats
1. The app runs on **15-min candles**. The v2 spec mentions 1-min entry confirmation
   in addition to 15-min setup; that's a 1-min execution layer this app doesn't have.
   The 15-min execution here is a faithful approximation — same SL/TGT logic, same
   entry trigger (mother high/low touch), same exit logic.
2. Backtest P&L is on the index — actual options trading will eat ~10–15 pts/trade
   in spread + slippage, which the backtest does NOT model.
3. The first 10 trading days of any new dataset will not have enough history for
   the regime gate; the strategy defaults to "trade allowed" in that case.
