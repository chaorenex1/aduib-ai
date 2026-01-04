"""Offline evaluation for TaskGrader.

Goals
- Replay a fixed benchmark set (configs/task_grade/task_grade_benchmark.json)
- Compute metrics (accuracy, confusion matrix, per-label precision/recall)
- Optional: run against real LLM router or a deterministic stub for CI

Usage (PowerShell):
    python scripts/task_grade_eval.py --mode stub
    python scripts/task_grade_eval.py --mode live --limit 20

Notes
- "stub" mode is deterministic and intended for regression gate / CI.
- "live" mode calls TaskGrader and requires runtime config + API keys.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


LEVELS = ("L0", "L1", "L2", "L3")


@dataclass(frozen=True)
class BenchmarkItem:
    id: str
    input: str
    expected_level: str


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def load_benchmark(path: pathlib.Path) -> List[BenchmarkItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items: List[BenchmarkItem] = []
    for row in data:
        items.append(BenchmarkItem(id=row["id"], input=row["input"], expected_level=row["expected_level"]))
    return items


def _normalize_level(level: Any) -> str:
    if not isinstance(level, str):
        return "L1"
    u = level.strip().upper()
    return u if u in LEVELS else "L1"


def _stub_grade(prompt: str) -> str:
    """Deterministic heuristic stub.

    Designed to be stable for regression gating without external dependencies.
    It's not "smart"; it just provides a consistent baseline and catches
    accidental breaking changes in glue code / parsing / data pipeline.
    """
    p = prompt.strip().lower()

    # Risk-ish phrases -> L2 (aligned with benchmark "RISK-*" expected L2)
    risk_keywords = [
        "利息",
        "药",
        "剂量",
        "合同",
        "风险",
        "漏洞",
        "攻击",
        "安全",
        "投资",
        "单点",
        "丢失",
        "配置",
    ]
    if any(k in p for k in risk_keywords):
        return "L2"

    # Simple transforms -> L0
    l0_keywords = [
        "翻译",
        "美化",
        "排序",
        "提取",
        "改写",
        "要点",
        "去掉",
        "转成",
        "markdown",
        "csv",
        "日期",
        "50",
    ]
    if any(k in p for k in l0_keywords):
        return "L0"

    # Creative writing -> L3
    l3_keywords = [
        "故事",
        "slogan",
        "广告",
        "脱口秀",
        "世界",
        "设定",
        "独白",
        "小说",
        "脚本",
        "旁白",
        "儿童",
    ]
    if any(k in p for k in l3_keywords):
        return "L3"

    # Engineering/design/analysis -> L2
    l2_keywords = [
        "sql",
        "并发",
        "架构",
        "内存",
        "泄漏",
        "rag",
        "向量",
        "幂等",
        "日志",
        "调度",
        "redis",
        "rabbitmq",
        "算法",
        "cpu",
        "排查",
        "数据库",
        "高可用",
        "api 网关",
        "网关",
    ]
    if any(k in p for k in l2_keywords):
        return "L2"

    # Default: explanation/summarization -> L1
    return "L1"


def _live_grade(prompt: str) -> str:
    from runtime.tasks.task_grade import TaskGrader

    res = TaskGrader.grade_task(prompt)
    if not res.get("done"):
        return "L1"
    return _normalize_level(res.get("task_level"))


def confusion_matrix(rows: Iterable[Tuple[str, str]]) -> Dict[str, Dict[str, int]]:
    mat: Dict[str, Dict[str, int]] = {e: {p: 0 for p in LEVELS} for e in LEVELS}
    for expected, predicted in rows:
        expected = _normalize_level(expected)
        predicted = _normalize_level(predicted)
        mat[expected][predicted] += 1
    return mat


def accuracy(rows: Iterable[Tuple[str, str]]) -> float:
    total = 0
    ok = 0
    for expected, predicted in rows:
        total += 1
        ok += int(_normalize_level(expected) == _normalize_level(predicted))
    return ok / total if total else 0.0


def per_label_prf(rows: Iterable[Tuple[str, str]]) -> Dict[str, Dict[str, float]]:
    tp = Counter()
    fp = Counter()
    fn = Counter()

    for expected, predicted in rows:
        e = _normalize_level(expected)
        p = _normalize_level(predicted)
        if e == p:
            tp[e] += 1
        else:
            fp[p] += 1
            fn[e] += 1

    out: Dict[str, Dict[str, float]] = {}
    for label in LEVELS:
        precision = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) else 0.0
        recall = tp[label] / (tp[label] + fn[label]) if (tp[label] + fn[label]) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[label] = {"precision": precision, "recall": recall, "f1": f1, "support": float(tp[label] + fn[label])}
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["stub", "live"], default="stub")
    parser.add_argument(
        "--benchmark",
        default=str(_repo_root() / "configs" / "task_grade" / "task_grade_benchmark.json"),
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json-out", default="")

    args = parser.parse_args(argv)

    items = load_benchmark(pathlib.Path(args.benchmark))
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    grader = _stub_grade if args.mode == "stub" else _live_grade

    pairs: List[Tuple[str, str]] = []
    failures: List[Dict[str, Any]] = []

    for it in items:
        pred = grader(it.input)
        exp = _normalize_level(it.expected_level)
        pairs.append((exp, pred))
        if exp != pred:
            failures.append({"id": it.id, "expected": exp, "predicted": pred, "input": it.input})

    acc = accuracy(pairs)
    mat = confusion_matrix(pairs)
    prf = per_label_prf(pairs)

    report: Dict[str, Any] = {
        "mode": args.mode,
        "n": len(items),
        "accuracy": acc,
        "confusion": mat,
        "per_label": prf,
        "failures": failures[:50],
    }

    if args.json_out:
        pathlib.Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Human-readable summary
    print(f"mode={args.mode} n={len(items)} accuracy={acc:.3f}")
    for lvl in LEVELS:
        r = prf[lvl]
        print(
            f"{lvl}: precision={r['precision']:.3f} recall={r['recall']:.3f} f1={r['f1']:.3f} support={int(r['support'])}"
        )

    if failures:
        print(f"\nTop mismatches (showing {min(10, len(failures))}):")
        for f in failures[:10]:
            print(f"- {f['id']}: expected={f['expected']} predicted={f['predicted']}")

    # Exit code: non-zero for severe regressions in stub mode only
    if args.mode == "stub" and acc < 0.80:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
