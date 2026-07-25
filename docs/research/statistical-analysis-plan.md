# Statistical Analysis Plan

## Likelihood structure

The pyhf workspace contains six channels:

```text
4e_low, 4e_high, 4mu_low, 4mu_high, 2e2mu_low, 2e2mu_high
```

Each channel uses 1 GeV four-lepton-mass bins from 105 through 160 GeV. Signal,
irreducible background, and reducible background are separate samples.
Sidebands and the signal interval belong to the same binned likelihood.

## Uncertainties

- Simulation statistical uncertainty: `staterror` or `shapesys`.
- Luminosity: 2.1%, correlated on simulated yields.
- Signal theory: 5%.
- Irreducible-background normalization: 10%.
- Reducible-background normalization: 50%.

These are deliberately limited pedagogical uncertainties. They do not
constitute a complete detector or theory systematic model.

## Template integrity

Signed yield weights populate templates. If a template bin is non-positive,
the builder merges it with a deterministic adjacent mass bin. If a positive
template cannot be obtained without crossing the analysis boundary, the fit
is rejected.

## Endpoints

The primary endpoint is the expected significance difference between
XGBoost-DDT and the cut-based baseline. Secondary endpoints include expected
significance ratios, \(\hat\mu\), confidence intervals, weighted ROC-AUC,
weighted PR-AUC, and background rejection.

The expected fit is executable during migration. An observed fit requires:

1. an explicit `--unblind` flag;
2. a valid analysis-freeze artifact;
3. matching hashes for configuration, catalog, canonical data, predictions,
   and templates;
4. all DDT and spurious-signal gates recorded as passed.

Missing or mismatched evidence causes refusal before reading signal-window
data.
