# Jetson Sampled Run Rehearsal

## 1. WHAT — 이 문서가 정하는 것

Jetson에서 `target_type: local`과 `sampler: jetson-tegrastats`를 함께 사용해 실제 sampled run을 만들고, `edgeenv runs sampler show <run_id>`로 sampler evidence를 확인하는 리허설 절차와 관측 결과를 기록한다.

이 흐름은 SSH target 구현이 아니다. Jetson에 접속한 뒤 Jetson shell에서 EdgeEnv를 local runner로 실행하는 검증이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `examples/profiles/jetson_nano_sampled_local.yaml` — Jetson local target with optional `jetson-tegrastats` sampler
- `examples/benches/jetson_sampled_local.yaml` — deterministic primary benchmark command for sampled-run smoke
- `examples/scripts/emit_delayed_local_metrics.py` — primary `EDGEENV_METRICS_JSON=` stand-in with a short delay to allow multiple samples
- `inferedge_env/samplers/jetson_tegrastats.py` — parser and sampler adapter
- `inferedge_env/runners/local.py` — sampler lifecycle wiring
- `inferedge_env/result/writer.py` — successful-run sampler metadata writer
- `inferedge_env/result/exporter.py` — successful-run sampler artifact export/import
- `inferedge_env/cli.py` — `runs sampler show`

기술 스택: Jetson Linux, `tegrastats`, Python 3.10, EdgeEnv local runner, sampler artifact JSON

## 3. HOW — 리허설 절차

Run these commands on the Jetson from the repo root:

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
edgeenv profile validate examples/profiles/jetson_nano_sampled_local.yaml
edgeenv bench validate examples/benches/jetson_sampled_local.yaml
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs list --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs show <run_id> --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs sampler show <run_id> --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs export <run_id> --output /tmp/InferEdgeEnv-jetson-sampled/<run_id>.zip --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs import /tmp/InferEdgeEnv-jetson-sampled/<run_id>.zip --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled-import/.edgeenv
edgeenv runs sampler show <run_id> --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled-import/.edgeenv
```

If the Jetson environment is using a source snapshot instead of an installed
package, set `PYTHONPATH` to the repo root before invoking `edgeenv`:

```bash
export PYTHONPATH="$PWD"
```

Expected checkpoints:

- `bench run` stores a successful run.
- `result.json.resource_metrics.source` is `jetson-tegrastats` when samples are parsed.
- `sampler/metadata.json` exists.
- `sampler/tegrastats.log` exists when `raw_log: true`.
- `runs sampler show` prints `warnings`, `sample_count`, and `raw_artifacts` without opening files manually.
- successful-run export/import preserves `sampler/metadata.json` and listed raw sampler artifacts.

## 4. HOW NOT — 피해야 할 함정

- Do not describe this as remote execution support. SSH is only how this rehearsal reaches the Jetson shell.
- Do not require the sampler for the smoke profile; `required: false` preserves the primary benchmark if `tegrastats` is unavailable.
- Do not treat Jetson host power as model-only energy.
- Do not add sampler fields to the registry schema for this rehearsal.
- Do not commit `.edgeenv/`, exported zip files, raw logs, models, engines, or datasets.

## 5. WHERE — 다른 설계와의 관계

- **LocalRunner Sampler Wiring Design**: this validates target-profile sampler enablement and start/stop lifecycle.
- **Sampler Metadata Artifact Policy**: this checks `sampler/metadata.json` plus raw artifact references.
- **Export/Import Design**: this checks optional sampler evidence portability.
- **Registry Resource Query Design**: this keeps sampler metadata artifact-first.
- **Comparability**: sampler evidence remains outside compare gates.

## 6. WHY — 배경 판단

The wrapper path proved that Jetson `tegrastats` can be normalized into resource metrics. This rehearsal validates the next integration layer: EdgeEnv starts and stops the sampler adapter around a normal local benchmark command, writes sampler evidence, and exposes that evidence through CLI inspection.

The command remains deterministic for primary benchmark metrics so the rehearsal focuses on platform sampling, artifact layout, and portability rather than model runtime variability.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Short benchmark commands can finish before the first `tegrastats` line appears; keep `startup_wait_ms` at least as large as one sampling interval and keep the smoke command alive briefly for sampled runs.

## Validation Record — nano01

Status: passed on `nano01`.

Environment:

```text
hostname: nano01
platform: Linux 5.15.148-tegra aarch64
python: /home/risenano01/miniconda3/envs/yolo_env/bin/python, Python 3.10.12
tegrastats: /usr/bin/tegrastats
```

Execution note:

- The default system Python did not have EdgeEnv runtime dependencies.
- The `yolo_env` conda environment had `typer`, `rich`, `pydantic`, and `yaml`.
- The validation used the branch source snapshot with `PYTHONPATH=/tmp/InferEdgeEnv-jetson-sampled-work`.
- `edgeenv doctor` and `edgeenv runs sampler show` were also verified through the console script with `PYTHONPATH` set.

Commands validated:

```bash
edgeenv doctor
edgeenv profile validate examples/profiles/jetson_nano_sampled_local.yaml
edgeenv bench validate examples/benches/jetson_sampled_local.yaml
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs show run-20260507-175020-bc3d65db --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs sampler show run-20260507-175020-bc3d65db --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs export run-20260507-175020-bc3d65db --output /tmp/InferEdgeEnv-jetson-sampled/run-20260507-175020-bc3d65db.zip --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled/.edgeenv
edgeenv runs import /tmp/InferEdgeEnv-jetson-sampled/run-20260507-175020-bc3d65db.zip --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled-import/.edgeenv
edgeenv runs sampler show run-20260507-175020-bc3d65db --edgeenv-root /tmp/InferEdgeEnv-jetson-sampled-import/.edgeenv
```

Observed run:

```text
Run ID: run-20260507-175020-bc3d65db
Latency mean: 12.3 ms
Resource metrics: stored (source=jetson-tegrastats, fields=memory_mean_mb, memory_peak_mb, power_mean_w, power_peak_w, temperature_peak_c)
Sampler metadata: stored (/tmp/InferEdgeEnv-jetson-sampled/.edgeenv/runs/run-20260507-175020-bc3d65db/sampler/metadata.json)
```

Observed `resource_metrics`:

```json
{
  "memory_mean_mb": 904.0,
  "memory_peak_mb": 904.0,
  "power_mean_w": 4.427,
  "power_peak_w": 4.482,
  "source": "jetson-tegrastats",
  "temperature_peak_c": 39.937
}
```

Observed `runs sampler show` summary:

```json
{
  "run_id": "run-20260507-175020-bc3d65db",
  "sampler_name": "jetson-tegrastats",
  "sample_count": 3,
  "warnings": [],
  "raw_artifacts": [
    "sampler/tegrastats.log"
  ],
  "files": {
    "metadata": "/tmp/InferEdgeEnv-jetson-sampled/.edgeenv/runs/run-20260507-175020-bc3d65db/sampler/metadata.json",
    "raw_artifacts": {
      "sampler/tegrastats.log": "/tmp/InferEdgeEnv-jetson-sampled/.edgeenv/runs/run-20260507-175020-bc3d65db/sampler/tegrastats.log"
    }
  }
}
```

Import verification:

```text
Run evidence exported
Archive: /tmp/InferEdgeEnv-jetson-sampled/run-20260507-175020-bc3d65db.zip
Run evidence imported
Result: /tmp/InferEdgeEnv-jetson-sampled-import/.edgeenv/runs/run-20260507-175020-bc3d65db/result.json
Imported runs sampler show preserved sampler/metadata.json and sampler/tegrastats.log.
```
