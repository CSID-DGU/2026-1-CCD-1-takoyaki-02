"""percentile/평균 헬퍼. numpy 없이 stdlib만 사용."""

from __future__ import annotations

import statistics


def percentile(values: list[float], p: float) -> float:
    """p ∈ [0, 100]. 빈 리스트면 0.0."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def summarize(values: list[float]) -> dict[str, float]:
    """p5/p50/p95/p99 + mean/min/max/stdev. 빈 리스트면 모두 0."""
    if not values:
        return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0,
                "stdev": 0.0, "p5": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "p5": percentile(values, 5),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
    }
