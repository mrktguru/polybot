from app.strategies.mm.config import MMConfig
from app.strategies.mm.quoting import InventorySkewMM


def _mm() -> InventorySkewMM:
    return InventorySkewMM(MMConfig())


def test_kill_zone_cancels():
    q = _mm().compute_quotes(mid=0.5, q=0, sigma=0.03, t_hours=10)
    assert q.action == "cancel_all"
    assert q.reason == "kill_zone"


def test_inventory_max_cancels():
    cfg = MMConfig(q_max=10)
    q = InventorySkewMM(cfg).compute_quotes(mid=0.5, q=10, sigma=0.03, t_hours=240)
    assert q.action == "cancel_all"
    assert q.reason == "inventory_max"


def test_thin_book_cancels():
    q = _mm().compute_quotes(
        mid=0.5, q=0, sigma=0.03, t_hours=240, orderbook_depth=1
    )
    assert q.action == "cancel_all"
    assert q.reason == "thin_book"


def test_stale_book_cancels():
    q = _mm().compute_quotes(
        mid=0.5, q=0, sigma=0.03, t_hours=240, book_age_sec=999
    )
    assert q.action == "cancel_all"
    assert q.reason == "stale_book"


def test_valid_quote_has_spread_floor():
    cfg = MMConfig(adverse_premium=0.02, fee_per_share=0.0)
    q = InventorySkewMM(cfg).compute_quotes(mid=0.5, q=0, sigma=0.03, t_hours=240)
    assert q.action == "quote"
    assert q.bid is not None and q.ask is not None
    assert q.ask > q.bid
    # Half-spread should be at least the adverse premium floor.
    assert (q.ask - q.bid) / 2 >= 0.02 - 1e-6


def test_inventory_skews_reservation_down_when_long():
    mm = _mm()
    flat = mm.compute_quotes(mid=0.5, q=0, sigma=0.05, t_hours=240)
    long = mm.compute_quotes(mid=0.5, q=20, sigma=0.05, t_hours=240)
    assert long.reservation < flat.reservation


def test_quotes_changed_threshold():
    mm = _mm()
    q = mm.compute_quotes(mid=0.5, q=0, sigma=0.03, t_hours=240)
    # Same quotes -> no change.
    assert mm.quotes_changed(q.bid, q.ask, q) is False
    # Far-off previous quotes -> change.
    assert mm.quotes_changed(0.1, 0.9, q) is True
