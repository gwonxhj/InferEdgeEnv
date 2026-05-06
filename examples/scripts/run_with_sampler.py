from __future__ import annotations

import json
import subprocess
import sys


METRICS_PREFIX = "EDGEENV_METRICS_JSON="


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] != "--":
        print(
            "Usage: python examples/scripts/run_with_sampler.py -- <benchmark command>",
            file=sys.stderr,
        )
        return 2

    command = sys.argv[2:]
    completed = subprocess.run(
        command,
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )

    metrics_line: str | None = None
    for line in completed.stdout.splitlines():
        if line.startswith(METRICS_PREFIX):
            metrics_line = line[len(METRICS_PREFIX) :]
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

    resource_metrics = {
        "memory_peak_mb": 384.0,
        "memory_mean_mb": 320.0,
        "power_mean_w": 6.5,
        "power_peak_w": 9.0,
        "energy_j": 24.5,
        "temperature_peak_c": 68.0,
        "source": "deterministic-wrapper-demo",
    }

    print(f"sampler-wrapper command={' '.join(command)}")
    print(f"EDGEENV_RESOURCE_METRICS_JSON={json.dumps(resource_metrics, sort_keys=True)}")
    print(f"{METRICS_PREFIX}{metrics_line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
