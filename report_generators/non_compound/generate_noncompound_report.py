"""
Inner Circle Capital — Non-Compounded Internal Dashboard
=========================================================
Generates a plain HTML performance report using simple (non-compounded) returns
suitable for a fixed-capital strategy account (e.g. TopstepX $150k).

Key differences from the institutional QuantStats tearsheet:
  - Simple returns (net_pnl / initial_capital), NOT compounded
  - Sharpe / Sortino on trade-days ONLY (77 days) — no zero-padding
  - MaxDD expressed as % of initial capital (not % of peak equity)
  - Calmar = Annualized Simple Return / MaxDD% of initial capital
  - VaR / CVaR computed on trade-days-only distribution in dollar terms
  - CAGR label replaced with "Ann. Simple Return" (CAGR requires compounding)

Usage:
    python scripts/generate_noncompound_report.py
    python scripts/generate_noncompound_report.py --report-only  (uses cache)
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORT_CACHE_JSON = ROOT / "reports" / "inner_circle_quantstats_cache.json"
OUTPUT_DIR        = ROOT / "reports" / "non_compound"

# Risk-free rate — Apr 2026 US T-bill (annualized). Update when rate changes.
RF_ANNUAL   = 0.0375
RF_DAILY_FRAC = RF_ANNUAL / 252   # as a daily fraction of capital


def _load_cache() -> tuple[dict, dict, float, str, str]:
    if not REPORT_CACHE_JSON.exists():
        raise FileNotFoundError(
            f"Cache not found: {REPORT_CACHE_JSON}\n"
            "Run generate_quantstats_report.py once (without --report-only) to build it."
        )
    with open(REPORT_CACHE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    daily_pnl = {k: float(v) for k, v in data["daily_pnl"].items()}
    metrics   = data["metrics"]
    cap       = float(data.get("initial_capital", 150_000.0))
    start     = str(data["report_start"])
    end       = str(data["report_end"])
    return daily_pnl, metrics, cap, start, end


def _sharpe(dollar_vals: list[float], capital: float) -> float:
    if len(dollar_vals) < 2:
        return 0.0
    rf_hurdle = capital * RF_DAILY_FRAC
    mu  = statistics.mean(dollar_vals) - rf_hurdle
    std = statistics.stdev(dollar_vals)
    return (mu / std) * math.sqrt(252.0) if std > 0 else 0.0


def _sortino(dollar_vals: list[float], capital: float) -> float:
    if len(dollar_vals) < 2:
        return 0.0
    rf_hurdle = capital * RF_DAILY_FRAC
    mu      = statistics.mean(dollar_vals) - rf_hurdle
    neg_sq  = [v * v for v in dollar_vals if v < 0]
    if not neg_sq:
        return float("inf")
    down_std = math.sqrt(sum(neg_sq) / len(dollar_vals))
    return (mu / down_std) * math.sqrt(252.0) if down_std > 0 else 0.0


def _var_cvar(dollar_vals: list[float], confidence: float = 0.95) -> tuple[float, float]:
    """VaR and CVaR (Expected Shortfall) at given confidence level, in dollars."""
    if not dollar_vals:
        return 0.0, 0.0
    sorted_vals = sorted(dollar_vals)
    idx = int(math.floor((1 - confidence) * len(sorted_vals)))
    idx = max(0, idx)
    var  = sorted_vals[idx]          # negative number = loss
    cvar = statistics.mean(sorted_vals[: idx + 1]) if idx >= 0 else sorted_vals[0]
    return var, cvar


def _build_html(metrics_table: list[tuple], period_note: str, output_path: Path) -> None:
    rows_html = ""
    for label, value, note in metrics_table:
        rows_html += (
            f"<tr><td class='label'>{label}</td>"
            f"<td class='value'>{value}</td>"
            f"<td class='note'>{note}</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Inner Circle Capital — Non-Compounded Report</title>
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f8f9fa; color: #212529; margin: 0; padding: 24px; }}
  .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
  h1 {{ font-size: 1.6rem; color: #1a1a2e; margin-bottom: 4px; }}
  h2 {{ font-size: 1.1rem; color: #495057; font-weight: 400; margin-top: 0; margin-bottom: 8px; }}
  .period {{ font-size: 0.85rem; color: #868e96; margin-bottom: 24px; }}
  .caveat {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px 14px; border-radius: 4px; font-size: 0.88rem; color: #664d03; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.93rem; }}
  thead th {{ background: #1a1a2e; color: white; padding: 10px 14px; text-align: left; }}
  tbody tr:nth-child(even) {{ background: #f8f9fa; }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #dee2e6; }}
  td.label {{ font-weight: 600; color: #343a40; width: 34%; }}
  td.value {{ font-family: 'Courier New', monospace; color: #0d6efd; width: 26%; }}
  td.note {{ color: #6c757d; font-size: 0.84rem; }}
  .section-header td {{ background: #e9ecef; font-weight: 700; font-size: 0.82rem; color: #495057; text-transform: uppercase; letter-spacing: 0.5px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Inner Circle Capital</h1>
  <h2>Non-Compounded Internal Dashboard &mdash; Fixed Capital ($150,000)</h2>
  <p class="period">{period_note}</p>
  <div class="caveat">
    <strong>Note:</strong> This report uses <strong>simple (non-compounded) returns</strong> appropriate for a fixed-capital
    trading account where profits are not reinvested. Sharpe and Sortino are computed on trade-days only (no
    zero-padding). Calmar = Annualized Simple Return / MaxDD% of initial capital. Risk-free rate: 3.75% annual
    (Apr 2026 US T-bill). Ratios annualised from a &lt;12-month sample &mdash; treat CAGR and Calmar as indicative only.
  </div>
  <table>
    <thead><tr><th>Metric</th><th>Value</th><th>Notes</th></tr></thead>
    <tbody>
{rows_html}    </tbody>
  </table>
</div>
</body>
</html>"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inner Circle Non-Compounded Dashboard")
    parser.add_argument("--report-only", action="store_true", help="Use cache, skip backtest")
    args = parser.parse_args()

    if not args.report_only:
        # Re-run the backtest and save cache via the quantstats script first
        print("Run generate_quantstats_report.py first to populate the cache, then use --report-only.")
        print("Or run without --report-only and this script will use the existing cache.")

    daily_pnl, m_cache, cap, period_start, period_end = _load_cache()

    # Trade-days only (days with at least one trade exit)
    trade_dollar_vals = sorted(daily_pnl.values())
    n_trade_days      = len(trade_dollar_vals)
    net_pnl           = sum(trade_dollar_vals)
    n_months          = n_trade_days / 21.0

    # Returns
    simple_ret    = net_pnl / cap
    ann_simple    = simple_ret * (252.0 / n_trade_days) if n_trade_days > 0 else 0.0

    # Risk metrics (trade days only)
    sharpe_val    = _sharpe(trade_dollar_vals, cap)
    sortino_val   = _sortino(trade_dollar_vals, cap)
    var95, cvar95 = _var_cvar(trade_dollar_vals, confidence=0.95)

    # Drawdown — use harness bar-by-bar figure (most accurate)
    max_dd_dollar = float(m_cache.get("max_drawdown_realized_trade_path", 0))
    max_dd_pct    = max_dd_dollar / cap if cap > 0 else 0.0
    rec_factor    = net_pnl / max_dd_dollar if max_dd_dollar > 0 else 0.0
    calmar        = ann_simple / max_dd_pct if max_dd_pct > 0 else 0.0

    # Win stats
    total_trades  = int(m_cache.get("total_trades", 0))
    win_rate      = float(m_cache.get("win_rate_pct", m_cache.get("win_rate", 0)))
    profit_factor = float(m_cache.get("profit_factor", 0))
    worst_day_abs = float(m_cache.get("max_daily_loss_dollar", 0))

    # Profit factor from daily PnL
    gross_win  = sum(v for v in trade_dollar_vals if v > 0)
    gross_loss = abs(sum(v for v in trade_dollar_vals if v < 0))

    period_note = (
        f"{period_start} to {period_end}  &bull;  "
        f"{n_trade_days} trading days ({n_months:.1f} months)  &bull;  "
        f"{total_trades} trades  &bull;  rf = {RF_ANNUAL:.2%} annual"
    )

    def fmt_pct(v: float) -> str:
        return f"{v:+.2%}"

    def fmt_usd(v: float) -> str:
        return f"${v:+,.2f}"

    def fmt_ratio(v: float) -> str:
        if v == float("inf"):
            return "&infin;"
        return f"{v:.3f}"

    metrics_table: list[tuple] = [
        # Section: Returns
        ("Returns", "", ""),
        ("Initial Capital",    f"${cap:,.0f}",                      "Fixed account — profits not reinvested"),
        ("Net PnL",            fmt_usd(net_pnl),                    "Sum of all realized trade PnL"),
        ("Simple Return",      fmt_pct(simple_ret),                 "net_pnl / initial_capital"),
        ("Ann. Simple Return", fmt_pct(ann_simple),                 f"simple_return × (252 / {n_trade_days}) — NOT CAGR"),
        # Section: Risk
        ("Risk", "", ""),
        ("MaxDD (intraday $)", fmt_usd(-max_dd_dollar),             "Harness bar-by-bar peak-to-trough"),
        ("MaxDD (% of capital)", fmt_pct(-max_dd_pct),              f"${max_dd_dollar:,.0f} / ${cap:,.0f} initial capital"),
        ("Worst Day",          fmt_usd(-worst_day_abs),             "Largest single-day realized loss"),
        ("Daily VaR 95%",      fmt_usd(var95),                      f"5% of {n_trade_days} trade days lose more than this"),
        ("Daily CVaR 95%",     fmt_usd(cvar95),                     "Mean loss on worst 5% of trade days"),
        ("Topstep Daily Limit","$2,500",                            f"Worst day ${worst_day_abs:,.0f} — {'PASS' if worst_day_abs <= 2_500 else 'FAIL'}"),
        # Section: Risk-Adjusted
        ("Risk-Adjusted", "", ""),
        ("Sharpe",        fmt_ratio(sharpe_val),                    f"Trade-days only ({n_trade_days}d), rf=3.75%"),
        ("Sortino",       fmt_ratio(sortino_val),                   f"Trade-days only ({n_trade_days}d), rf=3.75%"),
        ("Calmar",        fmt_ratio(calmar),                        f"Ann.Simple ({ann_simple:.1%}) / MaxDD% ({max_dd_pct:.2%})"),
        ("Recovery Factor", fmt_ratio(rec_factor),                  "Net PnL / MaxDD$"),
        # Section: Trade Stats
        ("Trade Statistics", "", ""),
        ("Total Trades",    str(total_trades),              ""),
        ("Win Rate",        f"{win_rate:.1f}%",             f"[Wilson 95% CI excluded — short sample]"),
        ("Profit Factor",   fmt_ratio(profit_factor),       "Gross profit / gross loss"),
        ("Gross Win",       fmt_usd(gross_win),             "Sum of profitable trade-days"),
        ("Gross Loss",      fmt_usd(-gross_loss),           "Sum of losing trade-days"),
    ]

    # Mark section headers
    formatted: list[tuple] = []
    for label, value, note in metrics_table:
        if value == "" and note == "":
            formatted.append((f'<tr class="section-header"><td colspan="3">{label}</td></tr>', None, None))
        else:
            formatted.append((label, value, note))

    # Rebuild HTML rows
    rows_html = ""
    for item in formatted:
        if item[1] is None:
            rows_html += item[0] + "\n"
        else:
            rows_html += (
                f"<tr><td class='label'>{item[0]}</td>"
                f"<td class='value'>{item[1]}</td>"
                f"<td class='note'>{item[2]}</td></tr>\n"
            )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Inner Circle Capital — Non-Compounded Report</title>
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f8f9fa; color: #212529; margin: 0; padding: 24px; }}
  .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
  h1 {{ font-size: 1.6rem; color: #1a1a2e; margin-bottom: 4px; }}
  h2 {{ font-size: 1.1rem; color: #495057; font-weight: 400; margin-top: 0; margin-bottom: 8px; }}
  .period {{ font-size: 0.85rem; color: #868e96; margin-bottom: 24px; }}
  .caveat {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px 14px; border-radius: 4px; font-size: 0.88rem; color: #664d03; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.93rem; }}
  thead th {{ background: #1a1a2e; color: white; padding: 10px 14px; text-align: left; }}
  tbody tr:nth-child(even) {{ background: #f8f9fa; }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #dee2e6; }}
  td.label {{ font-weight: 600; color: #343a40; width: 34%; }}
  td.value {{ font-family: 'Courier New', monospace; color: #0d6efd; width: 26%; }}
  td.note {{ color: #6c757d; font-size: 0.84rem; }}
  .section-header td {{ background: #e9ecef; font-weight: 700; font-size: 0.82rem; color: #495057; text-transform: uppercase; letter-spacing: 0.5px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Inner Circle Capital</h1>
  <h2>Non-Compounded Internal Dashboard &mdash; Fixed Capital (${cap:,.0f})</h2>
  <p class="period">{period_note}</p>
  <div class="caveat">
    <strong>Internal use only.</strong> Simple (non-compounded) returns for a fixed-capital account.
    Sharpe &amp; Sortino on {n_trade_days} trade-days only (no zero-padding). Calmar = Ann.Simple / MaxDD% of
    initial capital. rf = {RF_ANNUAL:.2%}. &lt;12-month sample &mdash; ratios are indicative.
  </div>
  <table>
    <thead><tr><th>Metric</th><th>Value</th><th>Notes</th></tr></thead>
    <tbody>
{rows_html}    </tbody>
  </table>
</div>
</body>
</html>"""

    fname = f"Inner_Circle_NonCompound_{period_start.replace('-','')}_{period_end.replace('-','')}.html"
    output_path = OUTPUT_DIR / fname
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Non-compounded report saved to: {output_path}")
    print(f"\nKey metrics ({n_trade_days} trade days, rf={RF_ANNUAL:.2%}):")
    print(f"  Simple Return:      {simple_ret:+.2%}")
    print(f"  Ann. Simple Return: {ann_simple:+.2%}  (not CAGR)")
    print(f"  Sharpe:             {sharpe_val:.3f}")
    print(f"  Sortino:            {sortino_val:.3f}")
    print(f"  Calmar:             {calmar:.3f}")
    print(f"  RecFactor:          {rec_factor:.3f}")
    print(f"  MaxDD ($):          ${max_dd_dollar:,.2f}  ({max_dd_pct:.2%} of capital)")
    print(f"  VaR 95% (daily):    ${var95:,.2f}")
    print(f"  CVaR 95% (daily):   ${cvar95:,.2f}")


if __name__ == "__main__":
    main()
