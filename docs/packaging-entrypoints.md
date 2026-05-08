# Packaging And Entrypoint Readiness

## 1. WHAT — 이 문서가 정하는 것

EdgeEnv MVP를 로컬 개발 환경에서 설치하고 실행할 때 기대하는 package metadata와 CLI entrypoint contract를 정리한다.

README의 첫 진입점은 다음 세 가지가 모두 동작한다는 전제 위에 있다.

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
```

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `pyproject.toml` — package metadata, dependencies, optional dev dependencies, console script
- `inferedge_env/__init__.py` — package version
- `inferedge_env/cli.py` — Typer CLI entrypoint
- `scripts/smoke_entrypoints.sh` — install/module/console entrypoint smoke
- `scripts/smoke_jetson_source_env.sh` — Jetson source snapshot + `PYTHONPATH` sampled-run smoke
- `scripts/smoke_jetson_sampled_compare.sh` — Jetson source snapshot + `PYTHONPATH` sampled compare smoke
- `scripts/smoke_jetson_sampled_conditional_compare.sh` — Jetson source snapshot + `PYTHONPATH` sampled conditional compare smoke
- `tests/test_entrypoints.py` — package metadata and entrypoint regression tests
- `.github/workflows/readiness.yml` — PR/main automation for entrypoint smoke and pytest

기술 스택: Python packaging, setuptools, PEP 621 metadata, Typer console script, pytest

## 3. HOW — readiness 확인 순서

### Editable install

```bash
python -m pip install -e ".[dev]"
```

Expected package metadata:

- project name: `inferedge-env`
- Python package: `inferedge_env`
- package version: matches `inferedge_env.__version__`
- console script: `edgeenv = inferedge_env.cli:main`
- dev extra includes `pytest`

### Module entrypoint

```bash
python -m inferedge_env.cli doctor
```

This path works directly from the Python package and is useful when a shell cannot find the installed console script yet.

### Console script entrypoint

```bash
edgeenv doctor
```

This path is the user-facing CLI after editable install.

### Smoke script

```bash
bash scripts/smoke_entrypoints.sh
```

The script intentionally checks install, module entrypoint, console script entrypoint, and the full pytest suite. It should be run from the repository root.

### CI workflow

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
python -m pytest -q
```

The GitHub Actions readiness workflow repeats the same entrypoint contract on Python 3.10 and 3.11.

### Jetson source snapshot smoke

When validating a copied source snapshot on Jetson, prefer the dedicated smoke
instead of assuming editable install support:

```bash
scripts/smoke_jetson_source_env.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

This script sets `PYTHONPATH` to the repo root, verifies runtime dependencies
and `tegrastats`, runs the sampled Jetson local example, inspects sampler
metadata, and checks successful-run export/import preservation.

## 4. HOW NOT — 피해야 할 함정

- README에서 `edgeenv doctor`를 먼저 보여주면서 `[project.scripts]`를 깨뜨리지 않는다.
- `pyproject.toml` version과 `inferedge_env.__version__`을 따로 움직이지 않는다.
- console script만 테스트하고 `python -m inferedge_env.cli doctor`를 놓치지 않는다.
- install smoke가 repo root `.edgeenv`를 만들도록 하지 않는다.
- Jetson source snapshot smoke에서 editable install을 필수로 만들지 않는다.
- packaging readiness 작업에 Docker/WSL/SSH/cloud release path를 섞지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **README**: 사용자가 처음 실행하는 install/doctor commands를 보여준다.
- **MVP Readiness Checklist**: MVP user path의 첫 단계가 install and smoke다.
- **CLI**: `inferedge_env.cli:main`이 console script target이다.
- **Tests**: metadata와 entrypoint behavior를 regression contract로 고정한다.
- **Jetson Environment Setup Hardening**: source snapshot validation uses `PYTHONPATH` plus a known-good Python environment.

## 6. WHY — 배경 판단

EdgeEnv는 CLI-first tool이므로, 설치 직후 `doctor`가 안정적으로 동작해야 이후 config validation, benchmark run, registry, compare workflow를 신뢰할 수 있다. Packaging readiness는 기능을 늘리는 일이 아니라 첫 사용자가 프로젝트 문서대로 들어올 수 있게 만드는 진입로 정비다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
