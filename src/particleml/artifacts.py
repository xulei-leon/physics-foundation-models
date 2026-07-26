"""Immutable, content-addressed directory artifacts."""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import canonical_json_bytes, require_sha256, sha256_document, sha256_file

COMPLETION_FILENAME = "completion.json"


class IntegrityError(RuntimeError):
    """Raised when an artifact cannot be trusted or atomically published."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Artifact:
    """Published artifact identity."""

    path: Path
    sha256: str
    schema_version: str = "2.1.0"


def _payload_records(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != COMPLETION_FILENAME:
            records.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    if not records:
        raise IntegrityError("ARTIFACT_EMPTY", "artifact contains no payload files")
    return records


def publish_artifact(
    final: Path,
    writer: Callable[[Path], None],
    validator: Callable[[Path], None],
    input_hashes: Mapping[str, str],
    config_sha256: str,
    writer_version: str,
) -> Artifact:
    """Write, validate, hash, atomically publish, and complete one artifact."""

    for label, value in input_hashes.items():
        try:
            require_sha256(value, label)
        except ValueError as exc:
            raise IntegrityError("ARTIFACT_INPUT_HASH", str(exc)) from exc
    try:
        require_sha256(config_sha256, "config_sha256")
    except ValueError as exc:
        raise IntegrityError("ARTIFACT_CONFIG_HASH", str(exc)) from exc
    if not writer_version:
        raise IntegrityError("ARTIFACT_WRITER_VERSION", "writer version must not be empty")
    if final.exists():
        raise IntegrityError("ARTIFACT_EXISTS", f"formal output already exists: {final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    partial = final.with_name(f"{final.name}.partial.{uuid.uuid4().hex}")
    partial.mkdir()
    published = False
    try:
        writer(partial)
        validator(partial)
        payloads = _payload_records(partial)
        artifact_hash = sha256_document(payloads)
        marker = {
            "schema_version": "2.1.0",
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "writer_version": writer_version,
            "input_hashes": dict(sorted(input_hashes.items())),
            "config_sha256": config_sha256,
            "payloads": payloads,
            "artifact_sha256": artifact_hash,
        }
        (partial / COMPLETION_FILENAME).write_bytes(canonical_json_bytes(marker))
        partial.rename(final)
        published = True
        return Artifact(final, artifact_hash)
    finally:
        if not published and partial.exists():
            shutil.rmtree(partial, ignore_errors=True)


def verify_artifact(path: Path) -> Artifact:
    """Recompute every payload digest and the aggregate completion hash."""

    marker_path = path / COMPLETION_FILENAME
    if not marker_path.is_file():
        raise IntegrityError("ARTIFACT_INCOMPLETE", f"missing {marker_path}")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("schema_version") != "2.1.0":
        raise IntegrityError("ARTIFACT_VERSION", "unsupported completion record version")
    actual = _payload_records(path)
    if actual != marker.get("payloads"):
        raise IntegrityError("ARTIFACT_PAYLOAD", "payload list or digest does not match")
    digest = sha256_document(actual)
    if digest != marker.get("artifact_sha256"):
        raise IntegrityError("ARTIFACT_HASH", "aggregate artifact hash does not match")
    return Artifact(path, digest)
