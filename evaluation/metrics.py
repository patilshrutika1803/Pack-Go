from __future__ import annotations

from statistics import mean, median
from typing import Iterable


def precision_at_k(retrieved: Iterable[str], relevant: Iterable[str], k: int) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    retrieved_k = list(retrieved)[:k]
    if not retrieved_k:
        return 0.0
    return len(set(retrieved_k) & set(relevant)) / k


def recall_at_k(retrieved: Iterable[str], relevant: Iterable[str], k: int) -> float:
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    return len(set(list(retrieved)[:k]) & relevant_set) / len(relevant_set)


def hit_rate(retrieved_cases: Iterable[Iterable[str]], relevant_cases: Iterable[Iterable[str]], k: int) -> float:
    retrieved = list(retrieved_cases)
    relevant = list(relevant_cases)
    if not retrieved:
        return 0.0
    hits = sum(bool(set(list(result)[:k]) & set(expected)) for result, expected in zip(retrieved, relevant, strict=True))
    return hits / len(retrieved)


def latency_summary(samples_ms: Iterable[float]) -> dict[str, float]:
    samples = sorted(float(sample) for sample in samples_ms)
    if not samples:
        return {"average_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0}
    index = min(len(samples) - 1, max(0, int(len(samples) * 0.95) - 1))
    return {"average_ms": mean(samples), "median_ms": median(samples), "p95_ms": samples[index]}


def failure_summary(total: int, **counts: int) -> dict[str, float | int]:
    if total < 0:
        raise ValueError("total must be non-negative")
    result: dict[str, float | int] = {"total": total}
    for name, count in counts.items():
        result[name] = count
        result[f"{name}_rate"] = count / total if total else 0.0
    return result


def groundedness_score(answer: str, evidence: str) -> float:
    answer_terms = {term.lower() for term in answer.split() if len(term) > 3}
    evidence_terms = {term.lower() for term in evidence.split()}
    if not answer_terms:
        return 0.0
    return len(answer_terms & evidence_terms) / len(answer_terms)


def answer_relevance_score(question: str, answer: str) -> float:
    question_terms = {term.lower() for term in question.split() if len(term) > 3}
    answer_terms = {term.lower() for term in answer.split()}
    if not question_terms:
        return 0.0
    return len(question_terms & answer_terms) / len(question_terms)


def citation_correctness(reported_sources: Iterable[str], retrieved_sources: Iterable[str]) -> float:
    reported = set(reported_sources)
    if not reported:
        return 0.0
    return len(reported & set(retrieved_sources)) / len(reported)


def build_report(*, cases: int, retrieval: dict, answer: dict, latency: dict, failures: dict) -> dict:
    return {
        "title": "RAG Evaluation",
        "cases": cases,
        "retrieval": retrieval,
        "answer": answer,
        "latency": latency,
        "failures": failures,
    }