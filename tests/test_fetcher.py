from __future__ import annotations

from src.config.settings import DataConfig
from src.data.fetcher import DataFetcher


def test_get_current_btc_price_falls_back_to_kraken(monkeypatch) -> None:
    fetcher = DataFetcher(DataConfig())
    calls: list[str] = []

    def fake_request(url: str, params=None):
        calls.append(url)
        if "okx.com" in url:
            raise RuntimeError("okx unavailable")
        if "kraken.com" in url:
            return {
                "result": {
                    "XXBTZUSD": {
                        "c": ["61234.5", "1.0"],
                    },
                    "last": 1234567890,
                }
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(fetcher, "_make_request", fake_request)

    assert fetcher._get_current_btc_price() == 61234.5
    assert calls == [
        "https://www.okx.com/api/v5/market/ticker",
        "https://api.kraken.com/0/public/Ticker",
    ]


def test_get_btc_price_history_falls_back_and_truncates_to_200(monkeypatch) -> None:
    fetcher = DataFetcher(DataConfig())

    def fake_request(url: str, params=None):
        if "okx.com" in url:
            raise RuntimeError("okx unavailable")
        if "kraken.com" in url:
            rows = []
            for index in range(205):
                timestamp = 1_700_000_000 + index * 86_400
                rows.append(
                    [
                        timestamp,
                        str(100 + index),
                        str(110 + index),
                        str(90 + index),
                        str(105 + index),
                        str(1000 + index),
                        str(102 + index),
                        str(2000 + index),
                    ]
                )
            return {"result": {"XXBTZUSD": rows, "last": rows[-1][0]}}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(fetcher, "_make_request", fake_request)

    history = fetcher._get_btc_price_history()

    assert len(history) == 200
    assert history[0][0] == 1_700_432_000
    assert history[-1][0] == 1_717_625_600
    assert history[0][1:6] == [105.0, 115.0, 95.0, 110.0, 1005.0]
    assert history[0][6:] == [0, 0, 0, 0, 0, 0]


def test_get_btc_price_history_normalizes_okx_descending_response(monkeypatch) -> None:
    fetcher = DataFetcher(DataConfig())

    def fake_request(url: str, params=None):
        if "okx.com" not in url:
            raise AssertionError(f"Unexpected URL: {url}")
        return {
            "data": [
                ["2000", "2", "3", "1", "2.5", "10"],
                ["1000", "1", "2", "0.5", "1.5", "8"],
            ]
        }

    monkeypatch.setattr(fetcher, "_make_request", fake_request)

    history = fetcher._get_btc_price_history()

    assert history == [
        [1000, 1.0, 2.0, 0.5, 1.5, 8.0, 0, 0, 0, 0, 0, 0],
        [2000, 2.0, 3.0, 1.0, 2.5, 10.0, 0, 0, 0, 0, 0, 0],
    ]
