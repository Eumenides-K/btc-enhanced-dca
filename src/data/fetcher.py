"""Data fetching module for BTC price and on-chain data."""

import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from scipy import stats

from src.config.settings import DataConfig

GENESIS = 1230940800

class DataFetcher:
    """Data fetching module for BTC data."""

    def __init__(self, config: DataConfig):
        """Initialize data fetcher with configuration."""
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "btc-enhanced-dca/1.0",
                "Accept": "application/json",
            }
        )

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make HTTP request with retry logic."""
        last_exception: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.request_timeout,
                )
                response.raise_for_status()

                # Check if response is actually JSON
                content_type = response.headers.get('content-type', '')
                if 'application/json' not in content_type:
                    print(f"[WARN] Unexpected content type from {url}: {content_type}")
                    # Try to get response text for debugging
                    response_text = response.text[:200]  # Limit log size
                    print(f"[ERROR] Response content preview: {response_text}")
                    raise ValueError(f"Expected JSON response, got {content_type}")

                return response.json()

            except requests.RequestException as e:
                last_exception = e
                print(f"[WARN] Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff with jitter
                    sleep_time = (2 ** attempt) + (attempt * 0.5)
                    print(f"[INFO] Retrying in {sleep_time:.1f} seconds...")
                    time.sleep(sleep_time)
                else:
                    break
            except ValueError as e:
                last_exception = e
                # JSON parsing error
                print(f"[WARN] JSON parsing failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff with jitter
                    sleep_time = (2 ** attempt) + (attempt * 0.5)
                    print(f"[INFO] Retrying in {sleep_time:.1f} seconds...")
                    time.sleep(sleep_time)
                else:
                    break

        raise RuntimeError(f"Failed request after retries: {url}") from last_exception

    def _fetch_first_success(
        self,
        providers: List[Tuple[str, Callable[[], Any]]],
        action: str,
    ) -> Any:
        last_exception: Optional[Exception] = None
        for provider_name, provider in providers:
            try:
                print(f"[INFO] Attempting to fetch {action} from {provider_name}")
                result = provider()
                print(f"[INFO] Successfully fetched {action} from {provider_name}")
                return result
            except Exception as e:
                last_exception = e
                print(f"[WARN] Failed to fetch {action} from {provider_name}: {e}")
                print("[INFO] Trying next exchange...")

        raise RuntimeError(f"All exchanges failed to fetch {action}") from last_exception

    def _fetch_okx_current_price(self) -> float:
        payload = self._make_request(
            "https://www.okx.com/api/v5/market/ticker",
            params={"instId": "BTC-USDT"},
        )
        data = payload.get("data") or []
        if not data:
            raise ValueError("OKX ticker response did not contain data")

        price = data[0].get("last")
        if price is None:
            raise ValueError("OKX ticker response did not contain last price")

        return float(price)

    def _fetch_kraken_current_price(self) -> float:
        payload = self._make_request(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": "XBTUSD"},
        )
        result = payload.get("result") or {}
        ticker = next((value for key, value in result.items() if key != "last"), None)
        if not ticker:
            raise ValueError("Kraken ticker response did not contain market data")

        close = ticker.get("c") or []
        if not close:
            raise ValueError("Kraken ticker response did not contain close price")

        return float(close[0])

    @staticmethod
    def _normalize_ohlcv_rows(rows: List[List[Any]]) -> List[List[float]]:
        normalized: List[List[float]] = []
        for row in rows:
            if len(row) < 6:
                continue
            normalized.append(
                [
                    int(float(row[0])),
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(row[5]),
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                ]
            )

        normalized.sort(key=lambda item: item[0])
        return normalized

    def _fetch_okx_price_history(self) -> List[List[float]]:
        payload = self._make_request(
            "https://www.okx.com/api/v5/market/history-candles",
            params={
                "instId": "BTC-USDT",
                "bar": "1Dutc",
                "limit": 200,
            },
        )
        rows = payload.get("data") or []
        if not rows:
            raise ValueError("OKX history response did not contain candles")

        return self._normalize_ohlcv_rows(rows)

    def _fetch_kraken_price_history(self) -> List[List[float]]:
        payload = self._make_request(
            "https://api.kraken.com/0/public/OHLC",
            params={"pair": "XBTUSD", "interval": 1440},
        )
        result = payload.get("result") or {}
        rows = next((value for key, value in result.items() if key != "last"), None)
        if not rows:
            raise ValueError("Kraken OHLC response did not contain candles")

        normalized_rows = self._normalize_ohlcv_rows(rows)
        if len(normalized_rows) > 200:
            normalized_rows = normalized_rows[-200:]
        return normalized_rows

    def _get_btc_price_history(self):
        """Get BTC price history from OKX first, fallback to Kraken."""
        return self._fetch_first_success(
            [
                ("OKX", self._fetch_okx_price_history),
                ("Kraken", self._fetch_kraken_price_history),
            ],
            "BTC price history",
        )

    def _get_current_btc_price(self):
        """Get current BTC price from OKX first, fallback to Kraken."""
        price = self._fetch_first_success(
            [
                ("OKX", self._fetch_okx_current_price),
                ("Kraken", self._fetch_kraken_current_price),
            ],
            "current BTC price",
        )
        print(f"[INFO] Current BTC price: ${price}")
        return float(price)

    def _calculate_btc_ahr999(self):
        """
        Calculate Ahr999 for a given list of BTC price data.
        ahr999 = (bitcoin_price / 200_day_dca_cost) * (bitcoin_price / exponential_growth_valuation)
        """
        klines_data = self._get_btc_price_history()

        if not klines_data or len(klines_data) < 200:
            raise ValueError("Not enough data for AHR999 calculation")

        try:
            low_prices = [float(kline[3]) for kline in klines_data]
            close_prices = [float(kline[4]) for kline in klines_data]
            current_price = close_prices[-1]

            # 200-day DCA cost
            investment_cost_200d = stats.gmean(low_prices)

            # days from genesis
            days = (int(time.time() * 1000) / 1000 - GENESIS) / (24 * 60 * 60)

            # exponential growth valuation
            growth_valuation = 10 ** (5.84 * math.log(days, 10) - 17.01)

            # calculating Ahr999
            ahr999 = (current_price / investment_cost_200d) * (current_price / growth_valuation)

            return ahr999
        except Exception as e:
            raise RuntimeError("Error calculating Ahr999") from e

    def _display_data(self, data: dict):
        """Display all data from fetcher."""
        print(f"Current BTC Price: ${data['current_price']}")
        print(f"Ahr999: {data['Ahr999']}")

    def get_data(self):
        """Get all data from fetcher."""
        cur_price = self._get_current_btc_price()
        ahr999 = self._calculate_btc_ahr999()
        data = {
            "current_price": cur_price,
            "Ahr999": ahr999
        }
        self._display_data(data)
        return data


if __name__ == "__main__":
    from src.config.settings import AppConfig
    config = AppConfig.from_env()
    fetcher = DataFetcher(config.data)
    fetcher.get_data()
