"""
Generate Inner Circle Capital QuantStats HTML tearsheet.

Uses the custom QuantStats fork (adriandecentral-sketch/Report) which handles
title, branding, metric filtering, and EOY cumulative natively -- no regex
post-processing needed.

Usage:
    python scripts/generate_quantstats_report.py
    python scripts/generate_quantstats_report.py --report-only   # no run_backtest; uses cache

After a full run, inputs are saved to ``reports/inner_circle_quantstats_cache.json``
so you can regenerate the HTML quickly.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import pandas as pd
import quantstats as qs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.engine import run_backtest
from backtest.profiles import topstep_backtest_config
from backtest.storage import BacktestMetrics

REPO = Path(__file__).resolve().parent.parent
CSV_5M = REPO / "data" / "orderflow_unified_5m.csv"
REPORT_CACHE_JSON = REPO / "reports" / "inner_circle_quantstats_cache.json"

# Report window; end date clamped to data availability.
REPORT_START = "2025-12-01"
REPORT_END_REQUESTED = "2026-04-24"
WARM_UP_BARS = 8_640  # pad ≈ 30 calendar days before REPORT_START (Nov 1 warm-up)
OF_CSV = str(REPO / "data" / "orderflow_5m_enriched_v2_perbar.csv")

# Risk-free rate (annualized). Update when US T-bill rate changes.
# Apr 2026: 3.75% (Fed Funds effective rate).
RISK_FREE_RATE = 0.0375


class _ReportInputs:
    """Minimal container for cached metrics + daily_pnl."""

    __slots__ = ("metrics", "daily_pnl")

    def __init__(self, metrics: BacktestMetrics, daily_pnl: dict) -> None:
        self.metrics = metrics
        self.daily_pnl = daily_pnl


def _save_report_cache(
    *,
    report_start: str,
    report_end: str,
    window_label: str,
    initial_capital: float,
    daily_pnl: dict,
    metrics: BacktestMetrics,
) -> None:
    REPORT_CACHE_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "report_start": report_start,
        "report_end": report_end,
        "window_label": window_label,
        "initial_capital": float(initial_capital),
        "daily_pnl": {str(k): float(v) for k, v in daily_pnl.items()},
        "metrics": dataclasses.asdict(metrics),
    }
    with open(REPORT_CACHE_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved report cache: {REPORT_CACHE_JSON}")


def _load_report_cache() -> tuple[_ReportInputs, str, str, float, str]:
    if not REPORT_CACHE_JSON.exists():
        raise FileNotFoundError(
            f"Missing {REPORT_CACHE_JSON}. Run once without --report-only to build the cache."
        )
    with open(REPORT_CACHE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    field_names = {f.name for f in dataclasses.fields(BacktestMetrics)}
    raw_m = {k: v for k, v in data["metrics"].items() if k in field_names}
    if "run_id" not in raw_m or not raw_m["run_id"]:
        raw_m["run_id"] = "cache"
    metrics = BacktestMetrics(**raw_m)
    daily_pnl = {k: float(v) for k, v in data["daily_pnl"].items()}
    window_label = data.get("window_label") or (
        f"{data['report_start']} to {data['report_end']} (unified data)"
    )
    initial_capital = float(data.get("initial_capital", metrics.initial_capital or 150_000.0))
    return (
        _ReportInputs(metrics, daily_pnl),
        str(data["report_start"]),
        str(data["report_end"]),
        initial_capital,
        window_label,
    )

def _last_data_date_ymd(csv_path: Path) -> str | None:
    """Last calendar date in orderflow_unified_5m (YYYY-MM-DD)."""
    if not csv_path.exists():
        return None
    try:
        tail = pd.read_csv(csv_path, usecols=["timestamp"]).tail(1)
        if tail.empty:
            return None
        ts = pd.to_datetime(tail["timestamp"].iloc[0])
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return None


def _clamp_end_date(requested: str, data_last: str | None) -> str:
    if not data_last:
        return requested
    return min(requested, data_last)


def _build_daily_returns(
    daily_pnl: dict,
    cap: float,
    start_date: str | None = None,
) -> pd.Series:
    daily_series = pd.Series(daily_pnl, name="Strategy", dtype=float)
    daily_series.index = pd.to_datetime(daily_series.index)
    daily_series = daily_series.sort_index()
    if daily_series.empty:
        return daily_series
    # Anchor start to REPORT_START so the header reflects the intended period,
    # even if the first trade occurred later (no-trade days are filled with 0.0).
    series_start = pd.to_datetime(start_date) if start_date else daily_series.index.min()
    all_dates = pd.date_range(series_start, daily_series.index.max(), freq="B")
    daily_series = daily_series.reindex(all_dates, fill_value=0.0)
    return daily_series / float(cap)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inner Circle QuantStats HTML report")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip run_backtest; use daily PnL + metrics from inner_circle_quantstats_cache.json",
    )
    args = parser.parse_args()

    if args.report_only:
        result, period_start, period_end, cap, window_label = _load_report_cache()
        m = result.metrics
        print(
            f"Report-only: cache Sharpe={m.sharpe_per_trade_exit_day:.2f} "
            f"PnL=${m.net_pnl_dollar:+,.0f} ({period_start}–{period_end})"
        )
    else:
        data_last = _last_data_date_ymd(CSV_5M)
        end_date = _clamp_end_date(REPORT_END_REQUESTED, data_last)
        window_label = f"{REPORT_START} to {end_date} (unified data)" + (
            f"; file last bar {data_last}" if data_last else ""
        )

        print(f"Backtest: topstep profile | {window_label}")

        cfg = topstep_backtest_config(
            start_date=REPORT_START,
            end_date=end_date,
            label="inner_circle_quantstats",
            data_source="unified",
            warm_up_bars=WARM_UP_BARS,
            orderflow_csv=OF_CSV,
            trim_csv_before_start=True,
        )

        result = run_backtest(cfg, persist=False)
        if not result.trades:
            print("No trades in window. Exiting.")
            return

        m = result.metrics
        print(
            f"Complete: {m.total_trades} trades, PnL=${m.net_pnl_dollar:+,.0f}, "
            f"Sharpe(harness)={m.sharpe_per_trade_exit_day:.2f}"
        )
        cap = float(cfg.initial_capital)
        period_start = REPORT_START
        period_end = end_date
        _save_report_cache(
            report_start=REPORT_START,
            report_end=end_date,
            window_label=window_label,
            initial_capital=cap,
            daily_pnl=dict(result.daily_pnl),
            metrics=m,
        )

    daily_returns = _build_daily_returns(dict(result.daily_pnl), cap, start_date=REPORT_START)
    if daily_returns.empty:
        print("No daily PnL in cache / result. Exiting.")
        return

    output_dir = REPO / "reports"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "Inner_Circle_Capital_Performance_Report_Dec2025_Apr2026.html"

    print("Generating QuantStats tearsheet (custom fork)...")
    qs.reports.html(
        daily_returns,
        benchmark=None,
        rf=RISK_FREE_RATE,
        title="Inner Circle Capital",
        output=str(output_path),
        compounded=False,
        periods_per_year=252,
        report_heading="Inner Circle Capital",
        report_subheading=(
            "Systematic Multi-Strategy Performance Report  |  "
            "Dec 2025\u2013Apr 2026 (4.8-month sample \u2014 "
            "CAGR and Calmar annualised from a short period, treat as indicative)"
        ),
    )

    print(f"\nReport saved to: {output_path}")
    print(f"Verified Sharpe (harness): {result.metrics.sharpe_per_trade_exit_day:.2f}")


if __name__ == "__main__":
    main()
