# CLI Error Message Polish

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

first-user가 README Quickstart나 Portfolio Demo Path를 따라가다 실패했을 때, CLI가 어떤 방식으로 실패 원인과 다음 행동을 알려야 하는지 정한다.

목표는 contract를 느슨하게 만드는 것이 아니라, 왜 EdgeEnv가 evidence를 거절했는지와 어떤 artifact/log를 봐야 하는지를 짧게 보여주는 것이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/cli.py` — user-facing `Error:` and `Hint:` output
- `inferedge_env/runners/local.py` — local command stdout metrics contract errors
- `inferedge_env/result/exporter.py` — export/import manifest, checksum, schema, and path safety errors
- `tests/test_cli.py` — expected actionable hints for common CLI failures
- `docs/local-command-contract.md` — local command troubleshooting table
- `docs/export-import-design.md` — evidence bundle validation contract
- `docs/portfolio-demo-path.md` — reviewer-facing flow that these errors support

기술 스택: Typer, Rich, pytest `CliRunner`

## 3. HOW — message policy

Expected user-facing failures should use:

```text
Error: <what failed>
Hint: <what to fix or inspect next>
```

The original error message remains the source of truth and is still written into failed-run artifacts when a local benchmark command fails. `Hint:` is supplemental CLI guidance only.

### Polished paths

| Failure path | Error keeps saying | Hint should point to |
|---|---|---|
| Invalid benchmark config | invalid config/YAML/schema details | required benchmark fields, protocol values, local command options |
| Invalid target profile | invalid profile/YAML/schema details | required target fields and v1 `fake`/`local` target types |
| Missing primary metrics | `Missing EDGEENV_METRICS_JSON=<json> line in stdout` | emit explicit stdout metrics JSON and inspect failed-run logs |
| Malformed primary metrics JSON | `Invalid EDGEENV_METRICS_JSON JSON` | use structured JSON writing such as `json.dumps(...)` |
| Invalid primary metrics schema | `Invalid local metrics schema` | include five numeric latency/throughput fields |
| Malformed resource metrics JSON | `Invalid EDGEENV_RESOURCE_METRICS_JSON JSON` | omit optional resource metrics or emit valid JSON |
| Command nonzero exit | `Local benchmark command failed with exit code N` | inspect `failed-runs show` stdout/stderr |
| Command timeout | timeout message | reduce loop or increase `timeout_seconds`, then inspect partial logs |
| Export missing/corrupt artifact | export error | re-run or inspect artifact directory |
| Import duplicate run ID | duplicate registry/artifact message | use a fresh `--edgeenv-root`; import never overwrites |
| Import checksum/path/schema failure | import validation error | re-export from source or use a compatible schema |

### Failed-run artifact policy

For local benchmark failures, CLI must continue to print:

```text
Failed run artifact: <path>
Registry: not updated
Error: <reason>
Hint: edgeenv failed-runs show <run_id> --edgeenv-root <root>
```

This preserves the existing failed-run inspection loop and avoids hiding evidence behind a generic exception.

## 4. HOW NOT — 피해야 할 함정

- Do not convert expected failures into successful runs with warnings.
- Do not remove failed-run artifacts when a local command fails.
- Do not put long stack traces in normal CLI output for expected user errors.
- Do not assert exact Rich styling in tests unless the style itself becomes a public contract.
- Do not weaken JSON/schema/checksum/path validation to make messages friendlier.
- Do not suggest Docker, WSL, SSH, cloud sync, dashboards, uploads, or ranking as fixes.

## 5. WHERE — 다른 설계와의 관계

- **Local Command Contract Guide**: explains how to fix local stdout metrics failures.
- **Failed Run Inspection Guide**: explains how to inspect captured stdout/stderr after command failure.
- **Export/Import Design**: explains why import rejects checksum, path, schema, and duplicate evidence issues.
- **Schema Versioning And Migration Policy**: explains why unknown future schemas are rejected.
- **Portfolio Demo Path**: benefits from clearer failure messages when a reviewer follows the demo.

## 6. WHY — 배경 판단

InferEdgeEnv's quality is visible when something fails. Clear errors make the evidence model feel deliberate: the CLI rejects bad or ambiguous evidence, preserves diagnostics, and tells the user exactly where to look next.

The project remains a local-first run evidence registry and comparability checker. Error polish should explain that boundary, not broaden product scope.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
