from __future__ import annotations

import json
import math
from pathlib import Path

import httpx
import pytest

import particleml.cli as cli
from particleml.config import load_config
from particleml.contracts import sha256_file, validate_document
from particleml.demo import DEMO_FIGURES, _write_synthetic_root, run_offline_demo
from particleml.models import FORMAL_SEEDS, MODEL_ROLES

ROOT = Path(__file__).resolve().parents[1]


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
    def network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline demo attempted an HTTP request")

    monkeypatch.setattr(httpx, "Client", network_forbidden)
    monkeypatch.setattr(httpx, "stream", network_forbidden)
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

    comparison = summary["primary_comparison"]
    assert isinstance(comparison, dict)
    assert all(math.isfinite(float(value)) for value in comparison.values())
    assert summary["runtime"]["xgboost_device"] == "cpu"
    assert summary["runtime"]["tree_method"] == "hist"

    formal = load_config(ROOT / "configs" / "analysis-v1.yaml", "analysis")
    assert formal["models"]["xgboost"]["device"] == "cuda"
    assert formal["models"]["xgboost"]["tree_method"] == "hist"

    report = output / "report.md"
    assert report.stat().st_size > 0
    assert "SYNTHETIC DEMO — NON-FORMAL" in report.read_text(encoding="utf-8")
    for name in ("report.md", *DEMO_FIGURES):
        assert (output / name).stat().st_size > 0
        assert summary["outputs"][name] == sha256_file(output / name)
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
