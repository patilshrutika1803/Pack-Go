"""
Itinerary Agent to synthesize all gathered data into a structured DayPlan.
Uses summarize_for_itinerary() to pass only a compact context to the LLM,
reducing token usage significantly vs. passing full JSON blobs.
"""
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from utils.llm_loader import invoke_with_fallback
from utils.context_summarizer import summarize_for_itinerary
from prompt_library.itinerary_prompt import SYSTEM_PROMPT
from models.schemas import DayPlan
from logger.logging import get_logger

logger = get_logger(__name__)

class ItineraryOutput(BaseModel):
    """Structured output containing a list of daily plans."""
    itinerary: List[DayPlan] = Field(description="The final day-by-day itinerary.")

def itinerary_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synthesizes preferences, weather, budget, and research data into a chronological
    DayPlan itinerary. Applies critic revisions if they exist.
    Uses summarize_for_itinerary() to keep the prompt compact.
    """
    logger.info("ItineraryAgent started.")

    preferences = state.get("preferences")
    if not preferences:
        logger.warning("No preferences found. Returning empty itinerary.")
        return {"itinerary": [], "completed_agents": ["ItineraryAgent"]}

    weather = state.get("weather_info")
    budget = state.get("budget_breakdown")
    research_data = state.get("research_data", {})
    critic_review = state.get("critic_review")

    # ── Compact context (Fix 3: token-efficient summarizer) ────────────────────
    context_summary = summarize_for_itinerary(research_data, weather, budget)

    # ── Core prompt ───────────────────────────────────────────────────────────
    content = (
        f"Destination: {preferences.destination}\n"
        f"Duration: {preferences.duration} days\n"
        f"Travel Style: {preferences.travel_style}\n"
        f"Group Size: {preferences.group_size}\n"
        f"Interests: {', '.join(preferences.interests) if preferences.interests else 'General'}\n\n"
        f"{context_summary}\n"
    )

    if critic_review and critic_review.requires_revision:
        content += "\nCRITIC REVISIONS REQUIRED:\n"
        content += "\n".join(f"- {instr}" for instr in critic_review.revision_instructions)

    def build_chain(llm):
        return llm.with_structured_output(ItineraryOutput)

    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
        final_response = invoke_with_fallback(build_chain, messages)
        logger.info(f"Itinerary created with {len(final_response.itinerary)} days.")
        return {
            "itinerary": [day.model_dump() for day in final_response.itinerary],
            "completed_agents": ["ItineraryAgent"],
        }

    except Exception as e:
        logger.error(f"ItineraryAgent failed: {e}")
        return {"itinerary": [], "failed_agents": ["ItineraryAgent"]}
