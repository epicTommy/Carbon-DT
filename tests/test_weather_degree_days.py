from auditcopilot.weather.degree_days import calculate_cdd, calculate_hdd


def test_calculate_hdd_returns_positive_difference_below_base() -> None:
    assert calculate_hdd(40.0) == 25.0


def test_calculate_hdd_returns_zero_at_or_above_base() -> None:
    assert calculate_hdd(65.0) == 0.0
    assert calculate_hdd(72.0) == 0.0


def test_calculate_cdd_returns_positive_difference_above_base() -> None:
    assert calculate_cdd(78.0) == 13.0


def test_calculate_cdd_returns_zero_at_or_below_base() -> None:
    assert calculate_cdd(65.0) == 0.0
    assert calculate_cdd(50.0) == 0.0
