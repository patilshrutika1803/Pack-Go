from rag.generation import (
    GENERATION_ERROR_ANSWER,
    NO_CONTEXT_ANSWER,
    GroundedAnswer,
    _unsupported_named_entities,
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


def _udaipur_document():
    return RetrievedDocument(
        content=(
            "The City Palace Museum in Udaipur is a historic palace complex. "
            "The visitor guide describes its museum galleries."
        ),
        document_id="udaipur-doc",
        source="udaipur-guide.pdf",
        filename="City Palace Museum Udaipur Visitor Guide.pdf",
        page=1,
        chunk_index=0,
        destination="Udaipur",
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


def test_grounding_validator_accepts_title_from_retrieved_filename():
    context = "filename: Goa-Travel-Guide.pdf\ncontent: Goa is a preferred holiday destination."

    assert _unsupported_named_entities(
        "The Goa Travel Guide describes Goa as a preferred holiday destination.",
        context,
    ) == []


def test_grounding_accepts_expanded_international_from_retrieved_intl_abbreviation(monkeypatch):
    document = _document()
    document.content = "Manohar Parrikar Int\u2019l Airport (GOX), Mopa."
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: {
            "answer": "Manohar Parrikar International Airport (GOX) is at Mopa.",
            "sources": [{
                "document_id": document.document_id,
                "filename": document.filename,
                "source": document.source,
                "page": document.page,
                "chunk_index": document.chunk_index,
                "destination": document.destination,
                "category": document.category,
                "document_type": document.document_type,
            }],
            "grounded": True,
            "query": "How can I reach Goa?",
            "retrieved_document_count": 1,
        },
    )

    response = generate_grounded_answer("How can I reach Goa?", [document])

    assert response.grounded is True
    assert response.sources[0].page == document.page
    assert response.sources[0].chunk_index == document.chunk_index


def test_grounded_response_preserves_retrieved_sources(monkeypatch):
    captured = {}

    def fake_invoke(chain_builder, messages, **_kwargs):
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


def test_grounded_response_accepts_source_title_from_metadata(monkeypatch):
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: {
            "answer": "The Goa Travel Guide describes Goa as a preferred holiday destination.",
            "sources": [{
                "document_id": "doc-1",
                "filename": "Goa-Travel-Guide.pdf",
                "source": "guide.pdf",
                "page": 1,
                "chunk_index": 0,
                "destination": "Goa",
                "category": "travel_guide",
                "document_type": "destination_guide",
            }],
            "grounded": True,
            "query": "What does the Goa Travel Guide say about Goa?",
            "retrieved_document_count": 1,
        },
    )

    response = generate_grounded_answer(
        "What does the Goa Travel Guide say about Goa?",
        [_document()],
    )

    assert response.answer.startswith("The Goa Travel Guide")
    assert response.grounded is True
    assert response.sources[0].filename == "Goa-Travel-Guide.pdf"


def test_grounded_citation_uses_retrieved_metadata_when_source_name_is_normalized(monkeypatch):
    document = _document()
    document.filename = "0c5086f8-Goa-Travel-Guide.pdf"
    document.source = document.filename
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: {
            "answer": "Keri and Arambol are listed as North Goa beaches.",
            "sources": [{
                "document_id": document.document_id,
                "filename": document.filename,
                "source": "Goa-Travel-Guide.pdf",
                "page": document.page,
                "chunk_index": document.chunk_index,
                "destination": document.destination,
                "category": document.category,
                "document_type": document.document_type,
            }],
            "grounded": True,
            "query": "wrong query",
            "retrieved_document_count": 0,
        },
    )

    response = generate_grounded_answer("best beaches in North Goa", [document])

    assert response.grounded is True
    assert response.sources[0].source == document.source
    assert response.sources[0].filename == document.filename


def test_direct_udaipur_answer_is_grounded_with_retrieved_citation(monkeypatch):
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: {
            "answer": "The City Palace Museum in Udaipur is a historic palace complex.",
            "sources": [{
                "document_id": "udaipur-doc",
                "filename": "City Palace Museum Udaipur Visitor Guide.pdf",
                "source": "udaipur-guide.pdf",
                "page": 1,
                "chunk_index": 0,
                "destination": "Udaipur",
                "category": "travel_guide",
                "document_type": "destination_guide",
            }],
            "grounded": True,
            "query": "tell me about city palace museum",
            "retrieved_document_count": 1,
        },
    )

    response = generate_grounded_answer(
        "tell me about city palace museum", [_udaipur_document()]
    )

    assert response.grounded is True
    assert response.sources[0].filename == "City Palace Museum Udaipur Visitor Guide.pdf"


def test_udaipur_broad_attraction_list_is_rejected_as_insufficient(monkeypatch):
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: {
            "answer": (
                "Udaipur attractions include City Palace, Lake Pichola, Jag Mandir, "
                "Saheliyon-Ki-Bari, Fateh Sagar Lake, and Monsoon Palace."
            ),
            "sources": [{
                "document_id": "udaipur-doc",
                "filename": "City Palace Museum Udaipur Visitor Guide.pdf",
                "source": "udaipur-guide.pdf",
                "page": 1,
                "chunk_index": 0,
                "destination": "Udaipur",
                "category": "travel_guide",
                "document_type": "destination_guide",
            }],
            "grounded": True,
            "query": "places to visit in udaipur",
            "retrieved_document_count": 1,
        },
    )

    response = generate_grounded_answer(
        "places to visit in udaipur", [_udaipur_document()]
    )

    assert response.answer == NO_CONTEXT_ANSWER
    assert response.grounded is False
    assert response.sources == []


def test_unrelated_mongolia_answer_is_rejected_without_citations(monkeypatch):
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: {
            "answer": "The capital of Mongolia is Ulaanbaatar.",
            "sources": [{
                "document_id": "udaipur-doc",
                "filename": "City Palace Museum Udaipur Visitor Guide.pdf",
                "source": "udaipur-guide.pdf",
                "page": 1,
                "chunk_index": 0,
                "destination": "Udaipur",
                "category": "travel_guide",
                "document_type": "destination_guide",
            }],
            "grounded": True,
            "query": "What is the capital of Mongolia?",
            "retrieved_document_count": 1,
        },
    )

    response = generate_grounded_answer(
        "What is the capital of Mongolia?", [_udaipur_document()]
    )

    assert response.answer == NO_CONTEXT_ANSWER
    assert response.grounded is False
    assert response.sources == []


def test_multiple_sources_are_separated_and_duplicates_are_removed(monkeypatch):
    captured = {}

    def fake_invoke(_chain_builder, messages, **_kwargs):
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
    def fake_invoke(_chain_builder, _messages, **_kwargs):
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
    monkeypatch.setattr("rag.generation.invoke_with_fallback", lambda *_args, **_kwargs: {"answer": "missing fields"})

    response = generate_grounded_answer("best beaches", [_document()])

    assert response.answer == GENERATION_ERROR_ANSWER
    assert response.grounded is False
    assert response.sources == []
    assert "provider" not in response.answer.lower()


def test_provider_failure_is_safe(monkeypatch):
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("secret provider token")),
    )

    response = generate_grounded_answer("best beaches", [_document()])

    assert response.answer == GENERATION_ERROR_ANSWER
    assert response.retrieval_status == "generation_failed"


def test_existing_fallback_helper_is_used_for_primary_and_secondary_provider(monkeypatch):
    calls = []

    def fake_invoke(chain_builder, messages, **kwargs):
        calls.append((chain_builder, messages, kwargs))
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
    assert calls[0][2]["fallback_on_primary_failure"] is True


def test_rag_provider_failure_tries_configured_fallback(monkeypatch):
    from utils import llm_loader

    calls = []

    class FakeProvider:
        def __init__(self, name):
            self.name = name

    class FakeChain:
        def __init__(self, provider):
            self.provider = provider

        def invoke(self, *_args, **_kwargs):
            calls.append(self.provider.name)
            if self.provider.name == "groq":
                raise RuntimeError("401 invalid credentials")
            return "gemini response"

    monkeypatch.setattr(llm_loader, "get_primary_llm", lambda: FakeProvider("groq"))
    monkeypatch.setattr(llm_loader, "get_fallback_llm", lambda: FakeProvider("gemini"))

    result = llm_loader.invoke_with_fallback(
        FakeChain,
        fallback_on_primary_failure=True,
    )

    assert result == "gemini response"
    assert calls == ["groq", "gemini"]