"""Breaking particleML v2 command-line interface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from .artifacts import Artifact, IntegrityError, publish_artifact, verify_artifact
from .blinding import (
    ALLOWED_WORKSPACES,
    authorize_observed_fit,
    create_freeze_document,
    create_unblinding_authorization,
    load_freeze,
    publish_freeze,
    publish_unblinding_authorization,
)
from .catalog import (
    download_https,
    freeze_catalog,
    publish_catalog,
    validate_catalog,
)
from .config import config_sha256, load_config
from .contracts import (
    ContractError,
    canonical_json_bytes,
    load_json,
    sha256_file,
    validate_document,
    validate_schema_suite,
)
from .dataset import audit_frame, load_dataset
from .decorrelation import DDTCalibrator, ddt_category, evaluate_decorrelation_gates
from .demo import run_offline_demo
from .evaluation import weighted_metrics
from .features import PRIMARY_FEATURES
from .inference import build_templates, build_workspace, fit_workspace, spurious_signal_sigma
from .ingestion import SourceDescriptor, ingest_sources, publish_canonical_dataset
from .models import MODEL_NAMES, PRIMARY_MODEL, save_seeded_models, train_seeded_models
from .observed import run_observed_pipeline
from .physics import PhysicsError, selection_from_config
from .reporting import build_blinded_report
from .study import run_blinded_study
from .tuning import tune_models


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _json(path: Path) -> dict[str, Any]:
    return load_json(path)


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    if path.exists():
        raise ContractError("OUTPUT_EXISTS", f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.partial")
    try:
        partial.write_bytes(canonical_json_bytes(document))
        partial.rename(path)
    finally:
        if partial.exists():
            partial.unlink()


def _catalog_validate(args: argparse.Namespace) -> None:
    load_config(args.config, "catalog-sources")
    catalog = _json(args.catalog)
    validate_catalog(catalog)
    print(sha256_file(args.catalog))


def _catalog_freeze(args: argparse.Namespace) -> None:
    config = load_config(args.config, "catalog-sources")
    catalog = freeze_catalog(config, args.cache)
    publish_catalog(args.output, catalog)
    print(sha256_file(args.output))


def _dataset_build(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    catalog = _json(args.catalog)
    validate_catalog(catalog)
    sources: list[tuple[Path, SourceDescriptor]] = []
    args.cache.mkdir(parents=True, exist_ok=True)
    for item in catalog["files"]:
        checksum = str(item["sha256"])
        cached = args.cache / str(item["cache_name"])
        if not cached.exists():
            download_https(str(item["url"]), cached, checksum)
        source = SourceDescriptor(
            dataset_id=str(item["dataset_id"]),
            file_checksum=checksum,
            is_data=bool(item["is_data"]),
            process_group=str(item["process_group"]),
            sample_role=str(item["sample_role"]),
            production_mode=(
                None if item["production_mode"] is None else str(item["production_mode"])
            ),
            partition=str(item["partition"]),
            variation_of=(
                None if item["variation_of"] is None else int(item["variation_of"])
            ),
            xsec_pb=None if bool(item["is_data"]) else float(item["xsec_pb"]),
            kfactor=None if bool(item["is_data"]) else float(item["kfactor"]),
            filter_efficiency=(
                None if bool(item["is_data"]) else float(item["filter_efficiency"])
            ),
            sum_of_generator_weights=(
                None
                if bool(item["is_data"])
                else float(item["sum_of_generator_weights"])
            ),
        )
        sources.append((cached, source))
    rows = ingest_sources(
        sources,
        selection_from_config(config),
        float(config["luminosity_pb"]),
        tree_name=args.tree,
        chunk_size=args.chunk_size,
        data_mode="sideband_only",
        signal_min_gev=float(cast(Mapping[str, Any], config["blinding"])["signal_min_gev"]),
        signal_max_gev=float(cast(Mapping[str, Any], config["blinding"])["signal_max_gev"]),
    )
    publish_canonical_dataset(
        rows,
        args.output,
        str(config["analysis_id"]),
        sha256_file(args.catalog),
        config_sha256(config),
    )


def _audit_data(args: argparse.Namespace) -> None:
    load_config(args.config, "analysis")
    frame, _ = load_dataset(args.dataset)
    print(json.dumps(audit_frame(frame), sort_keys=True))


def _training_writer(
    final: Path,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    model_name: str,
    dataset_artifact: Artifact,
    parsed_command: Sequence[str],
) -> Artifact:
    feature_config = cast(Mapping[str, Any], config["features"])
    configured_fields = tuple(str(value) for value in feature_config["primary"])
    if configured_fields != PRIMARY_FEATURES:
        raise ContractError(
            "FEATURE_CONFIG",
            "analysis config primary features do not match the v1 frozen contract",
        )
    seeded, ensemble, features, fitted_models = train_seeded_models(
        frame, config, model_name, fields=configured_fields
    )
    config_hash = config_sha256(config)

    def writer(partial: Path) -> None:
        for seed, prediction in seeded.items():
            prediction.to_parquet(partial / f"predictions-seed-{seed}.parquet", index=False)
        ensemble_path = partial / "predictions-ensemble.parquet"
        ensemble.to_parquet(ensemble_path, index=False)
        (partial / "model-input-fields.json").write_bytes(
            canonical_json_bytes({"fields": list(features.fields), "sha256": features.sha256})
        )
        model_metadata = save_seeded_models(
            fitted_models,
            model_name,
            features.fields,
            partial / "models",
            features.values,
            seeded,
        )
        validate_document(model_metadata, "model-metadata")
        (partial / "model-metadata.json").write_bytes(
            canonical_json_bytes(model_metadata)
        )
        run_record = {
            "schema_version": "2.1.0",
            "run_id": f"{model_name}-{features.sha256[:12]}",
            "command": list(parsed_command),
            "started_at": _now(),
            "completed_at": _now(),
            "status": "completed",
            "config_sha256": config_hash,
            "input_artifacts": {"dataset": dataset_artifact.sha256},
            "software": {
                "particleml_version": "0.4.0",
                "python_version": sys.version.split()[0],
                "git_commit": _git_commit(),
            },
            "model_input_fields": list(features.fields),
            "model_input_sha256": features.sha256,
            "error": None,
        }
        validate_document(run_record, "run-record")
        run_path = partial / "run-record.json"
        run_path.write_bytes(canonical_json_bytes(run_record))
        metadata = {
            "schema_version": "2.1.0",
            "run_record_sha256": sha256_file(run_path),
            "dataset_manifest_sha256": sha256_file(
                dataset_artifact.path / "dataset-manifest.json"
            ),
            "model_name": model_name,
            "seed_or_ensemble": "ensemble",
            "row_count": len(ensemble),
            "payload_fields": [
                "event_id",
                "dataset_id",
                "target",
                "w_yield",
                "raw_score",
                "ddt_score",
                "channel",
                "m4l",
                "model_name",
                "seed_or_ensemble",
                "is_data",
                "process_group",
                "sample_role",
                "production_mode",
                "sample_partition",
                "variation_of",
                "region",
                "split",
                "w_train",
            ],
            "payload_sha256": sha256_file(ensemble_path),
        }
        validate_document(metadata, "prediction-metadata")
        (partial / "prediction-metadata.json").write_bytes(canonical_json_bytes(metadata))

    def validator(partial: Path) -> None:
        validate_document(_json(partial / "run-record.json"), "run-record")
        validate_document(
            _json(partial / "prediction-metadata.json"), "prediction-metadata"
        )
        validate_document(_json(partial / "model-metadata.json"), "model-metadata")
        stored = pd.read_parquet(partial / "predictions-ensemble.parquet")
        if stored["event_id"].duplicated().any() or len(stored) != len(frame):
            raise ContractError("PREDICTION_ALIGNMENT", "stored predictions are misaligned")

    return publish_artifact(
        final,
        writer,
        validator,
        {"dataset": dataset_artifact.sha256},
        config_hash,
        "particleml-0.4.0",
    )


def _run_train(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    dataset_artifact = verify_artifact(args.dataset)
    frame, _ = load_dataset(args.dataset)
    _training_writer(
        args.output,
        frame,
        config,
        args.model,
        dataset_artifact,
        ["particleml", "run", "train", "--model", args.model],
    )


def _study_tune(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    dataset_artifact = verify_artifact(args.dataset)
    frame, _ = load_dataset(args.dataset)
    decision = tune_models(frame, config, dataset_artifact.sha256)
    validate_document(decision, "tuning-decision")
    config_hash = config_sha256(config)

    def writer(partial: Path) -> None:
        (partial / "tuning-decision.json").write_bytes(canonical_json_bytes(decision))

    def validator(partial: Path) -> None:
        validate_document(
            _json(partial / "tuning-decision.json"),
            "tuning-decision",
        )

    publish_artifact(
        args.output,
        writer,
        validator,
        {"dataset": dataset_artifact.sha256},
        config_hash,
        "particleml-0.4.0",
    )


def _study_run(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    dataset_artifact = verify_artifact(args.dataset)
    tuning_artifact = verify_artifact(args.tuning)
    catalog = _json(args.catalog)
    validate_catalog(catalog)
    frame, _ = load_dataset(args.dataset)
    tuning_document = _json(args.tuning / "tuning-decision.json")
    validate_document(tuning_document, "tuning-decision")
    config_hash = config_sha256(config)
    catalog_hash = sha256_file(args.catalog)

    def writer(partial: Path) -> None:
        run_blinded_study(
            frame,
            config,
            dataset_artifact.sha256,
            tuning_document,
            tuning_artifact.sha256,
            catalog_hash,
            partial,
            _git_commit(),
        )

    def validator(partial: Path) -> None:
        validate_document(_json(partial / "study-result.json"), "study-result")
        gates = _json(partial / "gate-sets.json")
        if not gates:
            raise ContractError("STUDY_GATES", "formal gate sets are missing")
        freeze_inputs = _json(partial / "freeze-inputs.json")
        if freeze_inputs["artifacts"]["config"] != config_hash:
            raise ContractError("STUDY_CONFIG_HASH", "freeze inputs have wrong config")

    publish_artifact(
        args.output,
        writer,
        validator,
        {
            "dataset": dataset_artifact.sha256,
            "tuning": tuning_artifact.sha256,
            "catalog": catalog_hash,
        },
        config_hash,
        "particleml-0.4.0",
    )


def _decorrelate(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    prediction_artifact = verify_artifact(args.predictions)
    frame = pd.read_parquet(args.predictions / "predictions-ensemble.parquet")
    calibration = frame[
        (~frame["is_data"].astype(bool))
        & (frame["target"] == 0)
        & (frame["split"] == "calibration")
    ].copy()
    ddt = cast(Mapping[str, Any], config["ddt"])
    calibrator = DDTCalibrator.fit_from_frame(
        calibration,
        minimum_effective_events=float(ddt["minimum_effective_events"]),
        initial_width=float(ddt["initial_bin_width_gev"]),
    )
    transformed = frame.copy()
    transformed["ddt_score"] = calibrator.transform(
        np.asarray(frame["raw_score"], dtype=np.float64),
        np.asarray(frame["m4l"], dtype=np.float64),
        np.asarray(frame["channel"].astype(str), dtype=np.str_),
    )
    transformed["ddt_category"] = [
        ddt_category(float(value), float(ddt["threshold"]))
        for value in transformed["ddt_score"]
    ]
    config_hash = config_sha256(config)

    def writer(partial: Path) -> None:
        transformed.to_parquet(partial / "predictions-ddt.parquet", index=False)
        (partial / "ddt-calibration.json").write_bytes(
            canonical_json_bytes(calibrator.to_document())
        )

    def validator(partial: Path) -> None:
        stored = pd.read_parquet(partial / "predictions-ddt.parquet")
        if not stored["ddt_score"].between(0.0, 1.0).all():
            raise ContractError("DDT_SCORE_RANGE", "stored DDT scores are outside [0, 1]")
        DDTCalibrator.from_document(_json(partial / "ddt-calibration.json"))

    publish_artifact(
        args.output,
        writer,
        validator,
        {"predictions": prediction_artifact.sha256},
        config_hash,
        "particleml-0.4.0",
    )


def _evaluate(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    prediction_artifact = verify_artifact(args.predictions)
    frame = pd.read_parquet(args.predictions / "predictions-ddt.parquet")
    nominal = frame["sample_role"].astype(str) == "nominal"
    test = frame[
        (~frame["is_data"].astype(bool))
        & nominal
        & (frame["split"] == "test")
    ]
    metrics = weighted_metrics(
        np.asarray(test["target"], dtype=np.int64),
        np.asarray(test["raw_score"], dtype=np.float64),
        np.asarray(test["w_yield"], dtype=np.float64),
    )
    background = frame[
        (~frame["is_data"].astype(bool))
        & nominal
        & (frame["target"] == 0)
        & (frame["split"] == "test")
    ]
    data = frame[frame["is_data"].astype(bool)]
    blinding = cast(Mapping[str, Any], config["blinding"])
    sideband = data[
        (
            (data["m4l"] >= float(blinding["analysis_min_gev"]))
            & (data["m4l"] < float(blinding["signal_min_gev"]))
        )
        | (
            (data["m4l"] >= float(blinding["signal_max_gev"]))
            & (data["m4l"] < float(blinding["analysis_max_gev"]))
        )
    ]
    ddt = cast(Mapping[str, Any], config["ddt"])
    calibration = _json(args.predictions / "ddt-calibration.json")
    bins = cast(Sequence[Mapping[str, object]], calibration["bins"])
    gates = evaluate_decorrelation_gates(
        background,
        sideband,
        args.spurious_signal_sigma,
        maximum_absolute_rho=float(ddt["max_abs_spearman"]),
        threshold=float(ddt["threshold"]),
        acceptance_minimum=float(ddt["sideband_acceptance_min"]),
        acceptance_maximum=float(ddt["sideband_acceptance_max"]),
        maximum_spurious_signal_sigma=float(ddt["max_spurious_signal_sigma"]),
        bin_ranges=bins,
        analysis_min=float(blinding["analysis_min_gev"]),
        analysis_max=float(blinding["analysis_max_gev"]),
        signal_min=float(blinding["signal_min_gev"]),
        signal_max=float(blinding["signal_max_gev"]),
    )
    config_hash = config_sha256(config)

    def writer(partial: Path) -> None:
        (partial / "metrics.json").write_bytes(canonical_json_bytes(metrics))
        (partial / "gates.json").write_bytes(canonical_json_bytes(gates))

    def validator(partial: Path) -> None:
        _json(partial / "gates.json")

    publish_artifact(
        args.output,
        writer,
        validator,
        {"predictions": prediction_artifact.sha256},
        config_hash,
        "particleml-0.4.0",
    )


def _fit_expected(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    prediction_artifact = verify_artifact(args.predictions)
    frame = pd.read_parquet(args.predictions / "predictions-ddt.parquet")
    blinding = cast(Mapping[str, Any], config["blinding"])
    ddt = cast(Mapping[str, Any], config["ddt"])
    fit_config = cast(Mapping[str, Any], config["fit"])
    test_fraction = float(fit_config["template_test_fraction"])
    weight_scale = float(fit_config["template_weight_scale"])
    if not np.isclose(test_fraction * weight_scale, 1.0, rtol=0.0, atol=1e-12):
        raise ContractError(
            "TEMPLATE_SCALING",
            "template_weight_scale must be the reciprocal of template_test_fraction",
        )
    templates = build_templates(
        frame,
        mass_min=float(blinding["analysis_min_gev"]),
        mass_max=float(blinding["analysis_max_gev"]),
        bin_width=float(fit_config["mass_bin_width_gev"]),
        ddt_threshold=float(ddt["threshold"]),
        simulation_split="test",
        weight_scale=weight_scale,
    )
    workspace = build_workspace(
        templates,
        float(fit_config["luminosity_uncertainty"]),
        float(fit_config["signal_theory_uncertainty"]),
        float(fit_config["irreducible_background_uncertainty"]),
        float(fit_config["reducible_background_uncertainty"]),
    )
    result = fit_workspace(workspace, "expected")
    spurious = spurious_signal_sigma(workspace)
    summary = {
        "spurious_signal_sigma": spurious,
        "maximum_sigma": float(ddt["max_spurious_signal_sigma"]),
        "passed": spurious < float(ddt["max_spurious_signal_sigma"]),
    }
    config_hash = config_sha256(config)

    def writer(partial: Path) -> None:
        (partial / "templates.json").write_bytes(canonical_json_bytes(templates))
        (partial / "workspace.json").write_bytes(canonical_json_bytes(workspace))
        (partial / "fit-result.json").write_bytes(canonical_json_bytes(result))
        (partial / "fit-summary.json").write_bytes(canonical_json_bytes(summary))

    def validator(partial: Path) -> None:
        validate_document(_json(partial / "fit-result.json"), "fit-result")
        _json(partial / "workspace.json")

    publish_artifact(
        args.output,
        writer,
        validator,
        {"predictions": prediction_artifact.sha256},
        config_hash,
        "particleml-0.4.0",
    )


def _analysis_freeze(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    root = args.inputs
    if (root / "demo-summary.json").is_file():
        raise ContractError("FREEZE_DEMO", "synthetic demo artifacts cannot enter a freeze")
    study = verify_artifact(root / "study")
    freeze_inputs = _json(study.path / "freeze-inputs.json")
    artifacts = cast(Mapping[str, str], freeze_inputs["artifacts"])
    if artifacts["config"] != config_sha256(config):
        raise ContractError("FREEZE_UPSTREAM_HASH", "config does not match study")
    if artifacts["study_result"] != sha256_file(study.path / "study-result.json"):
        raise ContractError("FREEZE_UPSTREAM_HASH", "study result does not match")
    gate_sets = _json(study.path / "gate-sets.json")
    document = create_freeze_document(args.freeze_id, artifacts, gate_sets)
    publish_freeze(args.output, document)


def _analysis_authorize(args: argparse.Namespace) -> None:
    freeze = load_freeze(args.freeze)
    document = create_unblinding_authorization(
        args.authorization_id,
        str(freeze["freeze_sha256"]),
        args.approver,
    )
    publish_unblinding_authorization(args.output, document)


def _analysis_observed(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    freeze, authorization = authorize_observed_fit(
        args.freeze,
        args.authorization,
        args.unblind,
        f"{PRIMARY_MODEL}-ensemble",
    )
    artifacts = cast(Mapping[str, str], freeze["artifacts"])
    if artifacts["config"] != config_sha256(config):
        raise ContractError("FREEZE_UPSTREAM_HASH", "config does not match freeze")
    catalog = _json(args.catalog)
    validate_catalog(catalog)
    catalog_hash = sha256_file(args.catalog)
    if catalog_hash != artifacts["catalog"]:
        raise ContractError("FREEZE_UPSTREAM_HASH", "catalog does not match freeze")
    dataset_artifact = verify_artifact(args.dataset)
    if dataset_artifact.sha256 != artifacts["dataset"]:
        raise ContractError("FREEZE_UPSTREAM_HASH", "dataset does not match freeze")
    study_artifact = verify_artifact(args.study)
    freeze_inputs = _json(study_artifact.path / "freeze-inputs.json")
    if freeze_inputs["artifacts"] != dict(artifacts):
        raise ContractError("FREEZE_UPSTREAM_HASH", "study components do not match freeze")
    frozen_dataset, _ = load_dataset(args.dataset)
    run_observed_pipeline(
        catalog=catalog,
        cache=args.cache,
        frozen_dataset=frozen_dataset,
        dataset_artifact=dataset_artifact,
        study_artifact=study_artifact,
        config=config,
        freeze_sha256=str(freeze["freeze_sha256"]),
        authorization_sha256=str(authorization["authorization_sha256"]),
        catalog_sha256=catalog_hash,
        output=args.output,
        tree_name=args.tree,
        chunk_size=args.chunk_size,
    )


def _fit_observed(args: argparse.Namespace) -> None:
    load_config(args.config, "analysis")
    authorize_observed_fit(
        args.freeze,
        args.authorization,
        args.unblind,
        args.workspace_name,
    )
    raise ContractError(
        "FIT_OBSERVED_FLOW",
        "use 'particleml analysis observed' for the guarded two-pass workflow",
    )


def _report_build(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    evaluation = verify_artifact(args.inputs / "evaluation")
    fit = verify_artifact(args.inputs / "expected-fit")
    metrics = _json(evaluation.path / "metrics.json")
    gates = _json(evaluation.path / "gates.json")
    fit_result = _json(fit.path / "fit-result.json")
    build_blinded_report(
        args.output,
        metrics,
        fit_result,
        gates,
        {"evaluation": evaluation.sha256, "fit": fit.sha256},
        config_sha256(config),
    )


def _contracts_validate(_: argparse.Namespace) -> None:
    validated = validate_schema_suite()
    load_config(Path("configs/analysis-v1.yaml"), "analysis")
    load_config(Path("configs/catalog-sources.yaml"), "catalog-sources")
    print("\n".join(validated))


def _demo_run(args: argparse.Namespace) -> None:
    artifact = run_offline_demo(args.output)
    print(artifact.sha256)


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path("configs/analysis-v1.yaml"))


def build_parser() -> argparse.ArgumentParser:
    """Build the exact nested v2 command surface."""

    parser = argparse.ArgumentParser(prog="particleml")
    top = parser.add_subparsers(dest="group", required=True)

    catalog = top.add_parser("catalog").add_subparsers(dest="action", required=True)
    catalog_validate = catalog.add_parser("validate")
    catalog_validate.add_argument(
        "--config", type=Path, default=Path("configs/catalog-sources.yaml")
    )
    catalog_validate.add_argument("--catalog", type=Path, required=True)
    catalog_validate.set_defaults(handler=_catalog_validate)
    catalog_freeze = catalog.add_parser("freeze")
    catalog_freeze.add_argument(
        "--config", type=Path, default=Path("configs/catalog-sources.yaml")
    )
    catalog_freeze.add_argument("--cache", type=Path, required=True)
    catalog_freeze.add_argument("--output", type=Path, required=True)
    catalog_freeze.set_defaults(handler=_catalog_freeze)

    dataset = top.add_parser("dataset").add_subparsers(dest="action", required=True)
    dataset_build = dataset.add_parser("build")
    _add_config(dataset_build)
    dataset_build.add_argument("--catalog", type=Path, required=True)
    dataset_build.add_argument("--cache", type=Path, required=True)
    dataset_build.add_argument("--output", type=Path, required=True)
    dataset_build.add_argument("--tree", default="analysis")
    dataset_build.add_argument("--mode", choices=("blinded",), default="blinded")
    dataset_build.add_argument("--chunk-size", type=int, default=50_000)
    dataset_build.set_defaults(handler=_dataset_build)

    audit = top.add_parser("audit").add_subparsers(dest="action", required=True)
    audit_data = audit.add_parser("data")
    _add_config(audit_data)
    audit_data.add_argument("--dataset", type=Path, required=True)
    audit_data.set_defaults(handler=_audit_data)

    run = top.add_parser("run").add_subparsers(dest="action", required=True)
    run_train = run.add_parser("train")
    _add_config(run_train)
    run_train.add_argument("--dataset", type=Path, required=True)
    run_train.add_argument("--output", type=Path, required=True)
    run_train.add_argument("--model", choices=MODEL_NAMES, default=PRIMARY_MODEL)
    run_train.set_defaults(handler=_run_train)

    study = top.add_parser("study").add_subparsers(dest="action", required=True)
    study_tune = study.add_parser("tune")
    _add_config(study_tune)
    study_tune.add_argument("--dataset", type=Path, required=True)
    study_tune.add_argument("--output", type=Path, required=True)
    study_tune.set_defaults(handler=_study_tune)
    study_run = study.add_parser("run")
    _add_config(study_run)
    study_run.add_argument("--catalog", type=Path, required=True)
    study_run.add_argument("--dataset", type=Path, required=True)
    study_run.add_argument("--tuning", type=Path, required=True)
    study_run.add_argument("--output", type=Path, required=True)
    study_run.set_defaults(handler=_study_run)

    decorrelate = top.add_parser("decorrelate")
    _add_config(decorrelate)
    decorrelate.add_argument("--predictions", type=Path, required=True)
    decorrelate.add_argument("--output", type=Path, required=True)
    decorrelate.set_defaults(handler=_decorrelate)

    evaluate = top.add_parser("evaluate")
    _add_config(evaluate)
    evaluate.add_argument("--predictions", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--spurious-signal-sigma", type=float, default=0.0)
    evaluate.set_defaults(handler=_evaluate)

    analysis = top.add_parser("analysis").add_subparsers(dest="action", required=True)
    freeze = analysis.add_parser("freeze")
    _add_config(freeze)
    freeze.add_argument("--inputs", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--freeze-id", default="atlas-h4l-v1-freeze")
    freeze.set_defaults(handler=_analysis_freeze)
    authorize = analysis.add_parser("authorize")
    authorize.add_argument("--freeze", type=Path, required=True)
    authorize.add_argument("--approver", required=True)
    authorize.add_argument("--output", type=Path, required=True)
    authorize.add_argument(
        "--authorization-id",
        default="atlas-h4l-v1-unblinding-authorization",
    )
    authorize.set_defaults(handler=_analysis_authorize)
    analysis_observed = analysis.add_parser("observed")
    _add_config(analysis_observed)
    analysis_observed.add_argument("--freeze", type=Path, required=True)
    analysis_observed.add_argument("--authorization", type=Path, required=True)
    analysis_observed.add_argument("--catalog", type=Path, required=True)
    analysis_observed.add_argument("--cache", type=Path, required=True)
    analysis_observed.add_argument("--dataset", type=Path, required=True)
    analysis_observed.add_argument("--study", type=Path, required=True)
    analysis_observed.add_argument("--output", type=Path, required=True)
    analysis_observed.add_argument("--tree", default="analysis")
    analysis_observed.add_argument("--chunk-size", type=int, default=50_000)
    analysis_observed.add_argument("--unblind", action="store_true")
    analysis_observed.set_defaults(handler=_analysis_observed)

    fit = top.add_parser("fit").add_subparsers(dest="action", required=True)
    expected = fit.add_parser("expected")
    _add_config(expected)
    expected.add_argument("--predictions", type=Path, required=True)
    expected.add_argument("--output", type=Path, required=True)
    expected.set_defaults(handler=_fit_expected)
    observed = fit.add_parser("observed")
    _add_config(observed)
    observed.add_argument("--freeze", type=Path)
    observed.add_argument("--authorization", type=Path)
    observed.add_argument("--workspace-name", choices=ALLOWED_WORKSPACES)
    observed.add_argument("--unblind", action="store_true")
    observed.add_argument("--workspace", type=Path)
    observed.add_argument("--output", type=Path)
    observed.set_defaults(handler=_fit_observed)

    report = top.add_parser("report").add_subparsers(dest="action", required=True)
    report_build = report.add_parser("build")
    _add_config(report_build)
    report_build.add_argument("--inputs", type=Path, required=True)
    report_build.add_argument("--output", type=Path, required=True)
    report_build.set_defaults(handler=_report_build)

    demo = top.add_parser("demo").add_subparsers(dest="action", required=True)
    demo_run = demo.add_parser("run")
    demo_run.add_argument("--output", type=Path, required=True)
    demo_run.set_defaults(handler=_demo_run)

    contracts = top.add_parser("contracts").add_subparsers(dest="action", required=True)
    contracts_validate = contracts.add_parser("validate")
    contracts_validate.set_defaults(handler=_contracts_validate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command and map stable contract failures to exit code 2."""

    parser = build_parser()
    args = parser.parse_args(argv)
    handler = cast(Callable[[argparse.Namespace], None], args.handler)
    try:
        handler(args)
    except (ContractError, IntegrityError, PhysicsError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"unexpected failure: {exc}", file=sys.stderr)
        return 1
    return 0


def entrypoint() -> NoReturn:
    """Console-script boundary."""

    raise SystemExit(main())
