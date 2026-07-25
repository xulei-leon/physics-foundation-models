from __future__ import annotations

from pathlib import Path

import pytest

from particleml.config import config_sha256, load_config
from particleml.contracts import ContractError

ROOT = Path(__file__).resolve().parents[1]


def test_analysis_and_catalog_configs_load_strictly() -> None:
    analysis = load_config(ROOT / "configs" / "analysis-v1.yaml", "analysis")
    catalog = load_config(ROOT / "configs" / "catalog-sources.yaml", "catalog-sources")
    assert analysis["schema_version"] == "2.0.0"
    assert catalog["catalog_id"] == "atlas-exactly4lep-2015-2016-v1"
    assert len(config_sha256(analysis)) == 64


def test_unknown_config_key_is_an_error(tmp_path: Path) -> None:
    source = (ROOT / "configs" / "analysis-v1.yaml").read_text(encoding="utf-8")
    path = tmp_path / "bad.yaml"
    path.write_text(source + "\nunknown_key: true\n", encoding="utf-8")
    with pytest.raises(ContractError, match="CONFIG_UNKNOWN_KEY"):
        load_config(path, "analysis")


def test_missing_nested_config_key_is_an_error(tmp_path: Path) -> None:
    source = (ROOT / "configs" / "analysis-v1.yaml").read_text(encoding="utf-8")
    path = tmp_path / "bad.yaml"
    path.write_text(source.replace("  threshold: 0.8\n", ""), encoding="utf-8")
    with pytest.raises(ContractError, match="CONFIG_MISSING_KEY"):
        load_config(path, "analysis")
