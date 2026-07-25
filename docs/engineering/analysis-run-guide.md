# Analysis Run Guide

## Offline contract check

```powershell
particleml contracts validate
pytest
```

## Formal blinded sequence

```powershell
particleml catalog validate --config configs/catalog-sources.yaml --catalog catalog.json
particleml dataset build --config configs/analysis-v1.yaml --catalog catalog.json --output artifacts/dataset
particleml audit data --dataset artifacts/dataset
particleml run train --config configs/analysis-v1.yaml --dataset artifacts/dataset --output artifacts/training
particleml decorrelate --config configs/analysis-v1.yaml --predictions artifacts/training --output artifacts/ddt
particleml evaluate --config configs/analysis-v1.yaml --predictions artifacts/ddt --output artifacts/evaluation
particleml fit expected --config configs/analysis-v1.yaml --predictions artifacts/ddt --output artifacts/expected-fit
particleml report build --inputs artifacts/evaluation artifacts/expected-fit --output artifacts/blinded-report
```

The five model seeds and ensemble are produced by `run train`; callers do not
substitute ad hoc seed lists.

## Freeze

After all simulation and real-data sideband gates pass:

```powershell
particleml analysis freeze --config configs/analysis-v1.yaml --inputs artifacts --output freeze.json
```

A freeze binds exact configuration, catalog, dataset, prediction, and template
hashes. Creating one does not run an observed fit.

## Observed-fit refusal

Both explicit intent and a valid matching freeze are required:

```powershell
particleml fit observed --config configs/analysis-v1.yaml --freeze freeze.json --unblind
```

Without `--unblind`, without a freeze, with any mismatched hash, or with any
failed gate, the command exits before opening observed signal-window data.
Migration acceptance never invokes this command on real data.
