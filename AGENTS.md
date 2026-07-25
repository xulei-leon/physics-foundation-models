# AGENTS.md

## Project

particleML is a blinded ATLAS Open Data analysis of
\(H\rightarrow ZZ^*\rightarrow4\ell\). The fixed research question asks how
much an XGBoost classifier, after validated mass decorrelation, improves
expected profile-likelihood sensitivity over a cut-based baseline.

## Non-negotiable scientific rules

- Treat the ATLAS education release as an outreach dataset, not an
  experiment-grade measurement.
- Keep real events out of training and keep the 120--130 GeV data window
  blinded until a valid analysis freeze exists.
- Never use `m4l`, identities, process labels, truth fields, or weights as model
  inputs.
- Use signed yield weights only for yields and templates; use absolute,
  class-normalized weights only for training.
- Fit DDT calibration only on calibration-split background simulation.
- A failed decorrelation, sideband-efficiency, or spurious-signal gate blocks
  unblinding. Do not silently retune or relax a gate.
- All data discovery and reads use direct HTTPS with checksum verification.

## Engineering rules

- Python 3.10--3.12; no deep-learning framework dependency.
- Canonical data are event-level Parquet files.
- Configurations reject unknown keys.
- Formal outputs use partial paths, validation, hashing, atomic publication,
  and completion records.
- Notebooks may consume published artifacts but must not contain unique
  analysis logic.
- Every scientific claim must trace to config, manifest, run record,
  predictions, freeze, and fit result.
- Prefer the codebase knowledge graph for code discovery before text search.
- Do not use web-service or remote-filesystem abstractions; make explicit
  HTTP/HTTPS requests and permit HTTPS only for analysis inputs.
- Ask for human confirmation before using multiple subagents.
- Do not enable optional superpower workflows unless the user explicitly asks.

All repository text, code comments, and documentation must be written in
English.
