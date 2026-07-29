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
publishes Parquet partitions plus a dataset manifest.

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
