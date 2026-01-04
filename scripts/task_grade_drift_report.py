"""Generate a task-grade drift report.

This is a lightweight ops script that:
- Loads recent TaskGradeRecord rows
- Computes task_level distribution
- Compares to a baseline distribution and emits a TVD-based alert signal

Usage (PowerShell):
    python scripts/task_grade_drift_report.py --window-hours 24

Optional:
    python scripts/task_grade_drift_report.py --window-hours 24 --json-out drift.json

Baseline
- Default baseline is conservative and should be replaced by a production-learned baseline.
- You can pass an explicit baseline via JSON string.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional

from runtime.tasks.task_grade_drift import DriftThresholds, build_drift_report


def _parse_baseline(s: str) -> Optional[Dict[str, float]]:
    if not s:
        return None
    obj: Any = json.loads(s)
    if not isinstance(obj, dict):
        raise ValueError("baseline must be a JSON object")
    out: Dict[str, float] = {}
    for k, v in obj.items():
        out[str(k).upper()] = float(v)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--tvd-alert", type=float, default=0.25)
    parser.add_argument("--min-samples", type=int, default=200)
    parser.add_argument("--baseline-json", default="")
    parser.add_argument("--json-out", default="")

    args = parser.parse_args()

    report = build_drift_report(
        window_hours=args.window_hours,
        baseline=_parse_baseline(args.baseline_json),
        thresholds=DriftThresholds(tvd_alert=args.tvd_alert, min_samples=args.min_samples),
    )

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    return 2 if report.get("alert") else 0


if __name__ == "__main__":
    raise SystemExit(main())

