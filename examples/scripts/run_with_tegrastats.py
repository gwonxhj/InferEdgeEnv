from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass


METRICS_PREFIX = "EDGEENV_METRICS_JSON="
RESOURCE_METRICS_PREFIX = "EDGEENV_RESOURCE_METRICS_JSON="


@dataclass(frozen=True)
class TegrastatsSummary:
    memory_mean_mb: float | None
    memory_peak_mb: float | None
    power_mean_w: float | None
    power_peak_w: float | None
    temperature_peak_c: float | None


def summarize_tegrastats(lines: list[str]) -> TegrastatsSummary | None:
    memory_values: list[float] = []
    power_instant_values: list[float] = []
    power_average_values: list[float] = []
    temperature_values: list[float] = []

    for line in lines:
        memory = _parse_memory_mb(line)
        if memory is not None:
            memory_values.append(memory)

        instant_mw, average_mw = _parse_vdd_in_mw(line)
        if instant_mw is not None:
            power_instant_values.append(instant_mw / 1000.0)
        if average_mw is not None:
            power_average_values.append(average_mw / 1000.0)

        temperature_values.extend(_parse_temperatures_c(line))

    if not memory_values and not power_instant_values and not temperature_values:
        return None

    return TegrastatsSummary(
        memory_mean_mb=_mean(memory_values),
        memory_peak_mb=max(memory_values) if memory_values else None,
        power_mean_w=_mean(power_average_values or power_instant_values),
        power_peak_w=max(power_instant_values) if power_instant_values else None,
        temperature_peak_c=max(temperature_values) if temperature_values else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wrap a benchmark command with Jetson tegrastats resource sampling."
    )
    parser.add_argument("--tegrastats-path", default="tegrastats")
    parser.add_argument("--interval-ms", type=int, default=500)
    parser.add_argument("--startup-wait-ms", type=int, default=250)
    parser.add_argument("--source", default="jetson-tegrastats")
    parser.add_argument("--require-tegrastats", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = _unwrap_command(args.command)
    if not command:
        print(
            "Usage: python examples/scripts/run_with_tegrastats.py "
            "[--tegrastats-path tegrastats] -- <benchmark command>",
            file=sys.stderr,
        )
        return 2

    tegrastats_path = shutil.which(args.tegrastats_path) or args.tegrastats_path
    sampler = _start_tegrastats(tegrastats_path, args.interval_ms)
    if sampler is None and args.require_tegrastats:
        print(f"tegrastats unavailable: {args.tegrastats_path}", file=sys.stderr)
        return 1
    if sampler is None:
        print("tegrastats unavailable; resource metrics omitted", file=sys.stderr)
    else:
        time.sleep(max(args.startup_wait_ms, 0) / 1000.0)

    completed = subprocess.run(
        command,
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )
    sampler_lines = _stop_tegrastats(sampler) if sampler is not None else []

    metrics_line: str | None = None
    for line in completed.stdout.splitlines():
        if line.startswith(METRICS_PREFIX):
            metrics_line = line[len(METRICS_PREFIX) :]
        elif line.startswith(RESOURCE_METRICS_PREFIX):
            print(
                "wrapped benchmark resource metrics ignored; using tegrastats sampler",
                file=sys.stderr,
            )
        else:
            print(line)

    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")

    if completed.returncode != 0:
        return completed.returncode

    if metrics_line is None:
        print(
            "Wrapped benchmark did not emit EDGEENV_METRICS_JSON=<json>",
            file=sys.stderr,
        )
        return 1

    summary = summarize_tegrastats(sampler_lines)
    if summary is None and sampler is not None:
        print("tegrastats produced no parseable resource metrics", file=sys.stderr)
    elif summary is not None:
        resource_metrics = _resource_metrics_payload(summary, args.source)
        print(
            f"{RESOURCE_METRICS_PREFIX}"
            f"{json.dumps(resource_metrics, sort_keys=True)}"
        )

    print(f"{METRICS_PREFIX}{metrics_line}")
    return 0


def _start_tegrastats(
    tegrastats_path: str,
    interval_ms: int,
) -> subprocess.Popen[str] | None:
    try:
        return subprocess.Popen(
            [tegrastats_path, "--interval", str(interval_ms)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError:
        return None


def _stop_tegrastats(process: subprocess.Popen[str]) -> list[str]:
    process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()

    if stderr:
        print(stderr, file=sys.stderr, end="")
    return stdout.splitlines()


def _parse_memory_mb(line: str) -> float | None:
    match = re.search(r"\bRAM\s+(\d+(?:\.\d+)?)/\d+(?:\.\d+)?MB\b", line)
    if match is None:
        return None
    return float(match.group(1))


def _parse_vdd_in_mw(line: str) -> tuple[float | None, float | None]:
    match = re.search(
        r"\bVDD_IN\s+(\d+(?:\.\d+)?)mW(?:/(\d+(?:\.\d+)?)mW)?\b",
        line,
    )
    if match is None:
        return None, None
    instant = float(match.group(1))
    average = float(match.group(2)) if match.group(2) is not None else None
    return instant, average


def _parse_temperatures_c(line: str) -> list[float]:
    return [
        float(value)
        for value in re.findall(r"\b[a-zA-Z0-9_]+@(\d+(?:\.\d+)?)C\b", line)
    ]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def _resource_metrics_payload(
    summary: TegrastatsSummary,
    source: str,
) -> dict[str, float | str]:
    payload: dict[str, float | str] = {"source": source}
    if summary.memory_peak_mb is not None:
        payload["memory_peak_mb"] = summary.memory_peak_mb
    if summary.memory_mean_mb is not None:
        payload["memory_mean_mb"] = summary.memory_mean_mb
    if summary.power_mean_w is not None:
        payload["power_mean_w"] = summary.power_mean_w
    if summary.power_peak_w is not None:
        payload["power_peak_w"] = summary.power_peak_w
    if summary.temperature_peak_c is not None:
        payload["temperature_peak_c"] = summary.temperature_peak_c
    return payload


def _unwrap_command(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


if __name__ == "__main__":
    raise SystemExit(main())
