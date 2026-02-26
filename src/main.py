from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.config.settings import AppConfig
from src.data.calculator import MultiplierCalculator
from src.data.fetcher import DataFetcher
from src.trading.okx_btc_usdt_trader import (
    InsufficientBalanceError,
    OKXBtcUsdtTrader,
    OrderAmountTooSmallError,
)

RUN_RESULT_PATH = Path("run_result.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_run_result() -> Dict[str, Any]:
    return {
        "run_time_utc": _utc_now(),
        "status": "failed",
        "failure_type": "exception",
        "ahr999": None,
        "btc_price": None,
        "investment_multiplier": None,
        "planned_invest_usdt": 0.0,
        "executed_invest_usdt": 0.0,
        "executed_btc_amount": 0.0,
        "error_message": "",
    }


def _write_run_result(run_result: Dict[str, Any]) -> None:
    RUN_RESULT_PATH.write_text(
        json.dumps(run_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[INFO] Wrote run result: {RUN_RESULT_PATH}")


def _fail(run_result: Dict[str, Any], stage: str, exc: Exception, failure_type: str = "exception") -> int:
    run_result["status"] = "failed"
    run_result["failure_type"] = failure_type
    run_result["error_message"] = f"{stage} failed: {exc}"
    print(f"[ERROR] {run_result['error_message']}")
    print("[ERROR] Traceback:")
    traceback.print_exc()
    return 1


def main() -> int:
    run_result = _build_run_result()

    try:
        app_config = AppConfig.from_env()

        fetcher = DataFetcher(app_config.data)
        data = fetcher.get_data()
        if data.get("Ahr999") is None or data.get("current_price") is None:
            raise ValueError("Data is not available")

        run_result["ahr999"] = _to_float(data["Ahr999"])
        run_result["btc_price"] = _to_float(data["current_price"])

        calculator = MultiplierCalculator(
            max_multiplier=app_config.trading.max_multiplier,
            min_multiplier=app_config.trading.min_multiplier,
        )
        investment_multiplier = calculator.calculate_daily_investment_multiplier(
            float(data["Ahr999"])
        )
        planned_invest = app_config.trading.base_investment_amount * investment_multiplier

        run_result["investment_multiplier"] = float(investment_multiplier)
        run_result["planned_invest_usdt"] = float(planned_invest)

        print(
            f'[INFO] Ahr999: {data["Ahr999"]} Investment amount: {planned_invest} current price: ${data["current_price"]}'
        )

        if planned_invest <= 0:
            run_result["status"] = "success"
            run_result["failure_type"] = "none"
            run_result["error_message"] = ""
            print("[INFO] Planned investment is 0, skip placing order.")
            return 0

        trader = OKXBtcUsdtTrader(app_config.okx, app_config.trading)
        trade_result = trader.buy_spot_btc_with_usdt(planned_invest)
        run_result["executed_invest_usdt"] = float(trade_result.get("spend_usdt", planned_invest))
        run_result["executed_btc_amount"] = float(trade_result.get("filled_btc") or 0.0)
        run_result["status"] = "success"
        run_result["failure_type"] = "none"
        run_result["error_message"] = ""
        return 0

    except InsufficientBalanceError as exc:
        print(
            "[ERROR] Place trade order failed: insufficient USDT balance. "
            "Please top up USDT or reduce BASE_INVESTMENT_AMOUNT."
        )
        exit_code = _fail(
            run_result,
            "Place trade order",
            exc,
            failure_type="insufficient_balance",
        )
    except OrderAmountTooSmallError as exc:
        print(
            "[ERROR] Place trade order failed: amount is below OKX minimum order requirement. "
            "Please increase BASE_INVESTMENT_AMOUNT or MIN_MULTIPLIER."
        )
        exit_code = _fail(
            run_result,
            "Place trade order",
            exc,
            failure_type="order_amount_too_small",
        )
    except Exception as exc:
        exit_code = _fail(run_result, "DCA run", exc)
    finally:
        _write_run_result(run_result)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
