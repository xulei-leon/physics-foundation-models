from __future__ import annotations

from particleml.cli import build_parser, main


def test_contract_command_validates_v2_suite() -> None:
    assert main(["contracts", "validate"]) == 0


def test_observed_fit_refuses_before_workspace_access(capsys: object) -> None:
    assert main(["fit", "observed"]) == 2
    assert main(["fit", "observed", "--unblind"]) == 2


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
        ["contracts", "validate"],
    ]
    for example in examples:
        assert callable(parser.parse_args(example).handler)
