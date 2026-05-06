from __future__ import annotations

import json
import os


VARIANTS = {
    "a": {
        "latency_mean_ms": 18.0,
        "latency_p50_ms": 17.6,
        "latency_p95_ms": 20.5,
        "latency_p99_ms": 22.0,
        "throughput_fps": 55.5,
    },
    "b": {
        "latency_mean_ms": 16.4,
        "latency_p50_ms": 16.0,
        "latency_p95_ms": 18.2,
        "latency_p99_ms": 19.7,
        "throughput_fps": 61.0,
    },
}


def main() -> int:
    variant = os.environ.get("LOCAL_COMPARE_VARIANT", "a")
    metrics = VARIANTS.get(variant)
    if metrics is None:
        valid = ", ".join(sorted(VARIANTS))
        print(f"Unknown LOCAL_COMPARE_VARIANT={variant!r}; expected one of {valid}")
        return 2

    print(f"compare_variant={variant}")
    print(f"benchmark={os.environ.get('EDGEENV_BENCHMARK_NAME', '')}")
    print(f"model={os.environ.get('EDGEENV_MODEL_NAME', '')}")
    print(f"EDGEENV_METRICS_JSON={json.dumps(metrics, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
