from __future__ import annotations

import hashlib

from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.runners.base import RunnerResult


class FakeRunner:
    """Deterministic runner used to exercise the MVP run lifecycle."""

    def run(self, config: BenchmarkConfig, target: TargetProfile) -> RunnerResult:
        seed = f"{config.name}|{config.model_name}|{config.runtime}|{target.target_name}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        offset = int(digest[:4], 16) % 1000 / 1000
        mean = round(12.0 + offset, 3)
        p50 = round(mean - 0.35, 3)
        p95 = round(mean + 1.75, 3)
        p99 = round(mean + 2.5, 3)
        fps = round(1000.0 / mean * config.batch_size, 3)
        return RunnerResult(
            latency_mean_ms=mean,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            throughput_fps=fps,
            stdout=f"FakeRunner completed benchmark '{config.name}' on '{target.target_name}'.",
            stderr="",
        )
