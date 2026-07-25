from __future__ import annotations

import numpy as np

from particleml.evaluation import weighted_metrics


def test_weighted_metrics_for_perfect_classifier() -> None:
    metrics = weighted_metrics(
        np.asarray([0, 0, 1, 1], dtype=np.int64),
        np.asarray([0.1, 0.2, 0.8, 0.9], dtype=np.float64),
        np.asarray([1.0, 2.0, 1.0, 2.0], dtype=np.float64),
    )
    assert metrics["weighted_roc_auc"] == 1.0
    assert metrics["weighted_pr_auc"] == 1.0
