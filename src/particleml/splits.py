"""Canonical event identity and deterministic per-dataset splits."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any, cast

from .contracts import ContractError

SPLITS = ("train", "calibration", "validation", "test")


def event_id(dataset_id: str, file_checksum: str, entry_index: int) -> str:
    """Create the canonical event digest from stable source identity."""

    if not dataset_id or not file_checksum or entry_index < 0:
        raise ContractError("SPLIT_IDENTITY", "invalid source identity")
    payload = f"{dataset_id}\0{file_checksum}\0{entry_index}".encode()
    return hashlib.sha256(payload).hexdigest()


def assign_split(dataset_id: str, file_checksum: str, entry_index: int) -> str:
    """Assign 70/10/10/10 from the first 64 digest bits."""

    digest = event_id(dataset_id, file_checksum, entry_index)
    bucket = int(digest[:16], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 80:
        return "calibration"
    if bucket < 90:
        return "validation"
    return "test"


def split_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Attach event identity and split while rejecting data leakage."""

    output: list[dict[str, object]] = []
    seen: set[str] = set()
    for original in rows:
        row = dict(original)
        entry_index = int(cast(Any, row["entry_index"]))
        identity = event_id(str(row["dataset_id"]), str(row["file_checksum"]), entry_index)
        if identity in seen:
            raise ContractError("SPLIT_DUPLICATE", f"duplicate event identity: {identity}")
        seen.add(identity)
        row["event_id"] = identity
        if bool(row["is_data"]):
            row["split"] = "data"
            if row.get("target") is not None or row.get("w_train") is not None:
                raise ContractError(
                    "SPLIT_DATA_LABEL", "data must not have target or training weight"
                )
        else:
            row["split"] = assign_split(
                str(row["dataset_id"]), str(row["file_checksum"]), entry_index
            )
        output.append(row)
    return output


def counts_by_dataset(rows: Iterable[Mapping[str, object]]) -> dict[str, dict[str, int]]:
    """Summarize simulation split coverage within each dataset."""

    counters: dict[str, Counter[str]] = {}
    for row in rows:
        if bool(row["is_data"]):
            continue
        dataset_id = str(row["dataset_id"])
        counters.setdefault(dataset_id, Counter())[str(row["split"])] += 1
    return {
        dataset_id: {split: counter.get(split, 0) for split in SPLITS}
        for dataset_id, counter in sorted(counters.items())
    }
