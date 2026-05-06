# CI Readiness Workflow

## 1. WHAT — 이 문서가 정하는 것

GitHub Actions에서 EdgeEnv MVP의 핵심 계약을 자동 검증하는 readiness workflow 범위를 정리한다.

이 workflow는 release automation이 아니라 PR마다 local-first MVP contract가 깨졌는지 확인하는 최소 안전망이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `.github/workflows/readiness.yml` — GitHub Actions workflow
- `pyproject.toml` — editable install and dev dependencies
- `tests/` — pytest regression suite
- `examples/` — representative config validation fixtures
- `docs/packaging-entrypoints.md` — install and entrypoint readiness
- `docs/mvp-readiness-checklist.md` — MVP user path and non-goals

기술 스택: GitHub Actions, Python 3.10/3.11, pip editable install, pytest, Typer CLI

## 3. HOW — workflow가 검증하는 것

Trigger:

- pull requests
- pushes to `main`

Python matrix:

- `3.10`
- `3.11`

Steps:

```text
checkout
setup-python
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv profile validate examples/profiles/local.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench validate examples/benches/local_template.yaml
edgeenv bench validate examples/benches/local_compare_a.yaml
python -m pytest -q
```

The workflow intentionally checks both module and console entrypoints because README exposes both paths.

## 4. HOW NOT — 피해야 할 함정

- CI에서 repo root `.edgeenv`에 long-lived artifact를 남기는 benchmark run을 기본으로 만들지 않는다.
- Docker/WSL/SSH/cloud target validation을 CI readiness에 섞지 않는다.
- public leaderboard, model upload, dataset upload 같은 non-goals를 CI path로 암시하지 않는다.
- Python version을 하나만 고정해 `requires-python >=3.10` contract를 놓치지 않는다.
- CI 실패를 무시하고 merge하지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **Packaging And Entrypoint Readiness**: install and doctor smoke path를 CI에서 반복한다.
- **MVP Readiness Checklist**: supported MVP user path 중 가벼운 validation subset을 자동화한다.
- **Tests**: full pytest suite가 executable spec 역할을 한다.
- **Examples**: 대표 profile/bench config가 README와 계속 맞는지 확인한다.

## 6. WHY — 배경 판단

EdgeEnv MVP는 아직 작은 프로젝트지만, result schema, registry, compare output, entrypoint가 서로 맞물려 있다. CI readiness는 큰 release pipeline보다 작고 빠른 검증으로 이 연결이 깨지는 순간을 PR에서 바로 잡기 위한 장치다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
