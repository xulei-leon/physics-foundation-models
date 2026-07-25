from __future__ import annotations

import pytest

from particleml.contracts import ContractError
from particleml.weights import attach_training_weights, yield_weight


def _metadata(mc_weight: float = 1.0) -> dict[str, float]:
    return {
        "xsec_pb": 2.0,
        "kfactor": 1.5,
        "filter_efficiency": 0.5,
        "sum_of_generator_weights": 10.0,
        "mcWeight": mc_weight,
        "ScaleFactor_PILEUP": 1.0,
        "ScaleFactor_ELE": 1.0,
        "ScaleFactor_MUON": 1.0,
        "ScaleFactor_LepTRIGGER": 1.0,
    }


def test_signed_yield_weight_formula() -> None:
    assert yield_weight(_metadata(-2.0), 100.0) == pytest.approx(-30.0)


def test_missing_or_zero_metadata_fails_closed() -> None:
    metadata = _metadata()
    del metadata["kfactor"]
    with pytest.raises(ContractError, match="WEIGHT_MISSING"):
        yield_weight(metadata, 100.0)
    metadata = _metadata()
    metadata["sum_of_generator_weights"] = 0.0
    with pytest.raises(ContractError, match="WEIGHT_SUMW"):
        yield_weight(metadata, 100.0)


def test_training_weights_are_absolute_and_class_balanced() -> None:
    rows = [
        {"is_data": False, "target": 1, "w_yield": -3.0},
        {"is_data": False, "target": 1, "w_yield": 1.0},
        {"is_data": False, "target": 0, "w_yield": 2.0},
        {"is_data": True, "target": None, "w_yield": 1.0},
    ]
    weighted = attach_training_weights(rows)
    assert sum(float(row["w_train"]) for row in weighted[:2]) == pytest.approx(0.5)
    assert float(weighted[2]["w_train"]) == pytest.approx(0.5)
    assert weighted[3]["w_train"] is None
