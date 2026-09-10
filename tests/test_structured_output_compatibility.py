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


def test_itinerary_agent_reconciles_budget_with_generated_day_costs(monkeypatch):
    generated_day = itinerary_module.ItineraryOutput(
        itinerary=[
            {
                "day_number": 1,
                "theme": "Highlights",
                "hotel": {"name": "Inn", "stars": 3, "price_per_night": "₹1,200", "description": "Central"},
                "meals": [{"meal_type": "Lunch", "restaurant_name": "Cafe", "estimated_cost": "₹350"}],
                "attractions": [{"place": {"name": "Palace", "entry_fee": "₹100"}, "timing": "10:00 AM"}],
                "activities": ["Heritage walk"],
                "transport": {"mode": "Taxi", "estimated_cost": "₹250"},
                "estimated_day_cost": 1900,
            }
        ]
    )
    monkeypatch.setattr(itinerary_module, "invoke_with_fallback", lambda chain_builder, messages: generated_day)

    response = itinerary_module.itinerary_agent_node({
        "preferences": UserPreferences(
            destination="Udaipur", duration=1, total_budget=5000,
            budget_currency="INR", travel_style="balanced",
        ),
        "budget_breakdown": {"total_estimated": 9999, "currency": "INR", "categories": []},
        "research_data": {"places": [{"name": "Palace"}], "restaurants": []},
    })

    categories = {item.name: item.amount for item in response["budget_breakdown"].categories}
    assert categories == {"Accommodation": 1200.0, "Food": 350.0, "Transport": 250.0, "Activities": 100.0}
    assert response["budget_breakdown"].total_estimated == 1900.0


def test_itinerary_agent_derives_activities_when_attractions_exist(monkeypatch):
    generated_day = itinerary_module.ItineraryOutput(
        itinerary=[
            {
                "day_number": 1,
                "theme": "Highlights",
                "hotel": {"name": "Inn", "stars": 3, "price_per_night": 1000, "description": "Central"},
                "meals": [{"meal_type": "Lunch", "restaurant_name": "Cafe", "estimated_cost": 300}],
                "attractions": [{"place": {"name": "City Palace"}, "timing": "10:00 AM"}],
                "activities": [],
                "transport": {"mode": "Walking", "estimated_cost": 0},
                "estimated_day_cost": 1300,
            }
        ]
    )
    monkeypatch.setattr(itinerary_module, "invoke_with_fallback", lambda chain_builder, messages: generated_day)

    response = itinerary_module.itinerary_agent_node({
        "preferences": UserPreferences(
            destination="Udaipur", duration=1, total_budget=5000,
            budget_currency="INR", travel_style="balanced",
        ),
        "budget_breakdown": {"total_estimated": 1300, "currency": "INR", "categories": []},
        "research_data": {"places": [{"name": "City Palace"}], "restaurants": []},
    })

    assert response["itinerary"][0]["activities"] == ["City Palace"]
