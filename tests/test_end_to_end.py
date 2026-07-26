from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

import awkward as ak
import numpy as np
import pandas as pd
import uproot

from particleml.config import load_config
from particleml.contracts import sha256_file
from particleml.decorrelation import DDTCalibrator
from particleml.inference import (
    build_templates,
    build_workspace,
    fit_workspace,
    spurious_signal_sigma,
)
from particleml.ingestion import SourceDescriptor, ingest_sources, publish_canonical_dataset
from particleml.models import train_seeded_predictions
from particleml.physics import Selection
from particleml.reporting import build_blinded_report

ROOT = Path(__file__).resolve().parents[1]


def _write_channel_root(path: Path, flavors: list[int], size: int = 120) -> None:
    lepton_pt: list[list[float]] = []
    lepton_phi: list[list[float]] = []
    for index in range(size):
        m4l = 106.0 + index % 53
        first_pt = 35.0
        second_pt = (m4l - 70.0) / 2.0
        lepton_pt.append([first_pt, first_pt, second_pt, second_pt])
        lepton_phi.append([0.0, math.pi, math.pi / 2, -math.pi / 2])
    with uproot.recreate(path) as root:
        root["analysis"] = {
            "lep_n": np.full(size, 4, dtype=np.int32),
            "lep_pt": ak.Array([[value * 1000.0 for value in row] for row in lepton_pt]),
            "lep_eta": ak.Array([[0.0] * 4 for _ in range(size)]),
            "lep_phi": ak.Array(lepton_phi),
            "lep_e": ak.Array([[value * 1000.0 for value in row] for row in lepton_pt]),
            "lep_charge": ak.Array([[1, -1, 1, -1] for _ in range(size)]),
            "lep_type": ak.Array([flavors for _ in range(size)]),
            "lep_isTightID": ak.Array([[True] * 4 for _ in range(size)]),
            "lep_isLooseIso": ak.Array([[True] * 4 for _ in range(size)]),
            "lep_isTrigMatched": ak.Array([[True, False, False, False] for _ in range(size)]),
            "jet_n": np.ones(size, dtype=np.int32),
            "jet_pt": ak.Array([[0.0] for _ in range(size)]),
            "jet_eta": ak.Array([[0.0] for _ in range(size)]),
            "jet_phi": ak.Array([[0.0] for _ in range(size)]),
            "jet_e": ak.Array([[0.0] for _ in range(size)]),
            "met_mpx": np.full(size, 5000.0),
            "met_mpy": np.zeros(size),
            "trigE": np.ones(size, dtype=np.bool_),
            "trigM": np.zeros(size, dtype=np.bool_),
            "trigDE": np.zeros(size, dtype=np.bool_),
            "trigDM": np.zeros(size, dtype=np.bool_),
            "trigML": np.zeros(size, dtype=np.bool_),
            "xsec": np.ones(size),
            "kfac": np.ones(size),
            "filteff": np.ones(size),
            "sum_of_weights": np.full(size, 120.0),
            "mcWeight": np.ones(size),
            "ScaleFactor_PILEUP": np.ones(size),
            "ScaleFactor_ELE": np.ones(size),
            "ScaleFactor_MUON": np.ones(size),
            "ScaleFactor_LepTRIGGER": np.ones(size),
        }


def test_offline_root_to_blinded_report_pipeline(tmp_path: Path) -> None:
    channel_flavors = {
        "4e": [11, 11, 11, 11],
        "4mu": [13, 13, 13, 13],
        "2e2mu": [11, 11, 13, 13],
    }
    sources: list[tuple[Path, SourceDescriptor]] = []
    for channel, flavors in channel_flavors.items():
        path = tmp_path / f"{channel}.root"
        _write_channel_root(path, flavors)
        checksum = sha256_file(path)
        for process in ("signal", "irreducible_background", "reducible_background", "data"):
            is_data = process == "data"
            sources.append(
                (
                    path,
                    SourceDescriptor(
                        dataset_id=f"{channel}-{process}",
                        file_checksum=checksum,
                        is_data=is_data,
                        process_group=process,
                        xsec_pb=None if is_data else 1.0,
                        kfactor=None if is_data else 1.0,
                        filter_efficiency=None if is_data else 1.0,
                        sum_of_generator_weights=None if is_data else 120.0,
                    ),
                )
            )
    rows = ingest_sources(sources, Selection(), luminosity_pb=1.0, chunk_size=37)
    dataset = publish_canonical_dataset(
        rows, tmp_path / "dataset", "fixture", "1" * 64, "2" * 64
    )
    config = deepcopy(load_config(ROOT / "configs" / "analysis-v1.yaml", "analysis"))
    _, ensemble, _ = train_seeded_predictions(pd.DataFrame(rows), config, "cut_based")
    calibration = ensemble[
        (~ensemble["is_data"].astype(bool))
        & (ensemble["target"] == 0)
        & (ensemble["split"] == "calibration")
    ]
    calibrator = DDTCalibrator.fit_from_frame(
        calibration, minimum_effective_events=5.0, initial_width=5.0
    )
    ensemble["ddt_score"] = calibrator.transform(
        np.asarray(ensemble["raw_score"], dtype=np.float64),
        np.asarray(ensemble["m4l"], dtype=np.float64),
        np.asarray(ensemble["channel"].astype(str), dtype=np.str_),
    )
    templates = build_templates(ensemble, bin_width=55.0)
    workspace = build_workspace(templates)
    fit_result = fit_workspace(workspace)
    assert spurious_signal_sigma(workspace) < 0.2
    report = build_blinded_report(
        tmp_path / "report",
        {"weighted_roc_auc": 0.5, "weighted_pr_auc": 0.5},
        fit_result,
        {"all_passed": False},
        {"dataset": dataset.sha256},
        "2" * 64,
    )
    assert (report.path / "report.md").is_file()
    assert "BLINDED" in (report.path / "report.md").read_text(encoding="utf-8")
