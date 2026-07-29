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

python -m ruff check src/particleml scripts tests
python -m mypy --cache-dir="$PARTICLEML_MYPY_CACHE" src/particleml
python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE"
python scripts/validate_software_docs.py
pnpm test
pnpm docs:build
```

Tests use generated ROOT and Parquet fixtures and must not require network
access. A network-dependent test belongs in an explicitly marked integration
profile, not the default suite.

## Failure classes

- `ContractError`: invalid schema, unknown config key, prohibited field, missing
  metadata, or blinding refusal. Fix the input or protocol.
- `IntegrityError`: checksum, hash, duplicate event, stale artifact, or atomic
  publication failure. Do not reuse the output.
- `PhysicsError`: no valid pairing, inconsistent units, non-finite kinematics,
  or selection invariant violation.

Do not work around a failed gate by changing a threshold after looking at test
or signal-window data. Update the research plan first and create a new plan
version.

## Artifact debugging

Inspect `completion.json` before payloads. Confirm the configuration and input
hashes, then recompute payload hashes. A directory without a completion record
is incomplete even if its payload files look valid.
