from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from particleml.contracts import ContractError
from particleml.decorrelation import (
    DDTCalibrator,
    ddt_category,
    effective_count,
    evaluate_decorrelation_gates,
    sideband_acceptance_gate,
    spearman_gate,
)


def test_weighted_conditional_cdf_and_adaptive_bin_merging() -> None:
    masses = np.concatenate(
        [np.linspace(low + 0.1, low + 4.9, 10) for low in (105.0, 110.0, 115.0, 120.0)]
    )
    scores = np.tile(np.linspace(0.05, 0.95, 10), 4)
    channels = np.asarray(["4e"] * len(scores), dtype=np.str_)
    weights = np.ones(len(scores), dtype=np.float64)
    calibrator = DDTCalibrator.fit(
        scores,
        masses,
        channels,
        weights,
        mass_min=105.0,
        mass_max=125.0,
        initial_width=5.0,
        minimum_effective_events=15.0,
    )
    assert [(item.low, item.high) for item in calibrator.bins] == [
        (105.0, 115.0),
        (115.0, 125.0),
    ]
    transformed = calibrator.transform(scores, masses, channels)
    assert np.all((0.0 <= transformed) & (transformed <= 1.0))
    assert effective_count(weights[:10]) == pytest.approx(10.0)
    assert ddt_category(0.799) == "low"
    assert ddt_category(0.8) == "high"


def test_fit_from_frame_rejects_non_calibration_or_signal_rows() -> None:
    frame = pd.DataFrame(
        {
            "raw_score": [0.1, 0.2, 0.3],
            "m4l": [110.0, 115.0, 140.0],
            "channel": ["4e"] * 3,
            "w_train": [1.0] * 3,
            "split": ["calibration", "train", "calibration"],
            "target": [0, 0, 0],
            "is_data": [False] * 3,
        }
    )
    with pytest.raises(ContractError, match="DDT_PROVENANCE"):
        DDTCalibrator.fit_from_frame(frame, minimum_effective_events=1)


def test_spearman_gate_blocks_mass_correlated_score() -> None:
    mass = np.linspace(105.0, 159.0, 100)
    rho, passed = spearman_gate(mass, mass)
    assert rho == pytest.approx(1.0)
    assert not passed


def _independent_sideband(seed: int, is_data: bool) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    masses = np.concatenate((rng.uniform(105.0, 120.0, 6000), rng.uniform(130.0, 160.0, 12000)))
    scores = rng.uniform(0.0, 1.0, len(masses))
    return pd.DataFrame(
        {
            "m4l": masses,
            "ddt_score": scores,
            "channel": "4e",
            "w_yield": 1.0,
            "is_data": is_data,
        }
    )


def test_sideband_and_combined_gates_pass_independent_fixture() -> None:
    mc = _independent_sideband(3, False)
    data = _independent_sideband(7, True)
    acceptances, passed = sideband_acceptance_gate(mc)
    assert acceptances and passed
    result = evaluate_decorrelation_gates(mc, data, spurious_signal_sigma=0.1)
    assert result["all_passed"] is True


def test_spurious_signal_gate_is_strict() -> None:
    mc = _independent_sideband(3, False)
    data = _independent_sideband(7, True)
    result = evaluate_decorrelation_gates(mc, data, spurious_signal_sigma=0.2)
    assert result["all_passed"] is False
