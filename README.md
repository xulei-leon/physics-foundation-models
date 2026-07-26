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
- Software and contract suite: `2.1.0`
- Python package: `0.3.0`
- Observed signal window: **blinded**
- Current migration status: implementation and offline fixture validation

No observed processing is permitted without both a valid analysis freeze and
a separately created, self-hashed human authorization bound to that freeze.
The implementation is verified with offline fixtures; formal physics results,
the analysis freeze, authorization, and observed fits have not been produced.

## Primary development platform

The declared development and debugging target is the **NVIDIA Jetson Orin Nano
Super Developer Kit with 8 GB memory**. Development runs in an isolated ARM64
Docker container on the JetPack host. Python 3.10, Node.js, pnpm, compilers,
and project dependencies are installed in the image rather than in the native
JetPack environment. The analysis uses CPU implementations of scikit-learn,
XGBoost, and pyhf; CUDA, PyTorch, and other deep-learning frameworks are not
required.

Use an NVMe SSD for the repository and the dedicated runtime cache and artifact
directory. Docker image-layer placement remains managed by the existing
JetPack Docker installation. Only the repository and the runtime directory are
mounted into the container.

## Quick start

```bash
export PARTICLEML_HOST_ROOT=/mnt/nvme/particleml
export PARTICLEML_DEV_IMAGE=particleml-jetson-dev:0.3.0

test "$(id -u)" -gt 0
test "$(id -g)" -gt 0

cd "$PARTICLEML_HOST_ROOT/particleML"
docker build \
  --build-arg HOST_UID="$(id -u)" \
  --build-arg HOST_GID="$(id -g)" \
  --file docker/jetson-dev/Dockerfile \
  --tag "$PARTICLEML_DEV_IMAGE" \
  .
```

The complete image build, bind-mount, resource-limit, verification, debugging,
and container lifecycle procedures are documented in the
[Jetson Orin Nano development guide](docs/engineering/jetson-orin-nano-development-guide.md).
The formal command sequence and configuration contracts are documented in the
[analysis run guide](docs/engineering/analysis-run-guide.md). The
[research plan](docs/research/research-plan.md) separates fixed methodology
from results that have not yet been produced.

The superseded project is preserved by a local annotated tag and archive
branch documented in the site archive.

## License

See [LICENSE](LICENSE).
