"""Update investment records from run_result.json."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

RUN_RESULT_PATH = Path("run_result.json")
RECORDS_PATH = Path("docs/data/investment_records.csv")

CSV_HEADERS = [
    "date",
    "status",
    "ahr999",
    "btc_price",
    "planned_invest_usdt",
    "executed_invest_usdt",
    "executed_btc_amount",
    "cum_invest_usdt",
    "cum_btc_amount",
    "portfolio_value_usdt",
    "pnl_usdt",
    "pnl_ratio",
    "benchmark_btc_amount",
    "benchmark_value_usdt",
    "benchmark_pnl_usdt",
    "benchmark_pnl_ratio",
    "alpha_usdt",
    "alpha_ratio",
    "run_time_utc",
    "note",
]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: float) -> str:
    return f"{value:.10f}"


def _load_run_result() -> Dict[str, Any]:
    if not RUN_RESULT_PATH.exists():
        raise FileNotFoundError(f"Missing run result file: {RUN_RESULT_PATH}")
    with RUN_RESULT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_date(run_time_utc: str) -> str:
    try:
        return datetime.strptime(run_time_utc, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid run_time_utc: {run_time_utc}") from exc


def _load_existing_rows() -> List[Dict[str, str]]:
    if not RECORDS_PATH.exists():
        return []
    with RECORDS_PATH.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _recalculate(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    rows_sorted = sorted(rows, key=lambda row: (row["date"], row["run_time_utc"]))

    cum_invest = 0.0
    cum_btc = 0.0
    benchmark_btc = 0.0
    calculated: List[Dict[str, str]] = []

    for row in rows_sorted:
        btc_price = _to_float(row.get("btc_price"))
        executed_invest = _to_float(row.get("executed_invest_usdt"))
        executed_btc = _to_float(row.get("executed_btc_amount"))

        cum_invest += executed_invest
        cum_btc += executed_btc
        portfolio_value = cum_btc * btc_price
        pnl_usdt = portfolio_value - cum_invest
        pnl_ratio = pnl_usdt / cum_invest if cum_invest > 0 else 0.0

        if btc_price > 0:
            benchmark_btc += executed_invest / btc_price
        benchmark_value = benchmark_btc * btc_price
        benchmark_pnl_usdt = benchmark_value - cum_invest
        benchmark_pnl_ratio = benchmark_pnl_usdt / cum_invest if cum_invest > 0 else 0.0

        alpha_usdt = pnl_usdt - benchmark_pnl_usdt
        alpha_ratio = pnl_ratio - benchmark_pnl_ratio

        updated = dict(row)
        updated["cum_invest_usdt"] = _fmt(cum_invest)
        updated["cum_btc_amount"] = _fmt(cum_btc)
        updated["portfolio_value_usdt"] = _fmt(portfolio_value)
        updated["pnl_usdt"] = _fmt(pnl_usdt)
        updated["pnl_ratio"] = _fmt(pnl_ratio)
        updated["benchmark_btc_amount"] = _fmt(benchmark_btc)
        updated["benchmark_value_usdt"] = _fmt(benchmark_value)
        updated["benchmark_pnl_usdt"] = _fmt(benchmark_pnl_usdt)
        updated["benchmark_pnl_ratio"] = _fmt(benchmark_pnl_ratio)
        updated["alpha_usdt"] = _fmt(alpha_usdt)
        updated["alpha_ratio"] = _fmt(alpha_ratio)
        calculated.append(updated)

    return calculated


def _build_row(run_result: Dict[str, Any]) -> Dict[str, str]:
    run_time_utc = str(run_result.get("run_time_utc", "")).strip()
    if not run_time_utc:
        raise ValueError("run_result missing run_time_utc")

    date = _extract_date(run_time_utc)
    status = str(run_result.get("status", "failed"))
    failure_type = str(run_result.get("failure_type", "exception"))

    note = ""
    if status == "failed":
        note = failure_type

    return {
        "date": date,
        "status": status,
        "ahr999": _fmt(_to_float(run_result.get("ahr999"), 0.0)),
        "btc_price": _fmt(_to_float(run_result.get("btc_price"), 0.0)),
        "planned_invest_usdt": _fmt(_to_float(run_result.get("planned_invest_usdt"), 0.0)),
        "executed_invest_usdt": _fmt(_to_float(run_result.get("executed_invest_usdt"), 0.0)),
        "executed_btc_amount": _fmt(_to_float(run_result.get("executed_btc_amount"), 0.0)),
        "cum_invest_usdt": _fmt(0.0),
        "cum_btc_amount": _fmt(0.0),
        "portfolio_value_usdt": _fmt(0.0),
        "pnl_usdt": _fmt(0.0),
        "pnl_ratio": _fmt(0.0),
        "benchmark_btc_amount": _fmt(0.0),
        "benchmark_value_usdt": _fmt(0.0),
        "benchmark_pnl_usdt": _fmt(0.0),
        "benchmark_pnl_ratio": _fmt(0.0),
        "alpha_usdt": _fmt(0.0),
        "alpha_ratio": _fmt(0.0),
        "run_time_utc": run_time_utc,
        "note": note,
    }


def update_records() -> int:
    run_result = _load_run_result()
    status = str(run_result.get("status", "failed"))
    failure_type = str(run_result.get("failure_type", "exception"))
    planned = _to_float(run_result.get("planned_invest_usdt"), 0.0)
    executed = _to_float(run_result.get("executed_invest_usdt"), 0.0)

    # User-required policy: skip pure no-buy success days.
    if status == "success" and failure_type == "none" and planned <= 0 and executed <= 0:
        print("[INFO] Skip record update for no-buy success day.")
        return 0

    if _to_float(run_result.get("btc_price"), 0.0) <= 0:
        raise ValueError("btc_price must be available for record updates")

    new_row = _build_row(run_result)
    rows = _load_existing_rows()

    rows = [row for row in rows if row.get("date") != new_row["date"]]
    rows.append(new_row)
    rows = _recalculate(rows)

    RECORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RECORDS_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[INFO] Updated investment records: {RECORDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(update_records())

