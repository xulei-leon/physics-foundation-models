from __future__ import annotations

import json
from pathlib import Path

import pytest

from particleml.contracts import (
    SCHEMA_NAMES,
    ContractError,
    model_input_hash,
    sha256_document,
    validate_document,
    validate_model_input_fields,
    validate_schema_suite,
)

ZERO_HASH = "0" * 64


def test_schema_suite_self_validates() -> None:
    assert validate_schema_suite() == SCHEMA_NAMES


def test_canonical_document_hash_is_order_independent() -> None:
    assert sha256_document({"b": 2, "a": 1}) == sha256_document({"a": 1, "b": 2})


@pytest.mark.parametrize(
    "field",
    [
        "m4l",
        "event_id",
        "dataset_id",
        "process_group",
        "truth_higgs",
        "eventWeight",
        "w_yield",
        "dsid",
    ],
)
def test_model_input_contract_rejects_leakage(field: str) -> None:
    with pytest.raises(ContractError, match="FEATURE_FORBIDDEN"):
        validate_model_input_fields(["z1_mass_fraction", field])


def test_model_input_hash_is_stable_and_order_sensitive() -> None:
    fields = ["lep1_pt_fraction", "z1_mass_fraction"]
    assert model_input_hash(fields) == model_input_hash(list(fields))
    assert model_input_hash(fields) != model_input_hash(list(reversed(fields)))


def test_dataset_catalog_rejects_unknown_key() -> None:
    document = {
        "schema_version": "2.1.0",
        "catalog_id": "fixture",
        "created_at": "2026-07-25T00:00:00Z",
        "records": [
            {
                "record_id": "atlas-93924",
                "kind": "data",
                "metadata_url": "https://example.test/data",
            },
            {
                "record_id": "atlas-93928",
                "kind": "mc",
                "metadata_url": "https://example.test/mc",
            },
        ],
        "files": [],
        "unexpected": True,
    }
    with pytest.raises(ContractError, match="CONTRACT_VALIDATION"):
        validate_document(document, "dataset-catalog")


def test_prediction_schema_requires_exact_payload_fields() -> None:
    document = {
        "schema_version": "2.1.0",
        "run_record_sha256": ZERO_HASH,
        "dataset_manifest_sha256": ZERO_HASH,
        "model_name": "xgboost",
        "seed_or_ensemble": "ensemble",
        "row_count": 1,
        "payload_fields": ["event_id"],
        "payload_sha256": ZERO_HASH,
    }
    with pytest.raises(ContractError, match="CONTRACT_VALIDATION"):
        validate_document(document, "prediction-metadata")


def test_all_schema_files_are_json_objects() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in SCHEMA_NAMES:
        value = json.loads((root / "schemas" / f"{name}.schema.json").read_text())
        assert isinstance(value, dict)
