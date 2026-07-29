from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from particleml.config import load_config
from particleml.contracts import validate_document
from particleml.tuning import apply_tuning_decision, tune_models

from .helpers import synthetic_event_frame

ROOT = Path(__file__).resolve().parents[1]


def test_validation_only_tuning_is_schema_valid_and_applicable() -> None:
    config = deepcopy(load_config(ROOT / "configs" / "analysis-v1.yaml", "analysis"))
    models = config["models"]
    assert isinstance(models, dict)
    tuning = models["tuning"]
    assert isinstance(tuning, dict)
    tuning["logistic_c"] = [1.0]
    tuning["xgboost_n_estimators"] = [5]
    tuning["xgboost_max_depth"] = [2]
    tuning["xgboost_learning_rate"] = [0.1]
    tuning["mlp_hidden_layer_sizes"] = [[1]]
    tuning["mlp_alpha"] = [0.0001]
    xgboost = models["xgboost"]
    mlp = models["mlp"]
    assert isinstance(xgboost, dict) and isinstance(mlp, dict)
    xgboost["device"] = "cpu"
    mlp["max_iter"] = 1000
    decision = tune_models(synthetic_event_frame(), config, "a" * 64)
    validate_document(decision, "tuning-decision")
    effective = apply_tuning_decision(config, decision)
    effective_models = effective["models"]
    assert isinstance(effective_models, dict)
    assert effective_models["xgboost"]["n_estimators"] == 5
