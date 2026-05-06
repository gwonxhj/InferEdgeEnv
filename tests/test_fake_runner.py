from __future__ import annotations

from edgeenv.runners.fake import FakeRunner


def test_fake_runner_deterministic_output(bench_config, target_profile):
    runner = FakeRunner()

    first = runner.run(bench_config, target_profile)
    second = runner.run(bench_config, target_profile)

    assert first == second
    assert first.latency_mean_ms == 12.588
    assert first.latency_p95_ms == 14.338
    assert first.throughput_fps == 79.441
    assert first.stderr == ""
