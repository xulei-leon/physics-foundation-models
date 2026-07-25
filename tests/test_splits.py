from __future__ import annotations

from collections import Counter

import pytest

from particleml.contracts import ContractError
from particleml.splits import SPLITS, assign_split, event_id, split_rows


def test_event_identity_and_split_are_deterministic() -> None:
    identity = event_id("410000", "a" * 64, 7)
    assert identity == event_id("410000", "a" * 64, 7)
    assert assign_split("410000", "a" * 64, 7) in SPLITS
    assert identity != event_id("410001", "a" * 64, 7)


def test_each_large_dataset_uses_same_bucket_rule() -> None:
    for dataset in ("signal", "background"):
        counts = Counter(assign_split(dataset, "b" * 64, index) for index in range(10_000))
        assert set(counts) == set(SPLITS)
        assert counts["train"] / 10_000 == pytest.approx(0.7, abs=0.02)
        for split in ("calibration", "validation", "test"):
            assert counts[split] / 10_000 == pytest.approx(0.1, abs=0.02)


def test_data_never_enter_training_and_cannot_have_label() -> None:
    row = {
        "dataset_id": "data",
        "file_checksum": "c" * 64,
        "entry_index": 0,
        "is_data": True,
        "target": None,
        "w_train": None,
    }
    assert split_rows([row])[0]["split"] == "data"
    row["target"] = 1
    with pytest.raises(ContractError, match="SPLIT_DATA_LABEL"):
        split_rows([row])


def test_duplicate_canonical_identity_is_rejected() -> None:
    row = {
        "dataset_id": "mc",
        "file_checksum": "d" * 64,
        "entry_index": 0,
        "is_data": False,
        "target": 0,
        "w_train": 0.5,
    }
    with pytest.raises(ContractError, match="SPLIT_DUPLICATE"):
        split_rows([row, row])
