from rag.generation import GroundedAnswer, generate_grounded_answer
from rag.retrieval import retrieve_documents_with_quality
from tests.test_rag_quality import FakeEmbeddingModel, SequencedCollection, _item


def test_controlled_end_to_end_goa_question_stays_in_travel_knowledge(monkeypatch):
    collection = SequencedCollection([[_item(distance=0.2)]])
    monkeypatch.setattr(
        "rag.generation.invoke_with_fallback",
        lambda *_args: GroundedAnswer(
            answer="The retrieved Goa guide mentions North Goa beaches.",
            sources=[{
                "document_id": "doc-1", "filename": "guide.pdf", "source": "guide.pdf",
                "page": 1, "chunk_index": 0, "destination": "Goa", "category": "travel_guide",
                "document_type": "destination_guide",
            }], grounded=True, query="wrong", retrieved_document_count=99,
        ),
    )

    quality = retrieve_documents_with_quality(
        "What are the best beaches in North Goa?",
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
    )
    answer = generate_grounded_answer(quality.query, quality.retrieved_documents)

    assert "Goa" in answer.answer
    assert answer.grounded is True
    assert answer.sources[0].filename == "guide.pdf"
    assert answer.sources[0].page == 1
    assert collection.queries[0]["include"] == ["documents", "metadatas", "distances"]
    assert collection.queries[0].get("where") is None