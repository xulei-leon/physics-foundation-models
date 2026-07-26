# Development and Debugging

## Environment

The primary development target is the Jetson Orin Nano Super Developer Kit
with 8 GB memory. Development dependencies run in an isolated ARM64 Docker
container and are not installed into native JetPack. Follow the
[Jetson Orin Nano development guide](jetson-orin-nano-development-guide.md)
for image construction, bind mounts, resource controls, verification, and
step-by-step debugging.

The portable software contract remains Python 3.10--3.12 and Node.js 20 or
later. Inside the Jetson container:

```bash
python -m pip install --no-deps --editable .
pnpm install --frozen-lockfile
```

## Local gates

```bash
python -m ruff check src/particleml scripts tests
python -m mypy src/particleml
python -m pytest -q
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
