from app.backtest.metrics import max_drawdown, profit_factor, sharpe, win_rate


def test_max_drawdown():
    assert max_drawdown([100, 120, 90, 110]) == (120 - 90) / 120


def test_max_drawdown_monotonic_up():
    assert max_drawdown([100, 110, 120]) == 0.0


def test_win_rate():
    assert win_rate([1, -1, 2, -3]) == 0.5


def test_profit_factor():
    assert profit_factor([2, -1]) == 2.0


def test_sharpe_zero_for_constant():
    assert sharpe([0.0, 0.0, 0.0]) == 0.0
