"""
Itinerary Agent to synthesize all gathered data into a structured DayPlan.
Uses summarize_for_itinerary() to pass only a compact context to the LLM,
reducing token usage significantly vs. passing full JSON blobs.
"""
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, model_validator
from utils.llm_loader import build_structured_output, invoke_with_fallback
from utils.context_summarizer import summarize_for_itinerary
from utils.plan_costs import reconcile_budget
from prompt_library.itinerary_prompt import SYSTEM_PROMPT
from models.schemas import BudgetBreakdown, DayPlan
from logger.logging import get_logger

logger = get_logger(__name__)

class ItineraryOutput(BaseModel):
    """Structured output containing a list of daily plans."""
    itinerary: List[DayPlan] = Field(description="The final day-by-day itinerary.")

    @model_validator(mode="before")
    @classmethod
    def normalize_missing_day_fields(cls, value):
        """Keep incomplete provider objects inside the strict DayPlan contract."""
        if not isinstance(value, dict) or not isinstance(value.get("itinerary"), list):
            return value

        normalized = []
        for index, raw_day in enumerate(value["itinerary"], start=1):
            if not isinstance(raw_day, dict):
                normalized.append(raw_day)
                continue
            day = dict(raw_day)
            day.setdefault("day_number", index)
            day.setdefault("theme", "Unspecified")
            day.setdefault(
                "hotel",
                {
                    "name": "Not specified",
                    "stars": "Unknown",
                    "price_per_night": "₹0",
                    "amenities": [],
                    "description": "No accommodation details were provided.",
                },
            )
            day.setdefault("meals", [])
            day.setdefault("attractions", [])
            day.setdefault("activities", [])
            day.setdefault("transport", {"mode": "Not specified", "estimated_cost": "Free"})
            day.setdefault("estimated_day_cost", 0)
            normalized.append(day)
        return {**value, "itinerary": normalized}

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
        return {
            "itinerary": None,
            "failed_agents": ["ItineraryAgent"],
            "failure_reasons": {"ItineraryAgent": "Preferences are unavailable."},
        }

    weather = state.get("weather_info")
    budget = state.get("budget_breakdown")
    if budget and not hasattr(budget, "model_copy"):
        budget = BudgetBreakdown.model_validate({"is_within_budget": True, **budget})
    research_data = state.get("research_data", {})
    critic_review = state.get("critic_review")

    failed_agents = set(state.get("failed_agents", []))
    if "BudgetAgent" in failed_agents or not budget:
        return {
            "itinerary": None,
            "failed_agents": ["ItineraryAgent"],
            "failure_reasons": {"ItineraryAgent": "BudgetAgent did not produce a valid budget."},
        }
    if "ResearchAgent" in failed_agents or not research_data or not research_data.get("places"):
        return {
            "itinerary": None,
            "failed_agents": ["ItineraryAgent"],
            "failure_reasons": {"ItineraryAgent": "Research data is unavailable."},
        }

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
        return build_structured_output(llm, ItineraryOutput)

    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
        final_response = invoke_with_fallback(build_chain, messages)
        logger.info(f"Itinerary created with {len(final_response.itinerary)} days.")
        researched_activities = research_data.get("activities", [])
        for day in final_response.itinerary:
            if not day.activities:
                day.activities = list(researched_activities[:3]) or [
                    attraction.place.name for attraction in day.attractions[:3]
                ]
        reconciled_budget = reconcile_budget(
            budget,
            final_response.itinerary,
            preferences.total_budget,
        )
        return {
            "itinerary": [day.model_dump() for day in final_response.itinerary],
            "budget_breakdown": reconciled_budget,
            "completed_agents": ["ItineraryAgent"],
        }

    except Exception as e:
        logger.error(f"ItineraryAgent failed: {e}")
        return {
            "itinerary": None,
            "failed_agents": ["ItineraryAgent"],
            "failure_reasons": {"ItineraryAgent": str(e)},
        }
