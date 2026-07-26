"""Authorized two-pass observed-data processing with frozen study objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from .artifacts import Artifact, publish_artifact
from .blinding import ALLOWED_WORKSPACES
from .config import config_sha256
from .contracts import (
    ContractError,
    canonical_json_bytes,
    load_json,
    sha256_document,
    sha256_file,
    validate_document,
)
from .decorrelation import DDTCalibrator
from .features import build_feature_matrix
from .inference import fit_workspace
from .ingestion import SourceDescriptor, ingest_sources
from .models import FORMAL_SEEDS, load_model
from .physics import selection_from_config


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("OBSERVED_INPUT", f"{label} must be a mapping")
    return cast(Mapping[str, Any], value)


def _data_sources(
    catalog: Mapping[str, Any],
    cache: Path,
) -> list[tuple[Path, SourceDescriptor]]:
    sources: list[tuple[Path, SourceDescriptor]] = []
    for item in cast(Sequence[Mapping[str, Any]], catalog["files"]):
        if not bool(item["is_data"]):
            continue
        path = cache / str(item["cache_name"])
        if not path.is_file():
            raise ContractError("OBSERVED_CACHE", f"authorized data file is missing: {path}")
        expected = str(item["sha256"])
        if sha256_file(path) != expected:
            raise ContractError(
                "OBSERVED_CHECKSUM",
                f"checksum mismatch before ROOT access: {path}",
            )
        sources.append(
            (
                path,
                SourceDescriptor(
                    dataset_id=str(item["dataset_id"]),
                    file_checksum=expected,
                    is_data=True,
                    process_group="data",
                    sample_role="nominal",
                    production_mode=None,
                    partition=str(item["partition"]),
                    variation_of=None,
                ),
            )
        )
    if not sources:
        raise ContractError("OBSERVED_CATALOG", "catalog has no real-data files")
    return sources


def _ingest_data(
    sources: Sequence[tuple[Path, SourceDescriptor]],
    config: Mapping[str, Any],
    data_mode: str,
    tree_name: str,
    chunk_size: int,
) -> pd.DataFrame:
    blinding = _mapping(config["blinding"], "blinding")
    rows = ingest_sources(
        sources,
        selection_from_config(config),
        float(config["luminosity_pb"]),
        tree_name=tree_name,
        chunk_size=chunk_size,
        data_mode=data_mode,
        signal_min_gev=float(blinding["signal_min_gev"]),
        signal_max_gev=float(blinding["signal_max_gev"]),
    )
    return pd.DataFrame(rows)


def verify_sideband_reproduction(
    frozen_dataset: pd.DataFrame,
    reproduced: pd.DataFrame,
) -> dict[str, object]:
    """Require the first pass to reproduce every frozen sideband data row."""

    expected = frozen_dataset[frozen_dataset["is_data"].astype(bool)].copy()
    if expected.empty or reproduced.empty:
        raise ContractError("OBSERVED_SIDEBAND_EMPTY", "sideband reproduction is empty")
    columns = sorted(set(expected.columns) & set(reproduced.columns))
    left = expected[columns].sort_values("event_id").reset_index(drop=True)
    right = reproduced[columns].sort_values("event_id").reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(
            left,
            right,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError as exc:
        raise ContractError(
            "OBSERVED_SIDEBAND_MISMATCH",
            "authorized first pass does not reproduce the frozen sidebands",
        ) from exc
    return {
        "passed": True,
        "row_count": len(right),
        "event_ids_sha256": sha256_document(right["event_id"].astype(str).tolist()),
    }


def _predict_observed(
    frame: pd.DataFrame,
    study: Path,
    model_name: str,
) -> pd.DataFrame:
    metadata = load_json(study / "models" / f"{model_name}-metadata.json")
    validate_document(metadata, "model-metadata")
    fields = tuple(str(value) for value in cast(Sequence[object], metadata["fields"]))
    features = build_feature_matrix(frame, fields)
    score_columns: list[np.ndarray[Any, np.dtype[np.float64]]] = []
    records = cast(Sequence[Mapping[str, Any]], metadata["files"])
    by_seed = {int(record["seed"]): record for record in records}
    for seed in FORMAL_SEEDS:
        record = by_seed[seed]
        path = study / "models" / model_name / str(record["path"])
        if sha256_file(path) != record["sha256"]:
            raise ContractError("OBSERVED_MODEL_HASH", f"frozen model changed: {path}")
        model = load_model(path, model_name, fields)
        score_columns.append(
            np.asarray(model.predict_proba(features.values)[:, 1], dtype=np.float64)
        )
    prediction = frame.copy()
    prediction["raw_score"] = np.mean(np.vstack(score_columns), axis=0)
    calibration_path = (
        study / "runs" / model_name / "ensemble" / "ddt-calibration.json"
    )
    calibrator = DDTCalibrator.from_document(load_json(calibration_path))
    prediction["ddt_score"] = calibrator.transform(
        np.asarray(prediction["raw_score"], dtype=np.float64),
        np.asarray(prediction["m4l"], dtype=np.float64),
        np.asarray(prediction["channel"].astype(str), dtype=np.str_),
    )
    return prediction


def replace_workspace_observations(
    frozen_workspace: Mapping[str, object],
    frozen_templates: Mapping[str, Mapping[str, object]],
    observed_prediction: pd.DataFrame,
    threshold: float,
) -> dict[str, object]:
    """Copy a frozen expected workspace and replace observations only."""

    workspace = deepcopy(dict(frozen_workspace))
    channels_before = sha256_document(workspace["channels"])
    observations: list[dict[str, object]] = []
    for channel_name, template in sorted(frozen_templates.items()):
        state, category = channel_name.rsplit("_", 1)
        selected = observed_prediction[
            (observed_prediction["channel"].astype(str) == state)
            & (
                np.where(
                    observed_prediction["ddt_score"].astype(float) < threshold,
                    "low",
                    "high",
                )
                == category
            )
        ]
        edges = np.asarray(template["edges"], dtype=np.float64)
        counts = np.histogram(
            np.asarray(selected["m4l"], dtype=np.float64),
            bins=edges,
        )[0].astype(float)
        observations.append({"name": channel_name, "data": counts.tolist()})
    workspace["observations"] = observations
    if sha256_document(workspace["channels"]) != channels_before:
        raise ContractError("OBSERVED_WORKSPACE_MUTATION", "frozen model channels changed")
    return workspace


def run_observed_pipeline(
    *,
    catalog: Mapping[str, Any],
    cache: Path,
    frozen_dataset: pd.DataFrame,
    dataset_artifact: Artifact,
    study_artifact: Artifact,
    config: Mapping[str, Any],
    freeze_sha256: str,
    authorization_sha256: str,
    catalog_sha256: str,
    output: Path,
    tree_name: str = "analysis",
    chunk_size: int = 50_000,
) -> Artifact:
    """Run sideband reproduction, then process full data with frozen objects."""

    sources = _data_sources(catalog, cache)
    sideband = _ingest_data(sources, config, "sideband_only", tree_name, chunk_size)
    sideband_check = verify_sideband_reproduction(frozen_dataset, sideband)
    observed = _ingest_data(sources, config, "observed", tree_name, chunk_size)
    blinding = _mapping(config["blinding"], "blinding")
    ddt = _mapping(config["ddt"], "ddt")
    signal_rows = observed[
        (observed["m4l"].astype(float) >= float(blinding["signal_min_gev"]))
        & (observed["m4l"].astype(float) < float(blinding["signal_max_gev"]))
    ]
    if observed.empty:
        raise ContractError("OBSERVED_DATA_EMPTY", "authorized full-range data are empty")
    results: dict[str, dict[str, object]] = {}
    for workspace_name in ALLOWED_WORKSPACES:
        model_name = workspace_name.removesuffix("-ensemble")
        prediction = _predict_observed(observed, study_artifact.path, model_name)
        run_root = study_artifact.path / "runs" / model_name / "ensemble"
        templates = cast(
            Mapping[str, Mapping[str, object]],
            load_json(run_root / "templates.json"),
        )
        frozen_workspace = load_json(run_root / "workspace.json")
        workspace = replace_workspace_observations(
            frozen_workspace,
            templates,
            prediction,
            float(ddt["threshold"]),
        )
        fit_result = fit_workspace(workspace, "observed", freeze_sha256)
        validate_document(fit_result, "fit-result")
        results[workspace_name] = {
            "workspace": workspace,
            "fit_result": fit_result,
        }
    config_hash = config_sha256(config)

    def writer(partial: Path) -> None:
        (partial / "sideband-reproduction.json").write_bytes(
            canonical_json_bytes(sideband_check)
        )
        (partial / "observed-data-summary.json").write_bytes(
            canonical_json_bytes(
                {
                    "row_count": len(observed),
                    "signal_window_row_count": len(signal_rows),
                    "workspaces": list(ALLOWED_WORKSPACES),
                }
            )
        )
        for name, record in results.items():
            root = partial / name
            root.mkdir()
            (root / "workspace.json").write_bytes(
                canonical_json_bytes(record["workspace"])
            )
            (root / "fit-result.json").write_bytes(
                canonical_json_bytes(record["fit_result"])
            )

    def validator(partial: Path) -> None:
        check = load_json(partial / "sideband-reproduction.json")
        if check.get("passed") is not True:
            raise ContractError("OBSERVED_SIDEBAND_MISMATCH", "sideband check failed")
        for name in ALLOWED_WORKSPACES:
            validate_document(
                load_json(partial / name / "fit-result.json"),
                "fit-result",
            )

    return publish_artifact(
        output,
        writer,
        validator,
        {
            "dataset": dataset_artifact.sha256,
            "study": study_artifact.sha256,
            "catalog": catalog_sha256,
            "freeze": freeze_sha256,
            "authorization": authorization_sha256,
        },
        config_hash,
        "particleml-0.3.0",
    )
