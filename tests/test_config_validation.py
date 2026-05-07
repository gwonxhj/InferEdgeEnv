from __future__ import annotations

import pytest

from inferedge_env.config.bench_config import BenchmarkConfig, load_benchmark_config
from inferedge_env.config.target_profile import (
    SamplerProfile,
    TargetProfile,
    load_target_profile,
)


def test_config_validation_success(config_files):
    bench_path, profile_path = config_files

    bench = load_benchmark_config(bench_path)
    profile = load_target_profile(profile_path)

    assert isinstance(bench, BenchmarkConfig)
    assert bench.input_shape == [1, 3, 640, 640]
    assert isinstance(profile, TargetProfile)
    assert profile.target_type == "fake"
    assert profile.sampler is None


def test_example_resource_metrics_config_validation():
    bench = load_benchmark_config("examples/benches/local_resource_metrics.yaml")
    profile = load_target_profile("examples/profiles/local.yaml")

    assert bench.command == "python examples/scripts/emit_resource_metrics.py"
    assert bench.extra_env == {"LOCAL_DEMO_FLAG": "resource-enabled"}
    assert profile.target_type == "local"


def test_example_sampler_wrapper_config_validation():
    bench = load_benchmark_config("examples/benches/local_sampler_wrapper.yaml")
    profile = load_target_profile("examples/profiles/local.yaml")

    assert bench.command == (
        "python examples/scripts/run_with_sampler.py -- "
        "python examples/scripts/emit_local_metrics.py"
    )
    assert bench.extra_env == {"LOCAL_DEMO_FLAG": "sampler-wrapper"}
    assert profile.target_type == "local"


def test_example_jetson_tegrastats_config_validation():
    bench = load_benchmark_config("examples/benches/jetson_tegrastats_local.yaml")
    profile = load_target_profile("examples/profiles/jetson_nano_local.yaml")

    assert "examples/scripts/run_with_tegrastats.py" in bench.command
    assert bench.extra_env == {"LOCAL_DEMO_FLAG": "jetson-tegrastats"}
    assert profile.target_type == "local"
    assert "jetson" in profile.runtime_tags
    assert profile.sampler is None


def test_target_profile_accepts_optional_sampler(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(
        """
target_name: jetson-nano-local
target_type: local
board_name: Jetson Nano
os: Ubuntu 22.04
runtime_tags:
  - jetson
sampler:
  name: jetson-tegrastats
  required: true
  interval_ms: 250
  startup_wait_ms: 100
  raw_log: false
  tegrastats_path: /usr/bin/tegrastats
""".strip(),
        encoding="utf-8",
    )

    profile = load_target_profile(path)

    assert isinstance(profile.sampler, SamplerProfile)
    assert profile.sampler.name == "jetson-tegrastats"
    assert profile.sampler.required is True
    assert profile.sampler.interval_ms == 250
    assert profile.sampler.startup_wait_ms == 100
    assert profile.sampler.raw_log is False
    assert profile.sampler.tegrastats_path == "/usr/bin/tegrastats"


def test_target_profile_rejects_unknown_sampler(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(
        """
target_name: local
target_type: local
board_name: dev
os: macOS
runtime_tags: []
sampler:
  name: unknown-sampler
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid target profile"):
        load_target_profile(path)


def test_config_validation_local_execution_options(tmp_path):
    path = tmp_path / "bench.yaml"
    path.write_text(
        """
name: local-options
command: python bench.py
model_name: demo
model_version: "1"
model_format: onnx
model_path: model.onnx
task: classification
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: local-python
execution_provider: cpu
precision: fp32
batch_size: 1
warmup_runs: 1
repeat_runs: 3
include_preprocess: true
include_postprocess: true
timeout_seconds: 5
working_directory: examples
extra_env:
  LOCAL_FLAG: enabled
""".strip(),
        encoding="utf-8",
    )

    config = load_benchmark_config(path)

    assert config.timeout_seconds == 5
    assert config.working_directory == "examples"
    assert config.extra_env == {"LOCAL_FLAG": "enabled"}


def test_config_validation_rejects_reserved_extra_env(tmp_path):
    path = tmp_path / "bench.yaml"
    path.write_text(
        """
name: local-options
command: python bench.py
model_name: demo
model_version: "1"
model_format: onnx
model_path: model.onnx
task: classification
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: local-python
execution_provider: cpu
precision: fp32
batch_size: 1
warmup_runs: 1
repeat_runs: 3
include_preprocess: true
include_postprocess: true
extra_env:
  EDGEENV_MODEL_NAME: bad
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reserved EDGEENV_ prefix"):
        load_benchmark_config(path)


def test_config_validation_failure(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
name: broken
command: echo broken
model_name: demo
model_version: "1"
model_format: onnx
model_path: model.onnx
task: classification
input_shape: [1, 0]
input_dtype: float32
runtime: fake
execution_provider: fake
precision: fp32
batch_size: 0
warmup_runs: 0
repeat_runs: 1
include_preprocess: true
include_postprocess: true
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid benchmark config"):
        load_benchmark_config(path)
