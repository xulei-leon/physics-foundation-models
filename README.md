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
- Python package: `0.4.0`
- Jetson Docker environment: verified on the documented ARM64/CUDA host
- Observed signal window: **blinded**
- Current migration status: implementation and offline fixture validation

No observed processing is permitted without both a valid analysis freeze and
a separately created, self-hashed human authorization bound to that freeze.
The implementation is verified with offline fixtures; formal physics results,
the analysis freeze, authorization, and observed fits have not been produced.

## Primary development platform

The declared development and debugging target is the **NVIDIA Jetson Orin Nano
Super Developer Kit with 8 GB memory**. Development runs in an isolated ARM64
Docker container on the JetPack host. The verified image is based on
`nvcr.io/nvidia/pytorch:25.06-py3-igpu` and provides CUDA 12.9, Python 3.12,
Node.js 20.19.5, pnpm 10.33.0, and XGBoost 3.3.0 compiled for SM 8.7. PyTorch
is supplied by the base image but is not a particleML dependency.

The formal XGBoost configuration uses CUDA with the histogram tree method.
Other model families remain on their native CPU implementations. The checkout
and dedicated runtime directory are stored on NVMe and bind-mounted into the
container; project-specific dependencies remain in Docker.

XGBoost is the primary model component, not a separate analysis stack.
Cut-based, Logistic Regression, XGBoost, and MLP paths share the same data,
feature, weighting, DDT, and expected-fit contracts.

## Quick start

```bash
export PARTICLEML_HOST_ROOT="$HOME/code/particleML"
export PARTICLEML_DEV_IMAGE=particleml-jetson-dev:0.4.0
export JETSON_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:25.06-py3-igpu

test "$(id -u)" -gt 0
test "$(id -g)" -gt 0

cd "$PARTICLEML_HOST_ROOT"
sudo docker buildx build \
  --load \
  --network host \
  --build-arg JETSON_PYTORCH_IMAGE="$JETSON_PYTORCH_IMAGE" \
  --build-arg HOST_UID="$(id -u)" \
  --build-arg HOST_GID="$(id -g)" \
  --file docker/jetson-dev/Dockerfile \
  --tag "$PARTICLEML_DEV_IMAGE" \
  .
```

The verified board requires `sudo docker`, `--runtime nvidia` for GPU-enabled
containers, and host networking for builds and the persistent development
container.

The deterministic offline demo uses synthetic ROOT inputs and the portable CPU
backend:

```bash
particleml demo run --output "$PARTICLEML_RUNTIME/artifacts/synthetic-demo"
```

The complete image build, bind-mount, resource-limit, verification, debugging,
and container lifecycle procedures are documented in the
[Jetson Orin Nano development guide](docs/engineering/jetson-orin-nano-development-guide.md).
The formal command sequence and configuration contracts are documented in the
[analysis run guide](docs/engineering/analysis-run-guide.md). The
[offline demo guide](docs/engineering/offline-demo-guide.md) documents the
non-formal, no-network engineering check. The
[research plan](docs/research/research-plan.md) separates fixed methodology
from results that have not yet been produced.

The superseded project is preserved by a local annotated tag and archive
branch documented in the site archive.

## License

See [LICENSE](LICENSE).
