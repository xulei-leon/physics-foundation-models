from __future__ import annotations

import json

import pandas as pd
import pytest

import particleml.cli as cli_module
from particleml.cli import build_parser, main


def test_contract_command_validates_v2_suite() -> None:
    assert main(["contracts", "validate"]) == 0


def test_observed_fit_refuses_before_workspace_access(capsys: object) -> None:
    assert main(["fit", "observed"]) == 2
    assert main(["fit", "observed", "--unblind"]) == 2


def test_audit_data_prints_simulation_weight_groups(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    frame = pd.DataFrame(
        [
            {
                "dataset_id": "mc",
                "process_group": "signal",
                "sample_role": "nominal",
                "split": "train",
                "is_data": False,
                "w_yield": -2.0,
            },
            {
                "dataset_id": "data",
                "process_group": "data",
                "sample_role": "nominal",
                "split": "data",
                "is_data": True,
                "w_yield": 1.0,
            },
        ]
    )
    monkeypatch.setattr(cli_module, "load_config", lambda *_: {})
    monkeypatch.setattr(cli_module, "load_dataset", lambda _: (frame, {}))
    monkeypatch.setattr(cli_module, "audit_frame", lambda _: {"rows": 2})

    assert main(["audit", "data", "--dataset", "unused"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "rows": 2,
        "simulation_weight_groups": [
            {
                "dataset_id": "mc",
                "process_group": "signal",
                "sample_role": "nominal",
                "split": "train",
                "events": 1,
                "negative_events": 1,
                "negative_fraction": 1.0,
                "sum_w_yield": -2.0,
                "sum_abs_w_yield": 2.0,
            }
        ],
    }


def test_public_command_tree_is_registered() -> None:
    parser = build_parser()
    examples = [
        ["catalog", "validate", "--catalog", "catalog.json"],
        ["dataset", "build", "--catalog", "c.json", "--cache", "cache", "--output", "out"],
        ["audit", "data", "--dataset", "dataset"],
        ["run", "train", "--dataset", "dataset", "--output", "training"],
        ["study", "tune", "--dataset", "dataset", "--output", "tuning"],
        [
            "study",
            "run",
            "--catalog",
            "catalog.json",
            "--dataset",
            "dataset",
            "--tuning",
            "tuning",
            "--output",
            "study",
        ],
        ["decorrelate", "--predictions", "training", "--output", "ddt"],
        ["evaluate", "--predictions", "ddt", "--output", "evaluation"],
        ["analysis", "freeze", "--inputs", "artifacts", "--output", "freeze.json"],
        [
            "analysis",
            "authorize",
            "--freeze",
            "freeze.json",
            "--approver",
            "Approver",
            "--output",
            "authorization.json",
        ],
        [
            "analysis",
            "observed",
            "--freeze",
            "freeze.json",
            "--authorization",
            "authorization.json",
            "--catalog",
            "catalog.json",
            "--cache",
            "cache",
            "--dataset",
            "dataset",
            "--study",
            "study",
            "--output",
            "observed",
            "--unblind",
        ],
        ["fit", "expected", "--predictions", "ddt", "--output", "fit"],
        ["fit", "observed", "--freeze", "freeze.json", "--unblind"],
        ["report", "build", "--inputs", "artifacts", "--output", "report"],
        ["demo", "run", "--output", "demo"],
        ["contracts", "validate"],
    ]
    for example in examples:
        assert callable(parser.parse_args(example).handler)
