import logging

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agent import agentic_workflow as workflow_module
from memory.short_term import CHECKPOINT_ALLOWED_TYPES
from models.schemas import (
    AttractionVisit,
    BudgetBreakdown,
    CriticReview,
    DayPlan,
    Hotel,
    MealInfo,
    Place,
    RevisionRecord,
    Transport,
    TravelPlan,
    UserPreferences,
    WeatherInfo,
)


def _preferences():
    return UserPreferences(
        destination="Udaipur",
        duration=2,
        total_budget=20000,
        budget_currency="INR",
        travel_style="balanced",
    )


def _weather():
    return WeatherInfo(
        summary="Clear",
        temperature_range="20C - 30C",
        conditions="Clear",
        data_source="mock",
    )


def _review(requires_revision=False):
    return CriticReview(overall_score=8 if not requires_revision else 5, requires_revision=requires_revision)


def _budget():
    return BudgetBreakdown(
        total_estimated=1000,
        currency="INR",
        categories=[],
        is_within_budget=True,
    )


def _day_plan():
    return DayPlan(
        day_number=1,
        theme="City highlights",
        hotel=Hotel(name="Mock Hotel", stars=3, price_per_night=1000, description="Mock"),
        meals=[MealInfo(meal_type="Lunch", restaurant_name="Mock Cafe", estimated_cost=200)],
        attractions=[
            AttractionVisit(
                place=Place(name="City Palace"),
                timing="10:00 AM",
            )
        ],
        transport=Transport(mode="Walking", estimated_cost=0),
        estimated_day_cost=1000,
    )


def _run_graph(monkeypatch, *, weather=None, budget=None, itinerary=None, critic=None, budget_observer=None):
    calls = []

    def supervisor(state):
        calls.append("Supervisor")
        return {"query": "Plan a trip"}

    def preferences(state):
        calls.append("PreferenceExtractor")
        return {"preferences": _preferences()}

    def research(state):
        calls.append("ResearchAgent")
        return {"research_data": {"places": [{"name": "City Palace"}], "restaurants": []}}

    def weather_node(state):
        calls.append("WeatherAgent")
        return weather or {"weather_info": _weather()}

    def budget_node(state):
        calls.append("BudgetAgent")
        if budget_observer:
            budget_observer(state)
        return budget or {"budget_breakdown": _budget()}

    def itinerary_node(state):
        calls.append("ItineraryAgent")
        return itinerary or {"itinerary": [_day_plan()]}

    def critic_node(state):
        calls.append("CriticAgent")
        return critic or {"critic_review": _review()}

    monkeypatch.setattr(workflow_module, "supervisor_node", supervisor)
    monkeypatch.setattr(workflow_module, "preference_extractor_node", preferences)
    monkeypatch.setattr(workflow_module, "research_agent_node", research)
    monkeypatch.setattr(workflow_module, "weather_agent_node", weather_node)
    monkeypatch.setattr(workflow_module, "budget_agent_node", budget_node)
    monkeypatch.setattr(workflow_module, "itinerary_agent_node", itinerary_node)
    monkeypatch.setattr(workflow_module, "critic_agent_node", critic_node)
    monkeypatch.setattr(workflow_module, "get_checkpointer", MemorySaver)

    graph = workflow_module.GraphBuilder().build_graph()
    state = graph.invoke(
        {"messages": [HumanMessage(content="Plan a trip")]},
        config={"configurable": {"thread_id": "mock-test"}},
    )
    return state, calls


def test_normal_successful_path(monkeypatch):
    state, calls = _run_graph(monkeypatch)
    plan = workflow_module.build_final_plan(state)
    assert plan.itinerary
    assert workflow_module.validate_final_state(state) == []
    assert calls[-1] == "CriticAgent"


def test_weather_failure_is_degraded_and_budget_sees_it(monkeypatch):
    seen = {}

    state, calls = _run_graph(
        monkeypatch,
        weather={
            "weather_info": _weather().model_copy(update={"fallback_used": True}),
            "failed_agents": ["WeatherAgent"],
            "failure_reasons": {"WeatherAgent": "provider unavailable"},
        },
        budget={"budget_breakdown": {"total_estimated": 1000}},
        budget_observer=lambda state: seen.update(failed_agents=state["failed_agents"]),
    )
    assert "WeatherAgent" in state["failed_agents"]
    assert "WeatherAgent" in seen["failed_agents"]
    assert "BudgetAgent" in calls


def test_budget_failure_stops_before_itinerary_and_critic(monkeypatch):
    state, calls = _run_graph(
        monkeypatch,
        budget={
            "budget_breakdown": None,
            "failed_agents": ["BudgetAgent"],
            "failure_reasons": {"BudgetAgent": "provider unavailable"},
        },
    )
    assert "ItineraryAgent" not in calls
    assert "CriticAgent" not in calls
    assert workflow_module.validate_final_state(state)


def test_itinerary_failure_stops_before_critic(monkeypatch):
    state, calls = _run_graph(
        monkeypatch,
        itinerary={
            "itinerary": None,
            "failed_agents": ["ItineraryAgent"],
            "failure_reasons": {"ItineraryAgent": "generation failed"},
        },
    )
    assert "ItineraryAgent" in calls
    assert "CriticAgent" not in calls
    assert workflow_module.validate_final_state(state)


def test_empty_itinerary_does_not_run_critic(monkeypatch):
    state, calls = _run_graph(monkeypatch, itinerary={"itinerary": []})
    assert "CriticAgent" not in calls
    assert state.get("critic_review") is None


def test_critic_failure_cannot_create_success(monkeypatch):
    state, calls = _run_graph(
        monkeypatch,
        critic={
            "critic_review": None,
            "failed_agents": ["CriticAgent"],
            "failure_reasons": {"CriticAgent": "provider unavailable"},
        },
    )
    assert calls[-1] == "CriticAgent"
    assert state.get("critic_review") is None
    assert workflow_module.validate_final_state(state)


def test_revision_loop_keeps_existing_three_iteration_limit(monkeypatch):
    state = {
        "critic_review": _review(requires_revision=True),
        "iteration_count": 1,
        "failed_agents": [],
    }
    assert workflow_module.reflection_router(state) == "ItineraryAgent"
    assert workflow_module.reflection_router({**state, "iteration_count": 3}) == "__end__"


def test_checkpoint_round_trip_preserves_pydantic_model_types(monkeypatch, caplog):
    saver = MemorySaver(
        serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_ALLOWED_TYPES)
    )
    monkeypatch.setattr(
        workflow_module,
        "get_checkpointer",
        lambda: saver,
    )

    def supervisor(state):
        return {"query": state["messages"][0].content, "intent": "plan_trip"}

    def preferences(state):
        return {"preferences": _preferences()}

    def research(state):
        return {"research_data": {"places": [{"name": "City Palace"}], "restaurants": []}}

    def weather_node(state):
        return {"weather_info": _weather()}

    def budget_node(state):
        return {"budget_breakdown": _budget()}

    def itinerary_node(state):
        return {"itinerary": [_day_plan()]}

    def critic_node(state):
        return {"critic_review": _review()}

    monkeypatch.setattr(workflow_module, "supervisor_node", supervisor)
    monkeypatch.setattr(workflow_module, "preference_extractor_node", preferences)
    monkeypatch.setattr(workflow_module, "research_agent_node", research)
    monkeypatch.setattr(workflow_module, "weather_agent_node", weather_node)
    monkeypatch.setattr(workflow_module, "budget_agent_node", budget_node)
    monkeypatch.setattr(workflow_module, "itinerary_agent_node", itinerary_node)
    monkeypatch.setattr(workflow_module, "critic_agent_node", critic_node)

    graph = workflow_module.GraphBuilder().build_graph()
    config = {"configurable": {"thread_id": "checkpoint-roundtrip"}}

    caplog.set_level(logging.WARNING, logger="langgraph.checkpoint.serde.jsonplus")
    caplog.clear()

    result = graph.invoke(
        {"messages": [HumanMessage(content="Plan a trip")]},
        config=config,
    )

    checkpoint = saver.get(config)
    restored = checkpoint["channel_values"]

    assert isinstance(result["preferences"], UserPreferences)
    assert isinstance(result["weather_info"], WeatherInfo)
    assert isinstance(result["budget_breakdown"], BudgetBreakdown)
    assert isinstance(result["itinerary"][0], DayPlan)
    assert isinstance(result["critic_review"], CriticReview)
    assert isinstance(restored["preferences"], UserPreferences)
    assert isinstance(restored["weather_info"], WeatherInfo)
    assert isinstance(restored["budget_breakdown"], BudgetBreakdown)
    assert isinstance(restored["itinerary"][0], DayPlan)
    assert isinstance(restored["critic_review"], CriticReview)
    assert restored["preferences"].destination == "Udaipur"
    assert "Deserializing unregistered type" not in "\n".join(caplog.messages)