from pathlib import Path

import pytest

from rag.retrieval import RetrievedDocument, retrieve_documents


class FakeEmbeddingModel:
    def encode(self, texts):
        return [[float(len(text)), 1.0] for text in texts]


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = documents or [
            {
                "id": "doc-1:1:0",
                "content": "North Goa beaches include Keri and Arambol.",
                "metadata": {
                    "document_id": "doc-1",
                    "source": "guide.pdf",
                    "filename": "guide.pdf",
                    "page": 1,
                    "chunk_index": 0,
                    "destination": "Goa",
                    "category": "travel_guide",
                    "document_type": "destination_guide",
                },
                "distance": 0.25,
            }
        ]
        self.last_query = None

    def count(self):
        return len(self.documents)

    def query(self, **kwargs):
        self.last_query = kwargs
        return {
            "ids": [[item["id"] for item in self.documents]],
            "documents": [[item["content"] for item in self.documents]],
            "metadatas": [[item["metadata"] for item in self.documents]],
            "distances": [[item["distance"] for item in self.documents]],
        }


def test_retrieval_returns_structured_metadata_and_distance(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(
        "rag.retrieval.get_knowledge_collection",
        lambda **kwargs: collection,
    )

    results = retrieve_documents(
        "best beaches",
        destination="Goa",
        category="travel_guide",
        embedding_model=FakeEmbeddingModel(),
    )

    assert results == [
        RetrievedDocument(
            content="North Goa beaches include Keri and Arambol.",
            document_id="doc-1",
            source="guide.pdf",
            filename="guide.pdf",
            page=1,
            chunk_index=0,
            destination="Goa",
            category="travel_guide",
            document_type="destination_guide",
            distance=0.25,
        )
    ]
    assert collection.last_query["n_results"] == 1
    assert collection.last_query["where"] == {
        "$and": [{"destination": "Goa"}, {"category": "travel_guide"}]
    }
    assert collection.last_query["include"] == ["documents", "metadatas", "distances"]


def test_retrieval_uses_only_injected_knowledge_collection():
    collection = FakeCollection()
    results = retrieve_documents(
        "beaches",
        top_k=1,
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
    )

    assert len(results) == 1
    assert collection.last_query["where"] is None


def test_empty_collection_returns_empty_without_embedding():
    class EmptyCollection(FakeCollection):
        def count(self):
            return 0

    class FailingEmbeddingModel:
        def encode(self, texts):
            raise AssertionError("empty searches must not embed")

    assert retrieve_documents(
        "no matching documents",
        collection=EmptyCollection(),
        embedding_model=FailingEmbeddingModel(),
    ) == []


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_empty_query_is_rejected(query):
    with pytest.raises(ValueError, match="query"):
        retrieve_documents(query, collection=FakeCollection(), embedding_model=FakeEmbeddingModel())


@pytest.mark.parametrize("top_k", [0, -1, 51, True, "5"])
def test_invalid_top_k_is_rejected(top_k):
    with pytest.raises(ValueError, match="top_k"):
        retrieve_documents(
            "beaches",
            top_k=top_k,
            collection=FakeCollection(),
            embedding_model=FakeEmbeddingModel(),
        )


def test_unknown_filters_are_forwarded_to_chroma():
    collection = FakeCollection()
    results = retrieve_documents(
        "beaches",
        destination="Atlantis",
        category="unknown",
        embedding_model=FakeEmbeddingModel(),
        collection=collection,
    )

    assert results == [
        RetrievedDocument(
            content="North Goa beaches include Keri and Arambol.",
            document_id="doc-1",
            source="guide.pdf",
            filename="guide.pdf",
            page=1,
            chunk_index=0,
            destination="Goa",
            category="travel_guide",
            document_type="destination_guide",
            distance=0.25,
        )
    ]
    assert collection.last_query["where"] == {
        "$and": [{"destination": "Atlantis"}, {"category": "unknown"}]
    }


@pytest.fixture(scope="module")
def real_goa_collection():
    from rag.vector_store import get_knowledge_collection

    collection = get_knowledge_collection()
    if collection.count() == 0:
        pytest.fail("The existing travel_knowledge collection is empty")
    return collection


def _search_real_goa(real_goa_collection, query):
    return retrieve_documents(query, top_k=5, collection=real_goa_collection)


def test_real_goa_retrieval_finds_north_goa_beaches(real_goa_collection):
    results = _search_real_goa(real_goa_collection, "What are the best beaches in North Goa?")
    content = " ".join(result.content.lower() for result in results)

    assert any(term in content for term in ("north goa", "keri", "arambol", "mandrem", "morjim"))
    assert len(results) <= 5
    assert all(result.destination == "Goa" for result in results)


def test_real_goa_retrieval_finds_transport_information(real_goa_collection):
    results = _search_real_goa(real_goa_collection, "How can I reach Goa?")
    content = " ".join(result.content.lower() for result in results)

    assert sum(term in content for term in ("air", "train", "road")) >= 2


def test_real_goa_retrieval_finds_season_information(real_goa_collection):
    results = _search_real_goa(real_goa_collection, "When is the best time to visit Goa?")
    content = " ".join(result.content.lower() for result in results)

    assert any(term in content for term in ("season", "monsoon", "winter", "october", "march"))


def test_real_goa_retrieval_finds_central_goa_attractions(real_goa_collection):
    results = _search_real_goa(real_goa_collection, "Tell me about Central Goa attractions.")
    content = " ".join(result.content.lower() for result in results)

    assert "central goa" in content or any(
        term in content for term in ("panaji", "panjim", "old goa", "fontainhas")
    )


def test_real_goa_destination_filter(real_goa_collection):
    results = retrieve_documents(
        "What are the best beaches?",
        top_k=5,
        destination="Goa",
        collection=real_goa_collection,
    )

    assert len(results) <= 5
    assert all(result.destination == "Goa" for result in results)
    assert Path("test-data/Goa-Travel-Guide.pdf").exists()


def test_real_goa_unknown_filters_return_no_results(real_goa_collection):
    results = retrieve_documents(
        "What are the best beaches?",
        top_k=5,
        destination="Atlantis",
        category="unknown",
        collection=real_goa_collection,
    )

    assert results == []
