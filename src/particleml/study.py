"""Formal blinded four-model study orchestration."""

from __future__ import annotations

import platform
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from .config import config_sha256
from .contracts import (
    ContractError,
    canonical_json_bytes,
    sha256_file,
    validate_document,
)
from .decorrelation import DDTCalibrator, ddt_category, evaluate_decorrelation_gates
from .evaluation import raw_score_shape_diagnostics, weighted_metrics
from .features import PRIMARY_FEATURES
from .inference import (
    build_templates,
    build_workspace,
    fit_workspace,
    spurious_signal_sigma,
)
from .models import (
    BASELINE_MODEL,
    FORMAL_SEEDS,
    MODEL_NAMES,
    PRIMARY_MODEL,
    save_seeded_models,
    train_seeded_models,
)
from .tuning import apply_tuning_decision


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("STUDY_INPUT", f"{label} must be a mapping")
    return cast(Mapping[str, Any], value)


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document))


def _apply_ddt(
    prediction: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, DDTCalibrator]:
    ddt = _mapping(config["ddt"], "ddt")
    nominal = prediction["sample_role"].astype(str) == "nominal"
    calibration = prediction[
        (~prediction["is_data"].astype(bool))
        & nominal
        & (prediction["target"] == 0)
        & (prediction["split"].astype(str) == "calibration")
    ]
    calibrator = DDTCalibrator.fit_from_frame(
        calibration,
        minimum_effective_events=float(ddt["minimum_effective_events"]),
        initial_width=float(ddt["initial_bin_width_gev"]),
    )
    transformed = prediction.copy()
    transformed["ddt_score"] = calibrator.transform(
        np.asarray(transformed["raw_score"], dtype=np.float64),
        np.asarray(transformed["m4l"], dtype=np.float64),
        np.asarray(transformed["channel"].astype(str), dtype=np.str_),
    )
    transformed["ddt_category"] = [
        ddt_category(float(value), float(ddt["threshold"]))
        for value in transformed["ddt_score"]
    ]
    return transformed, calibrator


def _expected_bundle(
    prediction: pd.DataFrame,
    config: Mapping[str, Any],
    generator_replacement: int | None = None,
) -> tuple[dict[str, dict[str, object]], dict[str, object], dict[str, object], float]:
    blinding = _mapping(config["blinding"], "blinding")
    ddt = _mapping(config["ddt"], "ddt")
    fit = _mapping(config["fit"], "fit")
    test_fraction = float(fit["template_test_fraction"])
    weight_scale = float(fit["template_weight_scale"])
    if not np.isclose(test_fraction * weight_scale, 1.0, rtol=0.0, atol=1e-12):
        raise ContractError(
            "TEMPLATE_SCALING",
            "template_weight_scale must be the reciprocal of template_test_fraction",
        )
    templates = build_templates(
        prediction,
        mass_min=float(blinding["analysis_min_gev"]),
        mass_max=float(blinding["analysis_max_gev"]),
        bin_width=float(fit["mass_bin_width_gev"]),
        ddt_threshold=float(ddt["threshold"]),
        simulation_split="test",
        weight_scale=weight_scale,
        generator_replacement=generator_replacement,
    )
    workspace = build_workspace(
        templates,
        float(fit["luminosity_uncertainty"]),
        float(fit["signal_theory_uncertainty"]),
        float(fit["irreducible_background_uncertainty"]),
        float(fit["reducible_background_uncertainty"]),
    )
    result = fit_workspace(workspace, "expected")
    return templates, workspace, result, spurious_signal_sigma(workspace)


def _metrics(prediction: pd.DataFrame) -> dict[str, float]:
    nominal_test = prediction[
        (~prediction["is_data"].astype(bool))
        & (prediction["sample_role"].astype(str) == "nominal")
        & (prediction["split"].astype(str) == "test")
    ]
    return weighted_metrics(
        np.asarray(nominal_test["target"], dtype=np.int64),
        np.asarray(nominal_test["raw_score"], dtype=np.float64),
        np.asarray(nominal_test["w_yield"], dtype=np.float64),
    )


def _gate_set(
    prediction: pd.DataFrame,
    calibrator: DDTCalibrator,
    spurious: float,
    config: Mapping[str, Any],
) -> dict[str, object]:
    blinding = _mapping(config["blinding"], "blinding")
    ddt = _mapping(config["ddt"], "ddt")
    nominal = prediction["sample_role"].astype(str) == "nominal"
    background = prediction[
        (~prediction["is_data"].astype(bool))
        & nominal
        & (prediction["target"] == 0)
        & (prediction["split"].astype(str) == "test")
    ]
    data = prediction[prediction["is_data"].astype(bool)]
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
    document = calibrator.to_document()
    bins = cast(Sequence[Mapping[str, object]], document["bins"])
    return evaluate_decorrelation_gates(
        background,
        sideband,
        spurious,
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


def _diagnostic_fits(
    templates: Mapping[str, Mapping[str, object]],
    config: Mapping[str, Any],
) -> dict[str, object]:
    fit = _mapping(config["fit"], "fit")
    uncertainties = {
        "lumi": float(fit["luminosity_uncertainty"]),
        "signal_theory": float(fit["signal_theory_uncertainty"]),
        "irreducible_norm": float(fit["irreducible_background_uncertainty"]),
        "reducible_norm": float(fit["reducible_background_uncertainty"]),
    }

    def run(disabled: set[str]) -> dict[str, object]:
        workspace = build_workspace(
            templates,
            0.0 if "lumi" in disabled else uncertainties["lumi"],
            0.0 if "signal_theory" in disabled else uncertainties["signal_theory"],
            0.0 if "irreducible_norm" in disabled else uncertainties["irreducible_norm"],
            0.0 if "reducible_norm" in disabled else uncertainties["reducible_norm"],
        )
        return fit_workspace(workspace, "expected")

    names = set(uncertainties)
    return {
        "statistical_only": run(names),
        "leave_one_nuisance_out": {
            name: run({name})
            for name in sorted(names)
        },
    }


def _index_hashes(directory: Path, paths: Mapping[str, Path], name: str) -> str:
    index = {
        label: {
            "path": path.relative_to(directory).as_posix(),
            "sha256": sha256_file(path),
        }
        for label, path in sorted(paths.items())
    }
    target = directory / f"{name}-index.json"
    _write_json(target, index)
    return sha256_file(target)


def run_blinded_study(
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    dataset_sha256: str,
    tuning_document: Mapping[str, Any],
    tuning_sha256: str,
    catalog_sha256: str,
    output: Path,
    git_commit: str = "unavailable",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Execute and materialize the full blinded study inside a partial directory."""

    if tuning_document.get("dataset_sha256") != dataset_sha256:
        raise ContractError("STUDY_TUNING_DATASET", "tuning decision does not match dataset")
    effective = apply_tuning_decision(config, tuning_document)
    model_paths: dict[str, Path] = {}
    prediction_paths: dict[str, Path] = {}
    ddt_paths: dict[str, Path] = {}
    template_paths: dict[str, Path] = {}
    fit_paths: dict[str, Path] = {}
    gate_sets: dict[str, Any] = {}
    study_models: dict[str, Any] = {}
    xgboost_ensemble: pd.DataFrame | None = None
    xgboost_calibrator: DDTCalibrator | None = None

    for model_name in MODEL_NAMES:
        seeded, ensemble, features, fitted = train_seeded_models(
            frame,
            effective,
            model_name,
            fields=PRIMARY_FEATURES,
        )
        model_directory = output / "models" / model_name
        metadata = save_seeded_models(
            fitted,
            model_name,
            features.fields,
            model_directory,
            features.values,
            seeded,
        )
        metadata_path = output / "models" / f"{model_name}-metadata.json"
        _write_json(metadata_path, metadata)
        model_paths[model_name] = metadata_path
        runs: dict[str, Any] = {}
        seed_significance_values: list[float] = []
        predictions: list[tuple[str, pd.DataFrame]] = [
            (f"seed-{seed}", seeded[seed]) for seed in FORMAL_SEEDS
        ]
        predictions.append(("ensemble", ensemble))
        for label, raw_prediction in predictions:
            shape_diagnostics = raw_score_shape_diagnostics(raw_prediction)
            transformed, calibrator = _apply_ddt(raw_prediction, effective)
            run_root = output / "runs" / model_name / label
            prediction_path = run_root / "predictions.parquet"
            prediction_path.parent.mkdir(parents=True, exist_ok=True)
            transformed.to_parquet(prediction_path, index=False)
            calibration_path = run_root / "ddt-calibration.json"
            _write_json(calibration_path, calibrator.to_document())
            metrics = _metrics(transformed)
            run_summary: dict[str, Any] = {
                "status": "completed",
                "metrics": metrics,
                "raw_score_shape_diagnostics": shape_diagnostics,
            }
            try:
                templates, workspace, fit_result, spurious = _expected_bundle(
                    transformed,
                    effective,
                )
                template_path = run_root / "templates.json"
                workspace_path = run_root / "workspace.json"
                fit_path = run_root / "fit-result.json"
                _write_json(template_path, templates)
                _write_json(workspace_path, workspace)
                _write_json(fit_path, fit_result)
                validate_document(fit_result, "fit-result")
                significance = float(str(fit_result["significance"]))
                if label != "ensemble":
                    seed_significance_values.append(significance)
                run_summary.update(
                    {
                        "expected_significance": significance,
                        "spurious_signal_sigma": spurious,
                    }
                )
                if label == "ensemble":
                    try:
                        diagnostic_fits = _diagnostic_fits(
                            cast(Mapping[str, Mapping[str, object]], templates),
                            effective,
                        )
                        run_summary["nuisance_diagnostics"] = {
                            "status": "completed",
                            "fits": diagnostic_fits,
                        }
                    except ContractError as exc:
                        run_summary["nuisance_diagnostics"] = {
                            "status": "blocked",
                            "error": {"code": exc.code, "message": exc.message},
                        }
                template_paths[f"{model_name}-{label}"] = template_path
                fit_paths[f"{model_name}-{label}"] = fit_path
            except ContractError as exc:
                ddt_config = _mapping(effective["ddt"], "ddt")
                spurious = float(ddt_config["max_spurious_signal_sigma"])
                run_summary.update(
                    {
                        "status": "blocked",
                        "expected_significance": None,
                        "spurious_signal_sigma": None,
                        "error": {"code": exc.code, "message": exc.message},
                    }
                )
            gates = _gate_set(transformed, calibrator, spurious, effective)
            gate_path = run_root / "gates.json"
            _write_json(gate_path, gates)
            run_summary["gates_passed"] = gates["all_passed"]
            runs[label] = run_summary
            key = f"{model_name}-{label}"
            prediction_paths[key] = prediction_path
            ddt_paths[key] = calibration_path
            if model_name == PRIMARY_MODEL or (
                model_name == BASELINE_MODEL and label == "ensemble"
            ):
                gate_sets[key] = gates
            if model_name == PRIMARY_MODEL and label == "ensemble":
                xgboost_ensemble = transformed
                xgboost_calibrator = calibrator
        if seed_significance_values:
            stability: dict[str, float | None] = {
                "mean_expected_significance": float(
                    np.mean(seed_significance_values)
                ),
                "standard_deviation": float(np.std(seed_significance_values)),
                "minimum": float(np.min(seed_significance_values)),
                "maximum": float(np.max(seed_significance_values)),
            }
        else:
            stability = {
                "mean_expected_significance": None,
                "standard_deviation": None,
                "minimum": None,
                "maximum": None,
            }
        study_models[model_name] = {
            "runs": runs,
            "stability": stability,
        }

    if xgboost_ensemble is None or xgboost_calibrator is None:
        raise ContractError("STUDY_XGBOOST", "XGBoost ensemble was not produced")
    generator_diagnostics: list[dict[str, object]] = []
    variations = sorted(
        {
            int(value)
            for value in xgboost_ensemble.loc[
                xgboost_ensemble["sample_role"].astype(str) == "generator_variation",
                "variation_of",
            ].dropna()
        }
    )
    nominal_value = study_models[PRIMARY_MODEL]["runs"]["ensemble"][
        "expected_significance"
    ]
    cut_value = study_models[BASELINE_MODEL]["runs"]["ensemble"][
        "expected_significance"
    ]
    nominal_significance = None if nominal_value is None else float(nominal_value)
    cut_significance = None if cut_value is None else float(cut_value)
    if nominal_significance is not None:
        for replaced_dsid in variations:
            try:
                _, _, variation_fit, _ = _expected_bundle(
                    xgboost_ensemble,
                    effective,
                    generator_replacement=replaced_dsid,
                )
                significance = float(str(variation_fit["significance"]))
                generator_diagnostics.append(
                    {
                        "replaced_dsid": replaced_dsid,
                        "status": "completed",
                        "expected_significance": significance,
                        "delta_from_nominal": significance - nominal_significance,
                    }
                )
            except ContractError as exc:
                generator_diagnostics.append(
                    {
                        "replaced_dsid": replaced_dsid,
                        "status": "blocked",
                        "error_code": exc.code,
                        "error_message": exc.message,
                    }
                )
    blocking_reasons = sorted(
        name
        for name, record in gate_sets.items()
        if record.get("all_passed") is not True
    )
    if nominal_significance is None or cut_significance is None:
        blocking_reasons.append("primary_fit_unavailable")
        primary_comparison: dict[str, float] | None = None
    else:
        primary_comparison = {
            "xgboost_expected_significance": nominal_significance,
            "cut_based_expected_significance": cut_significance,
            "delta": nominal_significance - cut_significance,
        }
    study_result: dict[str, Any] = {
        "schema_version": "2.1.0",
        "dataset_sha256": dataset_sha256,
        "tuning_sha256": tuning_sha256,
        "status": "blocked" if blocking_reasons else "completed",
        "blocking_reasons": blocking_reasons,
        "models": study_models,
        "primary_comparison": primary_comparison,
        "generator_diagnostics": generator_diagnostics,
    }
    validate_document(study_result, "study-result")
    study_result_path = output / "study-result.json"
    gate_sets_path = output / "gate-sets.json"
    _write_json(study_result_path, study_result)
    _write_json(gate_sets_path, gate_sets)
    software_path = output / "software.json"
    _write_json(
        software_path,
        {
            "particleml_version": "0.4.0",
            "python_version": platform.python_version(),
            "git_commit": git_commit,
        },
    )
    artifacts = {
        "config": config_sha256(config),
        "catalog": catalog_sha256,
        "dataset": dataset_sha256,
        "tuning": tuning_sha256,
        "models": _index_hashes(output, model_paths, "model"),
        "predictions": _index_hashes(output, prediction_paths, "prediction"),
        "ddt": _index_hashes(output, ddt_paths, "ddt"),
        "templates": _index_hashes(output, template_paths, "template"),
        "fits": _index_hashes(output, fit_paths, "fit"),
        "study_result": sha256_file(study_result_path),
        "software": sha256_file(software_path),
    }
    freeze_inputs = {"schema_version": "2.1.0", "artifacts": artifacts}
    _write_json(output / "freeze-inputs.json", freeze_inputs)
    return study_result, gate_sets, freeze_inputs
