from __future__ import annotations

import json
import os
import time


sleep_seconds = float(os.environ.get("LOCAL_DEMO_SLEEP_SECONDS", "1.2"))
time.sleep(sleep_seconds)

metrics = {
    "latency_mean_ms": 12.3,
    "latency_p50_ms": 12.0,
    "latency_p95_ms": 14.1,
    "latency_p99_ms": 15.0,
    "throughput_fps": 81.3,
}

print("delayed local benchmark smoke")
print(f"LOCAL_DEMO_FLAG={os.environ.get('LOCAL_DEMO_FLAG', '')}")
print(f"LOCAL_DEMO_SLEEP_SECONDS={sleep_seconds}")
print(f"EDGEENV_METRICS_JSON={json.dumps(metrics, sort_keys=True)}")
