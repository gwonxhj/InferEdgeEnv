# Compare Workflow Guide

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT — What This Document Defines

This guide walks through an end-to-end comparison flow: create two benchmark runs, inspect them with `runs list` and `runs show`, then use `report compare` to judge whether the results can be compared.

EdgeEnv compare does not rank runs with a single score. It first decides whether two runs are directly comparable, conditionally comparable as runtime/target comparisons, or not comparable at all.

## 2. CONTENTS — Files And Stack

Related files:

- `inferedge_env/compare/comparability.py` — compare rule implementation
- `inferedge_env/cli.py` — `runs list`, `runs show`, `report compare`
- `examples/benches/local_compare_a.yaml` — first same-condition local run example
- `examples/benches/local_compare_b.yaml` — second same-condition local run example
- `examples/scripts/emit_compare_metrics.py` — deterministic compare workflow fixture
- `docs/local-command-contract.md` — local command stdout contract

Stack: Typer CLI, SQLite registry, JSON artifacts, deterministic local command examples

## 3. HOW — Compare Workflow

### 1. Create Two Successful Runs

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
```

These example configs use the same model identity, input shape, task, precision, batch size, warmup/repeat protocol, runtime, execution provider, and target. Only the metric values differ, so EdgeEnv can treat them as a direct same-condition comparison.

### 2. Find Run IDs

```bash
edgeenv runs list
```

You can also use the `Run ID` printed by each `bench run` command.

### 3. Inspect Evidence

```bash
edgeenv runs show <run_id>
```

`runs show` uses both the registry row and the result artifact. If resource metrics exist, it reads them from the artifact, but resource metrics are not a direct comparability gate.

### 4. Compare

```bash
edgeenv report compare <run_id_a> <run_id_b>
```

Expected same-condition output:

```text
Comparable: Yes
Mode: same-condition
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
Metrics Delta:
- latency_mean_ms: 18.0 ms -> 16.4 ms (delta -1.6 ms, -8.89%)
- latency_p50_ms: 17.6 ms -> 16.0 ms (delta -1.6 ms, -9.09%)
- latency_p95_ms: 20.5 ms -> 18.2 ms (delta -2.3 ms, -11.22%)
- latency_p99_ms: 22.0 ms -> 19.7 ms (delta -2.3 ms, -10.45%)
- throughput_fps: 55.5 fps -> 61.0 fps (delta +5.5 fps, +9.91%)
```

`Metrics Delta` is supplemental evidence and appears only after `Comparable: Yes` with `Mode: same-condition`. Conditional or non-comparable reports suppress metric deltas because the CLI should not imply a direct regression comparison across runtime, provider, target, or protocol differences.

For the same principle on real sampled Jetson evidence, see [Jetson Sampled Comparison Rehearsal](jetson-sampled-comparison-rehearsal.md). That flow confirms `sampler/metadata.json` and `resource_metrics` remain supplemental artifacts and do not become compare gates.

For the conditional branch on real sampled Jetson evidence, see [Jetson Sampled Conditional Comparison Rehearsal](jetson-sampled-conditional-comparison-rehearsal.md). That flow changes only `execution_provider` and verifies `Metrics Delta` is suppressed.

For the target branch on real sampled Jetson evidence, see [Jetson Sampled Target Comparison Rehearsal](jetson-sampled-target-comparison-rehearsal.md). That flow changes only target profile metadata and verifies `Mode: target-comparison`.

For portability across workspaces, see [Jetson Sampled Evidence Bundle Handoff](jetson-sampled-evidence-bundle-handoff.md). That flow exports/imports same-condition, runtime-conditional, and target-conditional sampled bundles, then compares the imported runs.

### Reading Outcomes

| Output | Meaning | Next action |
| --- | --- | --- |
| `Comparable: Yes`, `Mode: same-condition` | Required fields, runtime, provider, and target match | Inspect the supplemental latency/throughput deltas |
| `Comparable: Conditional`, `Mode: runtime-comparison` | Required fields match, but runtime or execution provider differs | Treat as runtime/provider comparison, not direct regression |
| `Comparable: Conditional`, `Mode: target-comparison` | Required fields match, but target differs | Treat as target/platform comparison |
| `Comparable: No` | Required fields differ | Do not make direct regression claims |

### Runtime Regression Report

Use `report regression` when the compare judgement should be saved as
machine-readable runtime regression evidence:

```bash
edgeenv report regression <baseline_run_id> <candidate_run_id> \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output-json /tmp/edgeenv-regression.json \
  --output-md /tmp/edgeenv-regression.md
```

The command follows the same comparability-first rule as `report compare`.
It calculates mean/p95/p99/FPS/resource deltas only for
`Comparable: Yes` with `Mode: same-condition`. Conditional runtime/provider or
target comparisons are labelled as `runtime-comparison` or
`target-comparison`, and protocol mismatches are labelled
`protocol_mismatch` with a rerun recommendation. This keeps regression evidence
separate from runtime behavior comparisons and target/platform comparisons.

If a runtime telemetry history artifact is available, pass
`--telemetry-history` to attach coverage and evidence-gap context to the
regression report. Telemetry context remains supplemental evidence; it never
bypasses the same-condition comparability gate.

Committed replay-context examples are available when downstream tools need a
small EdgeEnv-owned fixture without running a benchmark:

- `examples/regression/edgeenv_candidate_telemetry_gap.json` shows a comparable
  same-condition report where the candidate run is missing runtime telemetry in
  both the result artifact and telemetry history.
- `examples/regression/edgeenv_sequence_inversion.json` shows a comparable
  same-condition report where baseline/candidate `execution_sequence_id` order
  is inverted in the replay context.

These examples intentionally do not include `guard_analysis` or a deployment
decision. EdgeEnv owns the registry, replay context, comparability judgement,
and regression evidence; AIGuard and Lab consume the artifact later.

Default starter thresholds:

| Signal | Threshold | Meaning |
| --- | ---: | --- |
| Mean latency | +15% | review |
| P99 latency | +25% | review / high severity |
| FPS | -20% | review |
| Memory peak | +30% | warning |

## 4. HOW NOT — What To Avoid

- Do not conclude regression from mean latency in `runs list` alone.
- Do not treat `Comparable: Conditional` as a failure. It is a separate interpretation mode for runtime or target differences.
- Do not mark runs as `Comparable: No` only because resource metrics are absent.
- Do not ignore differences in model hash, input shape, precision, batch size, warmup runs, repeat runs, or preprocess/postprocess boundaries.
- Do not use compare output as a public leaderboard or single-score ranking surface.

## 5. WHERE — Related Design Boundaries

- **Local Command Contract Guide**: the input contract for creating valid local result artifacts.
- **Local Runner Design**: the run creation step depends on the local runner.
- **Resource Metrics Design**: resource metrics are secondary evidence, not compare gates.
- **Jetson Sampled Comparison Rehearsal**: validates the same rule on real `tegrastats` sampled runs.
- **Jetson Sampled Conditional Comparison Rehearsal**: validates runtime/provider conditional mode and metric delta suppression on sampled runs.
- **Jetson Sampled Target Comparison Rehearsal**: validates target-comparison mode and metric delta suppression on sampled runs.
- **Jetson Sampled Evidence Bundle Handoff**: validates that imported sampled bundles keep the same compare judgement.
- **Registry Resource Query Design**: compare reads the result artifact through the registry `result_path`.

## 6. WHY — Background Judgment

The most common edge benchmark mistake is comparing two latency numbers before checking whether the runs were measured under the same conditions. EdgeEnv puts the comparability judgement first so users do not make false regression claims or overstate runtime/target comparisons.

This guide shows EdgeEnv's core value in CLI form: record first, compare honestly.

## 7. LEARNED CAUTIONS — Learned Cautions

_(None yet)_
