## 2. Validation Event Schema

All validation events share the same structure:

```json
{
  "qa_id": "qa-1234",
  "namespace": "project:my-mcp-server",
  "result": "pass",
  "signal_strength": "strong",
  "source": "qa-run",
  "context": {
    "command": "pytest -q",
    "exit_code": 0,
    "runtime_ms": 5320,
    "stdout_digest": "hash:...",
    "stderr_digest": "hash:..."
  },
  "client": {
    "client_id": "qa-run-cli",
    "session_id": null,
    "user_id": null
  },
  "ts": "2025-01-01T12:00:00Z"
}
```

### 2.1 `result`

| Value  | Meaning                          |
| ------ | -------------------------------- |
| `pass` | the solution worked in execution |
| `fail` | execution failed / unresolved    |

### 2.2 `signal_strength`

Represents reliability of the signal:

| Strength | Typical Source                      |
| -------- | ----------------------------------- |
| `strong` | tests, builds, integration checks   |
| `medium` | scripts / non-critical commands     |
| `weak`   | miscellaneous commands (low weight) |

Heuristic mapping (example):

```
test|pytest|npm test|go test → strong
build|compile|cargo build|npm run build → strong
script execution → medium
misc → weak
```

---

## 3. Stored Statistics (per QA)

Each QA entry maintains validation statistics:

```json
{
  "stats": {
    "total_pass": 7,
    "total_fail": 2,

    "strong_pass": 4,
    "strong_fail": 1,
    "medium_pass": 3,
    "medium_fail": 1,
    "weak_pass": 0,
    "weak_fail": 0,

    "consecutive_fail": 1,
    "last_result": "pass",
    "last_validated_at": "2025-01-01T11:30:00Z"
  },

  "score": {
    "trust_score": 0.87,
    "validation_level": 2
  },

  "ttl": {
    "expires_at": "2026-02-01T00:00:00Z"
  }
}
```

These values are updated on every `/qa/validate` event.

---

## 4. Trust Score Calculation

A weighted score captures reliability:

```python
def compute_trust_score(stats):
    sp, sf = stats.strong_pass, stats.strong_fail
    mp, mf = stats.medium_pass, stats.medium_fail
    wp, wf = stats.weak_pass, stats.weak_fail
    cf = stats.consecutive_fail

    score = 0.0
    score += 0.25 * sp
    score -= 0.35 * sf

    score += 0.10 * mp
    score -= 0.15 * mf

    score += 0.02 * wp
    score -= 0.05 * wf

    score -= 0.5 * min(cf, 3)

    score = max(-2.0, min(score, 3.0))
    return (score + 2.0) / 5.0   # normalize to [0,1]
```

Principles:

- **Strong signals dominate**
- Consecutive failures are heavily penalized
- Score remains stable but responsive

---

## 5. Validation Levels

Levels reflect maturity:

| Level | Criteria (suggested)                                              | Meaning   |
| ----: | ----------------------------------------------------------------- | --------- |
|     0 | no validation                                                     | candidate |
|     1 | trust ≥ 0.40 & ≥2 validations                                     | basic     |
|     2 | trust ≥ 0.65 & ≥3 validations & ≥1 strong pass                    | strong    |
|     3 | trust ≥ 0.80 & ≥5 validations & ≥2 strong passes & 0 strong fails | canonical |

Levels influence ranking & retention.








---

## 6. TTL & Decay

Each QA has an expiration timestamp.

Rules:

| Event       | TTL Effect               |
| ----------- | ------------------------ |
| Strong pass | +30 days (up to max 180) |
| Strong fail | −30 days (min = now+7d)  |
| No activity | gradual decay            |

Expired entries become **stale** and:

- drop in ranking, or
- are excluded from default retrieval

---

## 7. Validation Handler Logic (Summary)

When `/qa/validate` is called:

1. Load QA entry
2. Update pass/fail counters + streaks
3. Compute trust score
4. Recompute validation level
5. Adjust TTL
6. Persist changes
7. Return updated status

Return payload example:

```json
{
  "ok": true,
  "trust_score": 0.82,
  "validation_level": 2,
  "expires_at": "2026-02-01T00:00:00Z"
}
```

---

## 8. Search Ranking Integration

During `/qa/search`:

- Higher `validation_level` → positive boost
- Higher `trust_score` → positive boost
- `stale` or failure-prone entries → penalized
- Level 0 candidates appear only when no stronger matches exist

Result:

> The system naturally prefers frequently-validated solutions.

---

## 9. Safety & Guard Rails

To prevent noise:

- Ignore **weak** signals when they contradict multiple strong passes
- Never promote an entry with **recent consecutive fails ≥ 3**
- Cap strong promotion to avoid sudden spikes
- Log anomalies (e.g., alternating pass/fail every run)