"""
Critic Agent to evaluate the generated itinerary against constraints.
Ensures logical flow, budget adherence, weather safety, and user preferences.
"""
import json
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from utils.llm_loader import build_structured_output, invoke_with_fallback
from prompt_library.critic_prompt import SYSTEM_PROMPT
from models.schemas import CriticReview
from logger.logging import get_logger

logger = get_logger(__name__)

def critic_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates the current state (itinerary, budget, weather, preferences).
    Outputs a CriticReview with an overall score and revision instructions if the score is < 7.0.
    """
    logger.info("CriticAgent started.")
    
    preferences = state.get("preferences")
    itinerary = state.get("itinerary", [])
    budget = state.get("budget_breakdown")
    weather = state.get("weather_info")
    
    if not preferences:
        return {
            "critic_review": None,
            "failed_agents": ["CriticAgent"],
            "failure_reasons": {"CriticAgent": "Preferences are unavailable."},
        }
        
    if not itinerary or "ItineraryAgent" in state.get("failed_agents", []):
        logger.warning("No itinerary found to critique.")
        return {
            "critic_review": None,
            "failed_agents": ["CriticAgent"],
            "failure_reasons": {"CriticAgent": "Itinerary is empty or invalid."},
        }

    if "BudgetAgent" in state.get("failed_agents", []) or not budget:
        return {
            "critic_review": None,
            "failed_agents": ["CriticAgent"],
            "failure_reasons": {"CriticAgent": "Budget is unavailable."},
        }
    
    def build_chain(llm):
        return build_structured_output(llm, CriticReview)
        
    # Prepare payload for critique
    content = "Please evaluate the following travel plan:\n\n"
    content += f"PREFERENCES: {preferences.model_dump_json() if hasattr(preferences, 'model_dump_json') else preferences}\n"
    if weather:
        content += f"WEATHER: {weather.model_dump_json() if hasattr(weather, 'model_dump_json') else weather}\n"
    if budget:
        content += f"BUDGET: {budget.model_dump_json() if hasattr(budget, 'model_dump_json') else budget}\n"
        
    content += f"ITINERARY: {json.dumps(itinerary, indent=2)}\n"
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=content)
    ]
    
    try:
        final_response = invoke_with_fallback(build_chain, messages)
        logger.info(f"Critic Review complete. Score: {final_response.overall_score}/10")
        
        # Determine if revision is needed (enforce business rule)
        if final_response.overall_score < 7.0:
            final_response.requires_revision = True
            logger.warning("Critic score below threshold. Triggering revision loop.")
        else:
            final_response.requires_revision = False
            
        return {"critic_review": final_response, "completed_agents": ["CriticAgent"]}
        
    except Exception as e:
        logger.error(f"CriticAgent failed: {e}")
        return {
            "critic_review": None,
            "failed_agents": ["CriticAgent"],
            "failure_reasons": {"CriticAgent": str(e)},
        }
