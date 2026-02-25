from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import src.main as main_module
from src.trading.okx_btc_usdt_trader import InsufficientBalanceError


def _read_run_result(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "run_result.json").read_text(encoding="utf-8"))


def test_main_writes_success_result_for_zero_investment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_module, "RUN_RESULT_PATH", tmp_path / "run_result.json")

    fake_config = SimpleNamespace(
        data=SimpleNamespace(),
        trading=SimpleNamespace(base_investment_amount=10.0, min_multiplier=0.1, max_multiplier=4.0),
        okx=SimpleNamespace(),
    )
    monkeypatch.setattr(main_module.AppConfig, "from_env", staticmethod(lambda: fake_config))

    class FakeFetcher:
        def __init__(self, _config):
            pass

        def get_data(self):
            return {"Ahr999": 1.4, "current_price": 50000.0}

    class FakeCalculator:
        def __init__(self, **_kwargs):
            pass

        def calculate_daily_investment_multiplier(self, _ahr999):
            return 0.0

    class FailIfCalledTrader:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("Trader should not be initialized for zero investment")

    monkeypatch.setattr(main_module, "DataFetcher", FakeFetcher)
    monkeypatch.setattr(main_module, "MultiplierCalculator", FakeCalculator)
    monkeypatch.setattr(main_module, "OKXBtcUsdtTrader", FailIfCalledTrader)

    assert main_module.main() == 0
    result = _read_run_result(tmp_path)
    assert result["status"] == "success"
    assert result["failure_type"] == "none"
    assert result["planned_invest_usdt"] == 0.0
    assert result["executed_invest_usdt"] == 0.0


def test_main_writes_insufficient_balance_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_module, "RUN_RESULT_PATH", tmp_path / "run_result.json")

    fake_config = SimpleNamespace(
        data=SimpleNamespace(),
        trading=SimpleNamespace(base_investment_amount=10.0, min_multiplier=0.1, max_multiplier=4.0),
        okx=SimpleNamespace(),
    )
    monkeypatch.setattr(main_module.AppConfig, "from_env", staticmethod(lambda: fake_config))

    class FakeFetcher:
        def __init__(self, _config):
            pass

        def get_data(self):
            return {"Ahr999": 0.9, "current_price": 50000.0}

    class FakeCalculator:
        def __init__(self, **_kwargs):
            pass

        def calculate_daily_investment_multiplier(self, _ahr999):
            return 1.0

    class FakeTrader:
        def __init__(self, *_args, **_kwargs):
            pass

        def buy_spot_btc_with_usdt(self, _amount):
            raise InsufficientBalanceError("insufficient")

    monkeypatch.setattr(main_module, "DataFetcher", FakeFetcher)
    monkeypatch.setattr(main_module, "MultiplierCalculator", FakeCalculator)
    monkeypatch.setattr(main_module, "OKXBtcUsdtTrader", FakeTrader)

    assert main_module.main() == 1
    result = _read_run_result(tmp_path)
    assert result["status"] == "failed"
    assert result["failure_type"] == "insufficient_balance"
    assert result["executed_invest_usdt"] == 0.0

