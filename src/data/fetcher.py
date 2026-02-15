"""Data fetching module for BTC price and on-chain data."""

import time
import math
from typing import Dict, Optional
import requests
import ccxt

from scipy import stats
from src.config.settings import DataConfig

GENESIS = 1230940800

class DataFetcher:
    """Data fetching module for BTC data."""

    def __init__(self, config: DataConfig):
        """Initialize data fetcher with configuration."""
        self.config = config
        self.session = requests.Session()
        self.session.timeout = config.request_timeout

        # Initialize OKX exchange (primary)
        self.okx = ccxt.okx({
            'timeout': config.request_timeout * 1000,  # ccxt uses milliseconds
            'enableRateLimit': True,
        })

        # Initialize Binance exchange (fallback)
        self.binance = ccxt.binance({
            'timeout': config.request_timeout * 1000,  # ccxt uses milliseconds
            'enableRateLimit': True,
        })

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make HTTP request with retry logic."""
        last_exception: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(url, params=params)
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

    def _get_btc_price_history(self):
        """Get BTC price history from OKX API first, fallback to Binance if OKX fails."""
        exchanges = [
            ('OKX', self.okx),
            ('Binance', self.binance)
        ]
        last_exception: Optional[Exception] = None

        for exchange_name, exchange in exchanges:
            try:
                print(f"[INFO] Attempting to fetch BTC price history from {exchange_name}")
                # OKX uses BTC-USDT, Binance uses BTC/USDT
                symbol = 'BTC-USDT' if exchange_name == 'OKX' else 'BTC/USDT'
                ohlcv = exchange.fetch_ohlcv(symbol, '1d', limit=200)

                klines_data = []
                for candle in ohlcv:
                    klines_data.append([
                        candle[0],  # timestamp
                        candle[1],  # open
                        candle[2],  # high
                        candle[3],  # low
                        candle[4],  # close
                        candle[5],  # volume
                        # Add empty values for remaining fields to match original format
                        0, 0, 0, 0, 0, 0
                    ])

                print(f"[INFO] Successfully fetched {len(klines_data)} price records from {exchange_name}")
                return klines_data

            except Exception as e:
                last_exception = e
                print(f"[WARN] Failed to fetch BTC price history from {exchange_name}: {e}")
                print("[INFO] Trying next API...")

        raise RuntimeError("All exchanges failed to fetch BTC price history") from last_exception

    def _get_current_btc_price(self):
        """Get current BTC price from OKX API first, fallback to Binance if OKX fails."""
        exchanges = [
            ('OKX', self.okx),
            ('Binance', self.binance)
        ]
        last_exception: Optional[Exception] = None

        for exchange_name, exchange in exchanges:
            try:
                print(f"[INFO] Attempting to fetch current BTC price from {exchange_name}")
                # OKX uses BTC-USDT, Binance uses BTC/USDT
                symbol = 'BTC-USDT' if exchange_name == 'OKX' else 'BTC/USDT'
                ticker = exchange.fetch_ticker(symbol)
                price = float(ticker['last'])

                print(f"[INFO] Successfully fetched BTC price from {exchange_name}: ${price}")
                return price

            except Exception as e:
                last_exception = e
                print(f"[WARN] Failed to fetch current BTC price from {exchange_name}: {e}")
                print("[INFO] Trying next exchange...")

        raise RuntimeError("All exchanges failed to fetch current BTC price") from last_exception

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
