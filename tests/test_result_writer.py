from __future__ import annotations

import json

from edgeenv.result.writer import ResultArtifactWriter
from edgeenv.runners.fake import FakeRunner
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
