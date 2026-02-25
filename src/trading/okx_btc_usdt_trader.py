"""OKX spot BTC/USDT trader.

Only one public capability is exposed:
buy BTC spot with a specified USDT amount.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import ccxt
from ccxt.base.errors import InsufficientFunds

from src.config.settings import OKXConfig, TradingConfig


class InsufficientBalanceError(RuntimeError):
    """Raised when exchange balance is insufficient for order placement."""


class OKXBtcUsdtTrader:
    """Place BTC/USDT spot market buy orders on OKX by USDT cost."""

    def __init__(self, okx_config: OKXConfig, trading_config: TradingConfig):
        self.okx_config = okx_config
        self.trading_config = trading_config
        self.symbol = trading_config.symbol
        self._validate_credentials()
        self.exchange = self._build_exchange()

    def _validate_credentials(self) -> None:
        missing = []
        if not self.okx_config.api_key:
            missing.append("OKX_API_KEY")
        if not self.okx_config.secret_key:
            missing.append("OKX_SECRET_KEY")
        if not self.okx_config.passphrase:
            missing.append("OKX_PASSPHRASE")
        if missing:
            raise ValueError(f"Missing required OKX credentials: {', '.join(missing)}")

    def _build_exchange(self) -> ccxt.okx:
        """Initialize authenticated OKX client."""
        exchange = ccxt.okx(
            {
                "apiKey": self.okx_config.api_key,
                "secret": self.okx_config.secret_key,
                "password": self.okx_config.passphrase,
                "enableRateLimit": True,
            }
        )
        # Allow unified create_order(..., amount=<cost>) fallback usage if needed.
        exchange.options["createMarketBuyOrderRequiresPrice"] = False
        return exchange

    def _validate_usdt_amount(self, usdt_amount: float) -> None:
        if usdt_amount <= 0:
            raise ValueError("usdt_amount must be greater than 0")

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _place_market_buy_with_cost(self, usdt_amount: float) -> Dict[str, Any]:
        params = {"tdMode": "cash"}
        try:
            return self.exchange.create_market_buy_order_with_cost(self.symbol, usdt_amount, params)
        except AttributeError:
            # Fallback path for older CCXT versions.
            return self.exchange.create_order(self.symbol, "market", "buy", usdt_amount, None, params)
        except InsufficientFunds as e:
            raise InsufficientBalanceError(
                f"Insufficient funds for OKX market buy: symbol={self.symbol}, "
                f"requested_usdt={float(usdt_amount):.8f}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to place market buy order on OKX: {self.symbol}") from e

    def buy_spot_btc_with_usdt(self, usdt_amount: float) -> Dict[str, Any]:
        """Buy BTC/USDT spot with the specified USDT amount"""
        self._validate_usdt_amount(usdt_amount)

        order = self._place_market_buy_with_cost(usdt_amount)
        filled_btc = self._to_float(order.get("filled"))
        if filled_btc is None:
            filled_btc = self._to_float(order.get("amount"))

        avg_price = self._to_float(order.get("average"))
        order_cost = self._to_float(order.get("cost"))
        spend_usdt = order_cost if order_cost is not None else float(usdt_amount)
        if avg_price is None and filled_btc and filled_btc > 0 and spend_usdt is not None:
            avg_price = spend_usdt / filled_btc

        print(f"[INFO] Spot market buy order submitted: {order.get('id', 'unknown')}")
        return {
            "exchange": "okx",
            "symbol": self.symbol,
            "side": "buy",
            "type": "market",
            "spend_usdt": float(spend_usdt),
            "filled_btc": filled_btc,
            "avg_price": avg_price,
            "order": order,
        }


if __name__ == "__main__":
    from src.config.settings import AppConfig
    app_config = AppConfig.from_env()
    trader = OKXBtcUsdtTrader(app_config.okx, app_config.trading)
    print(trader.buy_spot_btc_with_usdt(app_config.trading.base_investment_amount))
