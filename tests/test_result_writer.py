from __future__ import annotations

import json

from inferedge_env.result.writer import FailedRunArtifactWriter, ResultArtifactWriter
from inferedge_env.runners.fake import FakeRunner
from helpers import make_result


def test_result_json_files_created(tmp_path, bench_config, target_profile, config_files):
    bench_path, profile_path = config_files
    runner_result = FakeRunner().run(bench_config, target_profile)
    result = make_result(bench_config, target_profile, run_id="run-artifact")

    run_dir = ResultArtifactWriter(tmp_path / ".edgeenv").write(
        result,
        bench_path,
        profile_path,
        runner_result.stdout,
        runner_result.stderr,
    )

    assert (run_dir / "result.json").is_file()
    assert (run_dir / "config.yaml").is_file()
    assert (run_dir / "target.yaml").is_file()
    assert (run_dir / "env.json").is_file()
    assert (run_dir / "stdout.log").read_text(encoding="utf-8")
    assert (run_dir / "stderr.log").read_text(encoding="utf-8") == ""
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-artifact"
    assert payload["schema_version"] == "edgeenv.result.v1"


def test_failed_run_artifact_files_created(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    bench_path, profile_path = config_files

    failed_dir = FailedRunArtifactWriter(tmp_path / ".edgeenv").write(
        config=bench_config,
        target=target_profile,
        config_path=bench_path,
        target_path=profile_path,
        error_message="Local benchmark command failed with exit code 7",
        stdout="failed stdout\n",
        stderr="failed stderr\n",
        return_code=7,
        run_id="run-failed",
        env={"python_version": "test"},
    )

    assert (failed_dir / "failure.json").is_file()
    assert (failed_dir / "config.yaml").is_file()
    assert (failed_dir / "target.yaml").is_file()
    assert (failed_dir / "env.json").is_file()
    assert (failed_dir / "stdout.log").read_text(encoding="utf-8") == "failed stdout\n"
    assert (failed_dir / "stderr.log").read_text(encoding="utf-8") == "failed stderr\n"
    payload = json.loads((failed_dir / "failure.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "edgeenv.failed-run.v1"
    assert payload["run_id"] == "run-failed"
    assert payload["return_code"] == 7
    assert payload["error_type"] == "LocalRunnerError"
