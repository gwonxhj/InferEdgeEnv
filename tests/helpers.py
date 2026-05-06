from __future__ import annotations

from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.result.writer import build_run_result
from inferedge_env.runners.fake import FakeRunner


def make_result(
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
    run_id: str = "run-test",
):
    runner_result = FakeRunner().run(bench_config, target_profile)
    return build_run_result(
        bench_config,
        target_profile,
        runner_result,
        run_id=run_id,
        env={"python_version": "test"},
    )
