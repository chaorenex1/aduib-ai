from __future__ import annotations

import json
import pathlib

from scripts.task_grade_eval import _normalize_level, _stub_grade, accuracy, load_benchmark


def test_task_grade_benchmark_stub_regression_gate() -> None:
    """Offline regression gate.

    This test does NOT call any real LLMs.
    It ensures our benchmark file stays valid and the offline evaluator
    keeps working. It's meant to guard against accidental breaking changes
    in parsing/glue code.
    """

    root = pathlib.Path(__file__).resolve().parents[1]
    items = load_benchmark(root / "configs" / "task_grade" / "task_grade_benchmark.json")

    pairs = [(_normalize_level(it.expected_level), _stub_grade(it.input)) for it in items]
    acc = accuracy(pairs)

    # Modest guardrail threshold: not a model-quality KPI.
    assert acc >= 0.80


def test_task_grade_benchmark_json_is_valid() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "configs" / "task_grade" / "task_grade_benchmark.json"

    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) > 0

    for row in data:
        assert "id" in row and "input" in row and "expected_level" in row

