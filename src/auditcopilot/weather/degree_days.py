"""Heating and cooling degree day helper functions."""


def calculate_hdd(avg_temp: float, base_temp: float = 65.0) -> float:
    """Return monthly heating degree days from an average temperature."""
    return max(base_temp - float(avg_temp), 0.0)


def calculate_cdd(avg_temp: float, base_temp: float = 65.0) -> float:
    """Return monthly cooling degree days from an average temperature."""
    return max(float(avg_temp) - base_temp, 0.0)
