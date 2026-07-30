"""Deterministic offline synthetic demonstration of the blinded study pipeline."""

from __future__ import annotations

import json
import math
import platform
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import awkward as ak  # type: ignore[import-untyped]
import matplotlib
import mplhep  # type: ignore[import-untyped]
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import sklearn  # type: ignore[import-untyped]
import uproot  # type: ignore[import-untyped]
import xgboost
from sklearn.metrics import roc_curve  # type: ignore[import-untyped]

from .artifacts import Artifact, publish_artifact
from .config import config_sha256, load_config
from .contracts import (
    ContractError,
    canonical_json_bytes,
    repository_root,
    sha256_document,
    sha256_file,
    validate_document,
)
from .dataset import audit_frame, load_dataset
from .ingestion import SourceDescriptor, ingest_sources, publish_canonical_dataset
from .models import (
    BASELINE_MODEL,
    FORMAL_SEEDS,
    MODEL_NAMES,
    MODEL_ROLES,
    PRIMARY_MODEL,
)
from .physics import selection_from_config
from .study import run_blinded_study
from .tuning import tune_models

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

DEMO_MODE = "synthetic-demo"
DEMO_EVENTS_PER_SOURCE = 360
DEMO_FIGURES = (
    "roc-comparison.png",
    "expected-significance-comparison.png",
    "xgboost-score-distribution.png",
    "xgboost-score-vs-m4l.png",
    "xgboost-m4l-by-ddt-category.png",
)
PROCESS_NAMES = ("signal", "irreducible_background", "reducible_background", "data")
CHANNEL_FLAVORS = {
    "4e": (11, 11, 11, 11),
    "4mu": (13, 13, 13, 13),
    "2e2mu": (11, 11, 13, 13),
}


def _demo_config() -> dict[str, Any]:
    config = deepcopy(
        load_config(repository_root() / "configs" / "analysis-v1.yaml", "analysis")
    )
    config["analysis_id"] = "atlas-h4l-synthetic-demo"
    config["luminosity_pb"] = 1000.0
    models = cast(dict[str, Any], config["models"])
    tuning = cast(dict[str, Any], models["tuning"])
    tuning.update(
        {
            "logistic_c": [1.0],
            "xgboost_n_estimators": [20],
            "xgboost_max_depth": [3],
            "xgboost_learning_rate": [0.05],
            "mlp_hidden_layer_sizes": [[8]],
            "mlp_alpha": [0.0001],
        }
    )
    cast(dict[str, Any], models["logistic"]).update({"C": 1.0, "max_iter": 1000})
    cast(dict[str, Any], models["xgboost"]).update(
        {
            "device": "cpu",
            "tree_method": "hist",
            "n_estimators": 20,
            "max_depth": 3,
            "learning_rate": 0.05,
        }
    )
    cast(dict[str, Any], models["mlp"]).update(
        {
            "hidden_layer_sizes": [8],
            "alpha": 0.0001,
            "max_iter": 300,
            "solver": "lbfgs",
        }
    )
    cast(dict[str, Any], config["ddt"])["minimum_effective_events"] = 5.0
    cast(dict[str, Any], config["fit"])["mass_bin_width_gev"] = 5.0
    return config


def _mass_and_z1(process: str, index: int) -> tuple[float, float]:
    if process == "signal":
        return 121.0 + 0.5 * (index % 17), 88.0 + 0.5 * math.sin(index)
    mass = 106.0 + float((index * (11 if process == "data" else 7)) % 53)
    if process == "irreducible_background":
        return mass, 76.0 + 4.0 * math.sin(index / 9.0)
    if process == "reducible_background":
        return mass, 62.0 + 5.0 * math.cos(index / 7.0)
    z1 = 76.0 if index % 3 else 62.0
    return mass, z1 + 3.0 * math.sin(index / 8.0)


def _write_synthetic_root(
    path: Path,
    channel: str,
    process: str,
    size: int,
) -> float:
    flavors = CHANNEL_FLAVORS[channel]
    lepton_pt: list[list[float]] = []
    lepton_phi: list[list[float]] = []
    jet_pt: list[list[float]] = []
    jet_eta: list[list[float]] = []
    jet_phi: list[list[float]] = []
    jet_energy: list[list[float]] = []
    mc_weights: list[float] = []
    met_x: list[float] = []
    for index in range(size):
        mass, z1_mass = _mass_and_z1(process, index)
        first_pt = z1_mass / 2.0
        second_pt = (mass - z1_mass) / 2.0
        if second_pt < 10.0:
            raise ContractError("DEMO_KINEMATICS", "synthetic lepton pT fell below selection")
        lepton_pt.append([first_pt, first_pt, second_pt, second_pt])
        lepton_phi.append([0.0, math.pi, math.pi / 2.0, -math.pi / 2.0])
        if process == "signal":
            leading_jet = 28.0 + index % 9
        elif process == "irreducible_background":
            leading_jet = 18.0 + index % 11
        elif process == "reducible_background":
            leading_jet = 42.0 + index % 13
        else:
            leading_jet = (18.0 if index % 3 else 42.0) + index % 7
        jet_pt.append([leading_jet * 1000.0])
        jet_eta.append([0.0])
        jet_phi.append([0.0])
        jet_energy.append([leading_jet * 1000.0])
        met_x.append((8.0 + leading_jet / 4.0) * 1000.0)
        mc_weights.append(-0.2 if process != "data" and index % 29 == 0 else 1.0)

    sum_weights = float(sum(mc_weights))
    is_muon = channel == "4mu"
    with uproot.recreate(
        path,
        uuid_function=lambda: uuid.uuid5(uuid.NAMESPACE_URL, f"particleml-demo:{path.name}"),
    ) as root:
        root["analysis"] = {
            "lep_n": np.full(size, 4, dtype=np.int32),
            "lep_pt": ak.Array([[value * 1000.0 for value in row] for row in lepton_pt]),
            "lep_eta": ak.Array([[0.0] * 4 for _ in range(size)]),
            "lep_phi": ak.Array(lepton_phi),
            "lep_e": ak.Array([[value * 1000.0 for value in row] for row in lepton_pt]),
            "lep_charge": ak.Array([[1, -1, 1, -1] for _ in range(size)]),
            "lep_type": ak.Array([list(flavors) for _ in range(size)]),
            "lep_isTightID": ak.Array([[True] * 4 for _ in range(size)]),
            "lep_isLooseIso": ak.Array([[True] * 4 for _ in range(size)]),
            "lep_isTrigMatched": ak.Array([[True, False, False, False] for _ in range(size)]),
            "jet_n": np.ones(size, dtype=np.int32),
            "jet_pt": ak.Array(jet_pt),
            "jet_eta": ak.Array(jet_eta),
            "jet_phi": ak.Array(jet_phi),
            "jet_e": ak.Array(jet_energy),
            "met_mpx": np.asarray(met_x, dtype=np.float64),
            "met_mpy": np.zeros(size, dtype=np.float64),
            "trigE": np.full(size, not is_muon, dtype=np.bool_),
            "trigM": np.full(size, is_muon, dtype=np.bool_),
            "trigDE": np.zeros(size, dtype=np.bool_),
            "trigDM": np.zeros(size, dtype=np.bool_),
            "trigML": np.zeros(size, dtype=np.bool_),
            "xsec": np.full(size, 1.0, dtype=np.float64),
            "kfac": np.ones(size, dtype=np.float64),
            "filteff": np.ones(size, dtype=np.float64),
            "sum_of_weights": np.full(size, sum_weights, dtype=np.float64),
            "mcWeight": np.asarray(mc_weights, dtype=np.float64),
            "ScaleFactor_PILEUP": np.ones(size, dtype=np.float64),
            "ScaleFactor_ELE": np.ones(size, dtype=np.float64),
            "ScaleFactor_MUON": np.ones(size, dtype=np.float64),
            "ScaleFactor_LepTRIGGER": np.ones(size, dtype=np.float64),
        }
    return sum_weights


def _synthetic_sources(
    directory: Path,
    events_per_source: int,
) -> tuple[list[tuple[Path, SourceDescriptor]], str]:
    directory.mkdir(parents=True)
    sources: list[tuple[Path, SourceDescriptor]] = []
    catalog_records: list[dict[str, object]] = []
    for channel in CHANNEL_FLAVORS:
        for process in PROCESS_NAMES:
            path = directory / f"{channel}-{process}.root"
            sum_weights = _write_synthetic_root(path, channel, process, events_per_source)
            checksum = sha256_file(path)
            is_data = process == "data"
            source = SourceDescriptor(
                dataset_id=f"demo-{channel}-{process}",
                file_checksum=checksum,
                is_data=is_data,
                process_group=process,
                sample_role="nominal",
                production_mode="synthetic" if process == "signal" else None,
                xsec_pb=None if is_data else 1.0,
                kfactor=None if is_data else 1.0,
                filter_efficiency=None if is_data else 1.0,
                sum_of_generator_weights=None if is_data else sum_weights,
            )
            sources.append((path, source))
            catalog_records.append(
                {
                    "dataset_id": source.dataset_id,
                    "sha256": checksum,
                    "is_data": is_data,
                    "process_group": process,
                }
            )
    return sources, sha256_document({"mode": DEMO_MODE, "files": catalog_records})


def _ensemble_frames(study: Path) -> dict[str, pd.DataFrame]:
    return {
        model_name: pd.read_parquet(
            study / "runs" / model_name / "ensemble" / "predictions.parquet"
        )
        for model_name in MODEL_NAMES
    }


def _watermark(axis: Any) -> None:
    axis.text(
        0.5,
        0.5,
        "SYNTHETIC DEMO — NON-FORMAL",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=14,
        color="0.5",
        alpha=0.18,
        rotation=24,
    )


def _save_figure(figure: Any, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=140, metadata={"Software": "particleML synthetic demo"})
    plt.close(figure)


def _nominal_test(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        (~frame["is_data"].astype(bool))
        & (frame["sample_role"].astype(str) == "nominal")
        & (frame["split"].astype(str) == "test")
    ]


def _plot_roc(frames: Mapping[str, pd.DataFrame], path: Path) -> None:
    figure, axis = plt.subplots(figsize=(7.0, 5.5))
    for model_name in MODEL_NAMES:
        selected = _nominal_test(frames[model_name])
        false_positive, true_positive, _ = roc_curve(
            np.asarray(selected["target"], dtype=np.int64),
            np.asarray(selected["raw_score"], dtype=np.float64),
            sample_weight=np.abs(np.asarray(selected["w_yield"], dtype=np.float64)),
        )
        axis.plot(false_positive, true_positive, label=model_name)
    axis.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", color="0.5")
    axis.set(xlabel="Background efficiency", ylabel="Signal efficiency", title="ROC comparison")
    axis.legend()
    _watermark(axis)
    _save_figure(figure, path)


def _plot_significance(study_result: Mapping[str, Any], path: Path) -> None:
    models = cast(Mapping[str, Any], study_result["models"])
    values: list[float] = []
    for model_name in MODEL_NAMES:
        run = cast(Mapping[str, Any], models[model_name])["runs"]["ensemble"]
        value = cast(Mapping[str, Any], run).get("expected_significance")
        values.append(float("nan") if value is None else float(value))
    figure, axis = plt.subplots(figsize=(7.0, 5.5))
    axis.bar(MODEL_NAMES, values)
    for index, value in enumerate(values):
        if not math.isfinite(value):
            axis.text(index, 0.0, "unavailable", rotation=90, ha="center", va="bottom")
    axis.set(ylabel="Expected significance", title="Synthetic expected-fit comparison")
    axis.tick_params(axis="x", rotation=20)
    _watermark(axis)
    _save_figure(figure, path)


def _plot_xgboost_scores(frame: pd.DataFrame, path: Path) -> None:
    selected = _nominal_test(frame)
    figure, axis = plt.subplots(figsize=(7.0, 5.5))
    for target, label in ((0, "background"), (1, "signal")):
        rows = selected[selected["target"] == target]
        axis.hist(
            rows["raw_score"],
            bins=20,
            range=(0.0, 1.0),
            weights=np.abs(np.asarray(rows["w_yield"], dtype=np.float64)),
            histtype="step",
            density=True,
            label=label,
        )
    axis.set(xlabel="Raw XGBoost score", ylabel="Normalized density", title="XGBoost score")
    axis.legend()
    _watermark(axis)
    _save_figure(figure, path)


def _plot_score_vs_mass(frame: pd.DataFrame, path: Path) -> None:
    selected = _nominal_test(frame)
    selected = selected[selected["target"] == 0]
    figure, axis = plt.subplots(figsize=(7.0, 5.5))
    axis.scatter(selected["m4l"], selected["ddt_score"], s=10, alpha=0.5)
    axis.set(
        xlabel=r"$m_{4\ell}$ [GeV]",
        ylabel="DDT score",
        title="Background DDT score versus mass",
    )
    _watermark(axis)
    _save_figure(figure, path)


def _plot_mass_categories(frame: pd.DataFrame, path: Path) -> None:
    selected = _nominal_test(frame)
    edges = np.arange(105.0, 165.0, 5.0)
    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.5), sharey=True)
    for axis, category in zip(axes, ("low", "high"), strict=True):
        rows = selected[selected["ddt_category"] == category]
        for process in ("signal", "irreducible_background", "reducible_background"):
            process_rows = rows[rows["process_group"] == process]
            axis.hist(
                process_rows["m4l"],
                bins=edges,
                weights=np.asarray(process_rows["w_yield"], dtype=np.float64),
                histtype="step",
                label=process,
            )
        axis.set(xlabel=r"$m_{4\ell}$ [GeV]", title=f"XGBoost DDT {category}")
        _watermark(axis)
    axes[0].set_ylabel("Signed expected yield")
    axes[1].legend(fontsize="small")
    _save_figure(figure, path)


def _model_summary(
    study_result: Mapping[str, Any],
    study_path: Path,
) -> dict[str, object]:
    models = cast(Mapping[str, Any], study_result["models"])
    summary: dict[str, object] = {}
    for model_name in MODEL_NAMES:
        runs = cast(Mapping[str, Any], models[model_name])["runs"]
        expected_runs = {*(f"seed-{seed}" for seed in FORMAL_SEEDS), "ensemble"}
        if set(runs) != expected_runs:
            raise ContractError("DEMO_SEEDS", f"{model_name} does not contain five seeded runs")
        ensemble = cast(Mapping[str, Any], runs)["ensemble"]
        run = cast(Mapping[str, Any], ensemble)
        gates_path = study_path / "runs" / model_name / "ensemble" / "gates.json"
        gates = cast(dict[str, object], _read_json(gates_path))
        summary[model_name] = {
            "role": MODEL_ROLES[model_name],
            "seeds": list(FORMAL_SEEDS),
            "metrics": dict(cast(Mapping[str, Any], run["metrics"])),
            "expected_significance": run.get("expected_significance"),
            "gates": gates,
        }
    return summary


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("DEMO_JSON", f"{path} does not contain an object")
    return value


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    model_records = cast(Mapping[str, Mapping[str, Any]], summary["models"])
    lines = [
        "# particleML Synthetic Offline Demo",
        "",
        "**SYNTHETIC DEMO — NON-FORMAL**",
        "",
        "**Observed signal window:** BLINDED; no real collision data were read.",
        "",
        "This artifact verifies the shared engineering path. It is not eligible for an "
        "analysis freeze and carries no physics claim.",
        "",
        "## Model roles and expected results",
        "",
        "| Model | Role | Weighted ROC-AUC | Expected significance | DDT gates passed |",
        "|---|---|---:|---:|---|",
    ]
    for model_name in MODEL_NAMES:
        record = model_records[model_name]
        metrics = cast(Mapping[str, Any], record["metrics"])
        significance = record["expected_significance"]
        significance_text = "unavailable" if significance is None else f"{float(significance):.6g}"
        gates = cast(Mapping[str, Any], record["gates"])
        lines.append(
            f"| `{model_name}` | {record['role']} | "
            f"{float(metrics['weighted_roc_auc']):.6g} | {significance_text} | "
            f"{'yes' if gates.get('all_passed') is True else 'no'} |"
        )
    comparison = cast(Mapping[str, Any] | None, summary["primary_comparison"])
    lines.extend(["", "## Primary comparison", ""])
    if comparison is None:
        lines.append("- XGBoost versus cut-based expected comparison: unavailable.")
    else:
        lines.append(
            "- Expected significance delta "
            f"`{PRIMARY_MODEL} - {BASELINE_MODEL}`: `{float(comparison['delta']):.6g}`."
        )
    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "- Input ROOT files were generated locally and deterministically.",
            "- Pseudo-data contain no target, no training weight, and no 120--130 GeV rows.",
            "- Figures use simulation test rows and pseudo-data sidebands only.",
            "- No freeze input, authorization, or observed workspace was published.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_offline_demo(
    output: Path,
    events_per_source: int = DEMO_EVENTS_PER_SOURCE,
) -> Artifact:
    """Run and atomically publish the fixed synthetic, non-formal demonstration."""

    if events_per_source < 120:
        raise ContractError("DEMO_SIZE", "events_per_source must be at least 120")
    config = _demo_config()
    config_hash = config_sha256(config)
    with tempfile.TemporaryDirectory(prefix="particleml-demo-") as temporary:
        temporary_path = Path(temporary)
        sources, catalog_hash = _synthetic_sources(temporary_path / "root", events_per_source)
        rows = ingest_sources(
            sources,
            selection_from_config(config),
            float(config["luminosity_pb"]),
            chunk_size=113,
            data_mode="sideband_only",
            signal_min_gev=120.0,
            signal_max_gev=130.0,
        )
        dataset = publish_canonical_dataset(
            rows,
            temporary_path / "dataset",
            str(config["analysis_id"]),
            catalog_hash,
            config_hash,
        )
        frame, _ = load_dataset(dataset.path)
        data_summary = audit_frame(frame)
        data_rows = frame[frame["is_data"].astype(bool)]
        data_summary.update(
            {
                "data_target_rows": int(data_rows["target"].notna().sum()),
                "data_training_weight_rows": int(data_rows["w_train"].notna().sum()),
                "data_signal_window_rows": int(
                    data_rows["m4l"].between(120.0, 130.0, inclusive="left").sum()
                ),
            }
        )
        split_counts = {
            str(name): int(count)
            for name, count in frame["split"].astype(str).value_counts().sort_index().items()
        }
        tuning = tune_models(frame, config, dataset.sha256)
        validate_document(tuning, "tuning-decision")
        tuning_hash = sha256_document(tuning)
        study_path = temporary_path / "study"
        study_result, _, _ = run_blinded_study(
            frame,
            config,
            dataset.sha256,
            tuning,
            tuning_hash,
            catalog_hash,
            study_path,
            git_commit="synthetic-demo",
        )
        frames = _ensemble_frames(study_path)
        models = _model_summary(study_result, study_path)
        base_summary: dict[str, Any] = {
            "schema_version": "2.1.0",
            "mode": DEMO_MODE,
            "formal_eligible": False,
            "blinded": True,
            "status": "completed",
            "study_status": study_result["status"],
            "blocking_reasons": list(cast(Sequence[str], study_result["blocking_reasons"])),
            "config_sha256": config_hash,
            "catalog_sha256": catalog_hash,
            "dataset_sha256": dataset.sha256,
            "tuning_sha256": tuning_hash,
            "data_summary": {**data_summary, "splits": split_counts},
            "runtime": {
                "particleml_version": "0.4.0",
                "python_version": platform.python_version(),
                "scikit_learn_version": sklearn.__version__,
                "xgboost_version": xgboost.__version__,
                "xgboost_device": "cpu",
                "tree_method": "hist",
            },
            "models": models,
            "primary_comparison": study_result["primary_comparison"],
        }

        def writer(partial: Path) -> None:
            plt.style.use(mplhep.style.ATLAS)
            _plot_roc(frames, partial / "roc-comparison.png")
            _plot_significance(study_result, partial / "expected-significance-comparison.png")
            xgboost_frame = frames[PRIMARY_MODEL]
            _plot_xgboost_scores(xgboost_frame, partial / "xgboost-score-distribution.png")
            _plot_score_vs_mass(xgboost_frame, partial / "xgboost-score-vs-m4l.png")
            _plot_mass_categories(xgboost_frame, partial / "xgboost-m4l-by-ddt-category.png")
            _write_report(partial / "report.md", base_summary)
            output_hashes = {
                name: sha256_file(partial / name)
                for name in ("report.md", *DEMO_FIGURES)
            }
            summary = {**base_summary, "outputs": output_hashes}
            validate_document(summary, "demo-summary")
            (partial / "demo-summary.json").write_bytes(canonical_json_bytes(summary))

        def validator(partial: Path) -> None:
            summary = _read_json(partial / "demo-summary.json")
            validate_document(summary, "demo-summary")
            if summary.get("formal_eligible") is not False:
                raise ContractError("DEMO_FORMAL", "demo output must not be formal-eligible")
            forbidden = ("freeze-inputs.json", "unblinding-authorization.json", "workspace.json")
            if any((partial / name).exists() for name in forbidden):
                raise ContractError("DEMO_FORMAL", "demo output contains a formal-only artifact")
            for name in ("report.md", *DEMO_FIGURES):
                if not (partial / name).is_file() or (partial / name).stat().st_size == 0:
                    raise ContractError("DEMO_OUTPUT", f"missing or empty demo output: {name}")

        return publish_artifact(
            output,
            writer,
            validator,
            {"dataset": dataset.sha256, "tuning": tuning_hash, "catalog": catalog_hash},
            config_hash,
            "particleml-0.4.0",
        )
