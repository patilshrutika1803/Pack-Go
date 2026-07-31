"""
LangGraph Multi-Agent Workflow definition.

Single-pass supervisor: Supervisor runs ONCE at the start and decides the
full sequence. Workers execute in a fixed linear pipeline. Only CriticAgent
can loop back to ItineraryAgent for a revision pass (max 3 times).
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from models.schemas import (
    UserPreferences, WeatherInfo, BudgetBreakdown,
    DayPlan, CriticReview, RevisionRecord, TravelPlan
)
from agent.supervisor import supervisor_node
from agent.preference_extractor import preference_extractor_node
from agent.research_agent import research_agent_node
from agent.weather_agent import weather_agent_node
from agent.budget_agent import budget_agent_node
from agent.itinerary_agent import itinerary_agent_node
from agent.critic_agent import critic_agent_node
from memory.short_term import get_checkpointer


# ── Reducers ──────────────────────────────────────────────────────────────────

def _union_list(left: List[str], right: List[str]) -> List[str]:
    """Set-union reducer: accumulates unique strings, never duplicates."""
    left = left or []
    if not right:
        return left
    existing = set(left)
    return left + [a for a in right if a not in existing]

def append_history(left: List[RevisionRecord], right: List[RevisionRecord]) -> List[RevisionRecord]:
    left = left or []
    return left + (right or [])


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    query: str                                            # extracted by Supervisor
    past_context: str
    preferences: Optional[UserPreferences]
    research_data: Optional[Dict[str, Any]]
    weather_info: Optional[WeatherInfo]
    budget_breakdown: Optional[BudgetBreakdown]
    itinerary: Optional[List[DayPlan]]
    critic_review: Optional[CriticReview]
    iteration_count: int
    revision_history: Annotated[List[RevisionRecord], append_history]
    failed_agents: Annotated[List[str], _union_list]
    completed_agents: Annotated[List[str], _union_list]
    data_freshness: Dict[str, str]
    final_plan: Optional[TravelPlan]


# ── Node wrappers ─────────────────────────────────────────────────────────────

def critic_agent_wrapper(state: AgentState) -> Dict[str, Any]:
    """Runs CriticAgent, increments iteration counter, appends revision history."""
    result = critic_agent_node(state)
    review: CriticReview = result["critic_review"]
    iteration = state.get("iteration_count", 0) + 1

    history_update = []
    if review.requires_revision:
        history_update.append(RevisionRecord(
            iteration=iteration,
            score=review.overall_score,
            changes_made="; ".join(review.revision_instructions)
        ))

    return {
        "critic_review": review,
        "iteration_count": iteration,
        "revision_history": history_update,
        "completed_agents": ["CriticAgent"],
    }


# ── Routers ───────────────────────────────────────────────────────────────────

def reflection_router(state: AgentState) -> str:
    """After CriticAgent: loop back to ItineraryAgent only if revision needed (max 3x)."""
    review = state.get("critic_review")
    iteration = state.get("iteration_count", 0)
    if review and review.requires_revision and iteration < 3:
        return "ItineraryAgent"
    return END


# ── Graph ─────────────────────────────────────────────────────────────────────

class GraphBuilder:
    def __init__(self, model_provider: str = "groq"):
        self.model_provider = model_provider

    def build_graph(self):
        workflow = StateGraph(AgentState)

        # Register nodes
        workflow.add_node("Supervisor", supervisor_node)
        workflow.add_node("PreferenceExtractor", preference_extractor_node)
        workflow.add_node("ResearchAgent", research_agent_node)
        workflow.add_node("WeatherAgent", weather_agent_node)
        workflow.add_node("BudgetAgent", budget_agent_node)
        workflow.add_node("ItineraryAgent", itinerary_agent_node)
        workflow.add_node("CriticAgent", critic_agent_wrapper)

        # ── Fixed linear pipeline ──────────────────────────────────────────
        # Supervisor runs ONCE, then agents run sequentially.
        # Supervisor is kept in the graph for its query-parsing role
        # (reads messages → sets query context) but does NOT re-run between agents.
        workflow.add_edge(START, "Supervisor")
        workflow.add_edge("Supervisor", "PreferenceExtractor")
        workflow.add_edge("PreferenceExtractor", "ResearchAgent")
        workflow.add_edge("ResearchAgent", "WeatherAgent")
        workflow.add_edge("WeatherAgent", "BudgetAgent")
        workflow.add_edge("BudgetAgent", "ItineraryAgent")
        workflow.add_edge("ItineraryAgent", "CriticAgent")

        # CriticAgent is the only node that can loop (revision) or end
        workflow.add_conditional_edges(
            "CriticAgent",
            reflection_router,
            {
                "ItineraryAgent": "ItineraryAgent",
                END: END,
            },
        )

        checkpointer = get_checkpointer()
        self.graph = workflow.compile(checkpointer=checkpointer)
        return self.graph

    def __call__(self):
        return self.build_graph()