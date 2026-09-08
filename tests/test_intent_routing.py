from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent import agentic_workflow as workflow_module
from agent import supervisor as supervisor_module
from models.schemas import SupervisorDecision
from models.schemas import UserPreferences


def _run_graph(monkeypatch, intent, query="Tell me something interesting about Rajasthan"):
    calls = []

    def supervisor(state):
        calls.append("Supervisor")
        return {"query": state["messages"][0].content, "intent": intent}

    def chat(state):
        calls.append("ChatAgent")
        return {"chat_response": "Here is a concise answer.", "completed_agents": ["ChatAgent"]}

    def unexpected_trip_agent(name):
        def node(state):
            calls.append(name)
            raise AssertionError(f"{name} must not run for {intent}")
        return node

    monkeypatch.setattr(workflow_module, "supervisor_node", supervisor)
    monkeypatch.setattr(workflow_module, "chat_agent_node", chat)
    for name in (
        "preference_extractor_node",
        "research_agent_node",
        "weather_agent_node",
        "budget_agent_node",
        "itinerary_agent_node",
        "critic_agent_node",
    ):
        monkeypatch.setattr(workflow_module, name, unexpected_trip_agent(name))
    monkeypatch.setattr(workflow_module, "get_checkpointer", MemorySaver)

    graph = workflow_module.GraphBuilder().build_graph()
    state = graph.invoke(
        {"messages": [HumanMessage(content=query)]},
        config={"configurable": {"thread_id": f"routing-{intent}"}},
    )
    return state, calls


def test_plan_trip_routes_to_preference_extractor(monkeypatch):
    calls = []

    def supervisor(state):
        calls.append("Supervisor")
        return {"query": state["messages"][0].content, "intent": "plan_trip"}

    def preferences(state):
        calls.append("PreferenceExtractor")
        return {"preferences": UserPreferences(
            destination="Udaipur",
            duration=4,
            total_budget=30000,
            budget_currency="INR",
            travel_style="balanced",
        )}

    def research(state):
        calls.append("ResearchAgent")
        return {"research_data": {}}

    def weather(state):
        calls.append("WeatherAgent")
        return {"weather_info": None}

    monkeypatch.setattr(workflow_module, "supervisor_node", supervisor)
    monkeypatch.setattr(workflow_module, "preference_extractor_node", preferences)
    monkeypatch.setattr(workflow_module, "research_agent_node", research)
    monkeypatch.setattr(workflow_module, "weather_agent_node", weather)
    monkeypatch.setattr(workflow_module, "get_checkpointer", MemorySaver)
    graph = workflow_module.GraphBuilder().build_graph()
    graph.invoke(
        {"messages": [HumanMessage(content="Plan a 4-day trip to Udaipur with a budget of ₹30,000")]},
        config={"configurable": {"thread_id": "routing-plan"}},
    )

    assert calls == ["Supervisor", "PreferenceExtractor", "ResearchAgent", "WeatherAgent"]


def test_supervisor_uses_structured_intent_decision(monkeypatch):
    monkeypatch.setattr(
        supervisor_module,
        "invoke_with_fallback",
        lambda chain_builder, messages: SupervisorDecision(intent="general_chat"),
    )

    state = supervisor_module.supervisor_node({
        "messages": [HumanMessage(content="What is the best time to visit Goa?")]
    })

    assert state["intent"] == "general_chat"
    assert state["query"] == "What is the best time to visit Goa?"


def test_general_chat_routes_only_to_chat_agent(monkeypatch):
    state, calls = _run_graph(monkeypatch, "general_chat")

    assert calls == ["Supervisor", "ChatAgent"]
    assert state["intent"] == "general_chat"
    assert state["chat_response"] == "Here is a concise answer."
    assert workflow_module.validate_final_state(state) == []


def test_general_travel_question_uses_general_chat_route(monkeypatch):
    state, calls = _run_graph(monkeypatch, "general_chat", "What is the best time to visit Goa?")

    assert state["query"] == "What is the best time to visit Goa?"
    assert calls[-1] == "ChatAgent"
    assert "PreferenceExtractor" not in calls