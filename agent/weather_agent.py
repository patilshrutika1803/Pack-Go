"""
Weather Agent for fetching live weather or seasonal fallbacks.
"""
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from utils.llm_loader import invoke_with_fallback
from prompt_library.weather_prompt import SYSTEM_PROMPT
from models.schemas import WeatherInfo
from tools.weather_info_tool import WeatherInfoTool
from logger.logging import get_logger

logger = get_logger(__name__)

def weather_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("WeatherAgent started.")
    
    preferences = state.get("preferences")
    if not preferences:
        return {"weather_info": None}
    
    def build_chain(llm):
        return llm.with_structured_output(WeatherInfo)
    
    weather_tools = WeatherInfoTool().weather_tool_list
    
    human_content = (
        f"Destination: {preferences.destination}\n"
        f"Travel Dates: {preferences.travel_dates or 'Not specified'}\n"
    )
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content)
    ]
    
    try:
        final_response = invoke_with_fallback(build_chain, messages)
        logger.info(f"Weather info generated. Condition: {final_response.conditions}")
        return {"weather_info": final_response, "completed_agents": ["WeatherAgent"]}
        
    except Exception as e:
        logger.error(f"WeatherAgent failed: {e}")
        return {"weather_info": WeatherInfo(
            summary="Weather data unavailable.",
            temperature_range="Unknown",
            conditions="Unknown",
            packing_suggestions=["Check local forecast"],
            travel_warnings=[],
            data_source="llm_fallback",
            fallback_used=True
        ), "completed_agents": ["WeatherAgent"]}
