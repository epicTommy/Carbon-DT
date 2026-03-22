from pathlib import Path

from auditcopilot.weather.providers import OpenMeteoWeatherProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.get_calls = 0

    def get(self, url, params=None, timeout=None):
        self.get_calls += 1
        if "geocoding-api" in url:
            return _FakeResponse(
                {
                    "results": [
                        {
                            "latitude": 40.7128,
                            "longitude": -74.0060,
                            "name": "New York",
                        }
                    ]
                }
            )
        return _FakeResponse(
            {
                "daily": {
                    "time": ["2025-01-01", "2025-01-02", "2025-02-01", "2025-02-02"],
                    "temperature_2m_mean": [30.0, 34.0, 40.0, 44.0],
                }
            }
        )


def test_open_meteo_weather_provider_fetches_and_caches_monthly_weather(tmp_path: Path) -> None:
    session = _FakeSession()
    provider = OpenMeteoWeatherProvider(
        query="10001",
        start_date="2025-01-01",
        end_date="2025-02-28",
        cache_dir=tmp_path,
        session=session,
    )

    first_df = provider.get_monthly_weather()
    second_df = provider.get_monthly_weather()

    assert session.get_calls == 2
    assert first_df.to_dict(orient="records") == second_df.to_dict(orient="records")
    assert first_df.to_dict(orient="records") == [
        {"year": 2025, "month": 1, "avg_temp": 32.0},
        {"year": 2025, "month": 2, "avg_temp": 42.0},
    ]
