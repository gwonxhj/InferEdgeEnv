# InferEdgeEnv Portfolio Summary

> Language: English | [한국어/원문](language.md#korean-overview)

InferEdgeEnv is a local-first run evidence registry and comparability checker for Edge AI inference benchmark results.

Release baseline: `v0.1.5` freezes InferEdgeEnv v1 as complete for this role. Future SSH, remote, cloud, dashboard, or broader target work belongs to v1.1+ extensions.

## 30-Second Structure

```text
User-owned benchmark command
-> EdgeEnv local runner / FakeRunner
-> .edgeenv/runs/<run_id>/ artifacts
-> SQLite registry index
-> comparability checker
-> optional runtime regression report
-> optional export/import bundle
-> optional read-only bundle summary
```

InferEdgeEnv answers a narrow question:

```text
Can this benchmark evidence be trusted and compared?
```

It does not answer whether a model should be deployed. That decision belongs to InferEdgeLab.

## One-Line Role

| Area | Role | Boundary |
|---|---|---|
| Config schema | Captures benchmark protocol and target identity | Does not standardize every model or dataset |
| FakeRunner | Produces deterministic evidence for tests and demos | Does not execute a real model |
| LocalRunner | Runs a user-owned command and captures explicit metrics JSON | Does not own the model runner or measurement loop |
| Artifact writer | Stores `result.json`, config, target, env, stdout, and stderr | Artifacts remain canonical; registry is rebuildable |
| Registry | Provides local SQLite lookup for successful runs and resource metrics | Not a cloud DB or public leaderboard |
| Comparability checker | Reports same-condition, conditional, or non-comparable judgement | Does not produce rankings or composite scores |
| Runtime regression report | Calculates mean/p95/p99/FPS/resource regression only after same-condition comparability passes | Not cloud monitoring or production observability |
| Export/import | Moves evidence bundles with manifest, checksum, and path-safety validation | Does not mutate evidence semantics |
| Sampler evidence | Stores optional resource/sampler metadata as supplemental evidence | Not a comparability gate |

## Portfolio Boundary

```text
InferEdge validates whether a model is deployable.
InferEdgeEnv records whether benchmark evidence can be trusted and compared.
```

Adjacent roles:

- InferEdgeLab is the validation / decision layer.
- InferEdgeEnv is the v0.1.5 v1-complete experiment hygiene / comparability layer.
- InferEdgeOrchestrator is the post-deployment runtime operation-control layer.

## What To Show First

For an external reviewer, use this order:

1. This summary.
2. `README.md`.
3. `docs/portfolio-demo-path.md`.
4. `docs/local-command-contract.md`.
5. `docs/compare-workflow-guide.md`.
6. `docs/export-import-design.md`.
7. `docs/schema-versioning-migration-policy.md`.
8. `docs/cross-repo-positioning-review.md`.

## What Not To Claim

- InferEdgeEnv is not an OS, VM manager, Docker target, WSL target, or cloud service.
- InferEdgeEnv is not a deployment decision engine.
- InferEdgeEnv is not InferEdgeLab.
- InferEdgeEnv is not InferEdgeOrchestrator.
- InferEdgeEnv is not a public benchmark leaderboard.
- InferEdgeEnv does not rank all models with one score.

## Validation Entry

Local validation:

```bash
python -m pytest -q
python -m inferedge_env.cli doctor
edgeenv doctor
```

Reviewer demo:

```bash
python -m pip install -e ".[dev]"
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

Then follow the canonical demo:

```text
docs/portfolio-demo-path.md
```
