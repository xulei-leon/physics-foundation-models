"""Analysis freeze and independent observed-data authorization contracts."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    ContractError,
    canonical_json_bytes,
    require_sha256,
    sha256_document,
    validate_document,
)
from .models import BASELINE_MODEL, FORMAL_SEEDS, PRIMARY_MODEL

ARTIFACT_FIELDS = (
    "config",
    "catalog",
    "dataset",
    "tuning",
    "models",
    "predictions",
    "ddt",
    "templates",
    "fits",
    "study_result",
    "software",
)
REQUIRED_GATE_SETS = (
    *(f"{PRIMARY_MODEL}-seed-{seed}" for seed in FORMAL_SEEDS),
    f"{PRIMARY_MODEL}-ensemble",
    f"{BASELINE_MODEL}-ensemble",
)
ALLOWED_WORKSPACES = (f"{PRIMARY_MODEL}-ensemble", f"{BASELINE_MODEL}-ensemble")
AUTHORIZATION_STATEMENT = (
    "I authorize the frozen particleML analysis to process the blinded 120--130 GeV "
    "data window only for the two declared observed workspaces."
)


def _self_digest(document: Mapping[str, Any], field: str, code: str) -> str:
    canonical = deepcopy(dict(document))
    if field not in canonical:
        raise ContractError(code, f"{field} is missing")
    del canonical[field]
    return sha256_document(canonical)


def freeze_digest(document: Mapping[str, Any]) -> str:
    """Hash a freeze document without its self-referential digest."""

    return _self_digest(document, "freeze_sha256", "FREEZE_HASH_FIELD")


def authorization_digest(document: Mapping[str, Any]) -> str:
    """Hash an authorization without its self-referential digest."""

    return _self_digest(
        document,
        "authorization_sha256",
        "AUTHORIZATION_HASH_FIELD",
    )


def create_freeze_document(
    freeze_id: str,
    artifacts: Mapping[str, str],
    gate_sets: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a freeze only after every required raw gate record passes."""

    missing = sorted(set(ARTIFACT_FIELDS) - set(artifacts))
    if missing:
        raise ContractError("FREEZE_INPUT", f"missing artifact hashes: {', '.join(missing)}")
    for field in ARTIFACT_FIELDS:
        require_sha256(str(artifacts[field]), field)
    missing_gate_sets = sorted(set(REQUIRED_GATE_SETS) - set(gate_sets))
    if missing_gate_sets:
        raise ContractError(
            "FREEZE_GATES",
            f"missing required gate sets: {', '.join(missing_gate_sets)}",
        )
    for name in REQUIRED_GATE_SETS:
        record = gate_sets[name]
        if not isinstance(record, Mapping) or record.get("all_passed") is not True:
            raise ContractError("FREEZE_GATES", f"gate set did not pass: {name}")
    document: dict[str, Any] = {
        "schema_version": "2.1.0",
        "freeze_id": freeze_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifacts": {field: str(artifacts[field]) for field in ARTIFACT_FIELDS},
        "gate_sets": {name: dict(record) for name, record in gate_sets.items()},
        "freeze_sha256": "0" * 64,
    }
    document["freeze_sha256"] = freeze_digest(document)
    validate_document(document, "analysis-freeze")
    return document


def _publish_json(
    path: Path,
    document: Mapping[str, Any],
    validator: Any,
    exists_code: str,
) -> Path:
    if path.exists():
        raise ContractError(exists_code, f"output already exists: {path}")
    validator(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.partial.{uuid.uuid4().hex}")
    try:
        partial.write_bytes(canonical_json_bytes(document))
        partial.rename(path)
        return path
    finally:
        if partial.exists():
            partial.unlink()


def publish_freeze(path: Path, document: Mapping[str, Any]) -> Path:
    """Validate and atomically publish one immutable freeze JSON file."""

    return _publish_json(path, document, validate_freeze_document, "FREEZE_EXISTS")


def validate_freeze_document(
    document: Mapping[str, Any],
    expected_artifacts: Mapping[str, str] | None = None,
) -> str:
    """Validate schema, self-hash, gate records, and optional artifact hashes."""

    validate_document(document, "analysis-freeze")
    actual = freeze_digest(document)
    if actual != document["freeze_sha256"]:
        raise ContractError("FREEZE_SELF_HASH", "analysis freeze self-hash does not match")
    if expected_artifacts is not None:
        stored = document["artifacts"]
        if not isinstance(stored, Mapping):
            raise ContractError("FREEZE_ARTIFACTS", "artifacts must be a mapping")
        for field in ARTIFACT_FIELDS:
            if field not in expected_artifacts:
                raise ContractError("FREEZE_EXPECTED_HASH", f"missing expected {field}")
            if stored[field] != expected_artifacts[field]:
                raise ContractError("FREEZE_UPSTREAM_HASH", f"{field} does not match")
    return actual


def load_freeze(
    path: Path,
    expected_artifacts: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Read and validate one freeze file."""

    document = _read_object(path, "FREEZE_READ", "freeze")
    validate_freeze_document(document, expected_artifacts)
    return document


def create_unblinding_authorization(
    authorization_id: str,
    freeze_sha256: str,
    approver: str,
) -> dict[str, Any]:
    """Create a separate, self-hashed human authorization artifact."""

    require_sha256(freeze_sha256, "freeze_sha256")
    if not approver.strip():
        raise ContractError("AUTHORIZATION_APPROVER", "approver must not be empty")
    document: dict[str, Any] = {
        "schema_version": "2.1.0",
        "authorization_id": authorization_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "freeze_sha256": freeze_sha256,
        "approver": approver.strip(),
        "statement": AUTHORIZATION_STATEMENT,
        "allowed_workspaces": list(ALLOWED_WORKSPACES),
        "authorization_sha256": "0" * 64,
    }
    document["authorization_sha256"] = authorization_digest(document)
    validate_document(document, "unblinding-authorization")
    return document


def validate_unblinding_authorization(
    document: Mapping[str, Any],
    freeze_sha256: str | None = None,
) -> str:
    """Validate an authorization's schema, self-hash, and freeze binding."""

    validate_document(document, "unblinding-authorization")
    actual = authorization_digest(document)
    if actual != document["authorization_sha256"]:
        raise ContractError(
            "AUTHORIZATION_SELF_HASH",
            "unblinding authorization self-hash does not match",
        )
    if freeze_sha256 is not None and document["freeze_sha256"] != freeze_sha256:
        raise ContractError(
            "AUTHORIZATION_FREEZE",
            "authorization is bound to a different analysis freeze",
        )
    return actual


def publish_unblinding_authorization(
    path: Path,
    document: Mapping[str, Any],
) -> Path:
    """Atomically publish an independent unblinding authorization."""

    return _publish_json(
        path,
        document,
        validate_unblinding_authorization,
        "AUTHORIZATION_EXISTS",
    )


def load_unblinding_authorization(
    path: Path,
    freeze_sha256: str | None = None,
) -> dict[str, Any]:
    """Read and validate an authorization artifact."""

    document = _read_object(path, "AUTHORIZATION_READ", "authorization")
    validate_unblinding_authorization(document, freeze_sha256)
    return document


def authorize_observed_fit(
    freeze_path: Path | None,
    authorization_path: Path | None,
    unblind: bool,
    workspace_name: str | None,
    expected_artifacts: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Refuse before data access unless intent, freeze, and authorization agree."""

    if not unblind:
        raise ContractError("BLINDING_FLAG", "observed fit requires explicit --unblind")
    if freeze_path is None:
        raise ContractError("BLINDING_FREEZE", "observed fit requires --freeze PATH")
    if authorization_path is None:
        raise ContractError(
            "BLINDING_AUTHORIZATION",
            "observed fit requires --authorization PATH",
        )
    if workspace_name not in ALLOWED_WORKSPACES:
        raise ContractError(
            "BLINDING_WORKSPACE",
            f"workspace must be one of {ALLOWED_WORKSPACES}",
        )
    freeze = load_freeze(freeze_path, expected_artifacts)
    authorization = load_unblinding_authorization(
        authorization_path,
        str(freeze["freeze_sha256"]),
    )
    allowed = authorization["allowed_workspaces"]
    if workspace_name not in allowed:
        raise ContractError(
            "BLINDING_WORKSPACE",
            f"authorization does not allow {workspace_name}",
        )
    return freeze, authorization


def _read_object(path: Path, code: str, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(code, f"cannot read {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ContractError(code, f"{label} file must contain an object")
    return document
