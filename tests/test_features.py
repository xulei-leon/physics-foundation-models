from __future__ import annotations

import numpy as np
import pytest

from particleml.contracts import ContractError
from particleml.features import (
    PRIMARY_FEATURES,
    build_feature_frame,
    build_feature_matrix,
    validate_angle_ranges,
)

from .helpers import synthetic_event_frame


def test_primary_feature_matrix_is_finite_dimensionless_and_hashed() -> None:
    frame = synthetic_event_frame(12)
    derived = build_feature_frame(frame)
    validate_angle_ranges(derived)
    matrix = build_feature_matrix(frame)
    assert matrix.fields == PRIMARY_FEATURES
    assert matrix.values.shape == (12, len(PRIMARY_FEATURES))
    assert np.isfinite(matrix.values).all()
    assert len(matrix.sha256) == 64
    assert not {"m4l", "event_id", "w_yield", "target"} & set(matrix.fields)


@pytest.mark.parametrize("forbidden", ["m4l", "event_id", "w_train", "truth_match"])
def test_model_matrix_rejects_forbidden_fields(forbidden: str) -> None:
    with pytest.raises(ContractError, match="FEATURE_FORBIDDEN"):
        build_feature_matrix(synthetic_event_frame(4), ("z1_mass_fraction", forbidden))


def test_duplicate_event_identity_is_rejected() -> None:
    frame = synthetic_event_frame(4)
    frame.loc[1, "event_id"] = frame.loc[0, "event_id"]
    with pytest.raises(ContractError, match="FEATURE_DUPLICATE"):
        build_feature_matrix(frame)
