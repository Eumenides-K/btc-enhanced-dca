"""Configuration management module."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class OKXConfig:
    """OKX API configuration."""
    api_key: str
    secret_key: str
    passphrase: str
    base_url: str = "https://www.okx.com"


@dataclass
class TradingConfig:
    """Trading parameters configuration."""
    base_investment_amount: float = os.getenv("BASE_INVESTMENT_AMOUNT", 10.0) # Base investment in USDT
    min_multiplier: float = os.getenv("MIN_MULTIPLIER", 0.1) # Minimum investment multiplier
    max_multiplier: float = os.getenv("MAX_MULTIPLIER", 4.0)  # Maximum investment multiplier
    symbol: str = "BTC/USDT"
    order_type: str = "market"
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class DataConfig:
    """Data source configuration."""
    request_timeout: int = 30
    max_retries: int = 3


@dataclass
class AppConfig:
    """Main application configuration."""
    okx: OKXConfig
    trading: TradingConfig
    data: DataConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        try:
            okx_config = OKXConfig(
                api_key=os.getenv("OKX_API_KEY", ""),
                secret_key=os.getenv("OKX_SECRET_KEY", ""),
                passphrase=os.getenv("OKX_PASSPHRASE", "")
            )

            trading_config = TradingConfig(
                base_investment_amount=float(os.getenv("BASE_INVESTMENT_AMOUNT", "10.0")),
                min_multiplier=float(os.getenv("MIN_MULTIPLIER", "0.1")),
                max_multiplier=float(os.getenv("MAX_MULTIPLIER", "4.0"))
            )

            data_config = DataConfig()
        except ValueError as e:
            raise ValueError(f"Invalid environment variable value: {e}") from e

        return cls(
            okx=okx_config,
            trading=trading_config,
            data=data_config
        )

