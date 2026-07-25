"""Blinded report generation from retained machine-readable artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import Artifact, publish_artifact
from .contracts import ContractError, canonical_json_bytes


def _number(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    return "not produced" if value is None else f"{float(value):.6g}"


def build_blinded_report(
    final: Path,
    metrics: Mapping[str, Any],
    fit_result: Mapping[str, Any],
    gates: Mapping[str, Any],
    input_hashes: Mapping[str, str],
    config_sha256: str,
) -> Artifact:
    """Publish a report that never includes observed signal-window results."""

    if fit_result.get("mode") != "expected":
        raise ContractError("REPORT_BLINDING", "migration report requires an expected fit")

    def writer(partial: Path) -> None:
        passed = gates.get("all_passed") is True
        lines = [
            "# particleML Blinded Analysis Report",
            "",
            "**Scope:** ATLAS education release; not an experiment-grade measurement.",
            "",
            "**Observed signal window:** BLINDED",
            "",
            "## Classification metrics",
            "",
            f"- Weighted ROC-AUC: {_number(metrics, 'weighted_roc_auc')}",
            f"- Weighted PR-AUC: {_number(metrics, 'weighted_pr_auc')}",
            "- Raw scores are reported only for ML diagnostics.",
            "",
            "## Expected profile-likelihood result",
            "",
            f"- Expected significance: {_number(fit_result, 'significance')}",
            f"- Asimov mu-hat: {_number(fit_result, 'mu_hat')}",
            "",
            "## Freeze readiness",
            "",
            f"- All decorrelation gates passed: {'yes' if passed else 'no'}",
            "- This report does not create a freeze or authorize an observed fit.",
            "",
            "## Evidence",
            "",
        ]
        lines.extend(f"- `{name}`: `{digest}`" for name, digest in sorted(input_hashes.items()))
        (partial / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        evidence = {
            "schema_version": "2.0.0",
            "blinded": True,
            "metrics": dict(metrics),
            "fit_result": dict(fit_result),
            "gates": dict(gates),
            "input_hashes": dict(sorted(input_hashes.items())),
        }
        (partial / "report-evidence.json").write_bytes(canonical_json_bytes(evidence))

    def validator(partial: Path) -> None:
        report = (partial / "report.md").read_text(encoding="utf-8")
        evidence = json.loads((partial / "report-evidence.json").read_text(encoding="utf-8"))
        if "Observed signal window:** BLINDED" not in report:
            raise ContractError("REPORT_BLINDING", "report is missing the blinding statement")
        if evidence.get("blinded") is not True:
            raise ContractError("REPORT_BLINDING", "report evidence is not marked blinded")

    return publish_artifact(
        final,
        writer,
        validator,
        input_hashes,
        config_sha256,
        "particleml-0.2.0",
    )
