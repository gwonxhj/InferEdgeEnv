from __future__ import annotations

import json
import os


def main() -> int:
    benchmark_name = os.environ.get("EDGEENV_BENCHMARK_NAME", "unknown-benchmark")
    model_name = os.environ.get("EDGEENV_MODEL_NAME", "unknown-model")
    target_name = os.environ.get("EDGEENV_TARGET_NAME", "unknown-target")
    template_mode = os.environ.get("LOCAL_TEMPLATE_MODE", "minimal")

    print(f"benchmark={benchmark_name}")
    print(f"model={model_name}")
    print(f"target={target_name}")
    print(f"template_mode={template_mode}")

    # Replace this deterministic block with your runtime/model benchmark loop.
    metrics = {
        "latency_mean_ms": 21.4,
        "latency_p50_ms": 20.9,
        "latency_p95_ms": 24.2,
        "latency_p99_ms": 26.0,
        "throughput_fps": 46.7,
    }
    resource_metrics = {
        "memory_peak_mb": 256.0,
        "memory_mean_mb": 240.0,
        "source": "local-template",
    }

    print(f"EDGEENV_RESOURCE_METRICS_JSON={json.dumps(resource_metrics, sort_keys=True)}")
    print(f"EDGEENV_METRICS_JSON={json.dumps(metrics, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
