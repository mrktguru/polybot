from app.strategies.mm.config import MMConfig
from app.strategies.mm.selector import MarketSelector


def _market(**over):
    base = {
        "market_id": "m1",
        "best_bid": 0.45,
        "best_ask": 0.55,
        "mid": 0.50,
        "volume_24h": 2000,
        "t_hours": 240,  # 10 days
        "sigma": 0.03,
        "max_jump_1h": 0.0,
        "orderbook_depth": 10,
        "category": "politics",
    }
    base.update(over)
    return base


def test_score_rejects_narrow_spread():
    sel = MarketSelector(MMConfig())
    assert sel.score(_market(best_bid=0.49, best_ask=0.50)) is None


def test_score_rejects_kill_zone():
    sel = MarketSelector(MMConfig())
    assert sel.score(_market(t_hours=10)) is None


def test_score_reasonable_market_positive():
    sel = MarketSelector(MMConfig())
    s = sel.score(_market())
    assert s is not None and s > 0


def test_excluded_category_penalized():
    sel = MarketSelector(MMConfig())
    normal = sel.score(_market(category="politics"))
    excluded = sel.score(_market(category="sports_live"))
    assert excluded < normal


def test_maker_reward_bonus_increases_score():
    sel = MarketSelector(MMConfig())
    base = sel.score(_market())
    boosted = sel.score(_market(maker_reward_score=1.0))
    assert boosted > base


def test_select_caps_to_max_active():
    cfg = MMConfig(max_active_markets=2)
    sel = MarketSelector(cfg)
    markets = [_market(market_id=f"m{i}") for i in range(5)]
    selected = sel.select(markets)
    assert len(selected) <= 2
