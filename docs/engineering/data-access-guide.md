# Data Access and Dataset Build

Run these commands from `/workspace/particleML` inside the Jetson development
container. Keep downloaded inputs and published artifacts in the bind-mounted
runtime directory:

```bash
export PARTICLEML_RUNTIME=/workspace/runtime
```

## Catalog

Generate record metadata and file entries only through direct HTTPS:

```bash
particleml catalog validate \
  --config configs/catalog-sources.yaml \
  --catalog "$PARTICLEML_RUNTIME/artifacts/catalog.json"
```

The formal catalog stores an HTTPS URL, byte size, and SHA-256 checksum for
every file. Redirects to a non-HTTPS scheme, missing checksums, unknown process
names, and ambiguous nominal signal generators are errors.

Full public files are not downloaded during the repository migration. The
default CI path uses synthetic local ROOT fixtures whose manifest has the same
contract.

## Canonical build

```bash
particleml dataset build \
  --config configs/analysis-v1.yaml \
  --catalog "$PARTICLEML_RUNTIME/artifacts/catalog.json" \
  --cache "$PARTICLEML_RUNTIME/cache/atlas" \
  --output "$PARTICLEML_RUNTIME/artifacts/dataset-v1"
```

The builder streams ROOT chunks, validates required branches, converts MeV to
GeV, runs selection and pairing, computes weights and split identity, and
publishes the canonical event-level Parquet partitions plus a dataset manifest.
Models and studies consume this event-level Parquet dataset rather than
re-reading ROOT.

## Data audit

```bash
particleml audit data \
  --config configs/analysis-v1.yaml \
  --dataset "$PARTICLEML_RUNTIME/artifacts/dataset-v1"
```

The audit checks checksum lineage, event uniqueness, unit ranges, cutflow
monotonicity, data target nullness, simulation metadata, split disjointness,
and process coverage. Passing the audit permits training; it does not permit
unblinding.

The printed JSON includes `simulation_weight_groups`, ordered by `dataset_id`,
`process_group`, `sample_role`, and `split`. Each simulation-only group reports
`events`, `negative_events`, `negative_fraction`, the signed `sum_w_yield`, and
`sum_abs_w_yield`. Nominal and generator-variation samples remain separate,
and data rows are excluded. These fields diagnose weight composition; they are
not inputs for rescaling yields or recomputing `w_train`.

## Offline Demo inputs

`particleml demo run` creates 12 deterministic local ROOT sources: one
signal, irreducible-background, reducible-background, and pseudo-data file for
each of `4e`, `4mu`, and `2e2mu`. Every source file has its own SHA-256
checksum, and the generated catalog hash binds those file records before the
normal ingestion path runs.

Pseudo-data are ingested in sideband-only mode. Events in `[120,130)` GeV are
removed, `target` remains null, and no `w_train` value is assigned. The Demo
therefore exercises the data-sideband path without creating a training or
observed-data input.
