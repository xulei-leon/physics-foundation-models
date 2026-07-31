# Reference Demo Diagnostics Adaptation Plan

**Date:** 2026-07-30

**Plan version:** 1.0.0

**Software contract version:** 2.1.0

**Package version:** 0.4.0

**Status:** in progress

## Objective

Adapt two narrow diagnostic ideas from the ignored
`var/higgs-xgboost-demo/higgs-xgboost-demo` reference project without making
that directory a dependency or copying its analysis design:

1. grouped signed and absolute simulation-weight summaries; and
2. class-conditional weighted score-shape comparisons between train and test.

These additions improve auditability. They do not change the fixed research
question, model roles, features, training weights, split fractions, DDT
calibration, pyhf workspaces, freeze gates, or blinding protocol.

## Execution sequence

The work is delivered through three sequential Sprints:

1. M1-01 implements grouped simulation-weight audit output.
2. M1-02 implements weighted raw-score diagnostics and study-result contracts.
3. M1-03 performs the long-running full Demo and repository regression.

M1-03 starts only after M1-01 and M1-02 are complete. It runs the full pytest
suite once so the expensive Demo study is not repeated by separate targeted and
complete-suite commands.

## Authority boundary

The reference project is historical, non-formal input to this plan. It must
not be imported, packaged, copied into `src/particleml`, or promoted into the
documentation authority chain.

The implementation must continue to use:

- direct HTTPS discovery and checksum verification;
- canonical event-level Parquet;
- the fixed four-lepton selection and deterministic pairing;
- the 70/10/10/10 train/calibration/validation/test split;
- signed `w_yield` for yields and templates;
- absolute class-normalized `w_train` for fitting;
- the fixed cut-based, Logistic, XGBoost, and MLP roles;
- five formal seeds, DDT, pyhf expected fits, and the existing freeze gates;
- formal XGBoost `device: cuda` and `tree_method: hist` on the verified Jetson
  path.

## Explicit non-goals

This plan does not:

- add a plugin, registry, model factory, or second analysis pipeline;
- adopt the reference 60/20/20 split;
- add raw mass-correlated features or use `m4l` as a model input;
- adopt its single-seed XGBoost training or `min_child_weight: 5`;
- select a score threshold with a counting-only Asimov approximation;
- add an overfitting gate or copy the reference `0.05` and `0.10` warning
  thresholds;
- read or plot real signal-window data;
- add `tqdm`, `vector`, or another dependency;
- add boosting-round validation monitoring to formal training;
- change package or contract versions.

## D1 — Grouped simulation-weight diagnostics

### Implementation

Add one pure summary function in `src/particleml/dataset.py`. It receives an
already audited canonical frame, excludes all data rows, and returns a
deterministically sorted list grouped by:

```text
dataset_id
process_group
sample_role
split
```

Each group records:

```text
events
negative_events
negative_fraction
sum_w_yield
sum_abs_w_yield
```

Requirements:

- `sum_w_yield` preserves the sign of `w_yield`;
- `sum_abs_w_yield` uses `abs(w_yield)`;
- data rows never appear in these summaries;
- nominal and generator-variation samples remain distinguishable;
- all numeric values must be finite;
- groups and keys must have deterministic ordering;
- the function must not modify the input frame or recompute `w_train`.

Update `particleml audit data` to add the result under
`simulation_weight_groups` in its printed JSON object. Keep `audit_frame`
unchanged so the existing Demo summary and its strict schema do not acquire an
unrelated contract change.

### Tests

Extend the existing dataset/ingestion tests with one focused fixture that
contains:

- positive and negative nominal simulation weights;
- a generator-variation row;
- multiple datasets and splits; and
- a data row with unit `w_yield`.

Assert exact signed sums, absolute sums, negative fractions, deterministic
group order, and complete exclusion of data. Retain the existing tests that
reject non-finite weights and data training weights.

### Documentation

Update `docs/engineering/data-access-guide.md` to describe the new audit
fields and state that they are diagnostics, not rescaling inputs.

## D2 — Non-blocking weighted score-shape diagnostics

### Weighted KS primitive

Add `weighted_ks_distance` to `src/particleml/evaluation.py`.

The function must:

- accept two one-dimensional score arrays and their weight arrays;
- use absolute weights because a signed cumulative sum is not a probability
  distribution;
- validate aligned shapes and finite inputs;
- use stable sorting and right-continuous empirical CDFs;
- return a finite value in `[0,1]`;
- raise `ContractError` for malformed or non-finite arrays;
- return no physics pass/fail interpretation.

Do not reuse the private DDT empirical-CDF helper. DDT uses weighted midranks,
while the KS distance requires two comparable right-continuous CDFs.

### Study integration

Add a small NumPy-based helper in `src/particleml/evaluation.py` that receives
aligned target, raw-score, split, and `w_yield` arrays. For each class it
compares nominal simulation train and test scores with absolute `w_yield`.

Every seed and ensemble run for every fixed model records:

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

The two KS values may be `null` only when a required class/split has no
positive absolute weight. Invalid shapes or non-finite inputs remain contract
errors.

The study must compute this record from `raw_score`, before DDT
interpretation, using nominal simulation only. Generator variations and data
must not enter the calculation.

### Non-blocking semantics

The diagnostic record deliberately has no `passed`, `threshold`, or
`blocking` field.

It must not:

- enter `gate_sets`;
- add an item to `blocking_reasons`;
- affect expected significance;
- affect the XGBoost-minus-cut-based primary comparison;
- alter freeze eligibility; or
- trigger automatic retuning.

If a future research-plan revision makes score-shape stability a freeze gate,
that revision must predeclare the statistic, threshold, applicable models,
seed aggregation, and failure policy before inspecting formal results.

### Contract and tests

Extend `schemas/study-result.schema.json` only enough to validate
`raw_score_shape_diagnostics` when present in a run. Preserve the currently
allowed run fields and contract version `2.1.0`.

Add tests that prove:

1. identical weighted samples return zero;
2. disjoint samples return one;
3. negative weights are treated through their absolute values;
4. malformed, non-finite, and misaligned inputs fail;
5. shifted class score shapes are detected even when ranking is unchanged;
6. the fixed study writes diagnostics for five seeds and the ensemble for all
   four models; and
7. changing the diagnostic values alone cannot change study status,
   `blocking_reasons`, or the primary comparison.

## D3 — Documentation and offline regression

Update:

- `docs/research/model-selection.md` to classify weighted KS as a
  non-blocking raw-score diagnostic;
- `docs/software/specification.md` to define its inputs and output fields;
- `docs/engineering/analysis-run-guide.md` to explain interpretation and the
  absence of a gate threshold; and
- `docs/engineering/development-and-debugging.md` with failure behavior for
  malformed diagnostic inputs.

The existing offline Demo remains the integration path. It must still
complete without network access and retain its fixed published artifact list.
No new plot or Demo-summary field is required by this plan.

## Deferred operational progress

Do not copy the reference XGBoost `TrainingCallback` now. It is XGBoost-only,
adds a dependency, and displays validation AUC without the current shared
weighting contract.

If measured Jetson runtime later justifies progress output, implement only
outer model/seed progress through the existing CLI execution path. It must
cover all four models, avoid validation metrics, add no training callback, and
add no dependency.

## Expected file scope

Implementation should normally be limited to:

```text
src/particleml/dataset.py
src/particleml/cli.py
src/particleml/evaluation.py
src/particleml/study.py
schemas/study-result.schema.json
tests/test_ingestion.py
tests/test_evaluation.py
tests/test_demo.py
docs/engineering/data-access-guide.md
docs/engineering/analysis-run-guide.md
docs/engineering/development-and-debugging.md
docs/research/model-selection.md
docs/software/specification.md
```

Do not modify the ignored reference directory.

## Verification

Run the focused tests first, then the complete local gates:

```bash
python -m pytest -q tests/test_ingestion.py tests/test_evaluation.py
python -m pytest -q
python -m ruff check src/particleml scripts tests
python -m mypy src/particleml
particleml contracts validate
python scripts/validate_software_docs.py
node --test
pnpm docs:build
git diff --check
```

The offline suite validates the portable CPU/hist Demo only. Formal
CUDA/hist model validation remains in the verified Jetson container.

## Acceptance criteria

The plan is complete when:

- `particleml audit data` reports deterministic per-group MC weight
  diagnostics without including data;
- every formal model run records class-conditional train-versus-test raw-score
  weighted KS values or an explicit `null`;
- the diagnostics cannot affect study or freeze blocking decisions;
- no score threshold, raw mass feature, data signal-window access, or new
  dependency is introduced;
- the existing Demo output contract remains unchanged; and
- all verification gates pass.
