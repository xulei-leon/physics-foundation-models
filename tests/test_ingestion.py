from __future__ import annotations

import math
from pathlib import Path

import awkward as ak
import numpy as np
import pandas as pd
import pytest
import uproot

from particleml.artifacts import verify_artifact
from particleml.contracts import ContractError, sha256_file
from particleml.dataset import audit_frame, load_dataset, summarize_simulation_weights
from particleml.ingestion import (
    SourceDescriptor,
    ingest_sources,
    publish_canonical_dataset,
)
from particleml.physics import Selection

from .helpers import synthetic_event_frame


def _write_root(path: Path) -> None:
    with uproot.recreate(path) as root:
        root["analysis"] = {
            "lep_n": np.array([4], dtype=np.int32),
            "lep_pt": ak.Array([[40_000.0, 40_000.0, 22_500.0, 22_500.0]]),
            "lep_eta": ak.Array([[0.0, 0.0, 0.0, 0.0]]),
            "lep_phi": ak.Array([[0.0, math.pi, math.pi / 2, -math.pi / 2]]),
            "lep_e": ak.Array([[40_000.0, 40_000.0, 22_500.0, 22_500.0]]),
            "lep_charge": ak.Array([[1, -1, 1, -1]]),
            "lep_type": ak.Array([[11, 11, 13, 13]]),
            "lep_isTightID": ak.Array([[True, True, True, True]]),
            "lep_isLooseIso": ak.Array([[True, True, True, True]]),
            "lep_isTrigMatched": ak.Array([[True, False, False, False]]),
            "jet_n": np.array([1], dtype=np.int32),
            "jet_pt": ak.Array([[0.0]]),
            "jet_eta": ak.Array([[0.0]]),
            "jet_phi": ak.Array([[0.0]]),
            "jet_e": ak.Array([[0.0]]),
            "met_mpx": np.array([5_000.0]),
            "met_mpy": np.array([0.0]),
            "trigE": np.array([True]),
            "trigM": np.array([False]),
            "trigDE": np.array([False]),
            "trigDM": np.array([False]),
            "trigML": np.array([False]),
            "xsec": np.array([1.0]),
            "kfac": np.array([1.0]),
            "filteff": np.array([1.0]),
            "sum_of_weights": np.array([1.0]),
            "mcWeight": np.array([1.0]),
            "ScaleFactor_PILEUP": np.array([1.0]),
            "ScaleFactor_ELE": np.array([1.0]),
            "ScaleFactor_MUON": np.array([1.0]),
            "ScaleFactor_LepTRIGGER": np.array([1.0]),
        }


def _source(checksum: str, dataset: str, process: str, is_data: bool = False) -> SourceDescriptor:
    return SourceDescriptor(
        dataset_id=dataset,
        file_checksum=checksum,
        is_data=is_data,
        process_group=process,
        xsec_pb=None if is_data else 1.0,
        kfactor=None if is_data else 1.0,
        filter_efficiency=None if is_data else 1.0,
        sum_of_generator_weights=None if is_data else 1.0,
    )


def _simulation_weight_audit_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset_id": "mc-signal",
                "process_group": "signal",
                "sample_role": "nominal",
                "split": "test",
                "is_data": False,
                "w_yield": 2.0,
                "w_train": 0.2,
            },
            {
                "dataset_id": "mc-signal",
                "process_group": "signal",
                "sample_role": "generator_variation",
                "split": "test",
                "is_data": False,
                "w_yield": -0.5,
                "w_train": None,
            },
            {
                "dataset_id": "mc-background",
                "process_group": "irreducible_background",
                "sample_role": "nominal",
                "split": "train",
                "is_data": False,
                "w_yield": -2.0,
                "w_train": 0.1,
            },
            {
                "dataset_id": "mc-background",
                "process_group": "irreducible_background",
                "sample_role": "nominal",
                "split": "train",
                "is_data": False,
                "w_yield": 1.0,
                "w_train": 0.1,
            },
            {
                "dataset_id": "data",
                "process_group": "data",
                "sample_role": "nominal",
                "split": "data",
                "is_data": True,
                "w_yield": 1.0,
                "w_train": None,
            },
        ]
    )


def test_simulation_weight_groups_are_signed_deterministic_and_data_free() -> None:
    frame = _simulation_weight_audit_frame()
    original = frame.copy(deep=True)

    assert summarize_simulation_weights(frame) == [
        {
            "dataset_id": "mc-background",
            "process_group": "irreducible_background",
            "sample_role": "nominal",
            "split": "train",
            "events": 2,
            "negative_events": 1,
            "negative_fraction": 0.5,
            "sum_w_yield": -1.0,
            "sum_abs_w_yield": 3.0,
        },
        {
            "dataset_id": "mc-signal",
            "process_group": "signal",
            "sample_role": "generator_variation",
            "split": "test",
            "events": 1,
            "negative_events": 1,
            "negative_fraction": 1.0,
            "sum_w_yield": -0.5,
            "sum_abs_w_yield": 0.5,
        },
        {
            "dataset_id": "mc-signal",
            "process_group": "signal",
            "sample_role": "nominal",
            "split": "test",
            "events": 1,
            "negative_events": 0,
            "negative_fraction": 0.0,
            "sum_w_yield": 2.0,
            "sum_abs_w_yield": 2.0,
        },
    ]
    pd.testing.assert_frame_equal(frame, original)


def test_simulation_weight_groups_reject_non_finite_weights() -> None:
    frame = _simulation_weight_audit_frame()
    frame.loc[0, "w_yield"] = np.inf

    with pytest.raises(ContractError, match="AUDIT_WEIGHT"):
        summarize_simulation_weights(frame)


def test_audit_frame_retains_weight_and_data_training_failures() -> None:
    frame = synthetic_event_frame(8)
    frame["sample_role"] = "nominal"
    frame["region"] = "signal"

    non_finite = frame.copy(deep=True)
    non_finite.loc[0, "w_yield"] = np.inf
    with pytest.raises(ContractError, match="AUDIT_WEIGHT"):
        audit_frame(non_finite)

    labeled_data = frame.copy(deep=True)
    labeled_data.loc[0, "is_data"] = True
    labeled_data.loc[0, "target"] = None
    labeled_data.loc[0, "split"] = "data"
    labeled_data.loc[0, "region"] = "sideband"
    with pytest.raises(ContractError, match="AUDIT_DATA_LABEL"):
        audit_frame(labeled_data)


def test_root_to_parquet_pipeline_converts_units_and_isolates_data(tmp_path: Path) -> None:
    root_path = tmp_path / "fixture.root"
    _write_root(root_path)
    checksum = sha256_file(root_path)
    sources = [
        (root_path, _source(checksum, "signal", "signal")),
        (root_path, _source(checksum, "background", "irreducible_background")),
        (root_path, _source(checksum, "data", "data", is_data=True)),
    ]
    rows = ingest_sources(
        sources,
        Selection(),
        luminosity_pb=1.0,
        chunk_size=1,
        signal_min_gev=130.0,
        signal_max_gev=140.0,
    )
    assert len(rows) == 3
    assert all(float(row["m4l"]) == pytest.approx(125.0) for row in rows)
    assert all(float(row["met"]) == pytest.approx(5.0) for row in rows)
    data = next(row for row in rows if bool(row["is_data"]))
    assert data["target"] is None
    assert data["w_train"] is None
    assert data["split"] == "data"

    output = tmp_path / "dataset"
    artifact = publish_canonical_dataset(
        rows,
        output,
        "fixture",
        catalog_sha256="1" * 64,
        config_sha256="2" * 64,
    )
    assert verify_artifact(output).sha256 == artifact.sha256
    frame, manifest = load_dataset(output)
    assert manifest["unit_system"] == "GeV"
    assert audit_frame(frame)["rows"] == 3


def test_ingestion_rejects_checksum_mismatch(tmp_path: Path) -> None:
    root_path = tmp_path / "fixture.root"
    _write_root(root_path)
    with pytest.raises(ContractError, match="INGEST_CHECKSUM"):
        ingest_sources(
            [(root_path, _source("0" * 64, "signal", "signal"))],
            Selection(),
            luminosity_pb=1.0,
        )
