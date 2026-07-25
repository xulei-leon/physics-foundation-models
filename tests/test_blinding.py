from __future__ import annotations

from pathlib import Path

import pytest

from particleml.blinding import (
    authorize_observed_fit,
    create_freeze_document,
    load_freeze,
    publish_freeze,
    validate_freeze_document,
)
from particleml.contracts import ContractError


def _hashes() -> dict[str, str]:
    return {
        "config_sha256": "1" * 64,
        "catalog_sha256": "2" * 64,
        "dataset_manifest_sha256": "3" * 64,
        "prediction_sha256": "4" * 64,
        "template_sha256": "5" * 64,
    }


def _gates(passed: bool = True) -> dict[str, object]:
    names = (
        "mc_spearman",
        "data_sideband_spearman",
        "sideband_acceptance",
        "spurious_signal",
    )
    return {
        **{name: {"passed": passed} for name in names},
        "all_passed": passed,
    }


def test_freeze_creation_requires_all_gates() -> None:
    with pytest.raises(ContractError, match="FREEZE_GATES"):
        create_freeze_document("freeze", _hashes(), _gates(False))


def test_observed_fit_refuses_without_flag_or_freeze(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="BLINDING_FLAG"):
        authorize_observed_fit(None, False)
    with pytest.raises(ContractError, match="BLINDING_FREEZE"):
        authorize_observed_fit(None, True)

    document = create_freeze_document("freeze", _hashes(), _gates())
    path = publish_freeze(tmp_path / "freeze.json", document)
    with pytest.raises(ContractError, match="BLINDING_FLAG"):
        authorize_observed_fit(path, False)
    assert authorize_observed_fit(path, True)["freeze_sha256"] == document["freeze_sha256"]


def test_freeze_self_hash_and_upstream_hash_are_verified(tmp_path: Path) -> None:
    document = create_freeze_document("freeze", _hashes(), _gates())
    path = publish_freeze(tmp_path / "freeze.json", document)
    assert load_freeze(path, _hashes()) == document
    tampered = dict(document)
    tampered["catalog_sha256"] = "f" * 64
    with pytest.raises(ContractError, match="FREEZE_SELF_HASH"):
        validate_freeze_document(tampered)
    expected = _hashes()
    expected["catalog_sha256"] = "e" * 64
    with pytest.raises(ContractError, match="FREEZE_UPSTREAM_HASH"):
        load_freeze(path, expected)
