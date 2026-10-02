from rag.generation import PREVIEW_LENGTH, GroundedAnswer, generate_grounded_answer
from tests.test_rag_generation import _document


def test_retrieved_source_gets_bounded_preview_and_metadata(monkeypatch):
    document = _document()
    document.content = "word " * 200
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: GroundedAnswer(
            answer="Supported answer.",
            sources=[{
                "document_id": "doc-1", "filename": "Goa-Travel-Guide.pdf", "source": "guide.pdf",
                "page": 1, "chunk_index": 0, "destination": "Goa", "category": "travel_guide",
                "document_type": "destination_guide",
            }], grounded=True, query="wrong", retrieved_document_count=9,
        ),
    )

    response = generate_grounded_answer("best beaches", [document])

    assert len(response.sources) == 1
    assert len(response.sources[0].preview) <= PREVIEW_LENGTH
    assert response.sources[0].page == document.page
    assert " " in response.sources[0].preview


def test_grounded_answer_without_provider_citations_uses_retrieved_sources(monkeypatch):
    document = _document()
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: GroundedAnswer(
            answer="The retrieved guide describes Goa beaches.",
            sources=[],
            grounded=True,
            query="wrong",
            retrieved_document_count=0,
        ),
    )

    response = generate_grounded_answer("Tell me about Goa", [document])

    assert response.grounded is True
    assert len(response.sources) == 1
    assert response.sources[0].filename == document.filename
    assert response.sources[0].source == document.source
    assert response.sources[0].page == document.page
    assert response.sources[0].preview == document.content


def test_weak_retrieval_stays_uncited_without_provider_call(monkeypatch):
    document = _document()
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("provider must not be called")),
    )

    response = generate_grounded_answer("Tell me about Goa", [document], retrieval_status="weak")

    assert response.grounded is False
    assert response.sources == []
    assert response.retrieval_status == "weak"


def test_no_context_has_no_citations():
    response = generate_grounded_answer("unknown", [])

    assert response.sources == []
    assert response.grounded is False