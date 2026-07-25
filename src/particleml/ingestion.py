"""Chunked ROOT ingestion and canonical event-level Parquet publication."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import awkward as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
import uproot  # type: ignore[import-untyped]

from .artifacts import Artifact, publish_artifact
from .contracts import (
    ContractError,
    canonical_json_bytes,
    sha256_document,
    sha256_file,
    validate_document,
)
from .physics import FourVector, Lepton, Selection, select_four_lepton_event
from .splits import counts_by_dataset, split_rows
from .weights import attach_training_weights, yield_weight

MEV_TO_GEV = 0.001

BASE_BRANCHES = (
    "lep_n",
    "lep_pt",
    "lep_eta",
    "lep_phi",
    "lep_E",
    "lep_charge",
    "lep_type",
    "lep_isTightID",
    "lep_isLooseIso",
    "lep_isTrigMatched",
    "jet_n",
    "jet_pt",
    "jet_eta",
    "jet_phi",
    "jet_E",
    "met_mpx",
    "met_mpy",
    "trigE",
    "trigM",
    "trigDE",
    "trigDM",
    "trigML",
)
MC_BRANCHES = (
    "mcWeight",
    "scaleFactor_PILEUP",
    "scaleFactor_ELE",
    "scaleFactor_MUON",
    "scaleFactor_LepTRIGGER",
)


@dataclass(frozen=True)
class SourceDescriptor:
    """Trusted catalog metadata for one ROOT file."""

    dataset_id: str
    file_checksum: str
    is_data: bool
    process_group: str
    xsec_pb: float | None = None
    kfactor: float | None = None
    filter_efficiency: float | None = None
    sum_of_generator_weights: float | None = None


def _as_list(chunk: ak.Array, name: str, row: int) -> list[Any]:
    value = ak.to_list(chunk[name][row])
    if not isinstance(value, list):
        raise ContractError("INGEST_JAGGED", f"{name} must be a per-event list")
    return value


def _leptons(chunk: ak.Array, row: int) -> list[Lepton]:
    values = {
        name: _as_list(chunk, name, row)
        for name in (
            "lep_pt",
            "lep_eta",
            "lep_phi",
            "lep_E",
            "lep_charge",
            "lep_type",
            "lep_isTightID",
            "lep_isLooseIso",
            "lep_isTrigMatched",
        )
    }
    lengths = {len(value) for value in values.values()}
    if len(lengths) != 1:
        raise ContractError("INGEST_LEPTON_LENGTH", "lepton branches have different lengths")
    count = lengths.pop()
    return [
        Lepton(
            index=index,
            pt=float(values["lep_pt"][index]) * MEV_TO_GEV,
            eta=float(values["lep_eta"][index]),
            phi=float(values["lep_phi"][index]),
            energy=float(values["lep_E"][index]) * MEV_TO_GEV,
            charge=int(values["lep_charge"][index]),
            flavor=int(values["lep_type"][index]),
            tight_id=bool(values["lep_isTightID"][index]),
            loose_iso=bool(values["lep_isLooseIso"][index]),
            trigger_matched=bool(values["lep_isTrigMatched"][index]),
        )
        for index in range(count)
    ]


def _jet_summary(chunk: ak.Array, row: int) -> tuple[int, float, float]:
    pts = [float(value) * MEV_TO_GEV for value in _as_list(chunk, "jet_pt", row)]
    etas = [float(value) for value in _as_list(chunk, "jet_eta", row)]
    phis = [float(value) for value in _as_list(chunk, "jet_phi", row)]
    energies = [float(value) * MEV_TO_GEV for value in _as_list(chunk, "jet_E", row)]
    if not (len(pts) == len(etas) == len(phis) == len(energies)):
        raise ContractError("INGEST_JET_LENGTH", "jet branches have different lengths")
    order = sorted(range(len(pts)), key=lambda index: (-pts[index], index))
    leading_pt = pts[order[0]] if order else 0.0
    dijet_mass = 0.0
    if len(order) >= 2:
        vectors = [
            FourVector.from_pt_eta_phi_energy(pts[index], etas[index], phis[index], energies[index])
            for index in order[:2]
        ]
        dijet_mass = (vectors[0] + vectors[1]).mass
    return len(pts), leading_pt, dijet_mass


def _branches(is_data: bool) -> tuple[str, ...]:
    return BASE_BRANCHES if is_data else BASE_BRANCHES + MC_BRANCHES


def iter_root_events(
    path: Path,
    source: SourceDescriptor,
    selection: Selection,
    luminosity_pb: float,
    tree_name: str = "mini",
    chunk_size: int = 50_000,
) -> Iterator[dict[str, object]]:
    """Yield selected canonical rows from one ROOT file."""

    entry_offset = 0
    target = None if source.is_data else int(source.process_group == "signal")
    for chunk in uproot.iterate(
        f"{path}:{tree_name}",
        expressions=list(_branches(source.is_data)),
        step_size=chunk_size,
        library="ak",
    ):
        for local_index in range(len(chunk)):
            entry_index = entry_offset + local_index
            if int(chunk["lep_n"][local_index]) != 4:
                continue
            leptons = _leptons(chunk, local_index)
            triggers = {
                name: bool(chunk[name][local_index])
                for name in ("trigE", "trigM", "trigDE", "trigDM", "trigML")
            }
            selected = select_four_lepton_event(leptons, triggers, selection)
            if selected is None:
                continue
            jet_n, leading_jet_pt, dijet_mass = _jet_summary(chunk, local_index)
            met = math.hypot(
                float(chunk["met_mpx"][local_index]),
                float(chunk["met_mpy"][local_index]),
            ) * MEV_TO_GEV
            row: dict[str, object] = {
                **selected,
                "dataset_id": source.dataset_id,
                "file_checksum": source.file_checksum,
                "entry_index": entry_index,
                "is_data": source.is_data,
                "process_group": source.process_group,
                "target": target,
                "jet_n": jet_n,
                "leading_jet_pt": leading_jet_pt,
                "dijet_mass": dijet_mass,
                "met": met,
            }
            if source.is_data:
                row["w_yield"] = 1.0
                row["w_train"] = None
            else:
                metadata = {
                    "xsec_pb": source.xsec_pb,
                    "kfactor": source.kfactor,
                    "filter_efficiency": source.filter_efficiency,
                    "sum_of_generator_weights": source.sum_of_generator_weights,
                    "mcWeight": float(chunk["mcWeight"][local_index]),
                    "ScaleFactor_PILEUP": float(chunk["scaleFactor_PILEUP"][local_index]),
                    "ScaleFactor_ELE": float(chunk["scaleFactor_ELE"][local_index]),
                    "ScaleFactor_MUON": float(chunk["scaleFactor_MUON"][local_index]),
                    "ScaleFactor_LepTRIGGER": float(
                        chunk["scaleFactor_LepTRIGGER"][local_index]
                    ),
                }
                row["w_yield"] = yield_weight(metadata, luminosity_pb)
            yield row
        entry_offset += len(chunk)


def ingest_sources(
    sources: Sequence[tuple[Path, SourceDescriptor]],
    selection: Selection,
    luminosity_pb: float,
    tree_name: str = "mini",
    chunk_size: int = 50_000,
) -> list[dict[str, object]]:
    """Ingest all files, normalize training weights, and assign splits."""

    rows: list[dict[str, object]] = []
    for path, source in sources:
        actual_checksum = sha256_file(path)
        if actual_checksum != source.file_checksum:
            raise ContractError(
                "INGEST_CHECKSUM",
                f"{path} expected {source.file_checksum}, found {actual_checksum}",
            )
        rows.extend(
            iter_root_events(
                path,
                source,
                selection,
                luminosity_pb,
                tree_name=tree_name,
                chunk_size=chunk_size,
            )
        )
    return split_rows(attach_training_weights(rows))


def publish_canonical_dataset(
    rows: Sequence[Mapping[str, object]],
    final: Path,
    dataset_id: str,
    catalog_sha256: str,
    config_sha256: str,
) -> Artifact:
    """Publish Parquet, dataset manifest, and split manifest atomically."""

    selected_rows = [dict(row) for row in rows]

    def writer(partial: Path) -> None:
        frame = pd.DataFrame(selected_rows)
        parquet = partial / "events.parquet"
        frame.to_parquet(parquet, index=False)
        manifest = {
            "schema_version": "2.0.0",
            "dataset_id": dataset_id,
            "catalog_sha256": catalog_sha256,
            "config_sha256": config_sha256,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "unit_system": "GeV",
            "row_count": len(frame),
            "columns": sorted(frame.columns.tolist()),
            "partitions": [
                {
                    "path": "events.parquet",
                    "sha256": sha256_file(parquet),
                    "rows": len(frame),
                }
            ],
            "cutflow": {"selected": len(frame)},
        }
        (partial / "dataset-manifest.json").write_bytes(canonical_json_bytes(manifest))
        split_manifest = {
            "schema_version": "2.0.0",
            "algorithm": "sha256-bucket-v1",
            "identity_fields": ["dataset_id", "file_checksum", "entry_index"],
            "fractions": {
                "train": 0.7,
                "calibration": 0.1,
                "validation": 0.1,
                "test": 0.1,
            },
            "dataset_manifest_sha256": sha256_document(manifest),
            "counts_by_dataset": counts_by_dataset(selected_rows),
        }
        (partial / "split-manifest.json").write_bytes(canonical_json_bytes(split_manifest))

    def validator(partial: Path) -> None:
        manifest = json.loads(
            (partial / "dataset-manifest.json").read_text(encoding="utf-8")
        )
        split_manifest = json.loads(
            (partial / "split-manifest.json").read_text(encoding="utf-8")
        )
        validate_document(manifest, "dataset-manifest")
        validate_document(split_manifest, "split-manifest")
        frame = pd.read_parquet(partial / "events.parquet")
        required = {
            "dataset_id",
            "file_checksum",
            "entry_index",
            "event_id",
            "is_data",
            "process_group",
            "channel",
            "split",
        }
        if not required.issubset(frame.columns):
            raise ContractError("DATASET_COLUMNS", "canonical identity columns are missing")
        if len(frame) != manifest["row_count"]:
            raise ContractError("DATASET_ROWS", "Parquet row count does not match manifest")

    return publish_artifact(
        final,
        writer,
        validator,
        {"catalog_sha256": catalog_sha256},
        config_sha256,
        "particleml-0.2.0",
    )
