import json

import pytest

from evaluation.metrics import answer_relevance_score, citation_correctness, failure_summary, groundedness_score, hit_rate, latency_summary, precision_at_k, recall_at_k
from evaluation.runner import load_cases


def test_evaluation_dataset_has_twenty_cases():
    cases = load_cases()

    assert len(cases) == 20
    assert {case["expected_topic"] for case in cases} >= {"beaches", "attractions", "transport", "seasons"}


@pytest.mark.parametrize(
    ("retrieved", "relevant", "expected_precision", "expected_recall"),
    [(["a", "b"], ["a", "b"], 1.0, 1.0), (["a", "x"], ["a", "b"], 0.5, 0.5), ([], ["a"], 0.0, 0.0)],
)
def test_retrieval_metrics(retrieved, relevant, expected_precision, expected_recall):
    assert precision_at_k(retrieved, relevant, 2) == expected_precision
    assert recall_at_k(retrieved, relevant, 2) == expected_recall


def test_hit_rate_and_latency_metrics():
    assert hit_rate([["a"], [], ["c"]], [["a"], ["b"], ["c"]], 5) == pytest.approx(2 / 3)
    assert latency_summary([10, 20, 30, 40])["average_ms"] == 25
    assert latency_summary([]) == {"average_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0}


def test_failure_summary_and_report_serialization():
    result = failure_summary(4, retrieval_failure=1, no_context=2)

    assert result["retrieval_failure_rate"] == 0.25
    assert result["no_context_rate"] == 0.5
    assert json.dumps(result)


def test_deterministic_answer_metrics():
    assert groundedness_score("Goa beaches", "Goa has beaches") == pytest.approx(1.0)
    assert answer_relevance_score("best beaches in Goa", "Goa beaches are listed") == pytest.approx(0.5)
    assert citation_correctness(["guide.pdf:1"], ["guide.pdf:1", "guide.pdf:2"]) == 1.0
    assert citation_correctness(["fake.pdf:9"], ["guide.pdf:1"]) == 0.0