from __future__ import annotations

import pytest

from edgeenv.config.bench_config import BenchmarkConfig, load_benchmark_config
from edgeenv.config.target_profile import TargetProfile, load_target_profile


def test_config_validation_success(config_files):
    bench_path, profile_path = config_files

    bench = load_benchmark_config(bench_path)
    profile = load_target_profile(profile_path)

    assert isinstance(bench, BenchmarkConfig)
    assert bench.input_shape == [1, 3, 640, 640]
    assert isinstance(profile, TargetProfile)
    assert profile.target_type == "fake"


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
