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
| Runtime Intelligence handoff | Preserves Runtime telemetry history, Orchestrator operation context, and AIGuard/Lab alignment markers | Does not produce Guard analysis or Lab deployment decisions |

Runtime Intelligence handoff also exposes
`lab_bundle_alignment.expected_report_markers` so the producer-side manifest can
name the Lab-owned report rows expected downstream: `Runtime Intelligence Risk Summary`,
`Runtime replay duration scope`, `Orchestrator operation feed context`,
`Orchestrator task event rollup`, `Lab EdgeEnv preservation context`,
`AIGuard task event rollup evidence`,
`AIGuard runtime operation anomalies`, `AIGuard remote dispatch event summary`,
`AIGuard remote event summary consistency`, `Remote fallback starter evidence`,
`lab=Remote fallback starter evidence; evidence=remote_execution_recovered_by_fallback`,
`AIGuard producer-lineage guard alignment`, and `Lab remains the final deployment decision owner.`.
When available, the same handoff summary preserves `duration_source` and
`duration_scope_label` values such as `source=entrypoint_requested_frames` as
producer-side traceability for the Lab-owned replay duration row.
This is traceability metadata for Lab's report gate, not an EdgeEnv deployment
decision.

## Portfolio Boundary

```text
InferEdge validates whether a model is deployable.
InferEdgeEnv records whether benchmark evidence can be trusted and compared.
```

Adjacent roles:

- InferEdgeLab is the validation / decision layer.
- InferEdgeEnv is the v0.1.5 v1-complete experiment hygiene / comparability layer.
- InferEdgeOrchestrator is the post-deployment runtime operation-control layer.
- InferEdgeAIGuard is the optional deterministic diagnosis evidence provider.

Remote dispatch starter evidence belongs to that adjacent operation/diagnosis
handoff, not to EdgeEnv's core execution role. Orchestrator produces
worker-selection, fallback, and compact event-summary evidence. EdgeEnv may
preserve related operation context and handoff markers as local evidence, but
it does not confirm production remote execution, long-lived worker readiness,
secure tunnel operation, production retry/failover, or cloud orchestration.
When present, the preserved markers are traceability fields such as
`evidence_role=remote_dispatch_runtime_event_compact_summary`,
`operation_boundary=remote dispatch starter evidence only`, and
`production_remote_execution=false`, not proof of remote execution.
Lab remains the final deployment decision owner.

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
- InferEdgeEnv is not InferEdgeAIGuard.
- InferEdgeEnv is not a remote dispatch or production remote execution layer.
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
