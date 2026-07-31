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

SIMULATION_WEIGHT_GROUP_KEYS = ("dataset_id", "process_group", "sample_role", "split")


def load_dataset(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Verify and load a published canonical dataset."""

    verify_artifact(path)
    manifest = json.loads((path / "dataset-manifest.json").read_text(encoding="utf-8"))
    validate_document(manifest, "dataset-manifest")
    frame = pd.read_parquet(path / "events.parquet")
    if len(frame) != int(manifest["row_count"]):
        raise ContractError("DATASET_ROWS", "manifest and Parquet row counts differ")
    return frame, manifest


def summarize_simulation_weights(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Summarize signed and absolute simulation weights by canonical group."""

    required = {*SIMULATION_WEIGHT_GROUP_KEYS, "is_data", "w_yield"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ContractError("AUDIT_COLUMNS", f"missing columns: {', '.join(missing)}")

    simulation = frame.loc[
        ~frame["is_data"].astype(bool), [*SIMULATION_WEIGHT_GROUP_KEYS, "w_yield"]
    ].copy()
    if not all(math.isfinite(float(value)) for value in simulation["w_yield"]):
        raise ContractError("AUDIT_WEIGHT", "w_yield contains a non-finite value")

    summaries: list[dict[str, object]] = []
    groups = simulation.groupby(
        list(SIMULATION_WEIGHT_GROUP_KEYS), sort=True, dropna=False, observed=True
    )
    for group_key, group in groups:
        weights = [float(value) for value in group["w_yield"]]
        sum_w_yield = math.fsum(weights)
        sum_abs_w_yield = math.fsum(abs(value) for value in weights)
        if not math.isfinite(sum_w_yield) or not math.isfinite(sum_abs_w_yield):
            raise ContractError("AUDIT_WEIGHT", "grouped w_yield sum is non-finite")
        negative_events = sum(value < 0.0 for value in weights)
        events = len(weights)
        summaries.append(
            {
                **dict(zip(SIMULATION_WEIGHT_GROUP_KEYS, map(str, group_key), strict=True)),
                "events": events,
                "negative_events": negative_events,
                "negative_fraction": negative_events / events,
                "sum_w_yield": sum_w_yield,
                "sum_abs_w_yield": sum_abs_w_yield,
            }
        )
    return summaries


def audit_frame(frame: pd.DataFrame) -> dict[str, object]:
    """Enforce canonical identity, blinding, unit, and split invariants."""

    required = {
        "dataset_id",
        "file_checksum",
        "entry_index",
        "event_id",
        "is_data",
        "process_group",
        "sample_role",
        "region",
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
    nominal_simulation = simulation[simulation["sample_role"].astype(str) == "nominal"]
    variations = simulation[simulation["sample_role"].astype(str) != "nominal"]
    if data["target"].notna().any() or data["w_train"].notna().any():
        raise ContractError("AUDIT_DATA_LABEL", "data contain target or training weights")
    if set(data["split"].unique()) - {"data"}:
        raise ContractError("AUDIT_DATA_SPLIT", "data entered a simulation split")
    if set(data["region"].astype(str).unique()) - {"sideband"}:
        raise ContractError("AUDIT_BLINDING", "pre-freeze data contain signal-window rows")
    if set(simulation["split"].unique()) - set(SPLITS):
        raise ContractError("AUDIT_MC_SPLIT", "simulation has an invalid split")
    if nominal_simulation["target"].isna().any() or nominal_simulation["w_train"].isna().any():
        raise ContractError("AUDIT_MC_LABEL", "nominal simulation is missing target or weight")
    if variations["w_train"].notna().any():
        raise ContractError("AUDIT_VARIATION_WEIGHT", "generator variations have training weight")
    if not frame["m4l"].between(105.0, 160.0, inclusive="left").all():
        raise ContractError("AUDIT_MASS_RANGE", "m4l is outside [105, 160) GeV")
    if not all(math.isfinite(float(value)) for value in frame["w_yield"]):
        raise ContractError("AUDIT_WEIGHT", "w_yield contains a non-finite value")
    return {
        "rows": len(frame),
        "data_rows": len(data),
        "simulation_rows": len(simulation),
        "variation_rows": len(variations),
        "datasets": int(frame["dataset_id"].nunique()),
        "channels": sorted(str(value) for value in frame["channel"].unique()),
    }
