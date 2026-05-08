from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from inferedge_env import __version__

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_metadata_declares_edgeenv_console_script():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["name"] == "inferedge-env"
    assert project["version"] == __version__
    assert project["scripts"]["edgeenv"] == "inferedge_env.cli:main"
    assert "pytest>=8.0" in project["optional-dependencies"]["dev"]
    assert "tomli>=2.0; python_version < '3.11'" in project["optional-dependencies"]["dev"]


def test_python_module_doctor_entrypoint():
    result = subprocess.run(
        [sys.executable, "-m", "inferedge_env.cli", "doctor"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "EdgeEnv doctor: OK" in result.stdout
    assert f"Version: {__version__}" in result.stdout


def test_console_script_doctor_entrypoint_available_after_install():
    edgeenv = shutil.which("edgeenv")

    assert edgeenv is not None, "Run python -m pip install -e '.[dev]' first"
    result = subprocess.run(
        [edgeenv, "doctor"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "EdgeEnv doctor: OK" in result.stdout
    assert f"Version: {__version__}" in result.stdout


def test_jetson_source_env_smoke_script_help():
    result = subprocess.run(
        ["bash", "scripts/smoke_jetson_source_env.sh", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Usage: scripts/smoke_jetson_source_env.sh" in result.stdout
    assert "PYTHONPATH" in result.stdout
    assert "Jetson source-snapshot sampler smoke" in result.stdout


def test_jetson_source_env_smoke_script_rejects_missing_option_value():
    result = subprocess.run(
        ["bash", "scripts/smoke_jetson_source_env.sh", "--python"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Missing value for --python" in result.stderr
