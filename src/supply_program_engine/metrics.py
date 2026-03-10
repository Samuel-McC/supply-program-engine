from __future__ import annotations

import time
from collections import defaultdict

REQUEST_COUNT = defaultdict(int)
REQUEST_LATENCY = defaultdict(list)


def record_request(path: str, duration: float) -> None:
    REQUEST_COUNT[path] += 1
    REQUEST_LATENCY[path].append(duration)


def snapshot():
    metrics = {}

    for path, count in REQUEST_COUNT.items():
        latencies = REQUEST_LATENCY[path]
        avg = sum(latencies) / len(latencies) if latencies else 0

        metrics[path] = {
            "count": count,
            "avg_latency_ms": round(avg * 1000, 2),
        }

    return metrics