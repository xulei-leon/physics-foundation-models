"""Weighted classification metrics for raw model scores."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    roc_auc_score,
    roc_curve,
)

from .contracts import ContractError


def _weighted_sample(
    scores: np.ndarray[Any, Any],
    weights: np.ndarray[Any, Any],
) -> tuple[
    np.ndarray[Any, np.dtype[np.float64]],
    np.ndarray[Any, np.dtype[np.float64]],
    float,
]:
    try:
        score_values = np.asarray(scores, dtype=np.float64)
        weight_values = np.asarray(weights, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ContractError("KS_TYPE", "weighted KS inputs must be numeric") from exc
    if score_values.ndim != 1 or weight_values.ndim != 1:
        raise ContractError("KS_SHAPE", "weighted KS inputs must be one-dimensional")
    if len(score_values) == 0 or len(score_values) != len(weight_values):
        raise ContractError("KS_LENGTH", "weighted KS inputs are empty or misaligned")
    if not np.isfinite(score_values).all() or not np.isfinite(weight_values).all():
        raise ContractError("KS_FINITE", "weighted KS inputs must be finite")
    absolute_weights = np.abs(weight_values)
    total_weight = float(np.sum(absolute_weights))
    if not math.isfinite(total_weight) or total_weight <= 0.0:
        raise ContractError("KS_WEIGHT", "weighted KS samples require positive total weight")
    return score_values, absolute_weights, total_weight


def _right_continuous_cdf(
    scores: np.ndarray[Any, np.dtype[np.float64]],
    weights: np.ndarray[Any, np.dtype[np.float64]],
    total_weight: float,
    points: np.ndarray[Any, np.dtype[np.float64]],
) -> np.ndarray[Any, np.dtype[np.float64]]:
    order = np.argsort(scores, kind="stable")
    sorted_scores = scores[order]
    cumulative = np.cumsum(weights[order], dtype=np.float64)
    positions = np.searchsorted(sorted_scores, points, side="right")
    cdf = np.zeros(len(points), dtype=np.float64)
    present = positions > 0
    cdf[present] = cumulative[positions[present] - 1] / total_weight
    return cdf


def weighted_ks_distance(
    scores_a: np.ndarray[Any, Any],
    weights_a: np.ndarray[Any, Any],
    scores_b: np.ndarray[Any, Any],
    weights_b: np.ndarray[Any, Any],
) -> float:
    """Return the absolute-weighted two-sample right-continuous KS distance."""

    sample_a, absolute_a, total_a = _weighted_sample(scores_a, weights_a)
    sample_b, absolute_b, total_b = _weighted_sample(scores_b, weights_b)
    points = np.union1d(sample_a, sample_b)
    cdf_a = _right_continuous_cdf(sample_a, absolute_a, total_a, points)
    cdf_b = _right_continuous_cdf(sample_b, absolute_b, total_b, points)
    distance = float(np.max(np.abs(cdf_a - cdf_b)))
    if not math.isfinite(distance):
        raise ContractError("KS_RESULT", "weighted KS distance is non-finite")
    return float(np.clip(distance, 0.0, 1.0))


def _class_shape_distance(frame: pd.DataFrame, target: int) -> float | None:
    samples: list[tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]] = []
    for split in ("train", "test"):
        selected = frame.loc[frame["split"].astype(str) == split]
        if selected.empty:
            return None
        try:
            scores = selected["raw_score"].to_numpy(dtype=np.float64)
            weights = selected["w_yield"].to_numpy(dtype=np.float64)
        except (TypeError, ValueError) as exc:
            raise ContractError(
                "KS_TYPE", f"target {target} shape diagnostic inputs must be numeric"
            ) from exc
        if not np.isfinite(scores).all() or not np.isfinite(weights).all():
            raise ContractError("KS_FINITE", "shape diagnostic inputs must be finite")
        if float(np.sum(np.abs(weights))) <= 0.0:
            return None
        samples.append((scores, weights))
    return weighted_ks_distance(*samples[0], *samples[1])


def raw_score_shape_diagnostics(frame: pd.DataFrame) -> dict[str, str | float | None]:
    """Compare nominal-simulation train and test raw scores by target class."""

    required = {"target", "raw_score", "split", "w_yield", "is_data", "sample_role"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ContractError("KS_COLUMNS", f"missing columns: {', '.join(missing)}")
    if not all(isinstance(value, (bool, np.bool_)) for value in frame["is_data"]):
        raise ContractError("KS_TYPE", "is_data values must be boolean")
    nominal = frame.loc[
        (~frame["is_data"].astype(bool))
        & (frame["sample_role"].astype(str) == "nominal")
        & frame["split"].astype(str).isin(("train", "test"))
    ].copy()
    if nominal["target"].isna().any():
        raise ContractError("KS_TARGET", "nominal simulation target is missing")
    try:
        target_values = pd.to_numeric(nominal["target"], errors="raise").to_numpy(
            dtype=np.float64
        )
    except (TypeError, ValueError) as exc:
        raise ContractError("KS_TARGET", "nominal simulation target is invalid") from exc
    if not np.isfinite(target_values).all() or not np.isin(target_values, (0.0, 1.0)).all():
        raise ContractError("KS_TARGET", "nominal simulation target must be binary")
    nominal["target"] = target_values.astype(np.int64)
    return {
        "comparison": "train-vs-test",
        "weighting": "absolute-w_yield",
        "signal_weighted_ks": _class_shape_distance(nominal[nominal["target"] == 1], 1),
        "background_weighted_ks": _class_shape_distance(nominal[nominal["target"] == 0], 0),
    }


def weighted_metrics(
    target: np.ndarray[Any, np.dtype[np.int64]],
    score: np.ndarray[Any, np.dtype[np.float64]],
    weights: np.ndarray[Any, np.dtype[np.float64]],
) -> dict[str, float]:
    """Return ROC-AUC, PR-AUC, and rejection near 50% signal efficiency."""

    if not (len(target) == len(score) == len(weights)) or len(target) == 0:
        raise ContractError("METRIC_LENGTH", "metric arrays are empty or misaligned")
    if set(target.tolist()) != {0, 1}:
        raise ContractError("METRIC_CLASS", "both target classes are required")
    absolute = np.abs(weights)
    if any(float(np.sum(absolute[target == label])) <= 0 for label in (0, 1)):
        raise ContractError("METRIC_WEIGHT", "both target classes require positive total weight")
    roc_auc = float(roc_auc_score(target, score, sample_weight=absolute))
    pr_auc = float(average_precision_score(target, score, sample_weight=absolute))
    false_positive, true_positive, _ = roc_curve(target, score, sample_weight=absolute)
    index = int(np.argmin(np.abs(true_positive - 0.5)))
    positive_false_positive = false_positive[false_positive > 0]
    efficiency = (
        float(false_positive[index])
        if false_positive[index] > 0
        else float(np.min(positive_false_positive))
    )
    rejection = 1.0 / efficiency
    return {
        "weighted_roc_auc": roc_auc,
        "weighted_pr_auc": pr_auc,
        "background_rejection_at_50_signal_efficiency": rejection,
    }
