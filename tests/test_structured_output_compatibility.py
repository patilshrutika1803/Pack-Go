from agent import preference_extractor as preference_module
from agent import research_agent as research_module
from agent import itinerary_agent as itinerary_module
from models.schemas import UserPreferences


class FakeGroq:
    def __init__(self):
        self.structured_calls = []

    def with_structured_output(self, schema, method=None):
        self.structured_calls.append((schema, method))
        if schema is UserPreferences:
            return UserPreferences(
                destination="Udaipur",
                duration=3,
                total_budget=20000,
                budget_currency="INR",
                travel_style="balanced",
            )
        if schema is research_module.ResearchOutput:
            return research_module.ResearchOutput(places=[], restaurants=[])
        if schema is itinerary_module.ItineraryOutput:
            return itinerary_module.ItineraryOutput(itinerary=[])
        raise AssertionError(f"Unexpected schema: {schema}")

    def bind_tools(self, tools):
        return self


def test_preference_extractor_uses_provider_aware_structured_output(monkeypatch):
    fake_llm = FakeGroq()
    called = []

    def fake_build_structured_output(llm, schema):
        called.append(schema)
        return llm.with_structured_output(schema)

    monkeypatch.setattr(preference_module, "build_structured_output", fake_build_structured_output)
    monkeypatch.setattr(preference_module, "invoke_with_fallback", lambda chain_builder, messages: chain_builder(fake_llm))
    monkeypatch.setattr(preference_module, "LongTermMemory", lambda: type("DummyMemory", (), {"retrieve_past_trips": lambda self, query: "past context"})())

    response = preference_module.preference_extractor_node({"query": "Plan a 3-day trip to Udaipur"})

    assert response["preferences"].destination == "Udaipur"
    assert called == [UserPreferences]


def test_research_agent_uses_provider_aware_structured_output(monkeypatch):
    fake_llm = FakeGroq()
    called = []

    def fake_build_structured_output(llm, schema):
        called.append(schema)
        return llm.with_structured_output(schema)

    monkeypatch.setattr(research_module, "build_structured_output", fake_build_structured_output)
    monkeypatch.setattr(research_module, "invoke_with_fallback", lambda chain_builder, messages: chain_builder(fake_llm))

    response = research_module.research_agent_node({
        "preferences": UserPreferences(
            destination="Udaipur",
            duration=3,
            total_budget=20000,
            budget_currency="INR",
            travel_style="balanced",
            interests=["history"],
            group_size=2,
        )
    })

    assert response["completed_agents"] == ["ResearchAgent"]
    assert called == [research_module.ResearchOutput]


def test_itinerary_agent_uses_provider_aware_structured_output(monkeypatch):
    fake_llm = FakeGroq()
    called = []

    def fake_build_structured_output(llm, schema):
        called.append(schema)
        return llm.with_structured_output(schema)

    monkeypatch.setattr(itinerary_module, "build_structured_output", fake_build_structured_output)
    monkeypatch.setattr(itinerary_module, "invoke_with_fallback", lambda chain_builder, messages: chain_builder(fake_llm))

    response = itinerary_module.itinerary_agent_node({
        "preferences": UserPreferences(
            destination="Udaipur",
            duration=3,
            total_budget=20000,
            budget_currency="INR",
            travel_style="balanced",
            interests=["history"],
            group_size=2,
        ),
        "weather_info": None,
        "budget_breakdown": {"total_estimated": 18000, "currency": "INR", "categories": []},
        "research_data": {"places": [{"name": "City Palace"}], "restaurants": []},
    })

    assert response["completed_agents"] == ["ItineraryAgent"]
    assert called == [itinerary_module.ItineraryOutput]
