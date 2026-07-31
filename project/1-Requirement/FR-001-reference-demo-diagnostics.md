# FR-001 Non-blocking Analysis Diagnostics

- `FR-ID`: `FR-001`
- `Title`: Non-blocking analysis diagnostics
- `Phase`: Phase 1 - Analysis diagnostics and auditability
- `Development order`: 1
- `Priority`: P1
- `Status`: In progress
- `Prerequisites`: `DATA-005`, `MODEL-002`, `DDT-002`, and `DEMO-001`
- `Affected packages`: `src/particleml`, `schemas`, `tests`, and analysis documentation
- `Prototype phase`: No
- `Source type`: Design strengthening
- `Original SRS section`: Software Requirements 2.1.0 (`DATA-005`, `MODEL-002`, `DEMO-001`)
- `Delivery Sprints`: [M1-01](../3-Plan/sprint-m1-01.md),
  [M1-02](../3-Plan/sprint-m1-02.md), and
  [M1-03](../3-Plan/sprint-m1-03.md)

## Goal

Improve the auditability of the fixed particleML analysis by adding:

1. deterministic grouped simulation-weight summaries; and
2. class-conditional train-versus-test raw-score weighted KS diagnostics.

Both diagnostics are descriptive only. They must not change model selection,
training, DDT, expected fits, freeze eligibility, or blinding.

## Background and problem

The ignored `var/higgs-xgboost-demo/higgs-xgboost-demo` project contains useful
diagnostic ideas, but its analysis design is not compatible with particleML.
particleML needs the useful observability without importing that project or
adopting its split, features, weighting, threshold optimization, training, or
real-data plotting choices.

The source adaptation proposal is
[Reference Demo Diagnostics Adaptation Plan](../3-Plan/2026-07-30-reference-demo-diagnostics-plan.md).
This FR converts that proposal into an implementation requirement while
preserving the current scientific contracts.

## Impact scope

- `particleml audit data` JSON output for simulation-weight summaries.
- Evaluation primitives for weighted empirical score distributions.
- Per-seed and ensemble records in the blinded study result.
- The optional study-result schema record.
- Focused ingestion and evaluation tests.
- The existing full offline Demo integration test.
- Engineering, research, and software specification documentation.

The Demo artifact list and strict Demo-summary schema are unchanged.

## Requirements

### Grouped simulation-weight diagnostics

- Add one pure dataset summary helper that consumes an already audited
  canonical frame and does not mutate it.
- Exclude all data rows.
- Group simulation rows by `dataset_id`, `process_group`, `sample_role`, and
  `split`.
- Emit deterministic group and key ordering.
- Record `events`, `negative_events`, `negative_fraction`, `sum_w_yield`, and
  `sum_abs_w_yield` for each group.
- Preserve the sign of `w_yield` in `sum_w_yield` and use `abs(w_yield)` only
  for `sum_abs_w_yield`.
- Keep nominal and generator-variation samples distinguishable.
- Require all reported numeric values to be finite.
- Do not recompute or modify `w_train`.
- Add the groups as `simulation_weight_groups` in the JSON printed by
  `particleml audit data`.
- Keep the existing `audit_frame` return contract unchanged.

### Weighted raw-score shape diagnostics

- Add a `weighted_ks_distance` evaluation primitive for two aligned pairs of
  one-dimensional score and weight arrays.
- Validate dimensions, aligned lengths, and finite values; malformed inputs
  raise `ContractError`.
- Convert weights to absolute values, use stable sorting, compare
  right-continuous weighted empirical CDFs, and return a finite distance in
  `[0, 1]`.
- Do not reuse the DDT weighted-midranks helper because it implements a
  different empirical-CDF convention.
- Add a small aligned-array helper that compares nominal simulation train and
  test `raw_score` values separately for signal and background.
- Exclude data and generator variations.
- Return `null` for a class only when its train or test sample has no positive
  absolute weight.
- Record the following optional object for every seed and ensemble run of all
  four fixed models:

```json
{
  "raw_score_shape_diagnostics": {
    "comparison": "train-vs-test",
    "weighting": "absolute-w_yield",
    "signal_weighted_ks": 0.0,
    "background_weighted_ks": 0.0
  }
}
```

### Study and contract behavior

- Compute the diagnostic from nominal simulation `raw_score` values before DDT
  interpretation.
- Emit the record for seeds 17, 42, 314, 2026, and 2718 plus each ensemble for
  cut-based, Logistic Regression, XGBoost, and MLP.
- Extend `schemas/study-result.schema.json` only enough to validate the
  optional record.
- Keep software contract version `2.1.0`.
- Do not add `passed`, `threshold`, or `blocking` fields.
- Do not add the diagnostic to `gate_sets` or `blocking_reasons`.
- Do not let diagnostic values affect expected significance, the primary
  XGBoost-minus-cut-based comparison, freeze eligibility, or retuning.

### Offline regression

- Reuse the existing full Demo test to verify study integration.
- Capture that Demo run's internal `study_result` and assert diagnostics for all
  four models, five seeds, and ensembles.
- Do not execute a second expensive study in `tests/test_demo.py`.
- Preserve the no-network Demo behavior, published artifact list, and strict
  Demo-summary schema.

## High-level constraints

- Keep the fixed four-model shared analysis chain. Do not add a plugin,
  registry, model factory, or second pipeline.
- Preserve direct HTTPS plus checksum ingestion, canonical event-level
  Parquet, fixed four-lepton selection, and deterministic pairing.
- Preserve the 70/10/10/10 train/calibration/validation/test split.
- Preserve signed `w_yield` for yields and templates and absolute
  class-normalized `w_train` for training.
- Preserve frozen safe features, five formal seeds, DDT, pyhf expected fits,
  current freeze gates, and the `[120,130)` GeV real-data blind.
- Formal XGBoost remains `device: cuda` with `tree_method: hist` in the
  verified Jetson environment. Portable Demo tests remain CPU/hist.
- Do not import, package, copy, or modify the ignored reference project.
- Add no dependency.

## Inputs

- An already audited canonical event frame for weight summaries.
- Aligned nominal-simulation `target`, `raw_score`, `split`, and `w_yield`
  arrays for score-shape diagnostics.
- Existing four-model, five-seed and ensemble study results.

Real data, generator variations, thresholds, and DDT scores are not inputs to
the weighted KS diagnostic.

## Outputs

- `simulation_weight_groups` in the `particleml audit data` JSON output.
- An optional `raw_score_shape_diagnostics` object in each study run record.
- Updated schema, automated tests, and documentation.

No new formal artifact type, Demo artifact, Demo-summary field, authorization,
observed workspace, or freeze input is produced.

## Failure and degradation

- Malformed, misaligned, or non-finite weighted-KS inputs fail closed with
  `ContractError`.
- A missing positive absolute weight for one required class/split produces
  `null` only for that class diagnostic.
- Scientific gates retain their existing behavior and cannot be relaxed because
  of a diagnostic result.
- Full formal CUDA validation remains assigned to the verified Jetson
  container; portable offline regression validates only CPU/hist execution.

## Out of scope

- The reference project's 60/20/20 split or raw mass-correlated features.
- Single-seed XGBoost, `min_child_weight: 5`, or counting-only Asimov threshold
  optimization.
- A weighted-KS pass/fail threshold or overfitting freeze gate.
- Automatic retuning based on diagnostic values.
- Real signal-window reads or plots.
- XGBoost `TrainingCallback`, `tqdm`, validation-AUC progress, or another
  dependency.
- Changes to package version, software contract version, or Demo outputs.

## Minimum verification

- Focused ingestion tests for exact grouped counts, signed and absolute sums,
  negative fractions, deterministic order, and data exclusion.
- Focused evaluation tests for identical, disjoint, negative-weight,
  malformed, non-finite, misaligned, and shifted-shape cases.
- The existing full offline Demo test, with captured `study_result`, for all
  models, seeds, and ensembles without a second study run.
- Study schema validation and regression checks proving diagnostic values do
  not change study status, blocking reasons, or the primary comparison.
- Repository lint, type, contract, documentation, and whitespace checks.

## Acceptance points

- `particleml audit data` reports deterministic grouped simulation-weight
  diagnostics and never includes data rows.
- Every fixed-model seed and ensemble study run records finite class-conditional
  weighted KS values or an allowed `null`.
- Diagnostic-only value changes cannot affect scientific gates, study status,
  freeze eligibility, expected significance, or the primary comparison.
- The offline Demo remains deterministic, network-isolated, and contract
  compatible.
- No unsafe reference-project method, new dependency, or real signal-window
  access is introduced.
- All required verification gates pass in their supported environments.

## Notes

- This remains one FR because the two diagnostics share one auditability
  outcome and scientific boundary. Delivery is split into three sequential
  Sprints at independently testable implementation boundaries.
- M1-03 is a dedicated long-running validation Sprint. It runs the complete
  pytest suite once rather than running `tests/test_demo.py` separately and
  repeating it in the full suite.
- Training progress output remains deferred. If measured Jetson runtime later
  justifies it, define a separate requirement for outer model/seed progress
  without validation metrics or an XGBoost callback.
- Current workflow phase: FR and three Sprint documents authored;
  implementation has not started.
