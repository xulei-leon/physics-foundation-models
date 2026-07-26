# Analysis Run Guide

## Offline software verification

```powershell
particleml contracts validate
pytest
python scripts/validate_software_docs.py
```

These checks verify software behavior with synthetic fixtures. They do not
produce or validate a physics result.

## Formal blinded sequence

All analysis inputs are obtained by direct HTTPS and verified against size,
Adler-32, and SHA-256 before ROOT access. The catalog command resolves only the
declared data, nominal simulation, and generator-variation allowlists.

```powershell
particleml catalog freeze `
  --config configs/catalog-sources.yaml `
  --cache cache/atlas `
  --output artifacts/catalog.json

particleml dataset build `
  --config configs/analysis-v1.yaml `
  --catalog artifacts/catalog.json `
  --cache cache/atlas `
  --output artifacts/dataset

particleml audit data `
  --config configs/analysis-v1.yaml `
  --dataset artifacts/dataset

particleml study tune `
  --config configs/analysis-v1.yaml `
  --dataset artifacts/dataset `
  --output artifacts/tuning

particleml study run `
  --config configs/analysis-v1.yaml `
  --catalog artifacts/catalog.json `
  --dataset artifacts/dataset `
  --tuning artifacts/tuning `
  --output artifacts/study
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

```powershell
particleml analysis freeze `
  --config configs/analysis-v1.yaml `
  --inputs artifacts `
  --output artifacts/freeze.json
```

The freeze records raw values and thresholds for the five XGBoost seeds, the
XGBoost ensemble, and the cut-based ensemble. It binds hashes for the
configuration, catalog, dataset, tuning decision, models, predictions, DDT
calibrations, templates, fits, study result, and software record. It contains
no observed-data authorization.

## Independent authorization and observed processing

Authorization is a separate explicit human action after review of the freeze:

```powershell
particleml analysis authorize `
  --freeze artifacts/freeze.json `
  --approver "APPROVER NAME" `
  --output artifacts/unblinding-authorization.json
```

The authorization is self-hashed, bound to the freeze, and permits only the
`xgboost-ensemble` and `cut_based-ensemble` observed workspaces. The blinded
pipeline never creates this file automatically.

An authorized observed run is:

```powershell
particleml analysis observed `
  --config configs/analysis-v1.yaml `
  --freeze artifacts/freeze.json `
  --authorization artifacts/unblinding-authorization.json `
  --catalog artifacts/catalog.json `
  --cache cache/atlas `
  --dataset artifacts/dataset `
  --study artifacts/study `
  --output artifacts/observed `
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
