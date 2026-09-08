"""
Chat Agent to handle general conversational queries.
"""
from typing import Dict, Any
import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from utils.llm_loader import invoke_with_fallback
from logger.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a helpful assistant for PACK & GO.
You are currently engaged in a conversation with a user about their travel plans.
Answer their questions clearly and concisely. If they ask about something in their itinerary, use the provided context to answer.
"""

def chat_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handles general chat questions and sets the chat_response state."""
    logger.info("ChatAgent started.")
    
    query = state.get("query", "")
    
    # Provide basic context from the current state so the LLM knows what we are talking about
    context = []
    if state.get("preferences"):
        context.append(f"Destination: {state['preferences'].destination}")
    if state.get("itinerary"):
        # Just give a lightweight summary of the itinerary to avoid token overload
        try:
            itinerary = state["itinerary"]
            for day in itinerary:
                context.append(f"Day {day.get('day_number')}: {day.get('theme')}")
                for attr in day.get('attractions', []):
                    place = attr.get('place', {})
                    context.append(f"  - {place.get('name')}: {place.get('description')}")
                for meal in day.get('meals', []):
                    context.append(f"  - {meal.get('meal_type')} at {meal.get('restaurant_name')}")
        except Exception:
            pass
        
    context_str = "\n".join(context)
    if context_str:
        system_content = f"{SYSTEM_PROMPT}\n\n[CURRENT TRIP CONTEXT]\n{context_str}"
    else:
        system_content = SYSTEM_PROMPT
        
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=query)
    ]
    
    def build_chain(llm):
        return llm | StrOutputParser()
        
    try:
        response = invoke_with_fallback(build_chain, messages)
        logger.info("ChatAgent successfully generated a response.")
        return {"chat_response": response, "completed_agents": ["ChatAgent"]}
    except Exception as e:
        logger.error(f"ChatAgent failed: {e}")
        return {"chat_response": "I'm sorry, I'm having trouble answering that right now.", "completed_agents": ["ChatAgent"]}
