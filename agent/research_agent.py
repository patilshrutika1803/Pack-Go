"""
Research Agent for finding places and restaurants.
"""
import json
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from utils.llm_loader import invoke_with_fallback
from prompt_library.research_prompt import SYSTEM_PROMPT
from models.schemas import Place, Restaurant
from pydantic import BaseModel, Field
from tools.place_search_tool import PlaceSearchTool
from logger.logging import get_logger

logger = get_logger(__name__)

class ResearchOutput(BaseModel):
    """Structured output containing lists of places and restaurants."""
    places: List[Place] = Field(description="List of top attractions and places to visit.")
    restaurants: List[Restaurant] = Field(description="List of highly rated restaurants.")

def research_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes multiple targeted searches using the PlaceSearchTool based on the destination
    and travel style. Returns a structured list of places and restaurants.
    """
    logger.info("ResearchAgent started.")
    
    preferences = state.get("preferences")
    if not preferences:
        logger.warning("No preferences found in state. Skipping research.")
        return {"research_data": {"places": [], "restaurants": []}, "failed_agents": ["ResearchAgent"]}

    def build_chain(llm):
        # PlaceSearchTool exposes tools via .place_search_tool_list (not .place_tool_list)
        search_tools = PlaceSearchTool().place_search_tool_list
        return llm.bind_tools(search_tools).with_structured_output(ResearchOutput)
        
    human_content = (
        f"Destination: {preferences.destination}\n"
        f"Travel Style: {preferences.travel_style}\n"
        f"Group Size: {preferences.group_size}\n"
        f"Interests: {', '.join(preferences.interests) if preferences.interests else 'General'}\n"
        f"Budget: {preferences.total_budget} {preferences.budget_currency}\n"
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content)
    ]

    try:
        final_response = invoke_with_fallback(build_chain, messages)
        logger.info(f"Research completed. Found {len(final_response.places)} places and {len(final_response.restaurants)} restaurants.")
        
        return {
            "research_data": {
                "places": [p.model_dump() for p in final_response.places],
                "restaurants": [r.model_dump() for r in final_response.restaurants]
            },
            "completed_agents": ["ResearchAgent"]
        }
    except Exception as e:
        logger.error(f"ResearchAgent failed: {e}")
        # Mark as failed so the supervisor never routes here again
        return {
            "research_data": {"places": [], "restaurants": []},
            "failed_agents": ["ResearchAgent"]
        }
