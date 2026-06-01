from app.risk.allocator import BASE_WEIGHTS, CapitalAllocator


def test_static_allocation_sums_to_capital():
    alloc = CapitalAllocator(total_capital=500)
    budgets = alloc.allocate()
    total = sum(budgets.values())
    assert abs(total - 500) < 1.0


def test_market_making_is_largest_budget():
    budgets = CapitalAllocator(total_capital=500).allocate()
    mm = budgets["market_making"]
    others = [v for k, v in budgets.items() if k not in ("market_making", "reserve")]
    assert all(mm >= o for o in others)


def test_performance_tilt_respects_bounds():
    alloc = CapitalAllocator(total_capital=1000, smoothing=1.0)
    # Extreme performance tilt toward whale_copying.
    budgets = alloc.allocate(performance={"whale_copying": 100.0})
    share = budgets["whale_copying"] / 1000
    lo, hi = 0.0, 0.15
    assert lo <= share <= hi + 1e-6


def test_reserve_preserved():
    budgets = CapitalAllocator(total_capital=1000).allocate(
        performance={"market_making": 5.0}
    )
    assert abs(budgets["reserve"] - BASE_WEIGHTS["reserve"] * 1000) < 1.0
