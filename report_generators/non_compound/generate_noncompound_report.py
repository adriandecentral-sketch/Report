"""
Inner Circle Capital — Non-Compounded Performance Report
=========================================================
Generates a QuantStats HTML tearsheet using simple (non-compounded) returns
suitable for a fixed-capital strategy account (e.g. TopstepX $150k).

Same visual format as the compound tearsheet, with these differences:
  - compounded=False passed to qs.reports.html()
  - Returns series: zero-filled from REPORT_START (business days)
  - Sharpe / Sortino on full calendar period (same methodology as compound)
  - CAGR replaced with Ann. Simple Return = total_pnl/capital × (252/n_trade_days)
  - Calmar = Ann. Simple Return / MaxDD% of initial capital

Usage:
    python scripts/generate_noncompound_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import quantstats as qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORT_CACHE_JSON = ROOT / "reports" / "inner_circle_quantstats_cache.json"
OUTPUT_DIR        = ROOT / "reports" / "non_compound"

# Risk-free rate — Apr 2026 US T-bill (annualized). Update when rate changes.
RISK_FREE_RATE = 0.0375


def _load_cache() -> tuple[dict, float, str, str]:
    if not REPORT_CACHE_JSON.exists():
        raise FileNotFoundError(
            f"Cache not found: {REPORT_CACHE_JSON}\n"
            "Run generate_quantstats_report.py once (without --report-only) to build it."
        )
    with open(REPORT_CACHE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    daily_pnl = {k: float(v) for k, v in data["daily_pnl"].items()}
    cap       = float(data.get("initial_capital", 150_000.0))
    start     = str(data["report_start"])
    end       = str(data["report_end"])
    return daily_pnl, cap, start, end


def _build_returns(daily_pnl: dict, cap: float, report_start: str) -> pd.Series:
    """Zero-fill from report_start through last trade date (business days).

    Anchoring to the full calendar period (same as compound report) ensures:
    - QS shows the correct Dec 1 start date
    - Sharpe / Sortino use the same calendar-period denominator as the compound report
    """
    s = pd.Series(daily_pnl, dtype=float) / cap
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    all_dates = pd.bdate_range(start=report_start, end=s.index[-1])
    return s.reindex(all_dates, fill_value=0.0)


def _max_dd_dollar(daily_pnl: dict) -> float:
    """Peak-to-trough dollar drawdown from cumulative daily P&L."""
    cum, peak, max_dd = 0.0, 0.0, 0.0
    for d in sorted(daily_pnl):
        cum += daily_pnl[d]
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    return max_dd


def _patch_html(html_path: Path, ann_simple_pct: float, calmar: float) -> None:
    """Replace CAGR label+value and Calmar value with non-compound equivalents.

    QuantStats always emits CAGR and always computes Calmar via geometric CAGR
    regardless of the compounded flag. This post-processing corrects both to the
    definitions appropriate for a fixed-capital account:
      Ann. Simple Return % = total_simple_return × (252 / n_trade_days) × 100
      Calmar               = Ann. Simple Return / MaxDD% of initial capital

    Uses regex string replacement (not BeautifulSoup) so the original HTML is
    preserved byte-for-byte except for the two patched cells — avoiding any
    layout/CSS degradation from full HTML re-serialisation.
    """
    import re

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    # 1. Rename the CAGR label cell
    html = html.replace("CAGR﹪%", "Ann. Simple Return %")

    # 2. Replace the value cell that immediately follows the (now-renamed) label.
    #    Pattern matches the label cell, optional whitespace, then the value cell.
    html = re.sub(
        r'(<td[^>]*>\s*Ann\. Simple Return %\s*</td>\s*<td[^>]*>)[^<]*(</td>)',
        rf'\g<1>{ann_simple_pct:.2f}\g<2>',
        html,
    )

    # 3. Replace the Calmar value cell that follows the Calmar label cell.
    html = re.sub(
        r'(<td[^>]*>\s*Calmar\s*</td>\s*<td[^>]*>)[^<]*(</td>)',
        rf'\g<1>{calmar:.2f}\g<2>',
        html,
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def main() -> None:
    daily_pnl, cap, period_start, period_end = _load_cache()

    returns = _build_returns(daily_pnl, cap, period_start)

    # ------------------------------------------------------------------ #
    # Non-compound metrics — computed here because QuantStats always uses  #
    # geometric CAGR internally regardless of the compounded flag.        #
    # ------------------------------------------------------------------ #
    trade_returns   = returns[returns != 0.0]
    n_trade_days    = len(trade_returns)
    total_simple    = returns.sum()                              # e.g. 0.6222
    ann_simple_pct  = total_simple * (252 / n_trade_days) * 100 # e.g. 203.65
    max_dd_dollar   = _max_dd_dollar(daily_pnl)                 # e.g. $3,600
    max_dd_pct_init = max_dd_dollar / cap                        # e.g. 0.0240
    calmar_correct  = (ann_simple_pct / 100) / max_dd_pct_init  # e.g. 84.85

    print(
        f"Non-compounded report\n"
        f"  Period         : {period_start} to {period_end}\n"
        f"  Trade days     : {n_trade_days}\n"
        f"  Calendar days  : {len(returns)}\n"
        f"  Total Return % : {total_simple * 100:.2f}%\n"
        f"  Ann. Simple Ret: {ann_simple_pct:.2f}%\n"
        f"  MaxDD ($)      : ${max_dd_dollar:,.0f}\n"
        f"  MaxDD (% init) : {max_dd_pct_init * 100:.2f}%\n"
        f"  Calmar         : {calmar_correct:.2f}\n"
        f"  rf             : {RISK_FREE_RATE:.2%}"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = (
        f"Inner_Circle_NonCompound"
        f"_{period_start.replace('-', '')}"
        f"_{period_end.replace('-', '')}.html"
    )
    output_path = OUTPUT_DIR / fname

    qs.reports.html(
        returns,
        benchmark=None,
        rf=RISK_FREE_RATE,
        title="Inner Circle Capital",
        output=str(output_path),
        compounded=False,
        periods_per_year=252,
        report_heading="Inner Circle Capital",
        report_subheading="Systematic Multi-Strategy Performance Report",
    )

    # Patch CAGR → Ann. Simple Return and correct Calmar in the generated HTML
    _patch_html(output_path, ann_simple_pct, calmar_correct)

    print(f"Report saved to : {output_path}")


if __name__ == "__main__":
    main()
