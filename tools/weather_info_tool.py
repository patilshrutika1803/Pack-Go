import os
from utils.weather_info import WeatherForecastTool
from langchain.tools import tool
from typing import List
from dotenv import load_dotenv

from models.schemas import WeatherInfo


class WeatherInfoTool:
    def __init__(self):
        load_dotenv()
        self.api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
        self.weather_service = WeatherForecastTool(self.api_key)
        self.weather_tool_list = self._setup_tools()

    def get_current_weather_info(self, city: str) -> WeatherInfo:
        """Fetch current weather and return the existing PACK-GO WeatherInfo schema."""
        weather_data = self.weather_service.get_current_weather(city)
        if not weather_data or not weather_data.get("main") or not weather_data.get("weather"):
            raise RuntimeError(f"Could not fetch weather for {city}")

        main = weather_data.get("main", {})
        description = weather_data.get("weather", [{}])[0].get("description", "Unknown")
        temp = main.get("temp")

        return WeatherInfo(
            summary=f"Current weather in {city}: {description}.",
            temperature_range=f"{temp}°C" if temp is not None else "Unknown",
            conditions=description,
            packing_suggestions=self._suggest_packing_items(temp, description),
            travel_warnings=[],
            data_source="live_api",
            fallback_used=False,
        )

    def _suggest_packing_items(self, temp, description: str) -> List[str]:
        suggestions = []
        if temp is not None:
            if temp >= 30:
                suggestions.append("Light breathable clothing")
                suggestions.append("Sunscreen and sunglasses")
            elif temp >= 20:
                suggestions.append("Comfortable daytime clothes")
            elif temp >= 10:
                suggestions.append("Light jacket or sweater")
            else:
                suggestions.append("Warm layers")
        if "rain" in description.lower() or "storm" in description.lower():
            suggestions.append("Umbrella or raincoat")
        if not suggestions:
            suggestions.append("Check local forecast before packing")
        return suggestions[:4]

    def _setup_tools(self) -> List:
        """Setup all tools for the weather forecast tool"""
        @tool
        def get_current_weather(city: str) -> str:
            """Get current weather for a city"""
            weather_data = self.weather_service.get_current_weather(city)
            if weather_data:
                temp = weather_data.get('main', {}).get('temp', 'N/A')
                desc = weather_data.get('weather', [{}])[0].get('description', 'N/A')
                return f"Current weather in {city}: {temp}°C, {desc}"
            return f"Could not fetch weather for {city}"

        @tool
        def get_weather_forecast(city: str) -> str:
            """Get weather forecast for a city"""
            forecast_data = self.weather_service.get_forecast_weather(city)
            if forecast_data and 'list' in forecast_data:
                forecast_summary = []
                for i in range(len(forecast_data['list'])):
                    item = forecast_data['list'][i]
                    date = item['dt_txt'].split(' ')[0]
                    temp = item['main']['temp']
                    desc = item['weather'][0]['description']
                    forecast_summary.append(f"{date}: {temp}°C, {desc}")
                return f"Weather forecast for {city}:\n" + "\n".join(forecast_summary)
            return f"Could not fetch forecast for {city}"

        return [get_current_weather, get_weather_forecast]