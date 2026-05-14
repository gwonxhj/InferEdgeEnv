# Install And Quickstart Resilience

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

README Quickstart의 첫 명령인 `python -m pip install -e ".[dev]"`가 실패했을 때, 사용자가 제품 오류와 환경/setup 오류를 구분할 수 있게 하는 troubleshooting 기준을 정한다.

이 문서는 packaging contract를 바꾸지 않는다. `inferedge-env`, `inferedge_env`, `edgeenv`, `python -m inferedge_env.cli` 관계를 더 명확히 설명하는 사용자-facing 보강이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `README.md` — 첫 사용자 진입점
- `docs/packaging-entrypoints.md` — install/module/console entrypoint contract
- `docs/readme-quickstart-cleanroom-rehearsal.md` — fresh source archive + venv validation record
- `scripts/smoke_entrypoints.sh` — local install/doctor/pytest smoke
- `pyproject.toml` — build system, dependencies, dev extra, console script

기술 스택: Python venv, pip editable install, setuptools build backend, Typer console script, pytest

## 3. HOW — 권장 triage 순서

### 1. Start from a fresh venv

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Use `python -m pip` so the selected Python environment and pip target are the same.

### 2. If install fails before EdgeEnv is imported

Symptoms:

- `Installing build dependencies` fails
- `Could not find a version that satisfies the requirement setuptools>=68`
- DNS or connection errors while pip is looking up packages

Likely cause:

- network is unavailable
- package index is blocked
- build dependencies are not cached
- pip is too old for the local packaging path

Recommended checks:

```bash
python -m pip --version
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
```

If the environment is intentionally offline, pre-cache build dependencies or use an environment where `setuptools`, `wheel`, and runtime dependencies are already available.

### 3. If install succeeds but `edgeenv` is not found

Use the module entrypoint first:

```bash
python -m inferedge_env.cli doctor
```

Then confirm the console script belongs to the same environment:

```bash
which edgeenv
python -m pip show inferedge-env
```

Common cause:

- the venv is not activated
- shell command lookup is using another Python environment
- non-interactive shell PATH does not include the venv `bin` directory

### 4. If both doctor commands work

Proceed with the fake run:

```bash
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
```

At this point install and entrypoint setup are not the blocker.

## 4. HOW NOT — 피해야 할 함정

- Do not describe a no-network pip build dependency failure as an EdgeEnv runtime failure.
- Do not recommend global `sudo pip install` as the default fix.
- Do not add Docker/WSL/cloud setup as a workaround for local install friction.
- Do not change package names to make installation wording shorter.
- Do not remove `python -m inferedge_env.cli doctor`; it is the best fallback when shell PATH cannot find `edgeenv`.

## 5. WHERE — 다른 문서와의 관계

- **README**: links users here when install fails.
- **Packaging And Entrypoint Readiness**: this document expands the troubleshooting portion of that contract.
- **README Quickstart Clean-room Rehearsal**: validates that install works in a fresh venv once network access is available.
- **CI Readiness**: confirms install and entrypoints on Python 3.10 and 3.11.

## 6. WHY — 배경 판단

The first user-facing failure mode is often packaging, not benchmark behavior. During clean-room validation, the only initial failure was a sandboxed no-network pip lookup for build dependencies. With network access, the editable install and all README commands passed.

This means the correct resilience improvement is clearer triage, not a new execution backend or a broader install system.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Keep install troubleshooting focused on Python environment and package index access; broad platform workarounds make the MVP scope look larger than it is.
