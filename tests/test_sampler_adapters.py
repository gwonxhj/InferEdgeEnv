from __future__ import annotations

import sys
from pathlib import Path

import pytest

from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.samplers.base import (
    SamplerContext,
    SamplerNoSamples,
    SamplerStartFailedRequired,
    SamplerSummary,
    SamplerUnavailable,
    SamplerUnparseableOutput,
)
from inferedge_env.samplers.jetson_tegrastats import (
    JetsonTegrastatsSampler,
    parse_tegrastats_line,
    summarize_tegrastats_samples,
)


def test_sampler_summary_metadata_is_json_ready(tmp_path):
    summary = SamplerSummary(
        resource_metrics=ResourceMetrics(memory_peak_mb=128.0),
        metadata={
            "schema_version": "edgeenv.sampler-metadata.v1",
            "sampler_name": "test-sampler",
        },
        raw_artifacts=[tmp_path / "sampler" / "raw.log"],
        warnings=["warning"],
    )

    assert summary.resource_metrics is not None
    assert summary.raw_artifacts == [tmp_path / "sampler" / "raw.log"]
    assert summary.warnings == ["warning"]


def test_parse_tegrastats_line_extracts_supported_fields():
    sample = parse_tegrastats_line(
        "05-07-2026 21:21:53 RAM 848/7620MB (lfb 3x4MB) "
        "CPU [2%@729,5%@729] GR3D_FREQ 0% cpu@35.593C gpu@36.437C "
        "VDD_IN 4408mW/4408mW VDD_SOC 1373mW/1373mW"
    )

    assert sample is not None
    assert sample.memory_used_mb == 848.0
    assert sample.vdd_in_instant_w == 4.408
    assert sample.vdd_in_average_w == 4.408
    assert sample.temperature_peak_c == 36.437


def test_summarize_tegrastats_samples_builds_metrics_and_metadata():
    lines = [
        (
            "RAM 848/7620MB CPU [2%@729] cpu@35.593C gpu@36.437C "
            "VDD_IN 4408mW/4408mW"
        ),
        (
            "RAM 852/7620MB CPU [0%@729] cpu@35.5C gpu@36.468C "
            "VDD_IN 4247mW/4314mW"
        ),
    ]

    metrics, metadata = summarize_tegrastats_samples(
        lines,
        sampling_interval_ms=500,
        startup_wait_ms=600,
        platform_tool_path="/usr/bin/tegrastats",
        raw_artifact="sampler/tegrastats.log",
    )

    assert metrics.memory_mean_mb == 850.0
    assert metrics.memory_peak_mb == 852.0
    assert metrics.power_mean_w == 4.361
    assert metrics.power_peak_w == 4.408
    assert metrics.temperature_peak_c == 36.468
    assert metrics.source == "jetson-tegrastats"
    assert metadata["schema_version"] == "edgeenv.sampler-metadata.v1"
    assert metadata["sample_count"] == 2
    assert metadata["sampling_scope"] == "host"
    assert metadata["fields"]["power_mean_w"]["source_field"] == "VDD_IN average"
    assert metadata["raw_artifacts"] == ["sampler/tegrastats.log"]


def test_summarize_tegrastats_samples_rejects_empty_or_unparseable_lines():
    with pytest.raises(SamplerNoSamples):
        summarize_tegrastats_samples([])

    with pytest.raises(SamplerUnparseableOutput):
        summarize_tegrastats_samples(["not tegrastats output"])


def test_jetson_sampler_unavailable_is_recoverable(tmp_path):
    sampler = JetsonTegrastatsSampler(
        tegrastats_path="missing-tegrastats-for-test",
        required=False,
    )
    context = _context(tmp_path)

    sampler.start(context)
    sampler.stop()
    summary = sampler.summary()

    assert summary.resource_metrics is None
    assert "tegrastats unavailable" in summary.warnings[0]
    assert summary.metadata["sampler_name"] == "jetson-tegrastats"
    assert summary.metadata["sample_count"] == 0


def test_jetson_sampler_unavailable_required_fails(tmp_path):
    sampler = JetsonTegrastatsSampler(
        tegrastats_path="missing-tegrastats-for-test",
        required=True,
    )

    with pytest.raises(SamplerStartFailedRequired):
        sampler.start(_context(tmp_path))


def test_jetson_sampler_process_writes_raw_artifact_and_summary(tmp_path, monkeypatch):
    class FakeProcess:
        def terminate(self):
            return None

        def communicate(self, timeout=None):
            return (
                "RAM 100/7620MB cpu@35.0C gpu@36.0C VDD_IN 4000mW/4000mW\n",
                "",
            )

    monkeypatch.setattr(
        "inferedge_env.samplers.jetson_tegrastats.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(),
    )
    sampler = JetsonTegrastatsSampler(
        tegrastats_path="tegrastats",
        interval_ms=50,
        startup_wait_ms=0,
    )

    sampler.start(_context(tmp_path))
    sampler.stop()
    summary = sampler.summary()

    assert summary.resource_metrics is not None
    assert summary.resource_metrics.memory_peak_mb == 100.0
    assert summary.resource_metrics.power_mean_w == 4.0
    assert summary.resource_metrics.temperature_peak_c == 36.0
    assert summary.metadata["sample_count"] == 1
    assert summary.raw_artifacts == [tmp_path / "sampler" / "tegrastats.log"]
    assert (tmp_path / "sampler" / "tegrastats.log").read_text(
        encoding="utf-8"
    ).startswith("RAM 100/7620MB")


def test_jetson_sampler_maps_permission_error_to_unavailable(tmp_path):
    fake_sampler = tmp_path / "tegrastats"
    fake_sampler.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_sampler.chmod(0o644)
    sampler = JetsonTegrastatsSampler(
        tegrastats_path=str(fake_sampler),
        required=False,
    )

    sampler.start(_context(tmp_path))
    sampler.stop()
    summary = sampler.summary()

    assert summary.resource_metrics is None
    assert summary.warnings
    assert summary.metadata["sample_count"] == 0


def _context(tmp_path: Path) -> SamplerContext:
    return SamplerContext(
        run_id="run-sampler-test",
        benchmark_name="sampler-test",
        target_name="jetson-test",
        target_type="local",
        command=[sys.executable, "-c", "print('benchmark')"],
        artifact_dir=tmp_path,
    )
