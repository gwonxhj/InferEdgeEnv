from __future__ import annotations

from typer.testing import CliRunner

from edgeenv.cli import app


def test_cli_doctor():
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "EdgeEnv doctor: OK" in result.output


def test_cli_bench_run_with_fake_profile(tmp_path, config_files):
    runner = CliRunner()
    bench_path, profile_path = config_files
    edgeenv_root = tmp_path / ".edgeenv"

    result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            str(profile_path),
            "--config",
            str(bench_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 0
    assert "Benchmark run stored" in result.output
    assert (edgeenv_root / "runs.db").is_file()
    run_dirs = list((edgeenv_root / "runs").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "result.json").is_file()
