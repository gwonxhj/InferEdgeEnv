from __future__ import annotations

from pathlib import Path

import pytest

from edgeenv.config.bench_config import BenchmarkConfig
from edgeenv.config.target_profile import TargetProfile


@pytest.fixture
def bench_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        name="yolov8n-fire-fake",
        command="python run_yolov8n.py --input fire.jpg",
        model_name="yolov8n-fire",
        model_version="1.0",
        model_format="onnx",
        model_path="models/yolov8n-fire.onnx",
        task="object-detection",
        input_shape=[1, 3, 640, 640],
        input_dtype="float32",
        runtime="fake-runtime",
        execution_provider="fake-provider",
        precision="fp32",
        batch_size=1,
        warmup_runs=3,
        repeat_runs=10,
        include_preprocess=True,
        include_postprocess=True,
    )


@pytest.fixture
def target_profile() -> TargetProfile:
    return TargetProfile(
        target_name="local-fake",
        target_type="fake",
        board_name="local-dev-machine",
        os="macOS",
        runtime_tags=["fake", "local"],
    )


@pytest.fixture
def config_files(tmp_path: Path) -> tuple[Path, Path]:
    bench_path = tmp_path / "bench.yaml"
    profile_path = tmp_path / "profile.yaml"
    bench_path.write_text(
        """
name: yolov8n-fire-fake
command: python run_yolov8n.py --input fire.jpg
model_name: yolov8n-fire
model_version: "1.0"
model_format: onnx
model_path: models/yolov8n-fire.onnx
task: object-detection
input_shape: [1, 3, 640, 640]
input_dtype: float32
runtime: fake-runtime
execution_provider: fake-provider
precision: fp32
batch_size: 1
warmup_runs: 3
repeat_runs: 10
include_preprocess: true
include_postprocess: true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    profile_path.write_text(
        """
target_name: local-fake
target_type: fake
board_name: local-dev-machine
os: macOS
runtime_tags: [fake, local]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return bench_path, profile_path
