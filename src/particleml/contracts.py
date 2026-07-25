"""Strict JSON/YAML contracts and canonical hashing for particleML v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

SCHEMA_VERSION = "2.0.0"
SCHEMA_NAMES = (
    "dataset-catalog",
    "dataset-manifest",
    "split-manifest",
    "run-record",
    "prediction-metadata",
    "analysis-freeze",
    "fit-result",
)

FORBIDDEN_EXACT_FIELDS = frozenset(
    {
        "m4l",
        "event_id",
        "dataset_id",
        "file_checksum",
        "entry_index",
        "is_data",
        "process_group",
        "split",
        "target",
        "label",
        "truth",
        "w_yield",
        "w_train",
        "weight",
        "mcweight",
        "dsid",
    }
)
FORBIDDEN_FIELD_TOKENS = (
    "truth",
    "weight",
    "identifier",
    "dataset_id",
    "file_checksum",
    "entry_index",
    "process_group",
)


class ContractError(ValueError):
    """Raised when an input violates a versioned analysis contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def repository_root() -> Path:
    """Return the source-checkout root."""

    return Path(__file__).resolve().parents[2]


def canonical_json_bytes(document: object) -> bytes:
    """Serialize a JSON-compatible object deterministically."""

    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""

    return hashlib.sha256(payload).hexdigest()


def sha256_document(document: object) -> str:
    """Hash a JSON-compatible document using canonical serialization."""

    return sha256_bytes(canonical_json_bytes(document))


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object or raise a stable contract error."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("CONTRACT_JSON", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("CONTRACT_OBJECT", f"{path} must contain a JSON object")
    return value


def schema_path(name: str, root: Path | None = None) -> Path:
    """Resolve one schema name from the v2 suite."""

    if name not in SCHEMA_NAMES:
        raise ContractError("CONTRACT_SCHEMA_NAME", f"unknown schema: {name}")
    base = root if root is not None else repository_root()
    return base / "schemas" / f"{name}.schema.json"


def load_schema(name: str, root: Path | None = None) -> dict[str, Any]:
    """Load and self-check one Draft 2020-12 schema."""

    schema = load_json(schema_path(name, root))
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ContractError("CONTRACT_SCHEMA_INVALID", f"{name}: {exc.message}") from exc
    return schema


def validate_document(
    document: Mapping[str, Any], name: str, root: Path | None = None
) -> None:
    """Validate a document and report the first deterministic error."""

    validator = Draft202012Validator(load_schema(name, root), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(dict(document)), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        raise ContractError("CONTRACT_VALIDATION", f"{name} at {path}: {error.message}")


def validate_file(path: Path, name: str, root: Path | None = None) -> dict[str, Any]:
    """Load and validate a JSON contract file."""

    document = load_json(path)
    validate_document(document, name, root)
    return document


def validate_schema_suite(root: Path | None = None) -> tuple[str, ...]:
    """Self-check every schema and return the validated names."""

    for name in SCHEMA_NAMES:
        load_schema(name, root)
    return SCHEMA_NAMES


def model_input_hash(fields: Iterable[str]) -> str:
    """Validate, canonicalize, and hash the serialized model input field list."""

    normalized = validate_model_input_fields(fields)
    return sha256_document(normalized)


def validate_model_input_fields(fields: Iterable[str]) -> list[str]:
    """Reject leakage-prone columns before a model matrix is constructed."""

    normalized = list(fields)
    if not normalized:
        raise ContractError("FEATURE_EMPTY", "model input field list must not be empty")
    if len(normalized) != len(set(normalized)):
        raise ContractError("FEATURE_DUPLICATE", "model input fields must be unique")
    for field in normalized:
        lowered = field.lower()
        if lowered in FORBIDDEN_EXACT_FIELDS or any(
            token in lowered for token in FORBIDDEN_FIELD_TOKENS
        ):
            raise ContractError("FEATURE_FORBIDDEN", f"forbidden model input field: {field}")
    return normalized


def require_sha256(value: str, label: str) -> None:
    """Reject malformed content digests."""

    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ContractError("CONTRACT_SHA256", f"{label} is not a lowercase SHA-256 digest")


def check_validation_error(document: Mapping[str, Any], name: str) -> ValidationError | None:
    """Return the first raw validation error for diagnostic tooling."""

    validator = Draft202012Validator(load_schema(name), format_checker=FormatChecker())
    return next(iter(validator.iter_errors(dict(document))), None)
