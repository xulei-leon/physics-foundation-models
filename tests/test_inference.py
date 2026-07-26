from __future__ import annotations

import pandas as pd
import pytest

from particleml.contracts import ContractError
from particleml.inference import (
    CATEGORIES,
    FINAL_STATES,
    build_templates,
    build_workspace,
    expected_significance_delta,
    fit_workspace,
    merge_nonpositive_bins,
    spurious_signal_sigma,
)


def template_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state in FINAL_STATES:
        for category in CATEGORIES:
            for process, weight in (
                ("signal", 5.0),
                ("irreducible_background", 20.0),
                ("reducible_background", 5.0),
            ):
                rows.append(
                    {
                        "m4l": 125.0,
                        "ddt_score": 0.9 if category == "high" else 0.5,
                        "channel": state,
                        "process_group": process,
                        "sample_role": "nominal",
                        "is_data": False,
                        "w_yield": weight,
                        "split": "test",
                        "dataset_id": f"mc-{process}",
                    }
                )
    return pd.DataFrame(rows)


def test_nonpositive_bins_merge_in_fixed_adjacent_order() -> None:
    edges, yields, variances = merge_nonpositive_bins(
        [105.0, 106.0, 107.0, 108.0],
        {"signal": [1.0, -0.5, 1.0], "background": [2.0, 2.0, 2.0]},
        {"signal": [1.0, 0.25, 1.0], "background": [4.0, 4.0, 4.0]},
    )
    assert edges == [105.0, 106.0, 108.0]
    assert yields["signal"] == [1.0, 0.5]
    assert variances["signal"] == [1.0, 1.25]


def test_nonpositive_total_blocks_fit() -> None:
    with pytest.raises(ContractError, match="TEMPLATE_NONPOSITIVE"):
        merge_nonpositive_bins(
            [105.0, 106.0],
            {"signal": [0.0], "background": [1.0]},
            {"signal": [1.0], "background": [1.0]},
        )


def test_six_channel_workspace_nuisances_and_expected_fit() -> None:
    templates = build_templates(template_frame(), bin_width=55.0)
    workspace = build_workspace(templates)
    assert len(workspace["channels"]) == 6
    serialized = str(workspace)
    for nuisance in ("lumi", "signal_theory", "irreducible_norm", "reducible_norm"):
        assert nuisance in serialized
    result = fit_workspace(workspace)
    assert result["mode"] == "expected"
    assert float(result["significance"]) > 0
    assert float(result["mu_hat"]) == pytest.approx(1.0, abs=1e-3)
    assert len(result["mu_interval"]) == 2
    assert spurious_signal_sigma(workspace) < 0.2
    comparison = expected_significance_delta(
        {"mode": "expected", "significance": 3.0},
        {"mode": "expected", "significance": 2.0},
    )
    assert comparison["absolute_delta"] == 1.0
    assert comparison["relative_delta"] == 0.5


def test_nominal_templates_exclude_variations_and_apply_fixed_scaling() -> None:
    frame = template_frame()
    frame.loc[frame["process_group"] == "signal", "dataset_id"] = "mc-1"
    variation = frame[frame["process_group"] == "signal"].copy()
    variation["sample_role"] = "generator_variation"
    variation["dataset_id"] = "mc-101"
    variation["variation_of"] = 1
    variation["w_yield"] = 7.0
    combined = pd.concat([frame, variation], ignore_index=True)
    nominal = build_templates(combined, bin_width=55.0, weight_scale=10.0)
    assert nominal["4e_low"]["yields"]["signal"] == [50.0]
    replacement = build_templates(
        combined,
        bin_width=55.0,
        weight_scale=10.0,
        generator_replacement=1,
    )
    assert replacement["4e_low"]["yields"]["signal"] == [70.0]
