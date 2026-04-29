# Report Generators

Two report generators for Inner Circle Capital performance reporting.

| Directory | Audience | Returns | Sharpe days | MaxDD denom |
|---|---|---|---|---|
| `compound/` | External investors | Compounded | 105 calendar bdays | Peak equity |
| `non_compound/` | Internal tracking | Simple | 77 trade-days only | Initial capital |

## When to use which

**`compound/`** — for investor review, fund documents, and external distribution.
Uses QuantStats tearsheet format (standard institutional convention). Sharpe includes
all calendar business days in the period (including flat/no-signal days), which is
the correct methodology for investor-facing documents.

**`non_compound/`** — for personal performance tracking of the TopstepX fixed-capital account.
Uses simple returns since the $150k capital base does not compound with profits.
MaxDD expressed as % of initial capital — not of peak equity — giving a more
conservative and honest picture of drawdown risk.

## Shared cache

Both generators share the same backtest cache at `reports/inner_circle_quantstats_cache.json`.
Run `compound/generate_quantstats_report.py` once to populate the cache, then both can
regenerate quickly using `--report-only` (compound) or just running the non-compound script.
