from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

from particleml.config import load_config
from particleml.contracts import ContractError
from particleml.models import (
    FORMAL_SEEDS,
    build_model,
    ensemble_predictions,
    train_seeded_predictions,
)

from .helpers import synthetic_event_frame

ROOT = Path(__file__).resolve().parents[1]


def _test_config() -> dict[str, object]:
    config = deepcopy(load_config(ROOT / "configs" / "analysis-v1.yaml", "analysis"))
    models = config["models"]
    assert isinstance(models, dict)
    xgboost = models["xgboost"]
    mlp = models["mlp"]
    assert isinstance(xgboost, dict) and isinstance(mlp, dict)
    xgboost["device"] = "cpu"
    xgboost["n_estimators"] = 10
    mlp["hidden_layer_sizes"] = [8]
    mlp["max_iter"] = 60
    return config


def test_xgboost_runtime_comes_from_frozen_config() -> None:
    config = deepcopy(load_config(ROOT / "configs" / "analysis-v1.yaml", "analysis"))
    model = build_model("xgboost", FORMAL_SEEDS[0], config)
    assert isinstance(model, XGBClassifier)
    assert model.get_params()["device"] == "cuda"
    assert model.get_params()["tree_method"] == "hist"

    models = config["models"]
    assert isinstance(models, dict)
    xgboost = models["xgboost"]
    assert isinstance(xgboost, dict)
    xgboost["device"] = "tpu"
    with pytest.raises(ContractError, match="unsupported XGBoost device"):
        build_model("xgboost", FORMAL_SEEDS[0], config)


@pytest.mark.parametrize("model_name", ["cut_based", "logistic", "xgboost", "mlp"])
def test_all_model_paths_produce_aligned_five_seed_ensemble(model_name: str) -> None:
    seeded, ensemble, features = train_seeded_predictions(
        synthetic_event_frame(), _test_config(), model_name
    )
    assert tuple(seeded) == FORMAL_SEEDS
    assert len(ensemble) == len(features.event_ids)
    assert ensemble["event_id"].tolist() == features.event_ids.tolist()
    assert ensemble["seed_or_ensemble"].eq("ensemble").all()
    assert ensemble["raw_score"].between(0.0, 1.0).all()


def test_seeded_logistic_training_is_reproducible() -> None:
    frame = synthetic_event_frame()
    _, first, _ = train_seeded_predictions(frame, _test_config(), "logistic")
    _, second, _ = train_seeded_predictions(frame, _test_config(), "logistic")
    np.testing.assert_allclose(first["raw_score"], second["raw_score"], rtol=0, atol=0)


def test_prediction_alignment_handles_order_and_rejects_missing_event() -> None:
    frame = synthetic_event_frame()
    seeded, _, _ = train_seeded_predictions(frame, _test_config(), "cut_based")
    reordered = {seed: value.sample(frac=1.0, random_state=seed) for seed, value in seeded.items()}
    aligned = ensemble_predictions(reordered)
    assert len(aligned) == len(frame)
    broken = dict(reordered)
    broken[FORMAL_SEEDS[-1]] = broken[FORMAL_SEEDS[-1]].iloc[:-1]
    with pytest.raises(ContractError, match="PREDICTION_ALIGNMENT"):
        ensemble_predictions(broken)


def test_data_rows_cannot_enter_training() -> None:
    frame = synthetic_event_frame()
    data = frame.iloc[[0]].copy()
    data["event_id"] = "f" * 64
    data["is_data"] = True
    data["split"] = "data"
    data["target"] = np.nan
    data["w_train"] = np.nan
    combined = pd.concat([frame, data], ignore_index=True)
    _, ensemble, _ = train_seeded_predictions(combined, _test_config(), "logistic")
    assert len(ensemble) == len(combined)
