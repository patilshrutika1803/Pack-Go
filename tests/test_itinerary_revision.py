import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

from agent import agentic_workflow as workflow_module
from agent import itinerary_agent as itinerary_module
from main import app
from models.schemas import (
    BudgetBreakdown,
    CriticReview,
    DayPlan,
    Hotel,
    MealInfo,
    Transport,
    TravelPlan,
    UserPreferences,
)


def _preferences(duration=5):
    return UserPreferences(
        destination="Udaipur",
        duration=duration,
        total_budget=40000,
        budget_currency="INR",
        travel_style="luxury",
    )


def _day(day_number, theme):
    return DayPlan(
        day_number=day_number,
        theme=theme,
        hotel=Hotel(
            name="Lake Hotel",
            stars=5,
            price_per_night=5000,
            description="Central hotel",
        ),
        meals=[
            MealInfo(
                meal_type="Lunch",
                restaurant_name="Lake Cafe",
                estimated_cost=1000,
            )
        ],
        attractions=[],
        activities=["City walk"],
        transport=Transport(mode="Taxi", estimated_cost=500),
        estimated_day_cost=6500,
    )


def _agent_state(critic_review=None, itinerary=None):
    return {
        "preferences": _preferences(),
        "weather_info": None,
        "budget_breakdown": BudgetBreakdown(
            total_estimated=40000,
            currency="INR",
            is_within_budget=True,
        ),
        "research_data": {"places": [{"name": "City Palace"}], "restaurants": []},
        "critic_review": critic_review,
        "itinerary": itinerary or [],
    }


@pytest.mark.parametrize(
    ("scores", "expected_itinerary_calls", "expected_revision"),
    [
        ([8.0], 1, False),
        ([5.0, 8.0], 2, True),
    ],
)
def test_workflow_finishes_with_or_without_critic_revision(
    monkeypatch, scores, expected_itinerary_calls, expected_revision
):
    review_iterator = iter(scores)
    critic_calls = []
    itinerary_responses = []
    structured_schemas = []
    fallback_options = []
    revision_prompts = []

    def supervisor(_state):
        return {"query": "Plan 5 days in Udaipur", "intent": "plan_trip"}

    def preference_node(_state):
        return {"preferences": _preferences()}

    def research_node(_state):
        return {
            "research_data": {
                "places": [{"name": "City Palace"}],
                "restaurants": [],
            }
        }

    def weather_node(_state):
        from models.schemas import WeatherInfo

        return {
            "weather_info": WeatherInfo(
                summary="Clear",
                temperature_range="20C-30C",
                conditions="Clear",
                data_source="test",
            )
        }

    def budget_node(_state):
        return {
            "budget_breakdown": BudgetBreakdown(
                total_estimated=40000,
                currency="INR",
                is_within_budget=True,
            )
        }

    def build_structured_output(_llm, schema):
        structured_schemas.append(schema)

        class FakeChain:
            def invoke(self, messages):
                return itinerary_responses[-1]

        return FakeChain()

    def invoke_with_fallback(chain_builder, messages, **kwargs):
        fallback_options.append(kwargs)
        if kwargs.get("fallback_on_primary_failure"):
            revision_prompts.append(messages[1].content)
        response_days = [
            _day(day_number, "Revised highlights" if kwargs.get("fallback_on_primary_failure") else "Highlights")
            for day_number in range(1, 6)
        ]
        itinerary_responses.append(itinerary_module.ItineraryOutput(itinerary=response_days))
        return chain_builder(object()).invoke(messages)

    def critic_node(_state):
        score = next(review_iterator)
        critic_calls.append(score)
        return {
            "critic_review": CriticReview(
                overall_score=score,
                requires_revision=score < 7,
                revision_instructions=[
                    'Replace "generic" evening with a lakefront activity. {keep fields}\nDo not alter the day count.'
                ]
                if score < 7
                else [],
            )
        }

    monkeypatch.setattr(workflow_module, "supervisor_node", supervisor)
    monkeypatch.setattr(workflow_module, "preference_extractor_node", preference_node)
    monkeypatch.setattr(workflow_module, "research_agent_node", research_node)
    monkeypatch.setattr(workflow_module, "weather_agent_node", weather_node)
    monkeypatch.setattr(workflow_module, "budget_agent_node", budget_node)
    monkeypatch.setattr(
        workflow_module, "itinerary_agent_node", itinerary_module.itinerary_agent_node
    )
    monkeypatch.setattr(workflow_module, "critic_agent_node", critic_node)
    monkeypatch.setattr(workflow_module, "get_checkpointer", MemorySaver)
    monkeypatch.setattr(itinerary_module, "build_structured_output", build_structured_output)
    monkeypatch.setattr(itinerary_module, "invoke_with_fallback", invoke_with_fallback)

    graph = workflow_module.GraphBuilder().build_graph()
    state = graph.invoke(
        {"messages": [HumanMessage(content="Plan 5 days in Udaipur")]},
        config={"configurable": {"thread_id": f"revision-test-{expected_revision}"}},
    )

    assert len(itinerary_responses) == expected_itinerary_calls
    assert len(critic_calls) == expected_itinerary_calls
    assert all(schema is itinerary_module.ItineraryOutput for schema in structured_schemas)
    assert len(state["itinerary"]) == 5
    assert workflow_module.validate_final_state(state) == []
    assert state["failed_agents"] == []
    if expected_revision:
        assert fallback_options == [{}, {"fallback_on_primary_failure": True}]
        assert len(state["revision_history"]) == 1
        assert state["critic_review"].overall_score == 8
        prompt = revision_prompts[0]
        itinerary_json = prompt.split("CURRENT ITINERARY:\n", maxsplit=1)[1].split(
            "\nCRITIC REVISION INSTRUCTIONS:\n", maxsplit=1
        )[0]
        instructions_json = prompt.split(
            "CRITIC REVISION INSTRUCTIONS:\n", maxsplit=1
        )[1].strip()
        assert json.loads(itinerary_json)[0]["theme"] == "Highlights"
        assert json.loads(instructions_json) == [
            'Replace "generic" evening with a lakefront activity. {keep fields}\nDo not alter the day count.'
        ]
        assert state["itinerary"][0]["theme"] == "Revised highlights"
    else:
        assert fallback_options == [{}]
        assert state["revision_history"] == []


def test_itinerary_agent_rejects_wrong_day_count(monkeypatch):
    monkeypatch.setattr(
        itinerary_module,
        "invoke_with_fallback",
        lambda *_args, **_kwargs: itinerary_module.ItineraryOutput(itinerary=[_day(1, "One day")]),
    )

    result = itinerary_module.itinerary_agent_node(_agent_state())

    assert result["itinerary"] is None
    assert result["failed_agents"] == ["ItineraryAgent"]
    assert "expected exactly 5" in result["failure_reasons"]["ItineraryAgent"]


def test_revision_failure_is_returned_as_agent_failure(monkeypatch):
    review = CriticReview(
        overall_score=5,
        requires_revision=True,
        revision_instructions=["Keep all required fields."],
    )

    def fail_revision(_builder, _messages, **kwargs):
        assert kwargs == {"fallback_on_primary_failure": True}
        raise RuntimeError("structured revision output unavailable")

    monkeypatch.setattr(itinerary_module, "invoke_with_fallback", fail_revision)
    result = itinerary_module.itinerary_agent_node(
        _agent_state(critic_review=review, itinerary=[_day(1, "Original")])
    )

    assert result["itinerary"] is None
    assert result["failed_agents"] == ["ItineraryAgent"]
    assert result["failure_reasons"]["ItineraryAgent"] == "structured revision output unavailable"


def test_json_validation_error_on_revision_uses_existing_provider_fallback(monkeypatch):
    from utils import llm_loader

    provider_calls = []
    schemas = []

    class FakeProvider:
        def __init__(self, name):
            self.name = name

    class FakeChain:
        def __init__(self, provider):
            self.provider = provider

        def invoke(self, _messages):
            provider_calls.append(self.provider.name)
            if self.provider.name == "primary":
                raise RuntimeError(
                    "HTTP 400 code=json_validate_failed: Failed to validate JSON."
                )
            return itinerary_module.ItineraryOutput(
                itinerary=[
                    _day(day_number, "Revised highlights")
                    for day_number in range(1, 6)
                ]
            )

    monkeypatch.setattr(llm_loader, "get_primary_llm", lambda: FakeProvider("primary"))
    monkeypatch.setattr(llm_loader, "get_fallback_llm", lambda: FakeProvider("fallback"))
    monkeypatch.setattr(itinerary_module, "invoke_with_fallback", llm_loader.invoke_with_fallback)

    def build_structured_output(provider, schema):
        schemas.append((provider.name, schema))
        return FakeChain(provider)

    monkeypatch.setattr(itinerary_module, "build_structured_output", build_structured_output)
    result = itinerary_module.itinerary_agent_node(
        _agent_state(
            critic_review=CriticReview(
                overall_score=5,
                requires_revision=True,
                revision_instructions=["Replace the evening activity."],
            ),
            itinerary=[_day(day_number, "Original") for day_number in range(1, 6)],
        )
    )

    assert provider_calls == ["primary", "fallback"]
    assert schemas == [
        ("primary", itinerary_module.ItineraryOutput),
        ("fallback", itinerary_module.ItineraryOutput),
    ]
    assert result["completed_agents"] == ["ItineraryAgent"]
    assert len(result["itinerary"]) == 5
    assert all(day["theme"] == "Revised highlights" for day in result["itinerary"])


def test_stream_sends_revised_itinerary_in_done_event(monkeypatch):
    preferences = _preferences()
    final_plan = TravelPlan(
        preferences=preferences,
        itinerary=[_day(day_number, "Revised highlights") for day_number in range(1, 6)],
    )

    class FakeGraph:
        def stream(self, _payload, config=None, stream_mode=None):
            assert stream_mode == "debug"
            yield {"type": "task", "payload": {"name": "ItineraryAgent"}}
            yield {"type": "task_result", "payload": {"name": "ItineraryAgent", "result": {}}}
            yield {"type": "task", "payload": {"name": "CriticAgent"}}
            yield {"type": "task_result", "payload": {"name": "CriticAgent", "result": {}}}

        def get_state(self, _config):
            return SimpleNamespace(values={"intent": "plan_trip"})

    class FakeTripService:
        def __init__(self, _db):
            pass

        def travelplan_to_trip(self, _plan, user_id=None):
            return object()

        def create_trip(self, _trip):
            return SimpleNamespace(id="revised-trip")

    import main

    monkeypatch.setattr(main, "GraphBuilder", lambda: SimpleNamespace(build_graph=lambda: FakeGraph()))
    monkeypatch.setattr(main, "validate_final_state", lambda _state: [])
    monkeypatch.setattr(main, "build_final_plan", lambda _state: final_plan)
    monkeypatch.setattr(main, "TripService", FakeTripService)
    monkeypatch.setattr(main, "_saved_preferences_context", lambda _user, _db: {})
    monkeypatch.setitem(main.app.dependency_overrides, main.get_db, lambda: None)

    with TestClient(app) as client:
        response = client.post(
            "/plan/stream",
            json={"question": "Plan 5 days in Udaipur", "remember_me": False},
        )

    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    done_event = next(event for event in events if event["status"] == "done")
    assert done_event["data"]["trip_id"] == "revised-trip"
    assert len(done_event["data"]["itinerary"]) == 5
    assert all(day["theme"] == "Revised highlights" for day in done_event["data"]["itinerary"])
    assert not any(event["message"] == "Workflow failed validation." for event in events)
