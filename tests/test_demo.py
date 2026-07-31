from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import httpx
import pytest

import particleml.cli as cli
import particleml.demo as demo_module
from particleml.config import load_config
from particleml.contracts import sha256_file, validate_document
from particleml.demo import DEMO_FIGURES, _write_synthetic_root, run_offline_demo
from particleml.models import FORMAL_SEEDS, MODEL_ROLES

ROOT = Path(__file__).resolve().parents[1]
StudyOutput = tuple[dict[str, Any], dict[str, Any], dict[str, Any]]


def _assert_primary_comparison_contract(summary: dict[str, Any]) -> None:
    comparison = summary["primary_comparison"]
    if comparison is None:
        assert summary["study_status"] == "blocked"
        assert "primary_fit_unavailable" in summary["blocking_reasons"]
        return
    assert isinstance(comparison, dict)
    assert all(math.isfinite(float(value)) for value in comparison.values())


@pytest.mark.parametrize(
    "summary",
    [
        {
            "study_status": "blocked",
            "blocking_reasons": ["primary_fit_unavailable"],
            "primary_comparison": None,
        },
        {
            "study_status": "completed",
            "blocking_reasons": [],
            "primary_comparison": {
                "xgboost_expected_significance": 2.0,
                "cut_based_expected_significance": 1.5,
                "delta": 0.5,
            },
        },
    ],
)
def test_demo_primary_comparison_contract(summary: dict[str, Any]) -> None:
    _assert_primary_comparison_contract(summary)


def test_synthetic_root_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first" / "4e-signal.root"
    second = tmp_path / "second" / "4e-signal.root"
    first.parent.mkdir()
    second.parent.mkdir()
    _write_synthetic_root(first, "4e", "signal", 120)
    _write_synthetic_root(second, "4e", "signal", 120)
    assert sha256_file(first) == sha256_file(second)


def test_full_offline_demo_is_blinded_non_formal_and_freeze_ineligible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_study_result: dict[str, Any] | None = None
    captured_gate_sets: dict[str, Any] | None = None
    study_call_count = 0

    def network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline demo attempted an HTTP request")

    original_run_blinded_study = demo_module.run_blinded_study

    def capture_study(*args: Any, **kwargs: Any) -> StudyOutput:
        nonlocal captured_gate_sets, captured_study_result, study_call_count
        study_call_count += 1
        result = original_run_blinded_study(*args, **kwargs)
        captured_study_result = result[0]
        captured_gate_sets = result[1]
        return result

    monkeypatch.setattr(httpx, "Client", network_forbidden)
    monkeypatch.setattr(httpx, "stream", network_forbidden)
    monkeypatch.setattr(demo_module, "run_blinded_study", capture_study)
    monkeypatch.setattr(
        cli,
        "run_offline_demo",
        lambda output: run_offline_demo(output, events_per_source=120),
    )
    monkeypatch.chdir(ROOT)

    output = tmp_path / "demo"
    assert cli.main(["demo", "run", "--output", str(output)]) == 0

    summary = json.loads((output / "demo-summary.json").read_text(encoding="utf-8"))
    assert isinstance(summary, dict)
    validate_document(summary, "demo-summary")
    assert summary["mode"] == "synthetic-demo"
    assert summary["formal_eligible"] is False
    assert summary["blinded"] is True
    assert summary["data_summary"]["data_target_rows"] == 0
    assert summary["data_summary"]["data_training_weight_rows"] == 0
    assert summary["data_summary"]["data_signal_window_rows"] == 0
    assert set(summary["models"]) == set(MODEL_ROLES)
    for name, role in MODEL_ROLES.items():
        model = summary["models"][name]
        assert model["role"] == role
        assert tuple(model["seeds"]) == FORMAL_SEEDS
        assert math.isfinite(float(model["metrics"]["weighted_roc_auc"]))
        assert isinstance(model["gates"]["all_passed"], bool)

    _assert_primary_comparison_contract(summary)
    assert summary["runtime"]["xgboost_device"] == "cpu"
    assert summary["runtime"]["tree_method"] == "hist"

    assert study_call_count == 1
    assert captured_study_result is not None
    assert captured_gate_sets is not None
    assert set(captured_study_result["models"]) == set(MODEL_ROLES)
    labels = {*(f"seed-{seed}" for seed in FORMAL_SEEDS), "ensemble"}
    for name in MODEL_ROLES:
        runs = captured_study_result["models"][name]["runs"]
        assert set(runs) == labels
        for run in runs.values():
            diagnostic = run["raw_score_shape_diagnostics"]
            assert set(diagnostic) == {
                "comparison",
                "weighting",
                "signal_weighted_ks",
                "background_weighted_ks",
            }
            assert diagnostic["comparison"] == "train-vs-test"
            assert diagnostic["weighting"] == "absolute-w_yield"
            for key in ("signal_weighted_ks", "background_weighted_ks"):
                value = diagnostic[key]
                assert value is None or (math.isfinite(float(value)) and 0.0 <= value <= 1.0)
    assert all(
        "raw_score_shape_diagnostics" not in record for record in captured_gate_sets.values()
    )
    assert all(
        "raw_score_shape_diagnostics" not in reason
        for reason in captured_study_result["blocking_reasons"]
    )

    formal = load_config(ROOT / "configs" / "analysis-v1.yaml", "analysis")
    assert formal["models"]["xgboost"]["device"] == "cuda"
    assert formal["models"]["xgboost"]["tree_method"] == "hist"

    report = output / "report.md"
    assert report.stat().st_size > 0
    assert "SYNTHETIC DEMO — NON-FORMAL" in report.read_text(encoding="utf-8")
    for name in ("report.md", *DEMO_FIGURES):
        assert (output / name).stat().st_size > 0
        assert summary["outputs"][name] == sha256_file(output / name)
    assert set(summary["outputs"]) == {"report.md", *DEMO_FIGURES}
    assert {path.name for path in output.iterdir()} == {
        "completion.json",
        "demo-summary.json",
        "report.md",
        *DEMO_FIGURES,
    }
    for name in (
        "freeze-inputs.json",
        "unblinding-authorization.json",
        "workspace.json",
    ):
        assert not (output / name).exists()

    assert (
        cli.main(
            [
                "analysis",
                "freeze",
                "--inputs",
                str(output),
                "--output",
                str(tmp_path / "freeze.json"),
            ]
        )
        == 2
    )
    assert "FREEZE_DEMO" in capsys.readouterr().err
    assert not (tmp_path / "freeze.json").exists()


@pytest.mark.parametrize("argument", ["--unblind", "--model", "--data-url"])
def test_demo_cli_rejects_unsafe_options(argument: str) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["demo", "run", "--output", "demo", argument, "value"])
