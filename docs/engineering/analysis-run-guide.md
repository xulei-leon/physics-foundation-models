# Analysis Run Guide

Run these commands from `/workspace/particleML` inside the Jetson development
container:

```bash
export PARTICLEML_RUNTIME=/workspace/runtime
export PARTICLEML_PYTEST_CACHE="$PARTICLEML_RUNTIME/tmp/pytest-cache"
```

## Offline software verification

```bash
ubuntu@leon-orin:/workspace/particleML$ particleml contracts validate
dataset-catalog
dataset-manifest
split-manifest
run-record
prediction-metadata
model-metadata
tuning-decision
study-result
analysis-freeze
unblinding-authorization
fit-result
demo-summary

ubuntu@leon-orin:/workspace/particleML$ python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE"
83 passed

ubuntu@leon-orin:/workspace/particleML$ python scripts/validate_software_docs.py
documentation validation passed (7 checks)
```

These checks verify software behavior with synthetic fixtures. They do not
produce or validate a physics result.

## Formal blinded sequence

The committed analysis configuration uses CUDA-enabled XGBoost with
`tree_method: hist` and `device: cuda` in the verified Jetson container. Run
the formal sequence with that reviewed configuration exactly as written.

The study is a fixed comparison, not a model-plugin platform. `cut_based` is
the primary physics baseline, `xgboost` is the primary research model,
`logistic` is the linear control, and `mlp` is the nonlinear control. The
primary endpoint is the DDT-transformed XGBoost ensemble expected
profile-likelihood significance minus the corresponding cut-based value.

All models share the same selected events, frozen features, deterministic
70/10/10/10 train/calibration/validation/test split, absolute
class-normalized training weights, signed yield weights, five seeds, DDT
calibration, templates, and expected fits. Because normalization gives each
training class total weight 0.5, XGBoost uses `min_child_weight: 0.01`; the
default value can prevent any tree split at this weight scale.

All analysis inputs are obtained by direct HTTPS and verified against size,
Adler-32, and SHA-256 before ROOT access. The catalog command resolves only the
declared data, nominal simulation, and generator-variation allowlists.

```bash
particleml catalog freeze \
  --config configs/catalog-sources.yaml \
  --cache "$PARTICLEML_RUNTIME/cache/atlas" \
  --output "$PARTICLEML_RUNTIME/artifacts/catalog.json"

particleml dataset build \
  --config configs/analysis-v1.yaml \
  --catalog "$PARTICLEML_RUNTIME/artifacts/catalog.json" \
  --cache "$PARTICLEML_RUNTIME/cache/atlas" \
  --output "$PARTICLEML_RUNTIME/artifacts/dataset"

particleml audit data \
  --config configs/analysis-v1.yaml \
  --dataset "$PARTICLEML_RUNTIME/artifacts/dataset"

particleml study tune \
  --config configs/analysis-v1.yaml \
  --dataset "$PARTICLEML_RUNTIME/artifacts/dataset" \
  --output "$PARTICLEML_RUNTIME/artifacts/tuning"

particleml study run \
  --config configs/analysis-v1.yaml \
  --catalog "$PARTICLEML_RUNTIME/artifacts/catalog.json" \
  --dataset "$PARTICLEML_RUNTIME/artifacts/dataset" \
  --tuning "$PARTICLEML_RUNTIME/artifacts/tuning" \
  --output "$PARTICLEML_RUNTIME/artifacts/study"
```

`study tune` is the one bounded validation-only tuning pass at seed 42.
`study run` trains all four model families at the five formal seeds, reloads
the persisted models, applies DDT to every seed and ensemble, uses nominal test
simulation only for nominal templates, scales the 10% test yield by the fixed
factor of ten, and produces expected fits and generator-replacement
diagnostics. Alternative generators never enter nominal training or nominal
yields.

Classification metrics use nominal test simulation and absolute weights. If
the measured false-positive rate at the point nearest 50% signal efficiency is
zero, the reported background rejection uses the smallest positive empirical
false-positive rate so the metric remains finite and JSON-safe.

Each seed and ensemble run records `raw_score_shape_diagnostics` before DDT
interpretation. Signal and background values compare nominal-simulation train
and test shapes with absolute `w_yield`; a class-specific `null` means that its
train or test sample has no positive absolute weight. There is deliberately no
KS threshold. The values are for diagnosis and cannot change study status,
blocking reasons, gate sets, expected significance, the primary comparison,
or freeze eligibility.

An expected pyhf optimizer failure is recorded as `FIT_MINIMIZATION`; the
affected run remains blocked with no expected significance. Ensemble nuisance
diagnostics are separate: if a leave-one-nuisance-out diagnostic fails after
the main fit succeeds, its diagnostic status is `blocked` without erasing the
successful main fit.

The study may complete with failed scientific gates so that failures remain
auditable. A failed gate prevents the next command.

## Analysis freeze

After inspecting the blinded study:

```bash
particleml analysis freeze \
  --config configs/analysis-v1.yaml \
  --inputs "$PARTICLEML_RUNTIME/artifacts" \
  --output "$PARTICLEML_RUNTIME/artifacts/freeze.json"
```

Passing a synthetic Demo artifact directory as `--inputs` is rejected with
`FREEZE_DEMO`.

The freeze records raw values and thresholds for the five XGBoost seeds, the
XGBoost ensemble, and the cut-based ensemble. It binds hashes for the
configuration, catalog, dataset, tuning decision, models, predictions, DDT
calibrations, templates, fits, study result, and software record. It contains
no observed-data authorization.

## Independent authorization and observed processing

Authorization is a separate explicit human action after review of the freeze:

```bash
particleml analysis authorize \
  --freeze "$PARTICLEML_RUNTIME/artifacts/freeze.json" \
  --approver "APPROVER NAME" \
  --output "$PARTICLEML_RUNTIME/artifacts/unblinding-authorization.json"
```

The authorization is self-hashed, bound to the freeze, and permits only the
`xgboost-ensemble` and `cut_based-ensemble` observed workspaces. The blinded
pipeline never creates this file automatically.

An authorized observed run is:

```bash
particleml analysis observed \
  --config configs/analysis-v1.yaml \
  --freeze "$PARTICLEML_RUNTIME/artifacts/freeze.json" \
  --authorization "$PARTICLEML_RUNTIME/artifacts/unblinding-authorization.json" \
  --catalog "$PARTICLEML_RUNTIME/artifacts/catalog.json" \
  --cache "$PARTICLEML_RUNTIME/cache/atlas" \
  --dataset "$PARTICLEML_RUNTIME/artifacts/dataset" \
  --study "$PARTICLEML_RUNTIME/artifacts/study" \
  --output "$PARTICLEML_RUNTIME/artifacts/observed" \
  --unblind
```

Before any ROOT file is opened, this command validates every freeze,
authorization, catalog, dataset, study, and cached-file hash. It then performs
two reads: a sideband-only pass that must reproduce the frozen data rows, and
a full `[105,160)` pass. Frozen models and DDT calibrations are reused. The two
expected workspaces are copied and only their observation arrays are replaced.

Do not run the authorization or observed commands during ordinary software
testing. Real data in `[120,130)` remain blinded until a valid freeze and
independent human authorization exist.
