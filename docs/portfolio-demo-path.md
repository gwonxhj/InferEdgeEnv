# Portfolio Demo Path

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

InferEdgeEnv를 포트폴리오, 리뷰, 인터뷰에서 짧고 반복 가능하게 보여주기 위한 canonical demo path를 정한다.

핵심 메시지:

```text
InferEdge validates whether a model is deployable.
InferEdgeEnv records whether benchmark evidence can be trusted and compared.
```

InferEdgeEnv is a local-first run evidence registry and comparability checker for Edge AI inference benchmark results. This demo shows evidence recording, comparability judgement, artifact portability, and optional Jetson sampled evidence without turning the project into a runner leaderboard or deployment decision layer.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `README.md` — first-user Quickstart and Guide Map
- `examples/profiles/local_fake.yaml` — deterministic fake target
- `examples/profiles/local.yaml` — local target profile for command examples
- `examples/benches/yolov8n_fire.yaml` — fake run config
- `examples/benches/local_adapter_template.yaml` — copyable real-command adapter template
- `examples/benches/local_compare_a.yaml`, `examples/benches/local_compare_b.yaml` — same-condition compare pair
- `examples/profiles/jetson_nano_sampled_local.yaml` — optional Jetson sampled profile
- `examples/benches/jetson_sampled_local.yaml` — optional Jetson sampled config
- `scripts/smoke_jetson_sampled_bundle_handoff.sh` — optional Jetson export/import/compare/bundle-summary smoke
- `docs/local-command-contract.md` — local command stdout contract
- `docs/compare-workflow-guide.md` — comparability interpretation
- `docs/export-import-design.md` — evidence bundle manifest/checksum/import policy
- `docs/schema-versioning-migration-policy.md` — schema compatibility and future-version rejection policy
- `docs/jetson-sampled-evidence-bundle-handoff.md` — real Jetson sampled bundle validation record
- `docs/bundle-report-generation-design.md` — read-only Markdown handoff summary contract

기술 스택: Typer CLI, Rich output, Pydantic schemas, local filesystem artifacts, SQLite registry, zip export/import, optional Jetson `tegrastats`

## 3. HOW — demo path

### Lane A: local-only reviewer demo

Use this lane first. It does not require Jetson hardware or real model files.

#### 0. Install and choose an isolated demo root

```bash
python -m pip install -e ".[dev]"
edgeenv doctor

export EDGEENV_DEMO_ROOT=/tmp/inferedgeenv-portfolio-demo
rm -rf "$EDGEENV_DEMO_ROOT"
mkdir -p "$EDGEENV_DEMO_ROOT"
```

#### 1. Record deterministic fake evidence

```bash
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench run \
  --target examples/profiles/local_fake.yaml \
  --config examples/benches/yolov8n_fire.yaml \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
edgeenv runs list --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
```

What this demonstrates:

- CLI and config validation work.
- A run artifact is created under `.edgeenv/runs/<run_id>/`.
- FakeRunner keeps the first demo deterministic and hardware-independent.

Expected artifact shape:

```text
$EDGEENV_DEMO_ROOT/.edgeenv/
  runs.db
  runs/<run_id>/
    result.json
    config.yaml
    target.yaml
    env.json
    stdout.log
    stderr.log
```

#### 2. Show the real-command adapter boundary

```bash
edgeenv bench run \
  --target examples/profiles/local.yaml \
  --config examples/benches/local_adapter_template.yaml \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
```

What this demonstrates:

- EdgeEnv does not own the model runner, dataset, or measurement loop.
- A user-owned command can be wrapped as long as it emits `EDGEENV_METRICS_JSON=...`.
- Optional resource metrics stay supplemental and do not become compare gates.

#### 3. Create two same-condition local runs

```bash
edgeenv bench run \
  --target examples/profiles/local.yaml \
  --config examples/benches/local_compare_a.yaml \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
edgeenv bench run \
  --target examples/profiles/local.yaml \
  --config examples/benches/local_compare_b.yaml \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
edgeenv runs list --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
```

Copy the two `Run ID` values from the compare runs:

```bash
export RUN_A=<local_compare_a_run_id>
export RUN_B=<local_compare_b_run_id>
```

#### 4. Compare only after comparability judgement

```bash
edgeenv runs show "$RUN_A" --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
edgeenv report compare "$RUN_A" "$RUN_B" --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
```

What this demonstrates:

- `Comparable` and `Mode` appear before any metric delta.
- Same-condition comparisons may show latency/throughput delta.
- Conditional and non-comparable paths must not be described as direct regressions.
- EdgeEnv does not rank all models with a composite score.

Expected same-condition judgement:

```text
Comparable: Yes
Mode: same-condition
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
Metrics Delta:
...
```

#### 5. Export/import the evidence bundle

```bash
mkdir -p "$EDGEENV_DEMO_ROOT/bundles"
edgeenv runs export "$RUN_A" \
  --output "$EDGEENV_DEMO_ROOT/bundles/edgeenv-run-$RUN_A.zip" \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"
edgeenv runs export "$RUN_B" \
  --output "$EDGEENV_DEMO_ROOT/bundles/edgeenv-run-$RUN_B.zip" \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/.edgeenv"

edgeenv runs import "$EDGEENV_DEMO_ROOT/bundles/edgeenv-run-$RUN_A.zip" \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/imported.edgeenv"
edgeenv runs import "$EDGEENV_DEMO_ROOT/bundles/edgeenv-run-$RUN_B.zip" \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/imported.edgeenv"

edgeenv report compare "$RUN_A" "$RUN_B" \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/imported.edgeenv"
```

What this demonstrates:

- The zip bundle carries artifact evidence, not `runs.db`.
- Import validates manifest/checksum/path safety and rebuilds the registry from `result.json`.
- Compare interpretation survives handoff into a fresh registry root.

#### 6. Generate a read-only handoff summary

```bash
edgeenv report bundle-summary \
  --scenario same-condition:"$RUN_A":"$RUN_B" \
  --edgeenv-root "$EDGEENV_DEMO_ROOT/imported.edgeenv" \
  --output "$EDGEENV_DEMO_ROOT/bundle-summary.md"
```

What this demonstrates:

- Markdown summary is for human handoff only.
- It does not replace `result.json`, sampler artifacts, manifest validation, or `report compare`.
- It must not introduce ranking or composite-score language.

### Lane B: optional Jetson sampled evidence

Use this lane only when a Jetson shell is available and the repo is already on the Jetson filesystem. It is optional; the portfolio demo must remain understandable without hardware.

Single sampled run:

```bash
edgeenv bench run \
  --target examples/profiles/jetson_nano_sampled_local.yaml \
  --config examples/benches/jetson_sampled_local.yaml
edgeenv runs sampler show <run_id>
```

Full sampled bundle handoff smoke:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output /tmp/InferEdgeEnv-jetson-bundle-summary.md \
  --bundle-summary-source-device nano01 \
  --keep-artifacts
```

What this demonstrates:

- `tegrastats` evidence is stored as optional sampler/resource evidence.
- `sampler/metadata.json` and raw sampler artifacts move through export/import.
- Same-condition sampled compares may show metric delta.
- Runtime/target conditional sampled compares suppress metric delta.
- Sampler/resource evidence remains supplemental and does not change compare mode.

## 4. HOW NOT — 피해야 할 함정

- Do not require Jetson for the main demo path.
- Do not claim EdgeEnv validates deployment readiness. That belongs to InferEdgeLab.
- Do not describe `EDGEENV_METRICS_JSON=` as automatic runtime log parsing. The benchmark command or adapter must emit explicit JSON.
- Do not present resource metrics, sampler metadata, or bundle summaries as comparability gates.
- Do not show conditional compare as a direct regression result.
- Do not export `runs.db` or treat SQLite rows as canonical evidence.
- Do not add leaderboard, ranking, composite score, cloud sync, auth, dashboard, Docker, WSL, SSH target, model upload, or dataset upload semantics to the demo.

## 5. WHERE — 다른 설계와의 관계

- **Local Command Contract Guide**: explains the stdout metrics contract used by local adapter examples.
- **Compare Workflow Guide**: defines same-condition, runtime-comparison, target-comparison, and no-comparison interpretation.
- **Export/Import Design**: defines evidence bundle manifest, checksum, path safety, and registry rebuild behavior.
- **Schema Versioning And Migration Policy**: defines accepted schema markers and unknown future-version rejection.
- **Jetson Sampled Evidence Bundle Handoff**: validates the optional hardware lane on real sampled Jetson evidence.
- **Bundle Report Generation Design**: defines `report bundle-summary` as a read-only human summary.

## 6. WHY — 배경 판단

Portfolio reviewers need a short route from thesis to proof.

This path demonstrates the InferEdgeEnv boundary:

- It records benchmark evidence as local artifacts and SQLite registry rows.
- It judges whether two results can be compared directly, conditionally, or not at all.
- It preserves evidence through export/import.
- It summarizes handoff evidence without replacing machine-verifiable artifacts.

That is distinct from InferEdgeLab, which is the validation/decision layer. InferEdgeEnv does not decide deployment readiness; it records whether benchmark evidence can be trusted and compared.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
