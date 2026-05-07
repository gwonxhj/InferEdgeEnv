# Local Real Benchmark Example Guide

## 1. WHAT — 이 문서가 정하는 것

`target_type: local`에서 실제 runtime command를 붙이기 직전의 adapter 형태를 설명한다. 이 예제는 모델이나 dataset artifact를 repo에 넣지 않고, 작은 subprocess command를 runtime stand-in으로 실행한 뒤 EdgeEnv stdout contract를 출력한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `examples/benches/local_runtime_adapter.yaml` — local runtime adapter demo config
- `examples/scripts/local_runtime_adapter_demo.py` — runtime command wrapper demo
- `examples/profiles/local.yaml` — local target profile
- `docs/local-command-contract.md` — required stdout contract
- `docs/failed-run-inspection.md` — failed command debugging flow

기술 스택: Python argparse, subprocess, YAML config, EdgeEnv metrics stdout contract

## 3. HOW — 예제를 실행하고 바꾸는 방법

Run the example:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_runtime_adapter.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

The config command has two layers:

```text
python examples/scripts/local_runtime_adapter_demo.py [adapter args] -- python -c "print('runtime-demo-inference')"
```

- Left of `--`: adapter arguments that describe runtime, model path, input shape, and protocol.
- Right of `--`: the runtime command that would be replaced with a user-owned command such as an ONNX Runtime, TensorRT, OpenVINO, or custom benchmark script invocation.

The demo adapter:

- executes the runtime command with `subprocess.run`
- forwards runtime stdout/stderr as diagnostic lines
- exits non-zero if the runtime command fails
- emits deterministic `EDGEENV_METRICS_JSON=...`
- optionally emits `EDGEENV_RESOURCE_METRICS_JSON=...`

To adapt this for a real benchmark, replace the deterministic metrics block with measured latency/throughput from the runtime command or from an in-process benchmark loop. Keep the final `EDGEENV_METRICS_JSON=` line explicit and structured.

## 4. HOW NOT — 피해야 할 함정

- 이 예제를 실제 model runner라고 설명하지 않는다. It is an adapter pattern and CLI smoke fixture.
- repo에 large model, dataset, engine, or trace artifact를 추가하지 않는다.
- wall-clock timing randomness에 테스트를 의존시키지 않는다.
- runtime command failure를 성공 metrics로 덮지 않는다.
- Docker, WSL, SSH, or cloud execution을 이 local example에 섞지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **Local Command Contract Guide**: final stdout metrics line and optional resource metrics line are the contract.
- **Failed Run Inspection Guide**: non-zero runtime command exits become failed-run artifacts.
- **Compare Workflow Guide**: successful local adapter runs can be compared only after comparability judgement.
- **Resource Metrics Design**: resource metrics remain optional secondary evidence.

## 6. WHY — 배경 판단

Users often need a concrete bridge between "toy script prints metrics" and "my runtime command benchmarks a model." This example provides that bridge without pretending EdgeEnv owns the runtime, model, dataset, or measurement loop. EdgeEnv records the result and preserves evidence; the local command remains responsible for benchmark correctness.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
