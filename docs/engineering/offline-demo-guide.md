# Offline Synthetic Demo

The offline demo is a deterministic engineering check of the shared particleML
pipeline. It generates local synthetic ROOT files, builds the canonical
sideband-only dataset, tunes and evaluates all four declared model families,
applies DDT, runs expected pyhf fits, and publishes a non-formal report.

Run it inside an installed particleML environment:

```bash
particleml demo run \
  --output "$PARTICLEML_RUNTIME/artifacts/synthetic-demo"
```

The command has no network, input-data, model-selection, or unblinding options.
XGBoost uses the portable CPU histogram backend in this demo. The committed
formal configuration remains CUDA-enabled and is not modified.

The default run generates 360 events per source. It writes 12 local ROOT files
for three channels and four source roles. The ROOT bytes and their independent
SHA-256 checksums are deterministic for the fixed generator inputs, and all
models use the fixed seeds `17`, `42`, `314`, `2026`, and `2718`.

## Model roles

| Model | Fixed role |
|---|---|
| `cut_based` | primary physics baseline |
| `logistic` | linear control |
| `xgboost` | primary research model |
| `mlp` | nonlinear control |

Every model receives the same selected events, feature contract, absolute
class-normalized training weights, five seeds, DDT transformation, test
templates, and expected-fit procedure. Only the XGBoost-versus-cut-based
expected significance difference is the primary endpoint.

## Outputs

The published artifact contains:

```text
report.md
demo-summary.json
roc-comparison.png
expected-significance-comparison.png
xgboost-score-distribution.png
xgboost-score-vs-m4l.png
xgboost-m4l-by-ddt-category.png
completion.json
```

Every report and figure is marked `SYNTHETIC DEMO — NON-FORMAL`.
`demo-summary.json` has `formal_eligible: false` and records the portable
runtime and the exact lineage needed to inspect the run:

- configuration, synthetic catalog, canonical dataset, and tuning-decision
  SHA-256 hashes;
- data counts and split counts;
- fixed model roles and five seeds;
- ensemble classification metrics, expected significance, and DDT gate
  results for all four models;
- the XGBoost-minus-cut-based primary comparison;
- particleML, Python, scikit-learn, and XGBoost versions plus the recorded
  CPU/hist backend; and
- SHA-256 hashes for the report and all five figures.

The ROC and score-distribution figures use nominal test simulation only, with
absolute `w_yield` values. The XGBoost mass-by-DDT-category figure uses signed
`w_yield` because it displays expected yields rather than classifier metrics.

## Safety boundary

- No ATLAS collision data or remote resource is read.
- Synthetic pseudo-data have no target or training weight.
- Synthetic pseudo-data in 120--130 GeV are removed during ingestion.
- Gate failures are retained as diagnostics and do not become physics claims.
- No usable `freeze-inputs.json`, authorization, or observed workspace is
  published.
- `particleml analysis freeze --inputs <demo-output>` fails with
  `FREEZE_DEMO`.

Scientific gates or an unavailable primary expected fit can set
`study_status: blocked` while the outer Demo still publishes with
`status: completed`. pyhf minimization failures are retained as
`FIT_MINIMIZATION` contract diagnostics. A failed ensemble nuisance diagnostic
is recorded separately and does not discard a successful main fit.

The demo proves that the engineering path executes. It does not validate the
formal CUDA runtime, public-data catalog, physics gates, analysis freeze, or
observed result, and it does not assert that XGBoost must outperform the
baseline on synthetic data.
