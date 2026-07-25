"""Weighted classification metrics for raw model scores."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    roc_auc_score,
    roc_curve,
)

from .contracts import ContractError


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
    roc_auc = float(roc_auc_score(target, score, sample_weight=absolute))
    pr_auc = float(average_precision_score(target, score, sample_weight=absolute))
    false_positive, true_positive, _ = roc_curve(target, score, sample_weight=absolute)
    index = int(np.argmin(np.abs(true_positive - 0.5)))
    rejection = float("inf") if false_positive[index] == 0 else float(1.0 / false_positive[index])
    return {
        "weighted_roc_auc": roc_auc,
        "weighted_pr_auc": pr_auc,
        "background_rejection_at_50_signal_efficiency": rejection,
    }
