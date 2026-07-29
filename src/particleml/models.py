"""Frozen model families, five-seed training, and aligned ensembling."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import joblib  # type: ignore[import-untyped]
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import sklearn  # type: ignore[import-untyped]
import xgboost
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.neural_network import MLPClassifier  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
from xgboost import XGBClassifier

from .contracts import ContractError, canonical_json_bytes, sha256_file
from .features import PRIMARY_FEATURES, FeatureMatrix, build_feature_matrix

FORMAL_SEEDS = (17, 42, 314, 2026, 2718)
MODEL_NAMES = ("cut_based", "logistic", "xgboost", "mlp")


class Classifier(Protocol):
    def fit(
        self,
        values: np.ndarray[Any, np.dtype[np.float64]],
        target: np.ndarray[Any, np.dtype[np.int64]],
        sample_weight: np.ndarray[Any, np.dtype[np.float64]] | None = None,
    ) -> Any: ...

    def predict_proba(
        self, values: np.ndarray[Any, np.dtype[np.float64]]
    ) -> np.ndarray[Any, np.dtype[np.float64]]: ...


class CutBasedClassifier:
    """Fixed transparent score using the two dilepton mass fractions."""

    def __init__(self, fields: Sequence[str]) -> None:
        self.z1_index = fields.index("z1_mass_fraction")
        self.z2_index = fields.index("z2_mass_fraction")

    def fit(
        self,
        values: np.ndarray[Any, np.dtype[np.float64]],
        target: np.ndarray[Any, np.dtype[np.int64]],
        sample_weight: np.ndarray[Any, np.dtype[np.float64]] | None = None,
    ) -> CutBasedClassifier:
        del values, target, sample_weight
        return self

    def predict_proba(
        self, values: np.ndarray[Any, np.dtype[np.float64]]
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        z1 = values[:, self.z1_index]
        z2 = values[:, self.z2_index]
        score = np.exp(-0.5 * (((z1 - 0.73) / 0.16) ** 2 + ((z2 - 0.25) / 0.15) ** 2))
        return np.column_stack((1.0 - score, score))


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("MODEL_CONFIG", f"{label} must be a mapping")
    return cast(Mapping[str, Any], value)


def build_model(
    name: str,
    seed: int,
    config: Mapping[str, Any],
    fields: Sequence[str] = PRIMARY_FEATURES,
) -> Classifier:
    """Construct one model from frozen configuration."""

    if name not in MODEL_NAMES:
        raise ContractError("MODEL_NAME", f"unknown model: {name}")
    if name == "cut_based":
        return CutBasedClassifier(fields)
    models = _mapping(config["models"], "models")
    if name == "logistic":
        params = _mapping(models["logistic"], "models.logistic")
        return cast(
            Classifier,
            Pipeline(
                [
                    ("scale", StandardScaler()),
                    (
                        "model",
                        LogisticRegression(
                            C=float(params["C"]),
                            max_iter=int(params["max_iter"]),
                            random_state=seed,
                        ),
                    ),
                ]
            ),
        )
    if name == "mlp":
        params = _mapping(models["mlp"], "models.mlp")
        solver = str(params["solver"])
        if solver not in {"lbfgs", "adam"}:
            raise ContractError("MODEL_CONFIG", f"unsupported MLP solver: {solver}")
        hidden = tuple(
            int(cast(Any, value))
            for value in cast(Sequence[object], params["hidden_layer_sizes"])
        )
        return cast(
            Classifier,
            Pipeline(
                [
                    ("scale", StandardScaler()),
                    (
                        "model",
                        MLPClassifier(
                            hidden_layer_sizes=hidden,
                            alpha=float(params["alpha"]),
                            max_iter=int(params["max_iter"]),
                            random_state=seed,
                            solver=solver,
                            early_stopping=False,
                        ),
                    ),
                ]
            ),
        )
    params = _mapping(models["xgboost"], "models.xgboost")
    device = str(params["device"])
    tree_method = str(params["tree_method"])
    if device not in {"cpu", "cuda"}:
        raise ContractError("MODEL_CONFIG", f"unsupported XGBoost device: {device}")
    if tree_method != "hist":
        raise ContractError("MODEL_CONFIG", f"unsupported XGBoost tree method: {tree_method}")
    return cast(
        Classifier,
        XGBClassifier(
            device=device,
            tree_method=tree_method,
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            learning_rate=float(params["learning_rate"]),
            subsample=float(params["subsample"]),
            colsample_bytree=float(params["colsample_bytree"]),
            reg_lambda=float(params["reg_lambda"]),
            random_state=seed,
            n_jobs=1,
            objective="binary:logistic",
            eval_metric="logloss",
        ),
    )


def _fit_with_weights(
    model: Classifier,
    values: np.ndarray[Any, np.dtype[np.float64]],
    target: np.ndarray[Any, np.dtype[np.int64]],
    weights: np.ndarray[Any, np.dtype[np.float64]],
) -> None:
    if isinstance(model, Pipeline):
        model.fit(values, target, model__sample_weight=weights)
    else:
        model.fit(values, target, sample_weight=weights)


def train_seeded_models(
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    model_name: str,
    seeds: Sequence[int] = FORMAL_SEEDS,
    fields: tuple[str, ...] = PRIMARY_FEATURES,
) -> tuple[dict[int, pd.DataFrame], pd.DataFrame, FeatureMatrix, dict[int, Classifier]]:
    """Train fixed seeds on simulation train events and predict every row."""

    if tuple(seeds) != FORMAL_SEEDS:
        raise ContractError("MODEL_SEEDS", f"formal seeds must be {FORMAL_SEEDS}")
    features = build_feature_matrix(frame, fields)
    nominal = (
        frame["sample_role"].astype(str) == "nominal"
        if "sample_role" in frame
        else pd.Series(True, index=frame.index)
    )
    train_mask = (
        (~frame["is_data"].astype(bool))
        & nominal
        & (frame["split"] == "train")
    )
    if not train_mask.any():
        raise ContractError("MODEL_TRAIN_EMPTY", "no simulation training events")
    missing_target = frame.loc[train_mask, "target"].isna().any()
    missing_weight = frame.loc[train_mask, "w_train"].isna().any()
    if missing_target or missing_weight:
        raise ContractError("MODEL_TRAIN_LABEL", "training rows are missing target or weight")
    target = np.asarray(frame.loc[train_mask, "target"], dtype=np.int64)
    weights = np.asarray(frame.loc[train_mask, "w_train"], dtype=np.float64)
    if set(target.tolist()) != {0, 1}:
        raise ContractError("MODEL_TRAIN_CLASS", "both signal and background are required")
    predictions: dict[int, pd.DataFrame] = {}
    fitted_models: dict[int, Classifier] = {}
    for seed in seeds:
        model = build_model(model_name, seed, config, fields)
        _fit_with_weights(model, features.values[train_mask.to_numpy()], target, weights)
        fitted_models[seed] = model
        score = np.asarray(model.predict_proba(features.values)[:, 1], dtype=np.float64)
        predictions[seed] = pd.DataFrame(
            {
                "event_id": frame["event_id"].astype(str).to_numpy(),
                "dataset_id": frame["dataset_id"].astype(str).to_numpy(),
                "target": frame["target"].to_numpy(),
                "w_yield": frame["w_yield"].astype(float).to_numpy(),
                "raw_score": score,
                "ddt_score": np.nan,
                "channel": frame["channel"].astype(str).to_numpy(),
                "m4l": frame["m4l"].astype(float).to_numpy(),
                "model_name": model_name,
                "seed_or_ensemble": seed,
                "is_data": frame["is_data"].astype(bool).to_numpy(),
                "process_group": frame["process_group"].astype(str).to_numpy(),
                "sample_role": (
                    frame["sample_role"].astype(str).to_numpy()
                    if "sample_role" in frame
                    else np.full(len(frame), "nominal", dtype=object)
                ),
                "production_mode": (
                    frame["production_mode"].to_numpy()
                    if "production_mode" in frame
                    else np.full(len(frame), None, dtype=object)
                ),
                "sample_partition": (
                    frame["sample_partition"].astype(str).to_numpy()
                    if "sample_partition" in frame
                    else np.full(len(frame), "inclusive", dtype=object)
                ),
                "variation_of": (
                    frame["variation_of"].to_numpy()
                    if "variation_of" in frame
                    else np.full(len(frame), None, dtype=object)
                ),
                "region": (
                    frame["region"].astype(str).to_numpy()
                    if "region" in frame
                    else np.where(frame["is_data"].astype(bool), "sideband", "simulation")
                ),
                "split": frame["split"].astype(str).to_numpy(),
                "w_train": frame["w_train"].to_numpy(),
            }
        )
    ensemble = ensemble_predictions(predictions)
    return predictions, ensemble, features, fitted_models


def train_seeded_predictions(
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    model_name: str,
    seeds: Sequence[int] = FORMAL_SEEDS,
    fields: tuple[str, ...] = PRIMARY_FEATURES,
) -> tuple[dict[int, pd.DataFrame], pd.DataFrame, FeatureMatrix]:
    """Train fixed seeds and return predictions while preserving the v2 API."""

    predictions, ensemble, features, _ = train_seeded_models(
        frame,
        config,
        model_name,
        seeds=seeds,
        fields=fields,
    )
    return predictions, ensemble, features


def save_seeded_models(
    models: Mapping[int, Classifier],
    model_name: str,
    fields: Sequence[str],
    directory: Path,
    feature_values: np.ndarray[Any, np.dtype[np.float64]],
    expected_predictions: Mapping[int, pd.DataFrame],
) -> dict[str, object]:
    """Persist fitted models and verify reloaded predictions before publication."""

    if tuple(sorted(models)) != tuple(sorted(FORMAL_SEEDS)):
        raise ContractError("MODEL_SEEDS", "all formal fitted models are required")
    directory.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []
    for seed in FORMAL_SEEDS:
        model = models[seed]
        if model_name == "cut_based":
            path = directory / f"model-seed-{seed}.json"
            path.write_bytes(
                canonical_json_bytes(
                    {
                        "model_name": model_name,
                        "seed": seed,
                        "fields": list(fields),
                    }
                )
            )
            format_name = "particleml-cut-v1"
        elif model_name == "xgboost":
            path = directory / f"model-seed-{seed}.json"
            cast(XGBClassifier, model).save_model(path)
            format_name = "xgboost-json"
        else:
            path = directory / f"model-seed-{seed}.joblib"
            joblib.dump(model, path, compress=3)
            format_name = "joblib"
        reloaded = load_model(path, model_name, fields)
        actual = np.asarray(reloaded.predict_proba(feature_values)[:, 1], dtype=np.float64)
        expected = np.asarray(expected_predictions[seed]["raw_score"], dtype=np.float64)
        if not np.allclose(actual, expected, rtol=0.0, atol=1e-12):
            raise ContractError(
                "MODEL_RELOAD",
                f"reloaded {model_name} seed {seed} changed predictions",
            )
        records.append(
            {
                "seed": seed,
                "path": path.name,
                "format": format_name,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": "2.1.0",
        "model_name": model_name,
        "fields": list(fields),
        "seeds": list(FORMAL_SEEDS),
        "libraries": {
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
        "files": records,
    }


def load_model(path: Path, model_name: str, fields: Sequence[str]) -> Classifier:
    """Load one frozen model from its declared family-specific format."""

    if model_name == "cut_based":
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError("MODEL_LOAD", f"cannot load {path}: {exc}") from exc
        if document.get("model_name") != "cut_based" or document.get("fields") != list(fields):
            raise ContractError("MODEL_LOAD", "cut-based model metadata do not match")
        return CutBasedClassifier(fields)
    if model_name == "xgboost":
        model = XGBClassifier()
        model.load_model(path)
        return cast(Classifier, model)
    try:
        loaded = joblib.load(path)
    except (OSError, ValueError, TypeError) as exc:
        raise ContractError("MODEL_LOAD", f"cannot load {path}: {exc}") from exc
    if not hasattr(loaded, "predict_proba"):
        raise ContractError("MODEL_LOAD", f"{path} is not a classifier")
    return cast(Classifier, loaded)


def ensemble_predictions(predictions: Mapping[int, pd.DataFrame]) -> pd.DataFrame:
    """Align by event identity, reject mismatches, and average raw scores."""

    if tuple(sorted(predictions)) != tuple(sorted(FORMAL_SEEDS)):
        raise ContractError("PREDICTION_SEEDS", "all five formal seed predictions are required")
    reference = predictions[FORMAL_SEEDS[0]].copy()
    if reference["event_id"].duplicated().any():
        raise ContractError("PREDICTION_DUPLICATE", "duplicate event_id in reference")
    event_order = reference["event_id"].astype(str).tolist()
    score_columns: list[np.ndarray[Any, np.dtype[np.float64]]] = []
    metadata = [
        "dataset_id",
        "target",
        "w_yield",
        "channel",
        "m4l",
        "model_name",
        "is_data",
        "process_group",
        "sample_role",
        "production_mode",
        "sample_partition",
        "variation_of",
        "region",
        "split",
        "w_train",
    ]
    for seed in FORMAL_SEEDS:
        candidate = predictions[seed]
        if candidate["event_id"].duplicated().any():
            raise ContractError("PREDICTION_DUPLICATE", f"duplicate event_id for seed {seed}")
        indexed = candidate.assign(event_id=candidate["event_id"].astype(str)).set_index("event_id")
        if set(indexed.index) != set(event_order):
            raise ContractError("PREDICTION_ALIGNMENT", f"event set mismatch for seed {seed}")
        aligned = indexed.loc[event_order].reset_index()
        for column in metadata:
            left = reference[column].reset_index(drop=True)
            right = aligned[column].reset_index(drop=True)
            if not left.equals(right):
                raise ContractError(
                    "PREDICTION_METADATA", f"{column} mismatch for seed {seed}"
                )
        score_columns.append(np.asarray(aligned["raw_score"], dtype=np.float64))
    reference["raw_score"] = np.mean(np.vstack(score_columns), axis=0)
    reference["seed_or_ensemble"] = "ensemble"
    return reference
