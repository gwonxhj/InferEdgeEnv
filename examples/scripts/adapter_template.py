from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copyable EdgeEnv local command adapter template. Replace the "
            "deterministic metric block with your measured benchmark values."
        )
    )
    parser.add_argument("--adapter-name", default="edgeenv-adapter-template")
    parser.add_argument("--latency-mean-ms", type=float, default=19.2)
    parser.add_argument("--latency-p50-ms", type=float, default=18.9)
    parser.add_argument("--latency-p95-ms", type=float, default=21.5)
    parser.add_argument("--latency-p99-ms", type=float, default=23.0)
    parser.add_argument("--throughput-fps", type=float, default=52.1)
    parser.add_argument("--include-resource-metrics", action="store_true")
    parser.add_argument("--resource-source", default="adapter-template")
    parser.add_argument("runtime_command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    runtime_command = _normalize_runtime_command(args.runtime_command)
    if not runtime_command:
        print("adapter template requires a command after --", file=sys.stderr)
        return 2

    print(f"adapter={args.adapter_name}")
    print(f"benchmark={os.environ.get('EDGEENV_BENCHMARK_NAME', '')}")
    print(f"model={os.environ.get('EDGEENV_MODEL_NAME', '')}")
    print(f"runtime={os.environ.get('EDGEENV_RUNTIME', '')}")
    print(f"target={os.environ.get('EDGEENV_TARGET_NAME', '')}")
    print(f"wrapped_command={' '.join(runtime_command)}")

    completed = subprocess.run(
        runtime_command,
        check=False,
        capture_output=True,
        text=True,
    )
    _forward_prefixed_lines("wrapped_stdout", completed.stdout, stream=sys.stdout)
    _forward_prefixed_lines("wrapped_stderr", completed.stderr, stream=sys.stderr)
    print(f"wrapped_command_exit={completed.returncode}")
    if completed.returncode != 0:
        return completed.returncode

    # Replace this deterministic block with measured values from your benchmark loop.
    metrics = {
        "latency_mean_ms": args.latency_mean_ms,
        "latency_p50_ms": args.latency_p50_ms,
        "latency_p95_ms": args.latency_p95_ms,
        "latency_p99_ms": args.latency_p99_ms,
        "throughput_fps": args.throughput_fps,
    }
    if args.include_resource_metrics:
        resource_metrics = {
            "memory_mean_mb": 320.0,
            "memory_peak_mb": 384.0,
            "source": args.resource_source,
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


def _forward_prefixed_lines(prefix: str, text: str, *, stream) -> None:
    for line in text.splitlines():
        print(f"{prefix}={line}", file=stream)


if __name__ == "__main__":
    raise SystemExit(main())
