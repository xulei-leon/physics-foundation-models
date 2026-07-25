# Data Access and Dataset Build

## Catalog

Generate record metadata and file entries only through direct HTTPS:

```powershell
particleml catalog validate --config configs/catalog-sources.yaml --catalog path/to/catalog.json
```

The formal catalog stores an HTTPS URL, byte size, and SHA-256 checksum for
every file. Redirects to a non-HTTPS scheme, missing checksums, unknown process
names, and ambiguous nominal signal generators are errors.

Full public files are not downloaded during the repository migration. The
default CI path uses synthetic local ROOT fixtures whose manifest has the same
contract.

## Canonical build

```powershell
particleml dataset build `
  --config configs/analysis-v1.yaml `
  --catalog path/to/catalog.json `
  --output artifacts/dataset-v1
```

The builder streams ROOT chunks, validates required branches, converts MeV to
GeV, runs selection and pairing, computes weights and split identity, and
publishes Parquet partitions plus a dataset manifest.

## Data audit

```powershell
particleml audit data --dataset artifacts/dataset-v1
```

The audit checks checksum lineage, event uniqueness, unit ranges, cutflow
monotonicity, data target nullness, simulation metadata, split disjointness,
and process coverage. Passing the audit permits training; it does not permit
unblinding.
