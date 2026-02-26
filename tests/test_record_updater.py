from __future__ import annotations

import csv
import json
from pathlib import Path

from src.reporting import record_updater


def _write_run_result(tmp_path: Path, payload: dict) -> None:
    (tmp_path / "run_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_rows(tmp_path: Path) -> list[dict[str, str]]:
    with (tmp_path / "docs" / "data" / "investment_records.csv").open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_update_records_success_and_recalculate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    _write_run_result(
        tmp_path,
        {
            "run_time_utc": "2026-02-25T00:00:00Z",
            "status": "success",
            "failure_type": "none",
            "ahr999": 0.9,
            "btc_price": 50000.0,
            "planned_invest_usdt": 10.0,
            "executed_invest_usdt": 10.0,
            "executed_btc_amount": 0.0002,
            "error_message": "",
        },
    )
    assert record_updater.update_records() == 0
    rows = _read_rows(tmp_path)
    assert len(rows) == 1
    assert float(rows[0]["cum_invest_usdt"]) == 10.0
    assert float(rows[0]["portfolio_value_usdt"]) == 10.0
    assert float(rows[0]["benchmark_btc_amount"]) == 10.0 / 50000.0

    _write_run_result(
        tmp_path,
        {
            "run_time_utc": "2026-02-26T00:00:00Z",
            "status": "failed",
            "failure_type": "insufficient_balance",
            "ahr999": 0.8,
            "btc_price": 60000.0,
            "planned_invest_usdt": 15.0,
            "executed_invest_usdt": 0.0,
            "executed_btc_amount": 0.0,
            "error_message": "insufficient balance",
        },
    )
    assert record_updater.update_records() == 0
    rows = _read_rows(tmp_path)
    assert len(rows) == 2
    assert rows[-1]["status"] == "failed"
    assert float(rows[-1]["cum_invest_usdt"]) == 10.0
    assert float(rows[-1]["portfolio_value_usdt"]) == 12.0


def test_update_records_skip_no_buy_success_day(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_run_result(
        tmp_path,
        {
            "run_time_utc": "2026-02-25T00:00:00Z",
            "status": "success",
            "failure_type": "none",
            "ahr999": 1.3,
            "btc_price": 50000.0,
            "planned_invest_usdt": 0.0,
            "executed_invest_usdt": 0.0,
            "executed_btc_amount": 0.0,
            "error_message": "",
        },
    )
    assert record_updater.update_records() == 0
    assert not (tmp_path / "docs" / "data" / "investment_records.csv").exists()

