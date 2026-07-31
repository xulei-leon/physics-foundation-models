from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from particleml.contracts import ContractError
from particleml.evaluation import (
    raw_score_shape_diagnostics,
    weighted_ks_distance,
    weighted_metrics,
)


def test_weighted_metrics_for_perfect_classifier() -> None:
    metrics = weighted_metrics(
        np.asarray([0, 0, 1, 1], dtype=np.int64),
        np.asarray([0.1, 0.2, 0.8, 0.9], dtype=np.float64),
        np.asarray([1.0, 2.0, 1.0, 2.0], dtype=np.float64),
    )
    assert metrics["weighted_roc_auc"] == 1.0
    assert metrics["weighted_pr_auc"] == 1.0
    assert math.isfinite(metrics["background_rejection_at_50_signal_efficiency"])


def test_weighted_ks_identical_disjoint_and_absolute_negative_weights() -> None:
    scores = np.asarray([0.0, 0.5, 1.0], dtype=np.float64)
    positive = np.asarray([1.0, 2.0, 1.0], dtype=np.float64)
    negative = -positive

    assert weighted_ks_distance(scores, positive, scores, positive) == 0.0
    assert weighted_ks_distance(scores, negative, scores, positive) == 0.0
    assert weighted_ks_distance(
        np.asarray([0.0, 0.1]),
        np.ones(2),
        np.asarray([0.9, 1.0]),
        np.ones(2),
    ) == 1.0


def test_weighted_ks_uses_right_continuous_cdfs_for_tied_scores() -> None:
    distance = weighted_ks_distance(
        np.asarray([0.0, 0.0, 1.0]),
        np.asarray([1.0, 3.0, 2.0]),
        np.asarray([0.0, 1.0, 1.0]),
        np.asarray([2.0, 1.0, 3.0]),
    )

    assert distance == pytest.approx(1.0 / 3.0)


@pytest.mark.parametrize(
    ("scores_a", "weights_a", "scores_b", "weights_b"),
    [
        (np.asarray([]), np.asarray([]), np.asarray([0.0]), np.asarray([1.0])),
        (np.asarray([[0.0]]), np.asarray([1.0]), np.asarray([0.0]), np.asarray([1.0])),
        (np.asarray([0.0]), np.asarray([1.0, 2.0]), np.asarray([0.0]), np.asarray([1.0])),
        (np.asarray([np.inf]), np.asarray([1.0]), np.asarray([0.0]), np.asarray([1.0])),
        (np.asarray([0.0]), np.asarray([0.0]), np.asarray([0.0]), np.asarray([1.0])),
    ],
)
def test_weighted_ks_rejects_malformed_or_zero_weight_samples(
    scores_a: np.ndarray, weights_a: np.ndarray, scores_b: np.ndarray, weights_b: np.ndarray
) -> None:
    with pytest.raises(ContractError, match="KS_"):
        weighted_ks_distance(scores_a, weights_a, scores_b, weights_b)


def _shape_diagnostic_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for target, train_scores, test_scores in (
        (1, (0.8, 0.9), (0.8, 0.9)),
        (0, (0.1, 0.2), (0.15, 0.25)),
    ):
        for split, scores in (("train", train_scores), ("test", test_scores)):
            rows.extend(
                {
                    "target": target,
                    "raw_score": score,
                    "split": split,
                    "w_yield": -1.0 if score == scores[0] else 1.0,
                    "is_data": False,
                    "sample_role": "nominal",
                }
                for score in scores
            )
    rows.extend(
        [
            {
                "target": None,
                "raw_score": 1.0e9,
                "split": "data",
                "w_yield": 1.0,
                "is_data": True,
                "sample_role": "nominal",
            },
            {
                "target": 1,
                "raw_score": -1.0e9,
                "split": "train",
                "w_yield": 1.0,
                "is_data": False,
                "sample_role": "generator_variation",
            },
        ]
    )
    return pd.DataFrame(rows)


def test_raw_score_shape_diagnostics_filter_non_nominal_rows() -> None:
    diagnostic = raw_score_shape_diagnostics(_shape_diagnostic_frame())

    assert diagnostic == {
        "comparison": "train-vs-test",
        "weighting": "absolute-w_yield",
        "signal_weighted_ks": 0.0,
        "background_weighted_ks": 0.5,
    }


def test_raw_score_shape_diagnostics_nulls_only_the_zero_weight_class() -> None:
    frame = _shape_diagnostic_frame()
    frame.loc[
        (~frame["is_data"])
        & (frame["sample_role"] == "nominal")
        & (frame["target"] == 1)
        & (frame["split"] == "train"),
        "w_yield",
    ] = 0.0

    diagnostic = raw_score_shape_diagnostics(frame)
    assert diagnostic["signal_weighted_ks"] is None
    assert diagnostic["background_weighted_ks"] == 0.5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("raw_score", "not-a-score"),
        ("w_yield", "not-a-weight"),
        ("target", 0.5),
        ("target", 2),
        ("is_data", "False"),
    ],
)
def test_raw_score_shape_diagnostics_rejects_malformed_frame_values(
    field: str, value: object
) -> None:
    frame = _shape_diagnostic_frame()
    if isinstance(value, str):
        frame[field] = frame[field].astype(object)
    frame.loc[0, field] = value

    with pytest.raises(ContractError, match="KS_"):
        raw_score_shape_diagnostics(frame)
