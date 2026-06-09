# Runtime Regression Replay Fixtures

These committed JSON fixtures are small EdgeEnv-owned runtime regression replay
artifacts for downstream Runtime Intelligence handoff checks. They let AIGuard,
Lab, and the top-level InferEdge entrypoint verify report ingestion without
running a live benchmark or needing a Jetson device.

Use `fixture_matrix.json` as the machine-readable index. It maps each fixture
to the mode it represents, whether regression deltas are allowed, and which
supplemental telemetry/replay context must be present.

| Role | Fixture | Mode | Deltas |
| --- | --- | --- | --- |
| same-condition regression | `edgeenv_same_condition_regression.json` | `same-condition` | allowed |
| runtime comparison blocked | `edgeenv_runtime_comparison_blocked.json` | `runtime-comparison` | blocked |
| target comparison blocked | `edgeenv_target_comparison_blocked.json` | `target-comparison` | blocked |
| protocol mismatch blocked | `edgeenv_protocol_mismatch_blocked.json` | `protocol_mismatch` | blocked |
| telemetry gap same-condition | `edgeenv_candidate_telemetry_gap.json` | `same-condition` | allowed |
| replay sequence context | `edgeenv_sequence_inversion.json` | `same-condition` | allowed |

Boundary:

- These fixtures do not include `guard_analysis`.
- These fixtures do not include Lab `deployment_decision`.
- Missing telemetry is evidence quality metadata, not a comparability gate.
- Runtime/provider and target comparisons are review context, not direct
  regression calculations.
- The fixtures are local-first replay evidence, not production monitoring or a
  public leaderboard.
