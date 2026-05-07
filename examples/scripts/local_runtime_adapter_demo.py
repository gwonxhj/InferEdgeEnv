from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic local runtime adapter demo for EdgeEnv."
    )
    parser.add_argument("--runtime-name", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--input-shape", required=True)
    parser.add_argument("--warmup-runs", type=int, required=True)
    parser.add_argument("--repeat-runs", type=int, required=True)
    parser.add_argument("--include-resource-metrics", action="store_true")
    parser.add_argument("runtime_command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    runtime_command = _normalize_runtime_command(args.runtime_command)
    if not runtime_command:
        print("runtime adapter requires a command after --", file=sys.stderr)
        return 2

    print("adapter=local-runtime-adapter-demo")
    print(f"benchmark={os.environ.get('EDGEENV_BENCHMARK_NAME', '')}")
    print(f"model={os.environ.get('EDGEENV_MODEL_NAME', '')}")
    print(f"model_path={args.model_path}")
    print(f"runtime={args.runtime_name}")
    print(f"input_shape={args.input_shape}")
    print(f"warmup_runs={args.warmup_runs}")
    print(f"repeat_runs={args.repeat_runs}")
    print(f"runtime_command={' '.join(runtime_command)}")

    completed = subprocess.run(
        runtime_command,
        check=False,
        capture_output=True,
        text=True,
    )
    for line in completed.stdout.splitlines():
        print(f"runtime_stdout={line}")
    for line in completed.stderr.splitlines():
        print(f"runtime_stderr={line}", file=sys.stderr)
    print(f"runtime_command_exit={completed.returncode}")
    if completed.returncode != 0:
        return completed.returncode

    metrics = _deterministic_metrics(args.warmup_runs, args.repeat_runs)
    if args.include_resource_metrics:
        resource_metrics = {
            "memory_mean_mb": 204.0,
            "memory_peak_mb": 216.0,
            "source": "local-runtime-adapter-demo",
        }
        print(
            "EDGEENV_RESOURCE_METRICS_JSON="
            + json.dumps(resource_metrics, sort_keys=True)
        )
    print("EDGEENV_METRICS_JSON=" + json.dumps(metrics, sort_keys=True))
    return 0


def _normalize_runtime_command(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def _deterministic_metrics(warmup_runs: int, repeat_runs: int) -> dict[str, float]:
    latency_mean = 18.0 + (warmup_runs * 0.2) + (repeat_runs * 0.1)
    latency_p50 = latency_mean - 0.4
    latency_p95 = latency_mean + 1.8
    latency_p99 = latency_mean + 2.4
    return {
        "latency_mean_ms": round(latency_mean, 1),
        "latency_p50_ms": round(latency_p50, 1),
        "latency_p95_ms": round(latency_p95, 1),
        "latency_p99_ms": round(latency_p99, 1),
        "throughput_fps": round(1000.0 / latency_mean, 1),
    }


if __name__ == "__main__":
    raise SystemExit(main())
