# Failed Run Inspection Guide

## 1. WHAT — 이 문서가 정하는 것

실패한 local benchmark run을 `.edgeenv/failed-runs/<run_id>/` artifact에서 안전하게 찾고 확인하는 CLI 흐름을 정리한다.

Failed run은 성공 run registry인 `.edgeenv/runs.db`에 insert되지 않는다. 대신 config, target, env, stdout, stderr, failure metadata를 diagnostic evidence bundle로 보존한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/cli.py` — `failed-runs list`, `failed-runs show`
- `inferedge_env/result/writer.py` — failed-run artifact writer
- `.edgeenv/failed-runs/<run_id>/failure.json` — failure metadata
- `.edgeenv/failed-runs/<run_id>/stdout.log` — captured stdout
- `.edgeenv/failed-runs/<run_id>/stderr.log` — captured stderr

기술 스택: Typer CLI, Rich table output, JSON artifact, filesystem evidence bundle

## 3. HOW — inspection workflow

### 1. Run a command that fails

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_malformed_resource.yaml
```

The CLI reports the failed-run artifact path and makes the registry state explicit:

```text
Failed run artifact: .edgeenv/failed-runs/<run_id>
Registry: not updated
Error: <reason>
```

### 2. List failed runs

```bash
edgeenv failed-runs list
```

The list output shows run ID, created time, benchmark, target, return code, and error message. This command reads `failure.json` files under `.edgeenv/failed-runs/`; it does not query or mutate `runs.db`.

### 3. Show a failed run

```bash
edgeenv failed-runs show <run_id>
```

The show output is JSON containing:

- `failure` metadata from `failure.json`
- `artifact_path`
- file paths for `config.yaml`, `target.yaml`, `env.json`, `stdout.log`, and `stderr.log`
- stdout/stderr previews

Use `--log-chars 0` to suppress log previews, or set a larger value when the first lines are not enough:

```bash
edgeenv failed-runs show <run_id> --log-chars 0
```

## 4. HOW NOT — 피해야 할 함정

- 실패 run을 `runs list`나 `runs show`에서 찾으려 하지 않는다. Those commands are for successful registry records.
- failed-run artifact를 성공 run처럼 compare하지 않는다.
- `failure.json` schema marker인 `edgeenv.failed-run.v1`을 임의로 바꾸지 않는다.
- stdout/stderr만 보고 benchmark result를 복구해 registry에 넣지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **Local Runner Design**: local command failure and malformed metrics create failed-run artifacts.
- **Sampler Failure Policy**: unavailable sampler can still produce a successful run, but malformed emitted resource metrics creates a failed-run artifact.
- **Local Command Contract Guide**: troubleshooting table explains common failure causes.
- **Registry**: successful run registry stays separate from failed-run diagnostics.

## 6. WHY — 배경 판단

Failed-run inspection is a debugging loop, not a benchmark result path. Keeping failed artifacts outside `runs.db` prevents accidental comparison against incomplete or invalid benchmark evidence while still preserving enough context to fix the command.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
