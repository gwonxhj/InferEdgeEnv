from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from inferedge_env.cli import app
from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.registry.db import RunRegistry
from inferedge_env.report.bundle_summary import (
    BundleScenario,
    render_bundle_summary_markdown,
)
from inferedge_env.result.writer import ResultArtifactWriter
from helpers import make_result


def test_bundle_summary_generates_markdown_for_three_scenarios(
    tmp_path: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
) -> None:
    edgeenv_root = tmp_path / ".edgeenv"
    same_a = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-a")
    same_b = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-b")
    runtime_a = _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "run-runtime-a",
    )
    runtime_b = _write_registered_run(
        edgeenv_root,
        bench_config.model_copy(update={"runtime": "fake-runtime-alt"}),
        target_profile,
        "run-runtime-b",
    )
    target_a = _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "run-target-a",
    )
    target_b = _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile.model_copy(update={"target_name": "local-fake-alt"}),
        "run-target-b",
    )
    for run_id in [same_a, same_b, runtime_a, runtime_b, target_a, target_b]:
        _write_sampler_metadata(edgeenv_root / "runs" / run_id)

    markdown = render_bundle_summary_markdown(
        [
            BundleScenario("same-condition", same_a, same_b),
            BundleScenario("runtime-conditional", runtime_a, runtime_b),
            BundleScenario("target-conditional", target_a, target_b),
        ],
        edgeenv_root=edgeenv_root,
    )

    assert "# EdgeEnv Evidence Bundle Handoff" in markdown
    assert (
        "| same-condition | run-a | run-b | core + sampler | "
        "metadata + raw log | absent | absent |"
    ) in markdown
    assert "| same-condition | Yes | same-condition | present | yes |" in markdown
    assert (
        "| runtime-conditional | Conditional | runtime-comparison | absent | yes |"
        in markdown
    )
    assert (
        "| target-conditional | Conditional | target-comparison | absent | yes |"
        in markdown
    )
    assert "- Sampler metadata present: yes" in markdown
    assert "- Raw sampler artifacts present: yes" in markdown
    assert "SHA-256/byte-size verification: previously validated during import" in (
        markdown
    )
    assert "ranking" not in markdown.lower()
    assert "composite score" not in markdown.lower()


def test_bundle_summary_preserves_scenario_order(
    tmp_path: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
) -> None:
    edgeenv_root = tmp_path / ".edgeenv"
    first = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-1")
    second = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-2")

    markdown = render_bundle_summary_markdown(
        [
            BundleScenario("second-label", second, first),
            BundleScenario("first-label", first, second),
        ],
        edgeenv_root=edgeenv_root,
    )

    assert markdown.index("| second-label |") < markdown.index("| first-label |")


def test_bundle_summary_allows_missing_optional_sampler_metadata(
    tmp_path: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
) -> None:
    edgeenv_root = tmp_path / ".edgeenv"
    first = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-1")
    second = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-2")

    markdown = render_bundle_summary_markdown(
        [BundleScenario("same-condition", first, second)],
        edgeenv_root=edgeenv_root,
    )

    assert "# EdgeEnv Evidence Bundle Handoff" in markdown
    assert "| same-condition | run-1 | run-2 | core | absent | absent | absent |" in markdown
    assert "- Sampler metadata present: no" in markdown
    assert "## Warnings" in markdown
    assert "run-1: sampler metadata absent" in markdown
    assert "run-2: resource metrics absent" in markdown


def test_bundle_summary_surfaces_runtime_operation_source(
    tmp_path: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
) -> None:
    edgeenv_root = tmp_path / ".edgeenv"
    first = _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "run-1",
        runtime_operation_summary={
            "source": "inferedge-runtime",
            "health_reason": "completed",
        },
    )
    second = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-2")

    markdown = render_bundle_summary_markdown(
        [BundleScenario("same-condition", first, second)],
        edgeenv_root=edgeenv_root,
    )

    assert (
        "| same-condition | run-1 | run-2 | core | absent | absent | "
        "inferedge-runtime / absent |"
    ) in markdown
    assert "runtime operation evidence was supplemental" in markdown


def test_bundle_summary_fails_when_required_artifact_is_missing(
    tmp_path: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
) -> None:
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    first = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-1")
    second = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-2")
    (edgeenv_root / "runs" / second / "stderr.log").unlink()

    result = runner.invoke(
        app,
        [
            "report",
            "bundle-summary",
            "--scenario",
            f"same-condition:{first}:{second}",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 1
    assert "Required run artifact file missing for run-2: stderr.log" in result.output


def test_cli_bundle_summary_writes_output_file(
    tmp_path: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
) -> None:
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    output_path = tmp_path / "reports" / "bundle-summary.md"
    first = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-1")
    second = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-2")

    result = runner.invoke(
        app,
        [
            "report",
            "bundle-summary",
            "--scenario",
            f"same-condition:{first}:{second}",
            "--source-device",
            "test-device",
            "--note",
            "Manual handoff note.",
            "--output",
            str(output_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 0
    assert "Bundle summary written" in result.output
    markdown = output_path.read_text(encoding="utf-8")
    assert "- Source device: test-device" in markdown
    assert "- Manual handoff note." in markdown
    assert "| same-condition | Yes | same-condition | present | yes |" in markdown


def test_cli_bundle_summary_rejects_malformed_and_duplicate_scenarios(
    tmp_path: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
) -> None:
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    first = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-1")
    second = _write_registered_run(edgeenv_root, bench_config, target_profile, "run-2")

    malformed = runner.invoke(
        app,
        [
            "report",
            "bundle-summary",
            "--scenario",
            "same-condition:run-1",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )
    duplicate = runner.invoke(
        app,
        [
            "report",
            "bundle-summary",
            "--scenario",
            f"same-condition:{first}:{second}",
            "--scenario",
            f"same-condition:{second}:{first}",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert malformed.exit_code == 1
    assert "Scenario must use the form" in malformed.output
    assert duplicate.exit_code == 1
    assert "Duplicate scenario label: same-condition" in duplicate.output


def _write_registered_run(
    edgeenv_root: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
    run_id: str,
    runtime_operation_summary: dict | None = None,
) -> str:
    config_path = edgeenv_root.parent / f"{run_id}-config.yaml"
    target_path = edgeenv_root.parent / f"{run_id}-target.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("name: test\n", encoding="utf-8")
    target_path.write_text("target_name: test\n", encoding="utf-8")
    result = make_result(bench_config, target_profile, run_id=run_id)
    if runtime_operation_summary is not None:
        result = result.model_copy(
            update={"runtime_operation_summary": runtime_operation_summary}
        )
    run_dir = ResultArtifactWriter(edgeenv_root).write(
        result=result,
        config_path=config_path,
        target_path=target_path,
        stdout="stdout\n",
        stderr="stderr\n",
    )
    RunRegistry(edgeenv_root / "runs.db").insert(result, run_dir / "result.json")
    return run_id


def _write_sampler_metadata(run_dir: Path) -> None:
    sampler_dir = run_dir / "sampler"
    sampler_dir.mkdir()
    (sampler_dir / "tegrastats.log").write_text("sample\n", encoding="utf-8")
    (sampler_dir / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "edgeenv.sampler-metadata.v1",
                "sampler_name": "jetson-tegrastats",
                "platform_tool": "tegrastats",
                "sampling_scope": "host",
                "benchmark_window": "sampler-start-before-command-stop-after-command",
                "sample_count": 1,
                "raw_artifacts": ["sampler/tegrastats.log"],
                "fields": {},
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
