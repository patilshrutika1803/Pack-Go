from types import SimpleNamespace

from rag.retrieval import retrieve_documents_with_quality


class FakeEmbeddingModel:
    def encode(self, texts):
        return [[float(len(text)), 1.0] for text in texts]


def _item(distance=0.25, chunk_index=0):
    return {
        "id": f"doc-1:1:{chunk_index}",
            "content": f"Goa travel information {chunk_index}. North Goa beaches are described.",
        "metadata": {
            "document_id": "doc-1",
            "source": "guide.pdf",
            "filename": "guide.pdf",
            "page": 1,
            "chunk_index": chunk_index,
            "destination": "Goa",
            "category": "travel_guide",
            "document_type": "destination_guide",
        },
        "distance": distance,
    }


class SequencedCollection:
    def __init__(self, responses):
        self.responses = responses
        self.queries = []

    def count(self):
        return 1

    def query(self, **kwargs):
        self.queries.append(kwargs)
        response = self.responses[min(len(self.queries) - 1, len(self.responses) - 1)]
        return {
            "ids": [[item["id"] for item in response]],
            "documents": [[item["content"] for item in response]],
            "metadatas": [[item["metadata"] for item in response]],
            "distances": [[item["distance"] for item in response]],
        }


def _settings(monkeypatch, threshold=0.75):
    monkeypatch.setattr(
        "rag.retrieval.get_rag_settings",
        lambda: SimpleNamespace(
            relevance_distance_threshold=threshold,
            max_retrieval_attempts=2,
        ),
    )


def test_strong_retrieval_does_not_retry(monkeypatch):
    _settings(monkeypatch)
    collection = SequencedCollection([[_item(distance=0.2)]])

    result = retrieve_documents_with_quality(
        "best beaches",
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
    )

    assert result.relevance_status == "strong"
    assert result.retrieval_success is True
    assert result.number_of_results == 1
    assert result.best_distance == 0.2
    assert result.average_distance == 0.2
    assert result.whether_retry_was_used is False
    assert len(collection.queries) == 1


def test_weak_retrieval_rewrites_and_retries(monkeypatch):
    _settings(monkeypatch)
    collection = SequencedCollection([[_item(distance=1.2)], [_item(distance=0.2)]])

    result = retrieve_documents_with_quality(
        "What should I know before going to Goa?",
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
    )

    assert result.relevance_status == "strong"
    assert result.whether_retry_was_used is True
    assert result.rewritten_query == (
        "What should I know before going to Goa? travel guide"
    )
    assert len(collection.queries) == 2


def test_retry_limit_is_two_attempts(monkeypatch):
    _settings(monkeypatch)
    collection = SequencedCollection([[_item(distance=1.2)], [_item(distance=1.1)]])

    result = retrieve_documents_with_quality(
        "vague travel question",
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
        max_attempts=2,
    )

    assert result.relevance_status == "weak"
    assert result.whether_retry_was_used is True
    assert len(collection.queries) == 2


def test_no_results_are_reported_after_bounded_retry(monkeypatch):
    _settings(monkeypatch)

    class EmptyCollection:
        def count(self):
            return 0

    result = retrieve_documents_with_quality(
        "unknown place",
        collection=EmptyCollection(),
        embedding_model=FakeEmbeddingModel(),
    )

    assert result.relevance_status == "no_results"
    assert result.retrieval_success is False
    assert result.number_of_results == 0
    assert result.whether_retry_was_used is True


def test_distance_threshold_is_configurable(monkeypatch):
    _settings(monkeypatch, threshold=0.2)
    collection = SequencedCollection([[_item(distance=0.25)], [_item(distance=0.3)]])

    result = retrieve_documents_with_quality(
        "beaches",
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
    )

    assert result.relevance_status == "weak"
    assert result.best_distance == 0.25


def test_duplicate_chunks_are_removed_before_quality_evaluation(monkeypatch):
    _settings(monkeypatch)
    duplicate = _item(distance=0.2)
    collection = SequencedCollection([[duplicate, duplicate]])

    result = retrieve_documents_with_quality(
        "beaches",
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
    )

    assert result.number_of_results == 1
    assert len(result.retrieved_documents) == 1


def test_quality_wrapper_preserves_metadata_filters(monkeypatch):
    _settings(monkeypatch)
    collection = SequencedCollection([[_item(distance=0.2)]])

    result = retrieve_documents_with_quality(
        "beaches",
        destination="Goa",
        category="travel_guide",
        document_type="destination_guide",
        collection=collection,
        embedding_model=FakeEmbeddingModel(),
    )

    assert result.relevance_status == "strong"
    assert collection.queries[0]["where"] == {
        "$and": [
            {"destination": "Goa"},
            {"category": "travel_guide"},
            {"document_type": "destination_guide"},
        ]
    }


def test_quality_wrapper_rejects_empty_query(monkeypatch):
    _settings(monkeypatch)

    try:
        retrieve_documents_with_quality(
            " ",
            collection=SequencedCollection([[_item()]]),
            embedding_model=FakeEmbeddingModel(),
        )
    except ValueError as exc:
        assert "query" in str(exc)
    else:
        raise AssertionError("empty queries must be rejected")