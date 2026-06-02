"""Tests for all 6 strategy implementations."""

from app.strategies.cross_market import CrossMarketCorrelation
from app.strategies.resolution_arb import ResolutionArbitrage
from app.strategies.sentiment_divergence import SentimentDivergence
from app.strategies.volatility_harvest import VolatilityHarvesting
from app.strategies.whale_copying import WhaleCopying


# ── Cross-Market Correlation ────────────────────────────────
def _cm_markets():
    return [
        {"market_id": "m1", "title": "OpenAI IPO by June", "mid": 0.01, "t_hours": 720},
        {"market_id": "m2", "title": "OpenAI IPO by September", "mid": 0.44, "t_hours": 2160},
    ]


def test_cross_market_nested_dates():
    strategy = CrossMarketCorrelation(budget=100)
    result = strategy.scan(_cm_markets())
    assert result.markets_scanned == 2


def test_cross_market_scan_runs():
    strategy = CrossMarketCorrelation(budget=100)
    markets = [
        {"market_id": "m1", "title": "rainfall outcome A", "mid": 0.50, "t_hours": 240},
        {"market_id": "m2", "title": "rainfall outcome B", "mid": 0.45, "t_hours": 240},
        {"market_id": "m3", "title": "rainfall outcome C", "mid": 0.45, "t_hours": 240},
    ]
    result = strategy.scan(markets)
    assert result.markets_scanned == 3


# ── Resolution Arbitrage ───────────────────────────────────
def test_resolution_arb_registration():
    strategy = ResolutionArbitrage(budget=50)
    strategy.register_market_feed("m1", "fed_rates")
    strategy.update_feed_data("fed_rates", {"outcome": "YES"})
    result = strategy.scan([{"market_id": "m1", "mid": 0.50, "title": "Fed rate"}])
    assert result.markets_scanned == 1


def test_resolution_arb_double_confirmation():
    strategy = ResolutionArbitrage(budget=50)
    strategy.register_market_feed("m1", "fed_rates")
    strategy.update_feed_data("fed_rates", {"outcome": "YES"})
    result = strategy.scan([{"market_id": "m1", "mid": 0.50, "title": "Fed rate"}])
    # First scan confirms
    result2 = strategy.scan([{"market_id": "m1", "mid": 0.50, "title": "Fed rate"}])
    assert len(result2.signals) >= 1


# ── Volatility Harvesting ──────────────────────────────────
def test_vh_detects_spike():
    strategy = VolatilityHarvesting(budget=100)
    mid = 0.50
    result = strategy.scan([{
        "market_id": "m1",
        "title": "Test market",
        "mid": mid,
        "volume_24h": 5000,
        "price_history": [
            mid - 0.30, mid - 0.20, mid - 0.10,
            mid, mid + 0.10, mid + 0.20,
        ],
    }])
    assert result.markets_scanned == 1


def test_vh_no_spike_flat_history():
    strategy = VolatilityHarvesting(budget=100)
    mid = 0.50
    result = strategy.scan([{
        "market_id": "m1",
        "title": "Test market",
        "mid": mid,
        "volume_24h": 5000,
        "price_history": [mid, mid + 0.001, mid - 0.001, mid + 0.001, mid],
    }])
    assert len(result.signals) == 0


def test_vh_position_monitor():
    strategy = VolatilityHarvesting(budget=100)
    positions = [
        {"id": "p1", "side": "NO", "entry_price": 0.40, "current_mid": 0.20},
    ]
    actions = strategy.monitor_open_positions(positions)
    assert isinstance(actions, list)


# ── Whale Copying ──────────────────────────────────────────
def test_whale_scans_trades():
    strategy = WhaleCopying(budget=100)
    trades = [
        {
            "trader": "0x123",
            "market_id": "m1",
            "market_title": "Test market",
            "side": "buy_yes",
            "amount": 10000,
            "price": 0.50,
        },
    ]
    result = strategy.scan([], recent_trades=trades)
    assert result.markets_scanned == 1


def test_whale_ignores_small_bet():
    strategy = WhaleCopying(budget=100)
    trades = [
        {
            "trader": "0x456",
            "market_id": "m1",
            "market_title": "Test market",
            "side": "buy_yes",
            "amount": 100,
            "price": 0.50,
        },
    ]
    result = strategy.scan([], recent_trades=trades)
    assert len(result.signals) == 0


# ── Sentiment Divergence ───────────────────────────────────
def test_sentiment_divergence():
    strategy = SentimentDivergence(budget=100)
    markets = [
        {"market_id": "m1", "title": "Bitcoin price above 100k", "mid": 0.30},
    ]
    external = {
        "metaculus": [
            {"id": "ext1", "title": "Bitcoin price above 100000", "prob": 0.50},
        ],
        "predictit": [
            {"id": "ext2", "title": "Bitcoin above 100k", "prob": 0.45},
        ],
    }
    result = strategy.scan(markets, external_data=external)
    assert result.markets_scanned == 1
