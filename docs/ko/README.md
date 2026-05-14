# EdgeEnv 한국어 README

> Language: [English](../../README.md) | 한국어

InferEdgeEnv는 Edge AI inference benchmark 결과를 local artifact와 SQLite registry로 고정하고, 결과 간 비교 가능성을 판정하는 local-first run evidence registry and comparability checker다. 사용자-facing CLI 명령은 `edgeenv`다.

## v0.1.4에서 시작하기

`v0.1.4`는 현재 release quality baseline이다. 첫 사용 경로는 다음 순서가 가장 안전하다.

1. 설치 후 `doctor`를 실행한다.
2. deterministic fake run을 기록한다.
3. local command run을 실행한다.
4. EdgeEnv가 comparability를 판정한 뒤에만 두 run의 metric delta를 읽는다.
5. Jetson 문서는 Jetson shell에서 EdgeEnv를 local로 실행할 준비가 됐을 때만 사용한다.

검증된 범위:

- fake/local benchmark recording
- `.edgeenv/runs/<run_id>/` artifact 저장
- SQLite registry lookup
- export/import
- comparability report
- optional resource metrics
- read-only bundle summary
- Jetson에서 local execution으로 수집하는 optional `tegrastats` sampled evidence

## 빠른 시작

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
```

Fake benchmark를 먼저 실행한다.

```bash
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

그 다음 local command 예제를 실행한다.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_echo_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_adapter_template.yaml
```

두 run을 비교할 때는 먼저 비교 가능성 판단을 읽는다.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
edgeenv runs list
edgeenv report compare <run_id_a> <run_id_b>
```

## EdgeEnv가 아닌 것

EdgeEnv는 다음을 구현하지 않는다.

- OS, bootloader, GRUB, BCD, Linux compatibility layer
- VM, Docker, WSL, SSH, cloud target manager
- cloud DB, login/auth, web dashboard, public leaderboard
- model upload server, dataset upload server
- 모든 모델을 하나의 점수로 줄 세우는 ranking system

## 어디를 읽으면 되는가

- 영어 대표 문서: [README](../../README.md)
- 문서 언어 가이드: [Documentation Language Guide](../language.md)
- benchmark command 연결: [Local Command Contract Guide](../local-command-contract.md)
- 비교 흐름: [Compare Workflow Guide](../compare-workflow-guide.md)
- 현재 릴리스 기준선: [EdgeEnv v0.1.4 Follow-up Note](../release-follow-up-v0.1.4.md)
- 릴리스 품질 기준: [Release Maintenance Checklist](../release-maintenance-checklist.md)

한국어 문서는 빠른 진입과 프로젝트 경계 확인을 돕기 위한 요약이다. 세부 설계와 최신 release evidence는 영어 대표 문서와 Guide Map을 함께 확인한다.
