from types import SimpleNamespace

from agent.weather_agent import weather_agent_node
from models.schemas import UserPreferences, WeatherInfo
from tools.weather_info_tool import WeatherInfoTool
from utils.weather_info import WeatherForecastTool


def test_current_weather_requests_metric_and_formats_celsius(monkeypatch):
    captured = {}

    def mock_get(url, params):
        captured.update(url=url, params=params)
        return SimpleNamespace(status_code=200, json=lambda: {
            "main": {"temp": 24.5},
            "weather": [{"description": "clear sky"}],
        })

    monkeypatch.setattr("utils.weather_info.requests.get", mock_get)
    service = WeatherForecastTool("test-key")
    weather = service.get_current_weather("Udaipur")

    assert captured["params"]["units"] == "metric"
    assert weather["main"]["temp"] == 24.5

    weather_tool = WeatherInfoTool.__new__(WeatherInfoTool)
    weather_tool.weather_service = service
    current_weather = weather_tool._setup_tools()[0]
    assert "24.5°C" in current_weather.invoke({"city": "Udaipur"})


def test_forecast_requests_metric(monkeypatch):
    captured = {}

    def mock_get(url, params):
        captured.update(url=url, params=params)
        return SimpleNamespace(status_code=200, json=lambda: {"list": [{
            "dt_txt": "2026-09-08 12:00:00",
            "main": {"temp": 26.0},
            "weather": [{"description": "clear sky"}],
        }]})

    monkeypatch.setattr("utils.weather_info.requests.get", mock_get)
    WeatherForecastTool("test-key").get_forecast_weather("Udaipur")

    assert captured["params"]["units"] == "metric"
    weather_tool = WeatherInfoTool.__new__(WeatherInfoTool)
    weather_tool.weather_service = WeatherForecastTool("test-key")
    forecast_tool = weather_tool._setup_tools()[1]
    assert "26.0°C" in forecast_tool.invoke({"city": "Udaipur"})


def test_weather_tool_returns_structured_weather_info(monkeypatch):
    def mock_get(url, params):
        return SimpleNamespace(status_code=200, json=lambda: {
            "main": {"temp": 24.5},
            "weather": [{"description": "clear sky"}],
        })

    monkeypatch.setattr("utils.weather_info.requests.get", mock_get)
    weather_tool = WeatherInfoTool.__new__(WeatherInfoTool)
    weather_tool.weather_service = WeatherForecastTool("test-key")

    result = weather_tool.get_current_weather_info("Udaipur")

    assert isinstance(result, WeatherInfo)
    assert result.data_source == "live_api"
    assert result.fallback_used is False
    assert result.temperature_range == "24.5°C"
    assert result.conditions == "clear sky"


def test_weather_tool_preserves_provider_failure_without_fabricating_values(monkeypatch):
    def mock_get(url, params):
        return SimpleNamespace(status_code=503, json=lambda: {"main": {"temp": 999}})

    monkeypatch.setattr("utils.weather_info.requests.get", mock_get)
    weather_tool = WeatherInfoTool.__new__(WeatherInfoTool)
    weather_tool.weather_service = WeatherForecastTool("test-key")
    current_weather = weather_tool._setup_tools()[0]

    assert current_weather.invoke({"city": "Udaipur"}) == "Could not fetch weather for Udaipur"


def test_weather_agent_uses_weather_tool_and_does_not_call_llm_for_live_data(monkeypatch):
    captured = {}

    class FakeTool:
        def get_current_weather_info(self, city):
            captured["city"] = city
            return WeatherInfo(
                summary="Clear sky",
                temperature_range="24.5°C",
                conditions="clear sky",
                packing_suggestions=["Sunscreen"],
                travel_warnings=[],
                data_source="live_api",
                fallback_used=False,
            )

    monkeypatch.setattr("agent.weather_agent.WeatherInfoTool", FakeTool)

    state = weather_agent_node({
        "preferences": UserPreferences(
            destination="Udaipur",
            duration=2,
            total_budget=20000,
            budget_currency="INR",
            travel_style="balanced",
        )
    })

    assert captured == {"city": "Udaipur"}
    assert state["weather_info"].data_source == "live_api"
    assert state["completed_agents"] == ["WeatherAgent"]


def test_weather_agent_reports_degraded_failure_when_weather_tool_fails(monkeypatch):
    class FailingTool:
        def get_current_weather_info(self, city):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr("agent.weather_agent.WeatherInfoTool", FailingTool)

    state = weather_agent_node({
        "preferences": UserPreferences(
            destination="Udaipur",
            duration=2,
            total_budget=20000,
            budget_currency="INR",
            travel_style="balanced",
        )
    })

    assert state["failed_agents"] == ["WeatherAgent"]
    assert state["weather_info"].data_source == "llm_fallback"
    assert state["weather_info"].fallback_used is True
    assert state["failure_reasons"]["WeatherAgent"] == "provider unavailable"