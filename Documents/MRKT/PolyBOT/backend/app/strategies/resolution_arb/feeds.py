"""Resolution Arbitrage data feeds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DataFeedConfig:
    name: str
    url: str
    poll_interval_sec: int
    keywords: list[str]
    category: str


FED_RATES = DataFeedConfig(
    name="fed_rates",
    url="https://www.federalreserve.gov/releases/h15/",
    poll_interval_sec=60,
    keywords=["federal funds rate", "fomc decision"],
    category="macro",
)

CDC_HEALTH = DataFeedConfig(
    name="cdc_health",
    url="https://data.cdc.gov/api/",
    poll_interval_sec=300,
    keywords=["confirmed case", "outbreak"],
    category="health",
)

CRYPTO_PRICES = DataFeedConfig(
    name="crypto_prices",
    url="wss://stream.binance.com/ws",
    poll_interval_sec=1,
    keywords=["BTC", "ETH", "XRP"],
    category="crypto",
)

SEC_FILINGS = DataFeedConfig(
    name="sec_filings",
    url="https://efts.sec.gov/LATEST/search-index?",
    poll_interval_sec=120,
    keywords=["S-1", "IPO", "initial public offering"],
    category="finance",
)

ALL_FEEDS: list[DataFeedConfig] = [FED_RATES, CDC_HEALTH, CRYPTO_PRICES, SEC_FILINGS]
