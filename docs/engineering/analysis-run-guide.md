# Analysis Run Guide

Run these commands from `/workspace/particleML` inside the Jetson development
container:

```bash
export PARTICLEML_RUNTIME=/workspace/runtime
export PARTICLEML_PYTEST_CACHE="$PARTICLEML_RUNTIME/tmp/pytest-cache"
```

## Offline software verification

```bash
particleml contracts validate
python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE"
python scripts/validate_software_docs.py
```

These checks verify software behavior with synthetic fixtures. They do not
produce or validate a physics result.

## Formal blinded sequence

The committed analysis configuration uses CUDA-enabled XGBoost with
`tree_method: hist` and `device: cuda` in the verified Jetson container. Run
the formal sequence with that reviewed configuration exactly as written.

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
