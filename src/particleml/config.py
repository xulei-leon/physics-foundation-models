"""Strict versioned YAML configuration loading."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .contracts import SCHEMA_VERSION, ContractError, sha256_document

Spec = Mapping[str, object]

ANALYSIS_SPEC: dict[str, object] = {
    "schema_version": None,
    "analysis_id": None,
    "research_plan_version": None,
    "luminosity_pb": None,
    "blinding": {
        "analysis_min_gev": None,
        "analysis_max_gev": None,
        "signal_min_gev": None,
        "signal_max_gev": None,
        "persistence_mode": None,
    },
    "selection": {
        "lepton_count": None,
        "ordered_pt_min_gev": None,
        "electron_abs_eta_max": None,
        "muon_abs_eta_max": None,
        "z1_min_gev": None,
        "z1_max_gev": None,
        "z2_min_gev": None,
        "z2_max_gev": None,
        "sfos_min_gev": None,
        "z_mass_gev": None,
    },
    "split": {
        "algorithm": None,
        "train": None,
        "calibration": None,
        "validation": None,
        "test": None,
    },
    "models": {
        "formal_seeds": None,
        "tuning_seed": None,
        "tuning": {
            "metric": None,
            "tie_tolerance": None,
            "logistic_c": None,
            "xgboost_n_estimators": None,
            "xgboost_max_depth": None,
            "xgboost_learning_rate": None,
            "mlp_hidden_layer_sizes": None,
            "mlp_alpha": None,
        },
        "logistic": {"C": None, "max_iter": None},
        "xgboost": {
            "device": None,
            "tree_method": None,
            "n_estimators": None,
            "max_depth": None,
            "learning_rate": None,
            "subsample": None,
            "colsample_bytree": None,
            "reg_lambda": None,
        },
        "mlp": {
            "hidden_layer_sizes": None,
            "alpha": None,
            "max_iter": None,
            "solver": None,
        },
    },
    "features": {"primary": None},
    "ddt": {
        "initial_bin_width_gev": None,
        "minimum_effective_events": None,
        "threshold": None,
        "max_abs_spearman": None,
        "sideband_acceptance_min": None,
        "sideband_acceptance_max": None,
        "max_spurious_signal_sigma": None,
    },
    "fit": {
        "mass_bin_width_gev": None,
        "template_test_fraction": None,
        "template_weight_scale": None,
        "luminosity_uncertainty": None,
        "signal_theory_uncertainty": None,
        "irreducible_background_uncertainty": None,
        "reducible_background_uncertainty": None,
    },
}

CATALOG_SOURCE_SPEC: dict[str, object] = {
    "schema_version": None,
    "catalog_id": None,
    "metadata_table_url": None,
    "download_base_url": None,
    "records": None,
    "transport": {
        "allowed_schemes": None,
        "verify_tls": None,
        "require_sha256": None,
    },
    "samples": {
        "nominal_signal": None,
        "generator_variations": None,
        "irreducible_background": None,
        "reducible_background": {
            "zjets": None,
            "ttbar": None,
        },
    },
}


def _strict_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ContractError("CONFIG_OBJECT", f"{label} must be a string-keyed mapping")
    return value


def _validate_keys(data: Mapping[str, Any], spec: Spec, path: str = "$") -> None:
    unknown = sorted(set(data) - set(spec))
    missing = sorted(set(spec) - set(data))
    if unknown:
        raise ContractError("CONFIG_UNKNOWN_KEY", f"{path}: {', '.join(unknown)}")
    if missing:
        raise ContractError("CONFIG_MISSING_KEY", f"{path}: {', '.join(missing)}")
    for key, nested_spec in spec.items():
        if isinstance(nested_spec, dict):
            nested_data = _strict_mapping(data[key], f"{path}.{key}")
            _validate_keys(nested_data, nested_spec, f"{path}.{key}")


def load_config(path: Path, kind: str) -> dict[str, Any]:
    """Load a strict YAML or JSON configuration."""

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError("CONFIG_READ", f"cannot read {path}: {exc}") from exc
    data = _strict_mapping(raw, str(path))
    specs = {"analysis": ANALYSIS_SPEC, "catalog-sources": CATALOG_SOURCE_SPEC}
    if kind not in specs:
        raise ContractError("CONFIG_KIND", f"unknown config kind: {kind}")
    _validate_keys(data, specs[kind])
    if data["schema_version"] != SCHEMA_VERSION:
        raise ContractError(
            "CONFIG_VERSION",
            f"{path} uses {data['schema_version']!r}; expected {SCHEMA_VERSION!r}",
        )
    return data


def config_sha256(config: Mapping[str, Any]) -> str:
    """Hash a parsed configuration independently of YAML formatting."""

    return sha256_document(dict(config))
