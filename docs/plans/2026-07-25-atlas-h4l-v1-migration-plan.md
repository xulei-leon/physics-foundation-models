# ATLAS H4l v1 Migration Plan

**Date:** 2026-07-25  
**Plan version:** 1.0.0  
**Software contract version:** 2.0.0  
**Package version:** 0.2.0  
**Status:** implementation in progress

## Objective

Migrate particleML to a blinded, reproducible study of
\(H\rightarrow ZZ^*\rightarrow4\ell\) classification and statistical
inference using the public ATLAS 2015+2016 education release. The main
comparison is XGBoost-DDT versus a fixed cut-based baseline. The migration
delivers code, documentation, schemas, offline fixtures, and reproducible
tests; it does not unblind the real-data signal window.

The legacy repository is preserved outside the active tree through an
annotated tag and an archive branch. The new line intentionally breaks the old
Python, CLI, data, and schema interfaces.

## Fixed scientific question

> Under a fixed \(H\to ZZ^*\to4\ell\) preselection and a validated
> mass-decorrelation protocol, how much does an XGBoost classifier improve
> expected profile-likelihood sensitivity over a cut-based baseline, and is
> the improvement stable across final states, seeds, and limited systematic
> variations?

Claims are limited to the education release. No result may be described as an
experiment-grade discovery or precision measurement.

## M0 — Archive

1. Record the clean pre-migration commit, Git tree, file tree, and test result.
2. Create the local annotated tag recorded in the legacy index.
3. Create the local archive branch recorded in the legacy index.
4. Create and switch to `codex/atlas-h4l-v1`.
5. Verify that both archive refs resolve to the pre-migration commit.
6. Keep only one active historical index in the new documentation.

The user explicitly chose local-only archival after authentication problems;
no remote push is part of this migration run.

## M1 — Research and contracts

1. Freeze Research Plan v1.0.0.
2. Replace all schemas with Draft 2020-12 contract suite 2.0.0:
   dataset catalog, dataset manifest, split manifest, run record, prediction
   metadata, analysis freeze, and fit result.
3. Add strict YAML configuration with unknown-key rejection.
4. Replace governance, requirements, architecture, specification,
   traceability, research, and engineering documentation.
5. Mark unexecuted science and external-data steps as `planned`, never
   `verified`.

Acceptance: schemas self-validate, negative fixtures fail, documentation links
resolve, and the migration/archive records agree with Git.

## M2 — Data pipeline

1. Resolve official records `atlas-93924` and `atlas-93928` through direct
   HTTPS and freeze file URLs, sizes, and SHA-256 checksums.
2. Fail closed for unknown simulated processes, missing normalisation
   metadata, alternative generators in nominal yields, non-HTTPS URLs, or
   checksum mismatch.
3. Read ROOT in chunks, convert MeV to GeV at ingestion, select and pair four
   leptons, calculate kinematics, weights, and deterministic splits, and
   publish event-level Parquet.
4. Preserve canonical identity:
   `dataset_id`, `file_checksum`, `entry_index`, `event_id`, `is_data`,
   `process_group`, `channel`, and `split`.

Acceptance: golden kinematics, pairing ambiguities, cut boundaries, unit
conversion, weight failures, data isolation, per-dataset split coverage, and
synthetic ROOT-to-Parquet tests pass offline.

## M3 — Models and decorrelation

1. Build the frozen primary feature matrix and reject mass, identity, process,
   truth, and weight columns.
2. Implement cut-based, Logistic Regression, XGBoost, and scikit-learn MLP.
3. Tune once with seed 42, freeze hyperparameters, run formal seeds
   17, 42, 314, 2026, and 2718, and align event predictions before averaging.
4. Fit a DDT conditional CDF on calibration-background simulation only.
5. Merge 5 GeV mass bins in deterministic adjacent order when
   \(n_\mathrm{eff}<200\).
6. Enforce the mass-correlation, sideband-efficiency, and spurious-signal
   gates without automatic retuning.

Acceptance: feature isolation, seed reproducibility, prediction alignment,
conditional-CDF behavior, adaptive merging, and gate refusal tests pass.

## M4 — Statistical inference and blinding

1. Build 1 GeV mass templates for three final states and low/high DDT
   categories.
2. Keep signal, irreducible background, and reducible background separate.
3. Add simulation statistical uncertainties and normalization nuisances:
   luminosity 2.1%, signal theory 5%, irreducible background 10%, and
   reducible background 50%.
4. Merge non-positive template bins with a fixed adjacent rule and fail if no
   positive template is possible.
5. Implement expected pyhf fits, background-only spurious-signal tests,
   analysis-freeze creation, and observed-fit refusal.
6. Produce a blinded report. Do not execute an observed fit on the real
   signal window during migration.

Acceptance: expected-fit fixture, nuisance contract, non-positive-bin handling,
freeze hash validation, and mandatory observed-fit refusal pass.

## M5 — Clean break and release verification

1. Remove all active legacy code, configurations, notebooks, tests, and
   historical planning/review material.
2. Retain only the legacy index for historical terminology.
3. Run ruff, strict mypy, Python 3.10--3.12 pytest expectations,
   documentation validation, VitePress tests/build, and a tracked-file
   stale-term audit.
4. Run a no-network synthetic end-to-end pipeline:
   ROOT to Parquet to train to DDT to expected fit to report.
5. Reindex the codebase knowledge graph.

Acceptance: a fresh clone can run the fixture pipeline without network access;
real data remain blinded; every formal artifact has validated hashes and
provenance.

## Fixed analysis contract

### Data and selection

- Exactly four electrons or muons.
- Ordered lepton \(p_T>20,15,10,7\) GeV.
- \(|\eta_e|<2.47\), \(|\eta_\mu|<2.7\).
- Tight identification, loose isolation, zero total charge.
- At least one trigger-matched lepton and a valid electron, muon, or dilepton
  trigger.
- Two same-flavour opposite-sign pairs. \(Z_1\) is closest to 91.1876 GeV;
  ties use lexicographic lepton indices.
- \(50<m_{Z_1}<106\) GeV, \(12<m_{Z_2}<115\) GeV, and every same-flavour
  opposite-sign pair above 5 GeV.
- Analysis range \(105\le m_{4\ell}<160\) GeV.
- Blinded window 120--130 GeV; sidebands 105--120 and 130--160 GeV.

### Training and features

The split key is the SHA-256 digest of dataset identifier, file checksum, and
entry index. Buckets are 70% train, 10% calibration, 10% validation, and 10%
test within every dataset.

The primary features are dimensionless lepton transverse-momentum fractions,
pairwise angular variables, dilepton mass fractions, four-lepton
transverse-momentum fraction, missing-transverse-momentum fraction, limited
jet ratios, normalized decay angles, and final-state channel indicators.

The model matrix must not include four-lepton mass, a complete raw
four-lepton four-vector, identifiers, weights, truth, or class-derived process
fields.

### Weights

```text
w_yield =
  luminosity_pb
  * xsec_pb * kfactor * filter_efficiency / sum_of_generator_weights
  * mcWeight
  * ScaleFactor_PILEUP
  * ScaleFactor_ELE
  * ScaleFactor_MUON
  * ScaleFactor_LepTRIGGER
```

```text
w_train = abs(w_yield) * class_normalization
```

Signal and background each contribute total absolute training weight 0.5.
Signed yield weights remain exclusive to yields and statistical templates.

### DDT gates

Define
\(score_\mathrm{ddt}=F_B(score_\mathrm{raw}\mid m_{4\ell},channel)\) using
calibration-background simulation. Final categories are low `[0,0.8)` and
high `[0.8,1]`.

Unblinding is blocked unless:

- background simulation and data sidebands each satisfy
  \(|\rho_\mathrm{Spearman}|<0.05\);
- every valid sideband bin has high-score acceptance in `[0.15,0.25]`;
- background-only spurious signal is below \(0.2\sigma\).

## Commit policy

M1 through M5 are committed independently on the local development branch.
No force push, remote push, observed fit, or deletion of archive refs is part
of this implementation.
