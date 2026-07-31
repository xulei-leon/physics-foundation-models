# Development and Debugging

## Environment

The primary development target is the Jetson Orin Nano Super Developer Kit
with 8 GB memory. The host stores the checkout on NVMe and may provide Git,
CA certificates, Docker, and Docker Buildx. ParticleML-specific dependencies
run in an isolated ARM64 container based on
`nvcr.io/nvidia/pytorch:25.06-py3-igpu`.

The verified container provides CUDA 12.9, Python 3.12, Node.js 20.19.5,
pnpm 10.33.0, and XGBoost 3.3.0 compiled for the Orin SM 8.7 GPU. Use
`sudo docker`, Buildx with `--load`, and `--runtime nvidia`; the documented
board also requires host networking because its Docker bridge cannot create
the legacy iptables `raw` rule. Follow the
[Jetson Orin Nano development guide](jetson-orin-nano-development-guide.md)
for image construction, bind mounts, resource controls, verification, and
step-by-step debugging.

The portable software contract remains Python 3.10--3.12 and Node.js 20 or
later. The formal XGBoost configuration uses `tree_method: hist` and
`device: cuda` in the verified Jetson container. Portable CPU-only test runs
must override the device explicitly and do not validate the CUDA path.

Inside the Jetson container:

```bash
cd /workspace/particleML
python -m pip install --no-deps --editable .
pnpm install --frozen-lockfile
```

## Local gates

```bash
export PARTICLEML_PYTEST_CACHE=/workspace/runtime/tmp/pytest-cache
export RUFF_CACHE_DIR=/workspace/runtime/tmp/ruff-cache
export PARTICLEML_MYPY_CACHE=/workspace/runtime/tmp/mypy-cache

ubuntu@leon-orin:/workspace/particleML$ python -m ruff check src/particleml scripts tests
All checks passed!

ubuntu@leon-orin:/workspace/particleML$ python -m mypy --cache-dir="$PARTICLEML_MYPY_CACHE" src/particleml
Success: no issues found in 23 source files

ubuntu@leon-orin:/workspace/particleML$ python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE"
83 passed

ubuntu@leon-orin:/workspace/particleML$ python scripts/validate_software_docs.py
documentation validation passed (7 checks)

pnpm test
pnpm docs:build
```

Tests use generated ROOT and Parquet fixtures and must not require network
access. A network-dependent test belongs in an explicitly marked integration
profile, not the default suite.

The complete portable pipeline can also be exercised offline:

```bash
particleml demo run --output "$PARTICLEML_RUNTIME/artifacts/synthetic-demo"
```

This command uses deterministic synthetic inputs and XGBoost
`device: cpu`/`tree_method: hist`. It does not validate the formal Jetson
CUDA path or produce an analysis-freeze input.

## Failure classes

- `ContractError`: invalid schema, unknown config key, prohibited field, missing
  metadata, blinding refusal, or a wrapped pyhf optimizer failure. A pyhf
  `FailedMinimization` is reported as `FIT_MINIMIZATION`; the affected fit is
  blocked and the original failure remains in the run diagnostics.
- `IntegrityError`: checksum, hash, duplicate event, stale artifact, or atomic
  publication failure. Do not reuse the output.
- `PhysicsError`: no valid pairing, inconsistent units, non-finite kinematics,
  or selection invariant violation.

Raw-score weighted-KS diagnostics fail with `ContractError` when score or
weight arrays are non-numeric, non-finite, non-one-dimensional, misaligned, or
when the primitive receives a sample with zero total absolute weight. The
study-level adapter converts only an absent positive absolute train or test
weight into a class-specific `null`; it still computes the other class when
valid. Do not replace malformed inputs with `null` or add a diagnostic
threshold to work around the failure.

If XGBoost produces constant scores or trees without splits, first confirm the
training weights are the required absolute class-normalized `w_train`. Each
class sums to 0.5, so the committed `min_child_weight: 0.01` is intentional;
XGBoost's default threshold is too large for that normalized scale.

Do not work around a failed gate by changing a threshold after looking at test
or signal-window data. Update the research plan first and create a new plan
version.

## Artifact debugging

Inspect `completion.json` before payloads. Confirm the configuration and input
hashes, then recompute payload hashes. A directory without a completion record
is incomplete even if its payload files look valid.
