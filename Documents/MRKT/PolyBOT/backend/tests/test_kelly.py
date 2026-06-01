from app.risk.kelly import kelly_fraction, kelly_size


def test_kelly_zero_edge_returns_zero():
    # Fair price equals probability -> no edge -> no bet.
    assert kelly_fraction(p=0.5, price=0.5) == 0.0


def test_kelly_positive_edge():
    f = kelly_fraction(p=0.6, price=0.5)
    assert 0.0 < f <= 1.0


def test_kelly_negative_edge_clamped():
    assert kelly_fraction(p=0.3, price=0.5) == 0.0


def test_kelly_size_respects_cap():
    size = kelly_size(p=0.95, price=0.5, capital=500, fraction=1.0, max_pct=0.20)
    assert size <= 500 * 0.20


def test_kelly_size_fractional_reduces_size():
    full = kelly_size(p=0.7, price=0.5, capital=500, fraction=1.0, max_pct=1.0)
    frac = kelly_size(p=0.7, price=0.5, capital=500, fraction=0.33, max_pct=1.0)
    assert frac < full
