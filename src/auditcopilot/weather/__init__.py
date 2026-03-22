"""Weather package exports."""

__all__ = [
    "DemoMonthlyWeatherProvider",
    "OpenMeteoWeatherProvider",
    "WeatherProvider",
    "build_monthly_weather_dataframe",
    "calculate_cdd",
    "calculate_hdd",
]


def __getattr__(name: str):
    if name in {"calculate_cdd", "calculate_hdd"}:
        from auditcopilot.weather.degree_days import calculate_cdd, calculate_hdd

        return {
            "calculate_cdd": calculate_cdd,
            "calculate_hdd": calculate_hdd,
        }[name]

    if name in {"DemoMonthlyWeatherProvider", "OpenMeteoWeatherProvider", "WeatherProvider"}:
        from auditcopilot.weather.providers import (
            DemoMonthlyWeatherProvider,
            OpenMeteoWeatherProvider,
            WeatherProvider,
        )

        return {
            "DemoMonthlyWeatherProvider": DemoMonthlyWeatherProvider,
            "OpenMeteoWeatherProvider": OpenMeteoWeatherProvider,
            "WeatherProvider": WeatherProvider,
        }[name]

    if name == "build_monthly_weather_dataframe":
        from auditcopilot.weather.monthly import build_monthly_weather_dataframe

        return build_monthly_weather_dataframe

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
