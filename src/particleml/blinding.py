"""Analysis-freeze creation and observed-fit authorization."""

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

HASH_FIELDS = (
    "config_sha256",
    "catalog_sha256",
    "dataset_manifest_sha256",
    "prediction_sha256",
    "template_sha256",
)


def freeze_digest(document: Mapping[str, Any]) -> str:
    """Hash a freeze document without its self-referential digest."""

    canonical = deepcopy(dict(document))
    if "freeze_sha256" not in canonical:
        raise ContractError("FREEZE_HASH_FIELD", "freeze_sha256 is missing")
    del canonical["freeze_sha256"]
    return sha256_document(canonical)


def create_freeze_document(
    freeze_id: str,
    hashes: Mapping[str, str],
    gate_results: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a freeze only after every hard decorrelation gate passes."""

    missing = sorted(set(HASH_FIELDS) - set(hashes))
    if missing:
        raise ContractError("FREEZE_INPUT", f"missing hashes: {', '.join(missing)}")
    for field in HASH_FIELDS:
        require_sha256(str(hashes[field]), field)
    if gate_results.get("all_passed") is not True:
        raise ContractError("FREEZE_GATES", "all decorrelation gates must pass")
    gate_names = (
        "mc_spearman",
        "data_sideband_spearman",
        "sideband_acceptance",
        "spurious_signal",
    )
    gates: dict[str, bool] = {}
    for name in gate_names:
        record = gate_results.get(name)
        if not isinstance(record, Mapping) or record.get("passed") is not True:
            raise ContractError("FREEZE_GATES", f"gate did not pass: {name}")
        gates[name] = True
    document: dict[str, Any] = {
        "schema_version": "2.0.0",
        "freeze_id": freeze_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **{field: str(hashes[field]) for field in HASH_FIELDS},
        "gates": gates,
        "observed_fit_authorized": True,
        "freeze_sha256": "0" * 64,
    }
    document["freeze_sha256"] = freeze_digest(document)
    validate_document(document, "analysis-freeze")
    return document


def publish_freeze(path: Path, document: Mapping[str, Any]) -> Path:
    """Validate and atomically publish one immutable freeze JSON file."""

    if path.exists():
        raise ContractError("FREEZE_EXISTS", f"freeze output already exists: {path}")
    validate_freeze_document(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.partial.{uuid.uuid4().hex}")
    try:
        partial.write_bytes(canonical_json_bytes(document))
        partial.rename(path)
        return path
    finally:
        if partial.exists():
            partial.unlink()


def validate_freeze_document(
    document: Mapping[str, Any], expected_hashes: Mapping[str, str] | None = None
) -> str:
    """Validate schema, self-hash, gate constants, and optional upstream hashes."""

    validate_document(document, "analysis-freeze")
    actual = freeze_digest(document)
    if actual != document["freeze_sha256"]:
        raise ContractError("FREEZE_SELF_HASH", "analysis freeze self-hash does not match")
    if expected_hashes is not None:
        for field in HASH_FIELDS:
            if field not in expected_hashes:
                raise ContractError("FREEZE_EXPECTED_HASH", f"missing expected {field}")
            if document[field] != expected_hashes[field]:
                raise ContractError("FREEZE_UPSTREAM_HASH", f"{field} does not match")
    return actual


def load_freeze(path: Path, expected_hashes: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Read and validate one freeze file."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("FREEZE_READ", f"cannot read {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ContractError("FREEZE_OBJECT", "freeze file must contain an object")
    validate_freeze_document(document, expected_hashes)
    return document


def authorize_observed_fit(
    freeze_path: Path | None,
    unblind: bool,
    expected_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Refuse before data access unless explicit intent and a valid freeze exist."""

    if not unblind:
        raise ContractError("BLINDING_FLAG", "observed fit requires explicit --unblind")
    if freeze_path is None:
        raise ContractError("BLINDING_FREEZE", "observed fit requires --freeze PATH")
    return load_freeze(freeze_path, expected_hashes)
