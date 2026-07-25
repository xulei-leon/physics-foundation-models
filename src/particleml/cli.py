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
from .blinding import authorize_observed_fit, create_freeze_document, publish_freeze
from .catalog import download_https, validate_catalog
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
from .evaluation import weighted_metrics
from .features import PRIMARY_FEATURES
from .inference import build_templates, build_workspace, fit_workspace, spurious_signal_sigma
from .ingestion import SourceDescriptor, ingest_sources, publish_canonical_dataset
from .models import MODEL_NAMES, train_seeded_predictions
from .physics import PhysicsError, selection_from_config
from .reporting import build_blinded_report


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


def _dataset_build(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    catalog = _json(args.catalog)
    validate_catalog(catalog)
    sources: list[tuple[Path, SourceDescriptor]] = []
    args.cache.mkdir(parents=True, exist_ok=True)
    for item in catalog["files"]:
        checksum = str(item["sha256"])
        cached = args.cache / f"{checksum}.root"
        if not cached.exists():
            download_https(str(item["url"]), cached, checksum)
        source = SourceDescriptor(
            dataset_id=str(item["dataset_id"]),
            file_checksum=checksum,
            is_data=bool(item["is_data"]),
            process_group=str(item["process_group"]),
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
    seeded, ensemble, features = train_seeded_predictions(
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
        run_record = {
            "schema_version": "2.0.0",
            "run_id": f"{model_name}-{features.sha256[:12]}",
            "command": list(parsed_command),
            "started_at": _now(),
            "completed_at": _now(),
            "status": "completed",
            "config_sha256": config_hash,
            "input_artifacts": {"dataset": dataset_artifact.sha256},
            "software": {
                "particleml_version": "0.2.0",
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
            "schema_version": "2.0.0",
            "run_record_sha256": sha256_file(run_path),
            "dataset_manifest_sha256": sha256_file(
                dataset_artifact.path / "dataset-manifest.json"
            ),
            "model_name": model_name,
            "seed_or_ensemble": "ensemble",
            "row_count": len(ensemble),
            "payload_fields": [
                "event_id",
                "target",
                "w_yield",
                "raw_score",
                "ddt_score",
                "channel",
                "m4l",
                "model_name",
                "seed_or_ensemble",
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
        stored = pd.read_parquet(partial / "predictions-ensemble.parquet")
        if stored["event_id"].duplicated().any() or len(stored) != len(frame):
            raise ContractError("PREDICTION_ALIGNMENT", "stored predictions are misaligned")

    return publish_artifact(
        final,
        writer,
        validator,
        {"dataset": dataset_artifact.sha256},
        config_hash,
        "particleml-0.2.0",
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
        "particleml-0.2.0",
    )


def _evaluate(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    prediction_artifact = verify_artifact(args.predictions)
    frame = pd.read_parquet(args.predictions / "predictions-ddt.parquet")
    test = frame[(~frame["is_data"].astype(bool)) & (frame["split"] == "test")]
    metrics = weighted_metrics(
        np.asarray(test["target"], dtype=np.int64),
        np.asarray(test["raw_score"], dtype=np.float64),
        np.asarray(test["w_yield"], dtype=np.float64),
    )
    background = frame[
        (~frame["is_data"].astype(bool))
        & (frame["target"] == 0)
        & (frame["split"] == "test")
    ]
    data = frame[frame["is_data"].astype(bool)]
    sideband = data[
        ((data["m4l"] >= 105.0) & (data["m4l"] < 120.0))
        | ((data["m4l"] >= 130.0) & (data["m4l"] < 160.0))
    ]
    gates = evaluate_decorrelation_gates(background, sideband, args.spurious_signal_sigma)
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
        "particleml-0.2.0",
    )


def _fit_expected(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    prediction_artifact = verify_artifact(args.predictions)
    frame = pd.read_parquet(args.predictions / "predictions-ddt.parquet")
    templates = build_templates(frame)
    fit_config = cast(Mapping[str, Any], config["fit"])
    workspace = build_workspace(
        templates,
        float(fit_config["luminosity_uncertainty"]),
        float(fit_config["signal_theory_uncertainty"]),
        float(fit_config["irreducible_background_uncertainty"]),
        float(fit_config["reducible_background_uncertainty"]),
    )
    result = fit_workspace(workspace, "expected")
    spurious = spurious_signal_sigma(workspace)
    summary = {"spurious_signal_sigma": spurious, "passed": spurious < 0.2}
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
        "particleml-0.2.0",
    )


def _analysis_freeze(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    root = args.inputs
    catalog_path = root / "catalog.json"
    dataset = verify_artifact(root / "dataset")
    predictions = verify_artifact(root / "ddt")
    fit = verify_artifact(root / "expected-fit")
    evaluation = verify_artifact(root / "evaluation")
    gates = _json(evaluation.path / "gates.json")
    fit_summary = _json(fit.path / "fit-summary.json")
    spurious = float(fit_summary["spurious_signal_sigma"])
    gates["spurious_signal"] = {"value_sigma": spurious, "passed": spurious < 0.2}
    gates["all_passed"] = all(
        cast(Mapping[str, Any], gates[name]).get("passed") is True
        for name in (
            "mc_spearman",
            "data_sideband_spearman",
            "sideband_acceptance",
            "spurious_signal",
        )
    )
    hashes = {
        "config_sha256": config_sha256(config),
        "catalog_sha256": sha256_file(catalog_path),
        "dataset_manifest_sha256": dataset.sha256,
        "prediction_sha256": predictions.sha256,
        "template_sha256": fit.sha256,
    }
    document = create_freeze_document(args.freeze_id, hashes, gates)
    publish_freeze(args.output, document)


def _fit_observed(args: argparse.Namespace) -> None:
    config = load_config(args.config, "analysis")
    freeze = authorize_observed_fit(args.freeze, args.unblind)
    if freeze["config_sha256"] != config_sha256(config):
        raise ContractError("FREEZE_UPSTREAM_HASH", "config_sha256 does not match")
    if args.workspace is None or args.output is None:
        raise ContractError(
            "FIT_OBSERVED_INPUT",
            "authorized observed fit additionally requires --workspace and --output",
        )
    template_artifact = verify_artifact(args.workspace.parent)
    if template_artifact.sha256 != freeze["template_sha256"]:
        raise ContractError("FREEZE_UPSTREAM_HASH", "template_sha256 does not match")
    workspace = _json(args.workspace)
    result = fit_workspace(workspace, "observed", str(freeze["freeze_sha256"]))
    _write_json(args.output, result)


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

    dataset = top.add_parser("dataset").add_subparsers(dest="action", required=True)
    dataset_build = dataset.add_parser("build")
    _add_config(dataset_build)
    dataset_build.add_argument("--catalog", type=Path, required=True)
    dataset_build.add_argument("--cache", type=Path, required=True)
    dataset_build.add_argument("--output", type=Path, required=True)
    dataset_build.add_argument("--tree", default="mini")
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
    run_train.add_argument("--model", choices=MODEL_NAMES, default="xgboost")
    run_train.set_defaults(handler=_run_train)

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

    fit = top.add_parser("fit").add_subparsers(dest="action", required=True)
    expected = fit.add_parser("expected")
    _add_config(expected)
    expected.add_argument("--predictions", type=Path, required=True)
    expected.add_argument("--output", type=Path, required=True)
    expected.set_defaults(handler=_fit_expected)
    observed = fit.add_parser("observed")
    _add_config(observed)
    observed.add_argument("--freeze", type=Path)
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
