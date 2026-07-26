from __future__ import annotations

from pathlib import Path

import pytest

from particleml.blinding import (
    REQUIRED_GATE_SETS,
    authorize_observed_fit,
    create_freeze_document,
    create_unblinding_authorization,
    load_freeze,
    publish_freeze,
    publish_unblinding_authorization,
    validate_freeze_document,
)
from particleml.contracts import ContractError


def _artifacts() -> dict[str, str]:
    names = (
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
    return {name: f"{index:x}" * 64 for index, name in enumerate(names, start=1)}


def _gate_set(passed: bool = True) -> dict[str, object]:
    return {
        "mc_spearman": {
            "value": 0.01,
            "maximum_absolute": 0.05,
            "passed": passed,
        },
        "data_sideband_spearman": {
            "value": -0.01,
            "maximum_absolute": 0.05,
            "passed": passed,
        },
        "sideband_acceptance": {
            "values": {"mc:4e:105:120": 0.2, "data:4e:105:120": 0.2},
            "minimum": 0.15,
            "maximum": 0.25,
            "passed": passed,
        },
        "spurious_signal": {
            "value_sigma": 0.1,
            "maximum_sigma": 0.2,
            "passed": passed,
        },
        "all_passed": passed,
    }


def _gate_sets(passed: bool = True) -> dict[str, object]:
    return {name: _gate_set(passed) for name in REQUIRED_GATE_SETS}


def test_freeze_creation_requires_all_raw_gate_sets() -> None:
    with pytest.raises(ContractError, match="FREEZE_GATES"):
        create_freeze_document("freeze", _artifacts(), _gate_sets(False))
    missing = _gate_sets()
    del missing["xgboost-seed-17"]
    with pytest.raises(ContractError, match="FREEZE_GATES"):
        create_freeze_document("freeze", _artifacts(), missing)


def test_observed_fit_requires_independent_authorization(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="BLINDING_FLAG"):
        authorize_observed_fit(None, None, False, None)
    with pytest.raises(ContractError, match="BLINDING_FREEZE"):
        authorize_observed_fit(None, None, True, "xgboost-ensemble")

    freeze_document = create_freeze_document("freeze", _artifacts(), _gate_sets())
    freeze_path = publish_freeze(tmp_path / "freeze.json", freeze_document)
    with pytest.raises(ContractError, match="BLINDING_AUTHORIZATION"):
        authorize_observed_fit(
            freeze_path,
            None,
            True,
            "xgboost-ensemble",
        )
    authorization = create_unblinding_authorization(
        "authorization",
        str(freeze_document["freeze_sha256"]),
        "Human Approver",
    )
    authorization_path = publish_unblinding_authorization(
        tmp_path / "authorization.json",
        authorization,
    )
    freeze, loaded_authorization = authorize_observed_fit(
        freeze_path,
        authorization_path,
        True,
        "xgboost-ensemble",
    )
    assert freeze["freeze_sha256"] == freeze_document["freeze_sha256"]
    assert loaded_authorization["approver"] == "Human Approver"
    assert "observed_fit_authorized" not in freeze


def test_freeze_self_hash_and_artifact_hash_are_verified(tmp_path: Path) -> None:
    document = create_freeze_document("freeze", _artifacts(), _gate_sets())
    path = publish_freeze(tmp_path / "freeze.json", document)
    assert load_freeze(path, _artifacts()) == document
    tampered = dict(document)
    tampered["freeze_id"] = "tampered"
    with pytest.raises(ContractError, match="FREEZE_SELF_HASH"):
        validate_freeze_document(tampered)
    expected = _artifacts()
    expected["catalog"] = "e" * 64
    with pytest.raises(ContractError, match="FREEZE_UPSTREAM_HASH"):
        load_freeze(path, expected)
