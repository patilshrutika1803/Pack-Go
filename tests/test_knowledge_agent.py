from rag.generation import GroundedAnswer, GroundedSource
from rag.retrieval import RetrievalQualityResult, RetrievedDocument
from agent.knowledge_agent import is_knowledge_query, knowledge_agent_node
from agent import chat_agent as chat_module
from agent import research_agent as research_module
from models.schemas import Place, Restaurant


def _document():
    return RetrievedDocument(
        content="Goa beaches are described in the guide.",
        document_id="doc-1",
        source="guide.pdf",
        filename="Goa-Travel-Guide.pdf",
        page=1,
        chunk_index=0,
        destination="Goa",
        category="travel_guide",
        document_type="destination_guide",
        distance=0.2,
    )


def test_knowledge_query_detection_is_selective():
    assert is_knowledge_query("What are the best beaches in Goa?") is True
    assert is_knowledge_query("How can I reach Goa?") is True
    assert is_knowledge_query("Hello") is False
    assert is_knowledge_query("How does PACK & GO work?") is False


def test_knowledge_agent_returns_grounded_answer_and_sources(monkeypatch):
    quality = RetrievalQualityResult(
        retrieved_documents=[_document()],
        query="best beaches in Goa",
        retrieval_success=True,
        relevance_status="strong",
        number_of_results=1,
        best_distance=0.2,
        average_distance=0.2,
    )
    answer = GroundedAnswer(
        answer="The guide describes Goa beaches.",
        sources=[GroundedSource(
            document_id="doc-1", filename="Goa-Travel-Guide.pdf", source="guide.pdf",
            page=1, chunk_index=0, destination="Goa", category="travel_guide",
            document_type="destination_guide",
        )],
        grounded=True,
        query="best beaches in Goa",
        retrieved_document_count=1,
    )
    monkeypatch.setattr("agent.knowledge_agent.retrieve_documents_with_quality", lambda query, **kwargs: quality)
    monkeypatch.setattr("agent.knowledge_agent.generate_grounded_answer", lambda query, documents, retrieval_status: answer)

    result = knowledge_agent_node({"query": "best beaches in Goa"})

    assert result["knowledge_answer"] == answer
    assert result["knowledge_documents"] == [_document()]
    assert result["completed_agents"] == ["KnowledgeAgent"]


def test_knowledge_agent_degrades_without_exposing_internal_error(monkeypatch):
    monkeypatch.setattr(
        "agent.knowledge_agent.retrieve_documents_with_quality",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret path")),
    )

    result = knowledge_agent_node({"query": "best beaches in Goa"})

    assert result["knowledge_answer"] is None
    assert result["knowledge_failure"] == "Knowledge retrieval is unavailable."
    assert "secret" not in str(result)


def test_chat_agent_uses_knowledge_for_relevant_question(monkeypatch):
    answer = GroundedAnswer(
        answer="Grounded Goa answer.",
        sources=[],
        grounded=False,
        query="best beaches in Goa",
        retrieved_document_count=1,
    )
    monkeypatch.setattr(
        chat_module,
        "knowledge_agent_node",
        lambda state: {"knowledge_answer": answer, "knowledge_documents": [_document()]},
    )

    result = chat_module.chat_agent_node({"query": "best beaches in Goa"})

    assert result["chat_response"] == "Grounded Goa answer."
    assert result["completed_agents"] == ["ChatAgent", "KnowledgeAgent"]


def test_research_agent_can_enrich_results_with_grounded_knowledge(monkeypatch):
    class ResearchResponse:
        places = [Place(name="Beach")]
        restaurants = [Restaurant(name="Cafe", cuisine="Goan", average_cost="100", rating="4", description="Local")]
        activities = ["Swimming"]

    answer = GroundedAnswer(
        answer="Grounded Goa research.",
        sources=[],
        grounded=True,
        query="Plan Goa",
        retrieved_document_count=1,
    )
    monkeypatch.setattr(research_module, "invoke_with_fallback", lambda *_args: ResearchResponse())
    monkeypatch.setattr(
        research_module,
        "knowledge_agent_node",
        lambda state: {"knowledge_answer": answer, "completed_agents": ["KnowledgeAgent"]},
    )

    result = research_module.research_agent_node({
        "knowledge_requested": True,
        "preferences": type("Preferences", (), {
            "destination": "Goa", "travel_style": "balanced", "group_size": 2,
            "interests": [], "total_budget": 1000, "budget_currency": "USD",
        })(),
    })

    assert result["research_data"]["grounded_knowledge"] == "Grounded Goa research."
    assert result["completed_agents"] == ["ResearchAgent", "KnowledgeAgent"]