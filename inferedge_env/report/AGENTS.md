# inferedge_env/report 작업 가이드

> Language: [English overview](../../docs/language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 모듈은 무엇을 하는가

human-readable report 생성 로직을 담당한다. 현재는 imported successful run artifact와 기존 comparability checker 결과를 읽어 Markdown bundle handoff summary를 생성한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택

- `bundle_summary.py` — `report bundle-summary`용 read-only Markdown generator

기술 스택: Python, Markdown text rendering, registry/result artifact readers, comparability checker

## 3. HOW — 일반적인 수정은 어떻게 하는가

report 로직은 read-only로 유지한다. 입력 run은 registry에서 찾아 artifact 파일을 읽고, 비교 판단은 반드시 `inferedge_env.compare`의 기존 checker를 재사용한다. CLI는 `inferedge_env/cli.py`에서 얇게 연결한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정

- report를 canonical evidence로 만들지 말 것. `result.json`, `sampler/metadata.json`, raw artifacts, manifest checksum이 canonical evidence다.
- export zip이나 `.edgeenv/runs/<run_id>/`에 report를 기본으로 쓰지 말 것.
- compare rule을 report 전용으로 재구현하지 말 것.
- conditional/non-comparable pair에 metric delta를 표시하지 말 것.
- ranking, composite score, leaderboard, cloud sync, auth, Docker/WSL/SSH target semantics를 넣지 말 것.

## 5. WHERE — 다른 모듈과의 의존성

- **의존**: `registry`, `result`, `compare`
- **피의존**: CLI `report bundle-summary`, docs, tests
- **경계 / 어댑터**: machine-verifiable artifacts를 사람이 빠르게 검토할 수 있는 Markdown summary로 바꾸는 boundary

## 6. WHY — 배경 판단

EdgeEnv의 evidence는 machine-verifiable artifact다. 하지만 PR/release/handoff에서는 짧은 사람이 읽는 요약이 필요하다. 이 모듈은 요약을 만들되, 증거 원본과 비교 판단을 대체하지 않는 선을 지킨다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
