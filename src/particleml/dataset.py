"""Canonical Parquet loading and data-quality audit."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from .artifacts import verify_artifact
from .contracts import ContractError, validate_document
from .splits import SPLITS


def load_dataset(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Verify and load a published canonical dataset."""

    verify_artifact(path)
    manifest = json.loads((path / "dataset-manifest.json").read_text(encoding="utf-8"))
    validate_document(manifest, "dataset-manifest")
    frame = pd.read_parquet(path / "events.parquet")
    if len(frame) != int(manifest["row_count"]):
        raise ContractError("DATASET_ROWS", "manifest and Parquet row counts differ")
    return frame, manifest


def audit_frame(frame: pd.DataFrame) -> dict[str, object]:
    """Enforce canonical identity, blinding, unit, and split invariants."""

    required = {
        "dataset_id",
        "file_checksum",
        "entry_index",
        "event_id",
        "is_data",
        "process_group",
        "channel",
        "split",
        "target",
        "w_yield",
        "w_train",
        "m4l",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ContractError("AUDIT_COLUMNS", f"missing columns: {', '.join(missing)}")
    if frame["event_id"].duplicated().any():
        raise ContractError("AUDIT_DUPLICATE", "event_id values are not unique")
    data = frame[frame["is_data"].astype(bool)]
    simulation = frame[~frame["is_data"].astype(bool)]
    if data["target"].notna().any() or data["w_train"].notna().any():
        raise ContractError("AUDIT_DATA_LABEL", "data contain target or training weights")
    if set(data["split"].unique()) - {"data"}:
        raise ContractError("AUDIT_DATA_SPLIT", "data entered a simulation split")
    if set(simulation["split"].unique()) - set(SPLITS):
        raise ContractError("AUDIT_MC_SPLIT", "simulation has an invalid split")
    if simulation["target"].isna().any() or simulation["w_train"].isna().any():
        raise ContractError("AUDIT_MC_LABEL", "simulation is missing target or training weight")
    if not frame["m4l"].between(105.0, 160.0, inclusive="left").all():
        raise ContractError("AUDIT_MASS_RANGE", "m4l is outside [105, 160) GeV")
    if not all(math.isfinite(float(value)) for value in frame["w_yield"]):
        raise ContractError("AUDIT_WEIGHT", "w_yield contains a non-finite value")
    return {
        "rows": len(frame),
        "data_rows": len(data),
        "simulation_rows": len(simulation),
        "datasets": int(frame["dataset_id"].nunique()),
        "channels": sorted(str(value) for value in frame["channel"].unique()),
    }
