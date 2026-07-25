"""Frozen model families, five-seed training, and aligned ensembling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.neural_network import MLPClassifier  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
from xgboost import XGBClassifier

from .contracts import ContractError
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
                            early_stopping=False,
                        ),
                    ),
                ]
            ),
        )
    params = _mapping(models["xgboost"], "models.xgboost")
    return cast(
        Classifier,
        XGBClassifier(
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


def train_seeded_predictions(
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    model_name: str,
    seeds: Sequence[int] = FORMAL_SEEDS,
    fields: tuple[str, ...] = PRIMARY_FEATURES,
) -> tuple[dict[int, pd.DataFrame], pd.DataFrame, FeatureMatrix]:
    """Train fixed seeds on simulation train events and predict every row."""

    if tuple(seeds) != FORMAL_SEEDS:
        raise ContractError("MODEL_SEEDS", f"formal seeds must be {FORMAL_SEEDS}")
    features = build_feature_matrix(frame, fields)
    train_mask = (~frame["is_data"].astype(bool)) & (frame["split"] == "train")
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
    for seed in seeds:
        model = build_model(model_name, seed, config, fields)
        _fit_with_weights(model, features.values[train_mask.to_numpy()], target, weights)
        score = np.asarray(model.predict_proba(features.values)[:, 1], dtype=np.float64)
        predictions[seed] = pd.DataFrame(
            {
                "event_id": frame["event_id"].astype(str).to_numpy(),
                "target": frame["target"].to_numpy(),
                "w_yield": frame["w_yield"].astype(float).to_numpy(),
                "raw_score": score,
                "ddt_score": np.nan,
                "channel": frame["channel"].astype(str).to_numpy(),
                "m4l": frame["m4l"].astype(float).to_numpy(),
                "model_name": model_name,
                "seed_or_ensemble": seed,
            }
        )
    ensemble = ensemble_predictions(predictions)
    return predictions, ensemble, features


def ensemble_predictions(predictions: Mapping[int, pd.DataFrame]) -> pd.DataFrame:
    """Align by event identity, reject mismatches, and average raw scores."""

    if tuple(sorted(predictions)) != tuple(sorted(FORMAL_SEEDS)):
        raise ContractError("PREDICTION_SEEDS", "all five formal seed predictions are required")
    reference = predictions[FORMAL_SEEDS[0]].copy()
    if reference["event_id"].duplicated().any():
        raise ContractError("PREDICTION_DUPLICATE", "duplicate event_id in reference")
    event_order = reference["event_id"].astype(str).tolist()
    score_columns: list[np.ndarray[Any, np.dtype[np.float64]]] = []
    metadata = ["target", "w_yield", "channel", "m4l", "model_name"]
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
