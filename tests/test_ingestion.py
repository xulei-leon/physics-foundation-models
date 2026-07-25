from __future__ import annotations

import math
from pathlib import Path

import awkward as ak
import numpy as np
import pytest
import uproot

from particleml.artifacts import verify_artifact
from particleml.contracts import ContractError, sha256_file
from particleml.dataset import audit_frame, load_dataset
from particleml.ingestion import (
    SourceDescriptor,
    ingest_sources,
    publish_canonical_dataset,
)
from particleml.physics import Selection


def _write_root(path: Path) -> None:
    with uproot.recreate(path) as root:
        root["mini"] = {
            "lep_n": np.array([4], dtype=np.int32),
            "lep_pt": ak.Array([[40_000.0, 40_000.0, 22_500.0, 22_500.0]]),
            "lep_eta": ak.Array([[0.0, 0.0, 0.0, 0.0]]),
            "lep_phi": ak.Array([[0.0, math.pi, math.pi / 2, -math.pi / 2]]),
            "lep_E": ak.Array([[40_000.0, 40_000.0, 22_500.0, 22_500.0]]),
            "lep_charge": ak.Array([[1, -1, 1, -1]]),
            "lep_type": ak.Array([[11, 11, 13, 13]]),
            "lep_isTightID": ak.Array([[True, True, True, True]]),
            "lep_isLooseIso": ak.Array([[True, True, True, True]]),
            "lep_isTrigMatched": ak.Array([[True, False, False, False]]),
            "jet_n": np.array([1], dtype=np.int32),
            "jet_pt": ak.Array([[0.0]]),
            "jet_eta": ak.Array([[0.0]]),
            "jet_phi": ak.Array([[0.0]]),
            "jet_E": ak.Array([[0.0]]),
            "met_mpx": np.array([5_000.0]),
            "met_mpy": np.array([0.0]),
            "trigE": np.array([True]),
            "trigM": np.array([False]),
            "trigDE": np.array([False]),
            "trigDM": np.array([False]),
            "trigML": np.array([False]),
            "mcWeight": np.array([1.0]),
            "scaleFactor_PILEUP": np.array([1.0]),
            "scaleFactor_ELE": np.array([1.0]),
            "scaleFactor_MUON": np.array([1.0]),
            "scaleFactor_LepTRIGGER": np.array([1.0]),
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


def test_root_to_parquet_pipeline_converts_units_and_isolates_data(tmp_path: Path) -> None:
    root_path = tmp_path / "fixture.root"
    _write_root(root_path)
    checksum = sha256_file(root_path)
    sources = [
        (root_path, _source(checksum, "signal", "signal")),
        (root_path, _source(checksum, "background", "irreducible_background")),
        (root_path, _source(checksum, "data", "data", is_data=True)),
    ]
    rows = ingest_sources(sources, Selection(), luminosity_pb=1.0, chunk_size=1)
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
