from rag.generation import (
    GENERATION_ERROR_ANSWER,
    NO_CONTEXT_ANSWER,
    GroundedAnswer,
    generate_grounded_answer,
)
from rag.retrieval import RetrievedDocument


def _document(page=1, chunk_index=0):
    return RetrievedDocument(
        content=f"North Goa beaches include Keri and Arambol. Page {page}.",
        document_id="doc-1",
        source="guide.pdf",
        filename="Goa-Travel-Guide.pdf",
        page=page,
        chunk_index=chunk_index,
        destination="Goa",
        category="travel_guide",
        document_type="destination_guide",
        distance=0.2,
    )


def test_no_context_returns_controlled_answer_without_provider_call(monkeypatch):
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *args: (_ for _ in ()).throw(AssertionError("provider must not be called")),
    )

    response = generate_grounded_answer("best beaches", [])

    assert response == GroundedAnswer(
        answer=NO_CONTEXT_ANSWER,
        sources=[],
        grounded=False,
        query="best beaches",
        retrieved_document_count=0,
        retrieval_status="strong",
    )


def test_grounded_response_preserves_retrieved_sources(monkeypatch):
    captured = {}

    def fake_invoke(chain_builder, messages):
        captured["system"] = messages[0].content
        captured["human"] = messages[1].content
        return GroundedAnswer(
            answer="Keri and Arambol are mentioned as North Goa beaches.",
            sources=[{
                "document_id": "doc-1",
                "filename": "Goa-Travel-Guide.pdf",
                "source": "guide.pdf",
                "page": 1,
                "chunk_index": 0,
                "destination": "Goa",
                "category": "travel_guide",
                "document_type": "destination_guide",
            }],
            grounded=True,
            query="wrong query",
            retrieved_document_count=99,
        )

    monkeypatch.setattr("rag.generation.invoke_with_fallback", fake_invoke)
    response = generate_grounded_answer("best beaches", [_document()])

    assert response.grounded is True
    assert response.query == "best beaches"
    assert response.retrieved_document_count == 1
    assert response.sources[0].page == 1
    assert "North Goa beaches" in captured["human"]
    system_prompt = captured["system"].lower()
    assert "do not invent facts" in system_prompt
    assert "do not fabricate" in system_prompt


def test_multiple_sources_are_separated_and_duplicates_are_removed(monkeypatch):
    captured = {}

    def fake_invoke(_chain_builder, messages):
        captured["human"] = messages[1].content
        return {
            "answer": "The guide contains beach information.",
            "sources": [],
            "grounded": False,
            "query": "best beaches",
            "retrieved_document_count": 0,
        }

    monkeypatch.setattr("rag.generation.invoke_with_fallback", fake_invoke)
    response = generate_grounded_answer("best beaches", [_document(), _document(), _document(page=2)])

    assert response.retrieved_document_count == 2
    assert captured["human"].count("SOURCE ") == 2


def test_fabricated_provider_sources_are_removed(monkeypatch):
    def fake_invoke(_chain_builder, _messages):
        return {
            "answer": "The context supports this answer.",
            "sources": [{
                "document_id": "not-retrieved",
                "filename": "fake.pdf",
                "source": "fake.pdf",
                "page": 99,
                "chunk_index": 0,
                "destination": "Atlantis",
                "category": "fake",
                "document_type": "fake",
            }],
            "grounded": True,
            "query": "best beaches",
            "retrieved_document_count": 1,
        }

    monkeypatch.setattr("rag.generation.invoke_with_fallback", fake_invoke)
    response = generate_grounded_answer("best beaches", [_document()])

    assert response.sources == []
    assert response.grounded is False


def test_malformed_provider_response_is_safe(monkeypatch):
    monkeypatch.setattr("rag.generation.invoke_with_fallback", lambda *_args: {"answer": "missing fields"})

    response = generate_grounded_answer("best beaches", [_document()])

    assert response.answer == GENERATION_ERROR_ANSWER
    assert response.grounded is False
    assert response.sources == []
    assert "provider" not in response.answer.lower()


def test_provider_failure_is_safe(monkeypatch):
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("secret provider token")),
    )

    response = generate_grounded_answer("best beaches", [_document()])

    assert response.answer == GENERATION_ERROR_ANSWER
    assert response.retrieval_status == "generation_failed"


def test_existing_fallback_helper_is_used_for_primary_and_secondary_provider(monkeypatch):
    calls = []

    def fake_invoke(chain_builder, messages):
        calls.append((chain_builder, messages))
        return {
            "answer": "Grounded answer.",
            "sources": [],
            "grounded": False,
            "query": "best beaches",
            "retrieved_document_count": 1,
        }

    monkeypatch.setattr("rag.generation.invoke_with_fallback", fake_invoke)
    response = generate_grounded_answer("best beaches", [_document()])

    assert response.answer == "Grounded answer."
    assert len(calls) == 1
    assert calls[0][1][0].content.startswith("You answer travel questions")