from __future__ import annotations

import argparse
import subprocess
import sys


METRICS_PREFIX = "EDGEENV_METRICS_JSON="


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic sampler failure policy wrapper examples."
    )
    parser.add_argument(
        "--mode",
        choices=["sampler-unavailable", "malformed-resource-metrics"],
        required=True,
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = _unwrap_command(args.command)
    if not command:
        print(
            "Usage: python examples/scripts/run_with_sampler_failure_modes.py "
            "--mode <mode> -- <benchmark command>",
            file=sys.stderr,
        )
        return 2

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

    if args.mode == "sampler-unavailable":
        print("sampler unavailable; resource metrics omitted", file=sys.stderr)
        print(f"{METRICS_PREFIX}{metrics_line}")
        return 0

    print("EDGEENV_RESOURCE_METRICS_JSON={bad sampler json")
    print(f"{METRICS_PREFIX}{metrics_line}")
    return 0


def _unwrap_command(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


if __name__ == "__main__":
    raise SystemExit(main())
