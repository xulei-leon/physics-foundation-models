# particleML

particleML is a reproducible, blinded machine-learning analysis of the public
ATLAS 2015+2016 education dataset for
\(H\rightarrow ZZ^*\rightarrow4\ell\). It compares a physics cut-based
baseline with Logistic Regression, XGBoost, and a scikit-learn MLP, then uses a
DDT-style conditional CDF to control four-lepton-mass sculpting before a
six-channel pyhf profile-likelihood fit.

The scientific scope is deliberately limited to the 36 fb\(^{-1}\) education
release. It is a portfolio-grade analysis, not an experimental discovery or
precision-measurement claim.

## Status

- Research plan: `v1.0.0`
- Software and contract suite: `2.0.0`
- Python package: `0.2.0`
- Observed signal window: **blinded**
- Current migration status: implementation and offline fixture validation

No observed fit is permitted without a valid analysis-freeze artifact whose
hash matches the inputs and whose decorrelation gates all pass.

## Quick start

```bash
python -m pip install --requirement requirements-ci.lock
python -m pip install --no-deps --editable .
particleml contracts validate
pytest
python scripts/validate_software_docs.py
```

The command sequence and configuration contracts are documented in
[the analysis run guide](docs/engineering/analysis-run-guide.md). The
[research plan](docs/research/research-plan.md) separates fixed methodology
from results that have not yet been produced.

The superseded project is preserved by a local annotated tag and archive
branch documented in the site archive.

## License

See [LICENSE](LICENSE).
