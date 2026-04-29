# Non-Compounded Internal Dashboard

**Audience**: Internal use — personal performance tracking for a fixed-capital trading account.

**Report style**: Plain HTML dashboard — simple returns, trade-days-only Sharpe, MaxDD as % of initial capital (not peak equity).

## Why non-compounded?

The TopstepX account has a fixed $150,000 capital base. Profits are not reinvested into position
sizing — the account balance grows but the risk allocation stays fixed. Compounded returns
would imply profits compound the trading base, which is not what happens here.

## Key parameters

| Setting | Value | Notes |
|---|---|---|
| Returns | Simple `net_pnl / initial_capital` | Correct for fixed-capital accounts |
| Sharpe | Trade-days only (77 days) | No zero-padding — cleaner signal |
| MaxDD % | % of **initial capital** ($150k) | Not % of peak equity |
| Calmar | Ann.Simple Return / MaxDD% of initial capital | Annualised from short sample — indicative |
| VaR/CVaR | Trade-days only, dollar terms | No zero-padding |
| rf | 3.75% annual (Apr 2026 US T-bill) | Update `RF_ANNUAL` when rate changes |

## Usage

Requires the cache to exist (run `compound/generate_quantstats_report.py` once first):

```bash
python generate_noncompound_report.py
```

## Output

`reports/non_compound/Inner_Circle_NonCompound_YYYYMMDD_YYYYMMDD.html` (+ PDF)
