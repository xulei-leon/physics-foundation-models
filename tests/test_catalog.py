from __future__ import annotations

import pytest

from particleml.catalog import classify_process, make_catalog, require_https, validate_catalog
from particleml.contracts import ContractError

ZERO_HASH = "0" * 64


def _records() -> list[dict[str, object]]:
    return [
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
    ]


def test_process_classification_fails_closed() -> None:
    assert classify_process("ggH125_ZZ4lep", False) == "signal"
    assert classify_process("continuum_ZZ", False) == "irreducible_background"
    assert classify_process("ttbar", False) == "reducible_background"
    assert classify_process("periodD", True) == "data"
    with pytest.raises(ContractError, match="CATALOG_UNKNOWN_PROCESS"):
        classify_process("mystery", False)


@pytest.mark.parametrize("url", ["http://example.test/file.root", "root://host/file.root", "file:///x"])
def test_only_direct_https_is_allowed(url: str) -> None:
    with pytest.raises(ContractError, match="CATALOG_HTTPS"):
        require_https(url)


def test_catalog_validates_explicit_file_identity() -> None:
    catalog = make_catalog(
        "fixture",
        _records(),
        [
            {
                "dataset_id": "data-A",
                "record_id": "atlas-93924",
                "url": "https://example.test/data.root",
                "sha256": ZERO_HASH,
                "size_bytes": 1,
                "is_data": True,
                "process_group": "data",
            },
            {
                "dataset_id": "ggH",
                "record_id": "atlas-93928",
                "url": "https://example.test/signal.root",
                "sha256": "1" * 64,
                "size_bytes": 1,
                "is_data": False,
                "process_group": "signal",
                "generator_group": "ggH",
                "is_nominal": True,
            },
        ],
    )
    validate_catalog(catalog)


def test_duplicate_nominal_signal_generator_is_rejected() -> None:
    files = [
        {
            "dataset_id": f"signal-{index}",
            "record_id": "atlas-93928",
            "url": f"https://example.test/signal-{index}.root",
            "sha256": str(index) * 64,
            "size_bytes": 1,
            "is_data": False,
            "process_group": "signal",
            "generator_group": "ggH",
            "is_nominal": True,
        }
        for index in (1, 2)
    ]
    with pytest.raises(ContractError, match="CATALOG_DUPLICATE_SIGNAL"):
        make_catalog("fixture", _records(), files)
