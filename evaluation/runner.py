from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from evaluation.metrics import build_report, failure_summary, hit_rate, latency_summary, precision_at_k, recall_at_k


CASES_PATH = Path(__file__).with_name("cases.json")


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("evaluation cases must be a non-empty list")
    required = {"question", "expected_topic", "expected_source", "expected_keywords", "destination", "category"}
    if any(not required.issubset(case) for case in cases):
        raise ValueError("evaluation cases have missing fields")
    return cases


def evaluate_retrieval(cases: list[dict], retrieve: Callable[[str], list[dict]], k: int = 5) -> dict:
    results = [retrieve(case["question"]) for case in cases]
    retrieved_ids = [[item.get("filename", "") for item in result] for result in results]
    relevant_ids = [[case["expected_source"]] for case in cases]
    distances = [item["distance"] for result in results for item in result if item.get("distance") is not None]
    return {
        f"precision_at_{k}": sum(precision_at_k(result, expected, k) for result, expected in zip(retrieved_ids, relevant_ids, strict=True)) / len(cases),
        f"recall_at_{k}": sum(recall_at_k(result, expected, k) for result, expected in zip(retrieved_ids, relevant_ids, strict=True)) / len(cases),
        "hit_rate": hit_rate(retrieved_ids, relevant_ids, k),
        "average_distance": sum(distances) / len(distances) if distances else 0.0,
    }


def write_report(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def empty_report(case_count: int) -> dict:
    return build_report(
        cases=case_count,
        retrieval={"precision_at_5": 0.0, "recall_at_5": 0.0, "hit_rate": 0.0, "average_distance": 0.0},
        answer={"groundedness": 0.0, "relevance": 0.0, "citation_correctness": 0.0},
        latency=latency_summary([]),
        failures=failure_summary(case_count, retrieval_failure=0, generation_failure=0, no_context=0, citation_failure=0),
    )