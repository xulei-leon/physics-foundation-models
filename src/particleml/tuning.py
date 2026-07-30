"""One-time validation-only hyperparameter selection."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from copy import deepcopy
from itertools import product
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]

from .config import config_sha256
from .contracts import ContractError
from .evaluation import weighted_metrics
from .features import PRIMARY_FEATURES, build_feature_matrix
from .models import TUNED_MODELS, _fit_with_weights, build_model


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("TUNING_CONFIG", f"{label} must be a mapping")
    return cast(Mapping[str, Any], value)


def _candidates(config: Mapping[str, Any], model_name: str) -> list[dict[str, Any]]:
    models = _mapping(config["models"], "models")
    tuning = _mapping(models["tuning"], "models.tuning")
    if model_name == "logistic":
        return [
            {"C": float(str(value))}
            for value in cast(Sequence[object], tuning["logistic_c"])
        ]
    if model_name == "xgboost":
        return [
            {
                "n_estimators": int(str(n_estimators)),
                "max_depth": int(str(max_depth)),
                "learning_rate": float(str(learning_rate)),
            }
            for n_estimators, max_depth, learning_rate in product(
                cast(Sequence[object], tuning["xgboost_n_estimators"]),
                cast(Sequence[object], tuning["xgboost_max_depth"]),
                cast(Sequence[object], tuning["xgboost_learning_rate"]),
            )
        ]
    if model_name == "mlp":
        return [
            {
                "hidden_layer_sizes": [int(str(item)) for item in hidden],
                "alpha": float(str(alpha)),
            }
            for hidden, alpha in product(
                cast(Sequence[Sequence[object]], tuning["mlp_hidden_layer_sizes"]),
                cast(Sequence[object], tuning["mlp_alpha"]),
            )
        ]
    raise ContractError("TUNING_MODEL", f"model is not tunable: {model_name}")


def _candidate_config(
    config: Mapping[str, Any], model_name: str, parameters: Mapping[str, Any]
) -> dict[str, Any]:
    candidate = deepcopy(dict(config))
    model_config = cast(dict[str, Any], cast(dict[str, Any], candidate["models"])[model_name])
    model_config.update(parameters)
    return candidate


def tune_models(
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    dataset_sha256: str,
) -> dict[str, Any]:
    """Select declared candidates using seed 42 and validation simulation only."""

    features = build_feature_matrix(frame, PRIMARY_FEATURES)
    nominal = (
        frame["sample_role"].astype(str) == "nominal"
        if "sample_role" in frame
        else pd.Series(True, index=frame.index)
    )
    simulation = ~frame["is_data"].astype(bool)
    train_mask = nominal & simulation & (frame["split"] == "train")
    validation_mask = nominal & simulation & (frame["split"] == "validation")
    if not train_mask.any() or not validation_mask.any():
        raise ContractError("TUNING_SPLIT", "training and validation rows are required")
    train_target = np.asarray(frame.loc[train_mask, "target"], dtype=np.int64)
    train_weight = np.asarray(frame.loc[train_mask, "w_train"], dtype=np.float64)
    validation_target = np.asarray(frame.loc[validation_mask, "target"], dtype=np.int64)
    validation_weight = np.asarray(
        frame.loc[validation_mask, "w_yield"], dtype=np.float64
    )
    if set(train_target.tolist()) != {0, 1} or set(validation_target.tolist()) != {0, 1}:
        raise ContractError("TUNING_CLASS", "both classes are required in train and validation")
    tuning_config = _mapping(_mapping(config["models"], "models")["tuning"], "models.tuning")
    seed = int(_mapping(config["models"], "models")["tuning_seed"])
    tolerance = float(tuning_config["tie_tolerance"])
    decisions: dict[str, Any] = {}
    for model_name in TUNED_MODELS:
        evaluations: list[dict[str, Any]] = []
        best_index: int | None = None
        best_roc = -np.inf
        best_pr = -np.inf
        for index, parameters in enumerate(_candidates(config, model_name)):
            candidate_config = _candidate_config(config, model_name, parameters)
            model = build_model(model_name, seed, candidate_config)
            convergence_messages: list[str] = []
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ConvergenceWarning)
                _fit_with_weights(
                    model,
                    features.values[train_mask.to_numpy()],
                    train_target,
                    train_weight,
                )
            convergence_messages = [
                str(item.message)
                for item in caught
                if issubclass(item.category, ConvergenceWarning)
            ]
            if convergence_messages:
                evaluations.append(
                    {
                        "index": index,
                        "parameters": parameters,
                        "status": "invalid_convergence",
                        "warnings": convergence_messages,
                        "metrics": None,
                    }
                )
                continue
            score = np.asarray(
                model.predict_proba(features.values[validation_mask.to_numpy()])[:, 1],
                dtype=np.float64,
            )
            metrics = weighted_metrics(validation_target, score, validation_weight)
            roc = float(metrics["weighted_roc_auc"])
            pr = float(metrics["weighted_pr_auc"])
            evaluations.append(
                {
                    "index": index,
                    "parameters": parameters,
                    "status": "valid",
                    "warnings": [],
                    "metrics": metrics,
                }
            )
            if (
                best_index is None
                or roc > best_roc + tolerance
                or (abs(roc - best_roc) <= tolerance and pr > best_pr + tolerance)
            ):
                best_index = index
                best_roc = roc
                best_pr = pr
        if best_index is None:
            raise ContractError("TUNING_NO_VALID_CANDIDATE", f"{model_name} has no valid candidate")
        selected = next(item for item in evaluations if item["index"] == best_index)
        decisions[model_name] = {
            "selected_index": best_index,
            "selected_parameters": selected["parameters"],
            "selection_metrics": selected["metrics"],
            "candidates": evaluations,
        }
    return {
        "schema_version": "2.1.0",
        "dataset_sha256": dataset_sha256,
        "base_config_sha256": config_sha256(config),
        "seed": seed,
        "selection_metric": str(tuning_config["metric"]),
        "tie_tolerance": tolerance,
        "models": decisions,
    }


def apply_tuning_decision(
    config: Mapping[str, Any], decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Return an effective config after validating and applying a tuning decision."""

    if decision.get("base_config_sha256") != config_sha256(config):
        raise ContractError("TUNING_CONFIG_HASH", "tuning decision does not match base config")
    effective = deepcopy(dict(config))
    models = cast(dict[str, Any], effective["models"])
    decisions = _mapping(decision["models"], "tuning.models")
    for model_name in TUNED_MODELS:
        selected = _mapping(
            _mapping(decisions[model_name], f"tuning.models.{model_name}")[
                "selected_parameters"
            ],
            f"tuning.models.{model_name}.selected_parameters",
        )
        cast(dict[str, Any], models[model_name]).update(dict(selected))
    return effective
