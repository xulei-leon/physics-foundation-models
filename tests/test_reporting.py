from __future__ import annotations

from pathlib import Path

import pytest

from particleml.contracts import ContractError
from particleml.reporting import build_blinded_report

ZERO_HASH = "0" * 64


def test_report_is_blinded_and_artifact_derived(tmp_path: Path) -> None:
    artifact = build_blinded_report(
        tmp_path / "report",
        {"weighted_roc_auc": 0.8, "weighted_pr_auc": 0.5},
        {"mode": "expected", "significance": 2.0, "mu_hat": 1.0},
        {"all_passed": False},
        {"fit": ZERO_HASH},
        ZERO_HASH,
    )
    text = (artifact.path / "report.md").read_text(encoding="utf-8")
    assert "Observed signal window:** BLINDED" in text
    assert "does not create a freeze" in text


def test_observed_result_cannot_enter_migration_report(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="REPORT_BLINDING"):
        build_blinded_report(
            tmp_path / "report",
            {},
            {"mode": "observed"},
            {},
            {},
            ZERO_HASH,
        )
