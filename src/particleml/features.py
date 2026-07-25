"""Frozen dimensionless feature construction and leakage prevention."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from .contracts import ContractError, model_input_hash, validate_model_input_fields

PRIMARY_FEATURES = (
    "lep1_pt_fraction",
    "lep2_pt_fraction",
    "lep3_pt_fraction",
    "lep4_pt_fraction",
    "z1_delta_eta",
    "z1_delta_phi_sin",
    "z1_delta_phi_cos",
    "z1_delta_r",
    "z2_delta_eta",
    "z2_delta_phi_sin",
    "z2_delta_phi_cos",
    "z2_delta_r",
    "z1_mass_fraction",
    "z2_mass_fraction",
    "h_pt_fraction",
    "met_fraction",
    "jet_n",
    "leading_jet_pt_fraction",
    "dijet_mass_fraction",
    "costheta_star",
    "costheta1",
    "costheta2",
    "phi",
    "phi1",
    "channel_4e",
    "channel_4mu",
    "channel_2e2mu",
)


@dataclass(frozen=True)
class FeatureMatrix:
    """Model-ready values bound to event order and field hash."""

    event_ids: np.ndarray[Any, np.dtype[np.str_]]
    values: np.ndarray[Any, np.dtype[np.float64]]
    fields: tuple[str, ...]
    sha256: str


def _sequence_value(value: object, index: int, label: str) -> float:
    if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != 4:
        raise ContractError("FEATURE_SOURCE", f"{label} must contain four values")
    return float(cast(Any, value[index]))


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive the complete safe primary feature frame."""

    required = {
        "m4l",
        "lep_pt",
        "z1_delta_eta",
        "z1_delta_phi",
        "z1_delta_r",
        "z2_delta_eta",
        "z2_delta_phi",
        "z2_delta_r",
        "m_z1",
        "m_z2",
        "h_pt",
        "met",
        "jet_n",
        "leading_jet_pt",
        "dijet_mass",
        "costheta_star",
        "costheta1",
        "costheta2",
        "phi",
        "phi1",
        "channel",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ContractError("FEATURE_SOURCE", f"missing source columns: {', '.join(missing)}")
    mass = frame["m4l"].astype(float)
    if (mass <= 0).any():
        raise ContractError("FEATURE_MASS", "m4l must be positive for dimensionless ratios")
    output = pd.DataFrame(index=frame.index)
    for index in range(4):
        output[f"lep{index + 1}_pt_fraction"] = [
            _sequence_value(value, index, "lep_pt") / denominator
            for value, denominator in zip(frame["lep_pt"], mass, strict=True)
        ]
    for z in ("z1", "z2"):
        output[f"{z}_delta_eta"] = frame[f"{z}_delta_eta"].astype(float)
        phi = frame[f"{z}_delta_phi"].astype(float)
        output[f"{z}_delta_phi_sin"] = np.sin(phi)
        output[f"{z}_delta_phi_cos"] = np.cos(phi)
        output[f"{z}_delta_r"] = frame[f"{z}_delta_r"].astype(float)
    output["z1_mass_fraction"] = frame["m_z1"].astype(float) / mass
    output["z2_mass_fraction"] = frame["m_z2"].astype(float) / mass
    output["h_pt_fraction"] = frame["h_pt"].astype(float) / mass
    output["met_fraction"] = frame["met"].astype(float) / mass
    output["jet_n"] = frame["jet_n"].astype(float)
    output["leading_jet_pt_fraction"] = frame["leading_jet_pt"].astype(float) / mass
    output["dijet_mass_fraction"] = frame["dijet_mass"].astype(float) / mass
    for angle in ("costheta_star", "costheta1", "costheta2", "phi", "phi1"):
        output[angle] = frame[angle].astype(float)
    for channel in ("4e", "4mu", "2e2mu"):
        output[f"channel_{channel}"] = (frame["channel"] == channel).astype(float)
    return output


def build_feature_matrix(
    frame: pd.DataFrame, fields: tuple[str, ...] = PRIMARY_FEATURES
) -> FeatureMatrix:
    """Validate the field contract, derive values, and bind them to event IDs."""

    normalized = tuple(validate_model_input_fields(fields))
    if "event_id" not in frame.columns:
        raise ContractError("FEATURE_EVENT_ID", "event_id is required for alignment")
    if frame["event_id"].duplicated().any():
        raise ContractError("FEATURE_DUPLICATE", "event_id values must be unique")
    derived = build_feature_frame(frame)
    missing = sorted(set(normalized) - set(derived.columns))
    if missing:
        raise ContractError("FEATURE_UNKNOWN", f"unknown feature fields: {', '.join(missing)}")
    values = np.asarray(derived.loc[:, list(normalized)], dtype=np.float64)
    if not np.isfinite(values).all():
        raise ContractError("FEATURE_NONFINITE", "feature matrix contains non-finite values")
    event_ids = np.asarray(frame["event_id"].astype(str), dtype=np.str_)
    return FeatureMatrix(event_ids, values, normalized, model_input_hash(normalized))


def validate_angle_ranges(feature_frame: pd.DataFrame) -> None:
    """Check standardized decay-angle ranges."""

    for cosine in ("costheta_star", "costheta1", "costheta2"):
        if not feature_frame[cosine].between(-1.0, 1.0).all():
            raise ContractError("FEATURE_ANGLE", f"{cosine} is outside [-1, 1]")
    for angle in ("phi", "phi1"):
        if not all(-math.pi <= float(value) <= math.pi for value in feature_frame[angle]):
            raise ContractError("FEATURE_ANGLE", f"{angle} is outside [-pi, pi]")
