from __future__ import annotations

from src.config.settings import OKXConfig, TradingConfig
from src.trading.okx_btc_usdt_trader import OKXBtcUsdtTrader, PatchedOKXExchange


def test_patched_okx_parse_market_handles_missing_quote_from_malformed_underlying() -> None:
    exchange = PatchedOKXExchange()

    market = {
        "instId": "BTC-USDT-SWAP",
        "instType": "SWAP",
        "baseCcy": "",
        "quoteCcy": "",
        "settleCcy": "USDT",
        "uly": "BTC",
        "ctVal": "1",
        "lever": "",
        "lotSz": "1",
        "minSz": "1",
        "tickSz": "0.1",
        "state": "live",
    }

    parsed = exchange.parse_market(market)

    assert parsed["base"] == "BTC"
    assert parsed["quote"] == "USDT"
    assert parsed["symbol"] == "BTC/USDT:USDT"


def test_trader_builds_patched_okx_exchange() -> None:
    trader = OKXBtcUsdtTrader(
        OKXConfig(api_key="key", secret_key="secret", passphrase="pass"),
        TradingConfig(base_investment_amount=10.0, min_multiplier=0.1, max_multiplier=4.0),
    )

    assert isinstance(trader.exchange, PatchedOKXExchange)
