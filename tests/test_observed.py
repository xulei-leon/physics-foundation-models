from __future__ import annotations

from copy import deepcopy

import pandas as pd
import pytest

from particleml.contracts import ContractError, sha256_document
from particleml.inference import build_templates, build_workspace
from particleml.observed import (
    replace_workspace_observations,
    verify_sideband_reproduction,
)

from .test_inference import template_frame


def test_sideband_reproduction_requires_matching_data_rows() -> None:
    frozen = pd.DataFrame(
        [
            {
                "event_id": "a" * 64,
                "is_data": True,
                "m4l": 110.0,
                "region": "sideband",
            }
        ]
    )
    reproduced = frozen.copy()
    assert verify_sideband_reproduction(frozen, reproduced)["passed"] is True
    reproduced.loc[0, "m4l"] = 111.0
    with pytest.raises(ContractError, match="OBSERVED_SIDEBAND_MISMATCH"):
        verify_sideband_reproduction(frozen, reproduced)


def test_observed_workspace_replaces_observations_only() -> None:
    templates = build_templates(template_frame(), bin_width=55.0)
    workspace = build_workspace(templates)
    observed_rows: list[dict[str, object]] = []
    for state in ("4e", "4mu", "2e2mu"):
        for score in (0.5, 0.9):
            observed_rows.append(
                {
                    "channel": state,
                    "m4l": 125.0,
                    "ddt_score": score,
                }
            )
    channels_before = sha256_document(workspace["channels"])
    observed_workspace = replace_workspace_observations(
        deepcopy(workspace),
        templates,
        pd.DataFrame(observed_rows),
        0.8,
    )
    assert sha256_document(observed_workspace["channels"]) == channels_before
    for observation in observed_workspace["observations"]:
        assert observation["data"] == [1.0]
