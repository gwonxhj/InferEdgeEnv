from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path("examples/scripts/run_with_tegrastats.py")


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "run_with_tegrastats",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summarize_tegrastats_parses_jetson_sample():
    module = _load_module()
    lines = [
        (
            "05-07-2026 21:21:53 RAM 848/7620MB (lfb 3x4MB) "
            "CPU [2%@729,5%@729] GR3D_FREQ 0% cpu@35.593C gpu@36.437C "
            "VDD_IN 4408mW/4408mW VDD_SOC 1373mW/1373mW"
        ),
        (
            "05-07-2026 21:21:54 RAM 852/7620MB (lfb 3x4MB) "
            "CPU [0%@729,1%@729] GR3D_FREQ 0% cpu@35.5C gpu@36.468C "
            "VDD_IN 4247mW/4314mW VDD_SOC 1334mW/1347mW"
        ),
    ]

    summary = module.summarize_tegrastats(lines)

    assert summary is not None
    assert summary.memory_mean_mb == 850.0
    assert summary.memory_peak_mb == 852.0
    assert summary.power_mean_w == 4.361
    assert summary.power_peak_w == 4.408
    assert summary.temperature_peak_c == 36.468


def test_summarize_tegrastats_returns_none_for_unparseable_lines():
    module = _load_module()

    assert module.summarize_tegrastats(["not tegrastats output"]) is None


def test_tegrastats_wrapper_omits_resource_metrics_when_sampler_unavailable():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--tegrastats-path",
            "missing-tegrastats-for-test",
            "--",
            sys.executable,
            "examples/scripts/emit_local_metrics.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "tegrastats unavailable; resource metrics omitted" in result.stderr
    assert "EDGEENV_METRICS_JSON=" in result.stdout
    assert "EDGEENV_RESOURCE_METRICS_JSON=" not in result.stdout


def test_resource_metrics_payload_omits_unavailable_fields():
    module = _load_module()
    summary = module.TegrastatsSummary(
        memory_mean_mb=100.0,
        memory_peak_mb=120.0,
        power_mean_w=None,
        power_peak_w=4.0,
        temperature_peak_c=36.0,
    )

    payload = module._resource_metrics_payload(summary, "jetson-tegrastats")

    assert payload["source"] == "jetson-tegrastats"
    assert payload["memory_mean_mb"] == 100.0
    assert payload["memory_peak_mb"] == 120.0
    assert "power_mean_w" not in payload
    assert payload["temperature_peak_c"] == 36.0
