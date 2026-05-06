# Compare Workflow Guide

## 1. WHAT — 이 문서가 정하는 것

두 benchmark run을 만든 뒤 `runs list`, `runs show`, `report compare`로 비교 가능성을 확인하는 end-to-end 흐름을 정리한다.

EdgeEnv compare는 어느 run이 더 좋은지 단일 점수로 줄 세우지 않는다. 먼저 두 run이 직접 비교 가능한 조건인지, runtime/target 비교로만 해석해야 하는지, 아니면 비교하면 안 되는지를 판정한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/compare/comparability.py` — compare rule implementation
- `inferedge_env/cli.py` — `runs list`, `runs show`, `report compare`
- `examples/benches/local_compare_a.yaml` — first same-condition local run example
- `examples/benches/local_compare_b.yaml` — second same-condition local run example
- `examples/scripts/emit_compare_metrics.py` — deterministic compare workflow fixture
- `docs/local-command-contract.md` — local command stdout contract

기술 스택: Typer CLI, SQLite registry, JSON artifacts, deterministic local command examples

## 3. HOW — compare workflow

### 1. Create two successful runs

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
```

두 example config는 같은 model identity, input shape, task, precision, batch size, warmup/repeat protocol, runtime, execution provider, target을 사용한다. Metrics 값만 다르기 때문에 direct same-condition comparison이 가능하다.

### 2. Find run IDs

```bash
edgeenv runs list
```

또는 각 run의 command output에 표시된 `Run ID`를 사용한다.

### 3. Inspect evidence

```bash
edgeenv runs show <run_id>
```

`runs show`는 registry row와 result artifact를 함께 사용한다. Resource metrics가 있으면 artifact에서 읽어 표시하지만, resource metrics 유무는 direct comparability gate가 아니다.

### 4. Compare

```bash
edgeenv report compare <run_id_a> <run_id_b>
```

Expected same-condition output:

```text
Comparable: Yes
Mode: same-condition
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
```

### Reading outcomes

| Output | Meaning | Next action |
| --- | --- | --- |
| `Comparable: Yes`, `Mode: same-condition` | Required fields, runtime, provider, and target match | It is reasonable to inspect latency/throughput deltas |
| `Comparable: Conditional`, `Mode: runtime-comparison` | Required fields match, but runtime or execution provider differs | Treat as runtime/provider comparison, not direct regression |
| `Comparable: Conditional`, `Mode: target-comparison` | Required fields match, but target differs | Treat as target/platform comparison |
| `Comparable: No` | Required fields differ | Do not make direct regression claims |

## 4. HOW NOT — 피해야 할 함정

- `runs list`의 mean latency만 보고 regression 결론을 내리지 않는다.
- `Comparable: Conditional`을 실패로 해석하지 않는다. 조건부 비교는 runtime/target 차이를 명시하는 별도 해석 모드다.
- resource metrics가 없다는 이유만으로 `Comparable: No`라고 판단하지 않는다.
- model hash, input shape, precision, batch size, warmup/repeat protocol 차이를 무시하지 않는다.
- public leaderboard나 single-score ranking처럼 사용하지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **Local Command Contract Guide**: local run이 valid result artifact를 만들기 위한 입력 contract다.
- **Local Runner Design**: compare workflow의 run 생성 단계가 local runner에 의존한다.
- **Resource Metrics Design**: resource metrics는 compare gate가 아니라 secondary evidence다.
- **Registry Resource Query Design**: compare는 registry `result_path`를 통해 result artifact를 읽는다.

## 6. WHY — 배경 판단

Edge benchmark에서 가장 흔한 실수는 latency 숫자 두 개를 바로 비교하는 것이다. EdgeEnv는 숫자를 보여주기 전에 두 run이 같은 조건인지 먼저 판정해, 사용자가 잘못된 regression claim이나 과장된 runtime 비교를 하지 않도록 돕는다.

이 guide는 EdgeEnv의 핵심 가치인 "record first, compare honestly"를 실제 CLI 흐름으로 보여준다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
