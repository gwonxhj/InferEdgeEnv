from __future__ import annotations

import json
import os


metrics = {
    "latency_mean_ms": 12.3,
    "latency_p50_ms": 12.0,
    "latency_p95_ms": 14.1,
    "latency_p99_ms": 15.0,
    "throughput_fps": 81.3,
}

print("local benchmark smoke")
print(f"LOCAL_DEMO_FLAG={os.environ.get('LOCAL_DEMO_FLAG', '')}")
print(f"EDGEENV_METRICS_JSON={json.dumps(metrics, sort_keys=True)}")
