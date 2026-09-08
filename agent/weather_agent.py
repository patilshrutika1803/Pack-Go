"""
Weather Agent for fetching live weather or explicit degraded fallbacks.
"""
from typing import Dict, Any

from models.schemas import WeatherInfo
from tools.weather_info_tool import WeatherInfoTool
from logger.logging import get_logger

logger = get_logger(__name__)


def weather_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("WeatherAgent started.")

    preferences = state.get("preferences")
    if not preferences:
        return {
            "weather_info": None,
            "failed_agents": ["WeatherAgent"],
            "failure_reasons": {"WeatherAgent": "Preferences are unavailable."},
        }

    try:
        weather_tool = WeatherInfoTool()
        weather_info = weather_tool.get_current_weather_info(preferences.destination)
        logger.info("Weather info generated via WeatherInfoTool. Condition: %s", weather_info.conditions)
        return {"weather_info": weather_info, "completed_agents": ["WeatherAgent"]}

    except Exception as e:
        logger.error("WeatherAgent failed: %s", e)
        return {
            "weather_info": WeatherInfo(
                summary="Weather data unavailable.",
                temperature_range="Unknown",
                conditions="Unknown",
                packing_suggestions=["Check local forecast"],
                travel_warnings=[],
                data_source="llm_fallback",
                fallback_used=True,
            ),
            "failed_agents": ["WeatherAgent"],
            "failure_reasons": {"WeatherAgent": str(e)},
        }
