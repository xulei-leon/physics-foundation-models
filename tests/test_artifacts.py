from __future__ import annotations

from pathlib import Path

import pytest

from particleml.artifacts import IntegrityError, publish_artifact, verify_artifact

ZERO_HASH = "0" * 64


def test_atomic_publication_and_payload_verification(tmp_path: Path) -> None:
    final = tmp_path / "artifact"

    def writer(partial: Path) -> None:
        (partial / "payload.txt").write_text("science\n", encoding="utf-8")

    artifact = publish_artifact(
        final, writer, lambda _: None, {"input": ZERO_HASH}, ZERO_HASH, "test"
    )
    assert artifact.path == final
    assert verify_artifact(final).sha256 == artifact.sha256


def test_failed_validation_leaves_no_output(tmp_path: Path) -> None:
    final = tmp_path / "artifact"

    def writer(partial: Path) -> None:
        (partial / "payload.txt").write_text("invalid\n", encoding="utf-8")

    def validator(_: Path) -> None:
        raise ValueError("rejected")

    with pytest.raises(ValueError, match="rejected"):
        publish_artifact(final, writer, validator, {"input": ZERO_HASH}, ZERO_HASH, "test")
    assert not final.exists()
    assert not list(tmp_path.glob("*.partial.*"))


def test_formal_output_is_never_overwritten(tmp_path: Path) -> None:
    final = tmp_path / "artifact"
    final.mkdir()
    with pytest.raises(IntegrityError, match="ARTIFACT_EXISTS"):
        publish_artifact(final, lambda _: None, lambda _: None, {}, ZERO_HASH, "test")
