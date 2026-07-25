# Development and Debugging

## Environment

Use Python 3.10--3.12 and Node.js 20 or later:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --requirement requirements-ci.lock
python -m pip install --no-deps --editable .
pnpm install --frozen-lockfile
```

## Local gates

```powershell
ruff check
mypy src/particleml
pytest
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
