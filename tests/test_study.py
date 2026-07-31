from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import particleml.study as study_module
from particleml.models import FORMAL_SEEDS, MODEL_NAMES

ZERO_HASH = "0" * 64
ONE_HASH = "1" * 64
TWO_HASH = "2" * 64


class _FakeCalibrator:
    def to_document(self) -> dict[str, object]:
        return {}


def _prediction_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "target": target,
                "raw_score": score,
                "split": split,
                "w_yield": 1.0,
                "is_data": False,
                "sample_role": "nominal",
                "variation_of": None,
            }
            for target, score in ((0, 0.2), (1, 0.8))
            for split in ("train", "test")
        ]
    )


def test_study_attaches_non_blocking_shape_diagnostics_to_every_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = _prediction_frame()
    diagnostic_calls: list[int] = []

    def fake_train_seeded_models(*args: object, **kwargs: object) -> tuple[object, ...]:
        seeded = {seed: frame.copy(deep=True) for seed in FORMAL_SEEDS}
        features = SimpleNamespace(fields=(), values=np.empty((len(frame), 0)))
        return seeded, frame.copy(deep=True), features, {}

    def fake_diagnostic(prediction: pd.DataFrame) -> dict[str, str | float | None]:
        diagnostic_calls.append(len(prediction))
        value = len(diagnostic_calls) / 100.0
        return {
            "comparison": "train-vs-test",
            "weighting": "absolute-w_yield",
            "signal_weighted_ks": value,
            "background_weighted_ks": value,
        }

    monkeypatch.setattr(study_module, "apply_tuning_decision", lambda config, _: config)
    monkeypatch.setattr(study_module, "train_seeded_models", fake_train_seeded_models)
    monkeypatch.setattr(study_module, "save_seeded_models", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        study_module,
        "_apply_ddt",
        lambda prediction, _: (prediction.copy(deep=True), _FakeCalibrator()),
    )
    monkeypatch.setattr(study_module, "_metrics", lambda _: {})
    monkeypatch.setattr(
        study_module,
        "_expected_bundle",
        lambda *args, **kwargs: ({}, {}, {"significance": "1.0"}, 0.0),
    )
    monkeypatch.setattr(study_module, "_diagnostic_fits", lambda *args, **kwargs: [])
    monkeypatch.setattr(study_module, "_gate_set", lambda *args, **kwargs: {"all_passed": True})
    monkeypatch.setattr(study_module, "validate_document", lambda *args, **kwargs: None)
    monkeypatch.setattr(study_module, "raw_score_shape_diagnostics", fake_diagnostic, raising=False)

    study_result, gate_sets, _ = study_module.run_blinded_study(
        frame,
        {},
        ZERO_HASH,
        {"dataset_sha256": ZERO_HASH},
        ONE_HASH,
        TWO_HASH,
        tmp_path / "study",
    )

    labels = {*(f"seed-{seed}" for seed in FORMAL_SEEDS), "ensemble"}
    assert set(study_result["models"]) == set(MODEL_NAMES)
    for model_name in MODEL_NAMES:
        runs = study_result["models"][model_name]["runs"]
        assert set(runs) == labels
        for run in runs.values():
            assert run["status"] == "completed"
            assert run["expected_significance"] == 1.0
            assert run["gates_passed"] is True
            diagnostic = run["raw_score_shape_diagnostics"]
            assert set(diagnostic) == {
                "comparison",
                "weighting",
                "signal_weighted_ks",
                "background_weighted_ks",
            }
    assert len(diagnostic_calls) == len(MODEL_NAMES) * len(labels)
    assert study_result["status"] == "completed"
    assert study_result["blocking_reasons"] == []
    assert study_result["primary_comparison"] == {
        "xgboost_expected_significance": 1.0,
        "cut_based_expected_significance": 1.0,
        "delta": 0.0,
    }
    assert all(record["all_passed"] is True for record in gate_sets.values())
    assert all("raw_score_shape_diagnostics" not in record for record in gate_sets.values())
