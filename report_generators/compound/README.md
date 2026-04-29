# Compound Report Generator

**Audience**: External investors, allocators, institutional review.

**Report style**: QuantStats HTML tearsheet — compounded returns, full calendar-period Sharpe (including non-trading days), standard institutional metrics.

## Key parameters

| Setting | Value | Notes |
|---|---|---|
| Returns | Compounded `(∏(1+r)) - 1` | Industry standard for tearsheets |
| Sharpe | Calendar period (105 business days) | Includes zero-return flat days |
| MaxDD % | % of peak equity | QS convention |
| CAGR | Compounded, annualised | Inflated on short samples — see caveat |
| rf | 3.75% annual (Apr 2026 US T-bill) | Update `RISK_FREE_RATE` when rate changes |

## Period caveat

CAGR and Calmar are annualised from a 4.8-month sample. These figures are indicative only.
The report subheading includes this note automatically.

## Usage

```bash
# Full run (re-runs backtest, saves cache)
python generate_quantstats_report.py

# Fast re-generate HTML/PDF from existing cache (no backtest)
python generate_quantstats_report.py --report-only
```

## Output

`reports/Inner_Circle_Capital_Performance_Report_Dec2025_Apr2026.html` (+ PDF)
