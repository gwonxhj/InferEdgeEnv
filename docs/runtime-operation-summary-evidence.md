# Runtime Operation Summary Evidence

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT - What This Document Defines

`runtime_operation_summary` is optional supplemental evidence attached to a
successful local run when an upstream runtime or orchestration flow already
produces structured operation context.

EdgeEnv preserves this payload in `result.json` and exposes it through
`runs show`, but it does not use the payload as a same-condition comparability
gate or as an automatic deployment decision.

## 2. CONTENTS - Files And Stack

Related files:

- `inferedge_env/runners/local.py` - parses
  `EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON=<json-object>` from stdout.
- `inferedge_env/result/schema.py` - keeps the optional
  `RunResult.runtime_operation_summary` field.
- `inferedge_env/result/writer.py` - persists the field in `result.json` only
  when present.
- `inferedge_env/cli.py` - includes the field in `runs show` by reading the
  result artifact through the registry `result_path`.
- `inferedge_env/compare/comparability.py` - keeps the required comparability
  fields unchanged.

Stack: Python, Pydantic, JSON artifact preservation, local SQLite registry
lookup by `result_path`.

## 3. HOW - Evidence Contract

A local benchmark command may emit the operation summary after producing or
collecting runtime operation evidence:

```text
EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON={"source":"inferedge-runtime","health_reason":"completed"}
```

Rules:

- The value must be a JSON object.
- If the line is omitted, the run remains valid and the field is omitted from
  `result.json`.
- If the line is malformed, the local run fails and EdgeEnv writes a failed-run
  diagnostic artifact instead of inserting a successful registry row.
- If multiple lines are emitted, the last one wins, matching the existing
  metrics/resource metrics stdout contract.

## 4. HOW NOT - What To Avoid

- Do not add `runtime_operation_summary` to required same-condition fields.
- Do not derive latency regression from this payload.
- Do not treat this payload as cloud monitoring, distributed tracing, or a
  production observability stream.
- Do not make EdgeEnv the deployment decision owner. Lab remains the owner for
  validation and decision reports.

## 5. WHERE - Registry And Compare Boundary

`runs.db` remains a local lookup index. EdgeEnv does not add a registry column
for `runtime_operation_summary`; richer operation evidence stays canonical in
`.edgeenv/runs/<run_id>/result.json`.

`runs show` loads the artifact through the registry `result_path` and returns
the optional payload when present. `report compare` and `report regression`
continue to apply the comparability-first policy before any regression
calculation.

## 6. WHY - Background Judgment

Runtime operation context is useful evidence when investigating timeout,
worker-health, queue, or operation-control behavior. It should travel with the
run bundle so later tools can inspect the same evidence, but it should not make
otherwise identical benchmark runs incomparable.

## 7. LEARNED CAUTIONS - Learned Cautions

_(None yet)_
