import traceback

from data.calculator import MultiplierCalculator
from data.fetcher import DataFetcher
from trading.okx_btc_usdt_trader import OKXBtcUsdtTrader, InsufficientBalanceError
from config.settings import AppConfig


def _print_exception_and_exit(stage: str, exc: Exception) -> None:
    """Print exception details and exit immediately."""
    print(f"[ERROR] {stage} failed: {exc}")
    print("[ERROR] Traceback:")
    traceback.print_exc()
    raise SystemExit(1)


def main():
    try:
        app_config = AppConfig.from_env()
    except Exception as exc:
        _print_exception_and_exit("Load app config", exc)

    try:
        fetcher = DataFetcher(app_config.data)
        data = fetcher.get_data()
        if not data.get("Ahr999") or not data.get("current_price"):
            raise ValueError("Data is not available")
    except Exception as exc:
        _print_exception_and_exit("Fetch indicator data", exc)

    try:
        calculator = MultiplierCalculator(
            max_multiplier=app_config.trading.max_multiplier,
            min_multiplier=app_config.trading.min_multiplier
        )
        investment_multiplier = calculator.calculate_daily_investment_multiplier(
            data["Ahr999"]
        )
        invest_amount = app_config.trading.base_investment_amount * investment_multiplier
        print(
            f'[INFO] Ahr999: {data["Ahr999"]} Investment amount: {invest_amount} current price: ${data["current_price"]}'
        )
    except Exception as exc:
        _print_exception_and_exit("Calculate investment multiplier", exc)

    try:
        trader = OKXBtcUsdtTrader(app_config.okx, app_config.trading)
        trader.buy_spot_btc_with_usdt(invest_amount)
    except InsufficientBalanceError:
        print(
            "[ERROR] Place trade order failed: insufficient USDT balance. "
            "Please top up USDT or reduce BASE_INVESTMENT_AMOUNT."
        )
        raise SystemExit(1)
    except Exception as exc:
        _print_exception_and_exit("Place trade order", exc)


if __name__ == '__main__':
    main()
