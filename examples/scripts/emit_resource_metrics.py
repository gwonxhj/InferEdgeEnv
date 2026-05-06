from __future__ import annotations

import json
import os


metrics = {
    "latency_mean_ms": 12.8,
    "latency_p50_ms": 12.4,
    "latency_p95_ms": 14.2,
    "latency_p99_ms": 15.1,
    "throughput_fps": 78.125,
}

resource_metrics = {
    "memory_peak_mb": 512.0,
    "memory_mean_mb": 420.5,
    "power_mean_w": 8.2,
    "power_peak_w": 11.4,
    "energy_j": 31.7,
    "temperature_peak_c": 72.0,
    "source": "example-script",
}

print("local resource metrics smoke")
print(f"LOCAL_DEMO_FLAG={os.environ.get('LOCAL_DEMO_FLAG', '')}")
print(f"EDGEENV_RESOURCE_METRICS_JSON={json.dumps(resource_metrics, sort_keys=True)}")
print(f"EDGEENV_METRICS_JSON={json.dumps(metrics, sort_keys=True)}")
