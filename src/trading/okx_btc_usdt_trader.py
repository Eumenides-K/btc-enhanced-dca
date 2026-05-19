"""OKX spot BTC/USDT trader.

Only one public capability is exposed:
buy BTC spot with a specified USDT amount.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

import ccxt
from ccxt.base.errors import InsufficientFunds, InvalidOrder
from ccxt.base.precise import Precise

from src.config.settings import OKXConfig, TradingConfig


class InsufficientBalanceError(RuntimeError):
    """Raised when exchange balance is insufficient for order placement."""


class OrderAmountTooSmallError(RuntimeError):
    """Raised when order size is below exchange minimum requirements."""


class PatchedOKXExchange(ccxt.okx):
    """OKX exchange client with a guard for malformed instrument metadata."""

    @staticmethod
    def _pick_symbol_part(parts: list[str], index: int) -> str:
        if index >= len(parts):
            return ""
        return parts[index] or ""

    @staticmethod
    def _first_non_empty(*values: Any) -> str:
        for value in values:
            if value:
                return str(value)
        return ""

    @staticmethod
    def _infer_exp_time_from_inst_id(inst_id: str) -> Optional[str]:
        if not inst_id:
            return None

        for part in inst_id.split("-"):
            if len(part) != 6 or not part.isdigit():
                continue
            try:
                expiry_date = datetime.datetime.strptime(part, "%y%m%d").replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                continue
            return str(int(expiry_date.timestamp() * 1000))

        return None

    def parse_market(self, market: dict) -> dict:
        normalized_market = dict(market)
        instrument_type = (self.safe_string_lower(normalized_market, "instType") or "")
        is_contract = instrument_type in {"swap", "futures", "future", "option"}
        needs_expiry = instrument_type in {"futures", "future", "option"}
        base_ccy = normalized_market.get("baseCcy") or ""
        quote_ccy = normalized_market.get("quoteCcy") or ""
        settle_ccy = normalized_market.get("settleCcy") or ""

        underlying = self.safe_string(normalized_market, "uly", "") or ""
        if underlying and (not base_ccy or not quote_ccy):
            underlying_parts = underlying.split("-")
            if not base_ccy:
                base_ccy = self._pick_symbol_part(underlying_parts, 0)
            if not quote_ccy:
                quote_ccy = self._pick_symbol_part(underlying_parts, 1)

        inst_id = self.safe_string(normalized_market, "instId", "") or ""
        if inst_id and (not base_ccy or not quote_ccy):
            inst_parts = inst_id.split("-")
            if not base_ccy:
                base_ccy = self._pick_symbol_part(inst_parts, 0)
            if not quote_ccy:
                quote_ccy = self._pick_symbol_part(inst_parts, 1)

        if is_contract and not settle_ccy:
            settle_ccy = self._first_non_empty(
                normalized_market.get("ctValCcy"),
                quote_ccy,
                base_ccy,
            )

        if needs_expiry and self.safe_integer(normalized_market, "expTime") is None:
            inferred_exp_time = self._infer_exp_time_from_inst_id(inst_id)
            if inferred_exp_time is not None:
                normalized_market["expTime"] = inferred_exp_time

        normalized_market["baseCcy"] = base_ccy
        normalized_market["quoteCcy"] = quote_ccy
        normalized_market["settleCcy"] = settle_ccy
        if base_ccy and quote_ccy:
            normalized_market["uly"] = f"{base_ccy}-{quote_ccy}"
        market_id = self.safe_string(normalized_market, "instId")
        market_type = instrument_type
        if market_type == "futures":
            market_type = "future"

        spot = market_type == "spot"
        future = market_type == "future"
        swap = market_type == "swap"
        option = market_type == "option"
        contract = swap or future or option

        base_id = self.safe_string(normalized_market, "baseCcy", "")
        quote_id = self.safe_string(normalized_market, "quoteCcy", "")
        settle_id = self.safe_string(normalized_market, "settleCcy")
        settle = self.safe_currency_code(settle_id)
        underlying = self.safe_string(normalized_market, "uly")
        if (underlying is not None) and not spot:
            parts = underlying.split("-")
            base_id = self.safe_string(parts, 0, base_id)
            quote_id = self.safe_string(parts, 1, quote_id)
        if ((base_id == "") or (quote_id == "")) and spot:
            inst_id = self.safe_string(normalized_market, "instId", "")
            parts = inst_id.split("-")
            base_id = self.safe_string(parts, 0, base_id)
            quote_id = self.safe_string(parts, 1, quote_id)

        base = self.safe_currency_code(base_id)
        quote = self.safe_currency_code(quote_id)
        symbol = base + "/" + quote
        if base == "" or quote == "":
            symbol = market_id

        expiry = None
        strike_price = None
        option_type = None
        if contract:
            if settle is not None:
                symbol = symbol + ":" + settle
            expiry = self.safe_integer(normalized_market, "expTime")
            if future and expiry is not None:
                symbol = symbol + "-" + self.yymmdd(expiry)
            elif option:
                strike_price = self.safe_string(normalized_market, "stk")
                option_type = self.safe_string(normalized_market, "optType")
                if expiry is not None:
                    symbol = symbol + "-" + self.yymmdd(expiry) + "-" + strike_price + "-" + option_type
                option_type = "put" if option_type == "P" else "call"

        fees = self.safe_dict_2(self.fees, market_type, "trading", {})
        max_leverage = self.safe_string(normalized_market, "lever", "1")
        max_leverage = Precise.string_max(max_leverage, "1")
        max_spot_cost = self.safe_number(normalized_market, "maxMktSz")
        status = self.safe_string(normalized_market, "state")
        inst_id_code = self.safe_integer(normalized_market, "instIdCode")

        return self.extend(
            fees,
            {
                "id": market_id,
                "instIdCode": inst_id_code,
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "settle": settle,
                "baseId": base_id,
                "quoteId": quote_id,
                "settleId": settle_id,
                "type": market_type,
                "spot": spot,
                "margin": spot and (Precise.string_gt(max_leverage, "1")),
                "swap": swap,
                "future": future,
                "option": option,
                "active": status == "live",
                "contract": contract,
                "linear": (quote_id == settle_id) if contract else None,
                "inverse": (base_id == settle_id) if contract else None,
                "contractSize": self.safe_number(normalized_market, "ctVal") if contract else None,
                "expiry": expiry,
                "expiryDatetime": self.iso8601(expiry),
                "strike": self.parse_number(strike_price),
                "optionType": option_type,
                "created": self.safe_integer_2(normalized_market, "contTdSwTime", "listTime"),
                "precision": {
                    "amount": self.safe_number(normalized_market, "lotSz"),
                    "price": self.safe_number(normalized_market, "tickSz"),
                },
                "limits": {
                    "leverage": {
                        "min": self.parse_number("1"),
                        "max": self.parse_number(max_leverage),
                    },
                    "amount": {
                        "min": self.safe_number(normalized_market, "minSz"),
                        "max": None,
                    },
                    "price": {
                        "min": None,
                        "max": None,
                    },
                    "cost": {
                        "min": None,
                        "max": None if contract else max_spot_cost,
                    },
                },
                "info": normalized_market,
            },
        )


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

    def _build_exchange(self) -> PatchedOKXExchange:
        """Initialize authenticated OKX client."""
        exchange = PatchedOKXExchange(
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
        except InvalidOrder as e:
            message = str(e)
            if "51020" in message or "minimum order amount" in message.lower():
                raise OrderAmountTooSmallError(
                    f"Order amount is below OKX minimum: symbol={self.symbol}, "
                    f"requested_usdt={float(usdt_amount):.8f}, detail={message}"
                ) from e
            raise RuntimeError(f"Invalid order on OKX: {self.symbol}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to place market buy order on OKX: {self.symbol}") from e

    def _get_realtime_min_order_usdt(self) -> Dict[str, float]:
        """Get realtime minimum order notional in USDT from exchange metadata and ticker."""
        self.exchange.load_markets()
        market = self.exchange.market(self.symbol)
        market_limits = market.get("limits", {})
        market_info = market.get("info", {})

        min_amount_btc = self._to_float(market_limits.get("amount", {}).get("min"))
        if min_amount_btc is None:
            min_amount_btc = self._to_float(market_info.get("minSz"))
        if min_amount_btc is None or min_amount_btc <= 0:
            raise RuntimeError(f"Unable to resolve minimum order amount for {self.symbol}")

        ticker = self.exchange.fetch_ticker(self.symbol)
        reference_price = (
            self._to_float(ticker.get("last"))
            or self._to_float(ticker.get("ask"))
            or self._to_float(ticker.get("bid"))
        )
        if reference_price is None or reference_price <= 0:
            raise RuntimeError(f"Unable to resolve reference price for {self.symbol}")

        min_notional_usdt = min_amount_btc * reference_price
        return {
            "min_amount_btc": float(min_amount_btc),
            "reference_price_usdt": float(reference_price),
            "min_notional_usdt": float(min_notional_usdt),
        }

    def _validate_min_order_notional(self, usdt_amount: float) -> None:
        min_order = self._get_realtime_min_order_usdt()
        min_notional_usdt = min_order["min_notional_usdt"]
        print(
            "[INFO] Realtime minimum order check: "
            f"symbol={self.symbol}, requested_usdt={float(usdt_amount):.8f}, "
            f"min_notional_usdt={min_notional_usdt:.8f}, "
            f"min_amount_btc={min_order['min_amount_btc']:.8f}, "
            f"reference_price_usdt={min_order['reference_price_usdt']:.8f}"
        )
        if usdt_amount < min_notional_usdt:
            raise OrderAmountTooSmallError(
                "Order amount is below realtime OKX minimum: "
                f"symbol={self.symbol}, requested_usdt={float(usdt_amount):.8f}, "
                f"min_notional_usdt={min_notional_usdt:.8f}, "
                f"min_amount_btc={min_order['min_amount_btc']:.8f}, "
                f"reference_price_usdt={min_order['reference_price_usdt']:.8f}"
            )

    def buy_spot_btc_with_usdt(self, usdt_amount: float) -> Dict[str, Any]:
        """Buy BTC/USDT spot with the specified USDT amount"""
        self._validate_usdt_amount(usdt_amount)
        self._validate_min_order_notional(usdt_amount)

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
