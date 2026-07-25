"""Six-channel template construction and pyhf profile-likelihood inference."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyhf  # type: ignore[import-untyped]
from scipy.stats import norm  # type: ignore[import-untyped]

from .contracts import ContractError, sha256_document, validate_document

FINAL_STATES = ("4e", "4mu", "2e2mu")
CATEGORIES = ("low", "high")
CHANNELS = tuple(f"{state}_{category}" for state in FINAL_STATES for category in CATEGORIES)
SAMPLES = ("signal", "irreducible_background", "reducible_background")


def merge_nonpositive_bins(
    edges: Sequence[float],
    yields: Mapping[str, Sequence[float]],
    variances: Mapping[str, Sequence[float]],
) -> tuple[list[float], dict[str, list[float]], dict[str, list[float]]]:
    """Merge a failing bin with its right neighbor, or left at the boundary."""

    merged_edges = [float(value) for value in edges]
    merged_yields = {name: [float(value) for value in values] for name, values in yields.items()}
    merged_variances = {
        name: [float(value) for value in values] for name, values in variances.items()
    }
    lengths = {len(values) for values in merged_yields.values()}
    lengths.update(len(values) for values in merged_variances.values())
    if len(lengths) != 1 or next(iter(lengths), 0) != len(merged_edges) - 1:
        raise ContractError("TEMPLATE_LENGTH", "template arrays and edges are misaligned")
    if set(merged_yields) != set(merged_variances):
        raise ContractError("TEMPLATE_SAMPLES", "yield and variance samples differ")
    while True:
        failing = next(
            (
                index
                for index in range(len(merged_edges) - 1)
                if any(values[index] <= 0 for values in merged_yields.values())
            ),
            None,
        )
        if failing is None:
            return merged_edges, merged_yields, merged_variances
        bins = len(merged_edges) - 1
        if bins == 1:
            raise ContractError(
                "TEMPLATE_NONPOSITIVE", "a sample remains non-positive after all legal merges"
            )
        left = failing if failing < bins - 1 else failing - 1
        right = left + 1
        for sample in merged_yields:
            merged_yields[sample][left] += merged_yields[sample][right]
            merged_variances[sample][left] += merged_variances[sample][right]
            del merged_yields[sample][right]
            del merged_variances[sample][right]
        del merged_edges[right]


def _histogram(
    frame: pd.DataFrame, edges: np.ndarray[Any, np.dtype[np.float64]]
) -> tuple[list[float], list[float]]:
    weights = np.asarray(frame["w_yield"], dtype=np.float64)
    masses = np.asarray(frame["m4l"], dtype=np.float64)
    values = np.histogram(masses, bins=edges, weights=weights)[0]
    variances = np.histogram(masses, bins=edges, weights=weights**2)[0]
    return values.astype(float).tolist(), variances.astype(float).tolist()


def build_templates(
    frame: pd.DataFrame,
    mass_min: float = 105.0,
    mass_max: float = 160.0,
    bin_width: float = 1.0,
    observed: bool = False,
) -> dict[str, dict[str, object]]:
    """Build process-separated templates for three states and two DDT categories."""

    required = {
        "m4l",
        "ddt_score",
        "channel",
        "process_group",
        "is_data",
        "w_yield",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ContractError("TEMPLATE_COLUMNS", f"missing columns: {', '.join(missing)}")
    working = frame.copy()
    working["category"] = np.where(working["ddt_score"].astype(float) < 0.8, "low", "high")
    base_edges = np.arange(mass_min, mass_max + bin_width / 2.0, bin_width)
    templates: dict[str, dict[str, object]] = {}
    for state in FINAL_STATES:
        for category in CATEGORIES:
            channel_name = f"{state}_{category}"
            selected = working[
                (working["channel"] == state) & (working["category"] == category)
            ]
            simulation = selected[~selected["is_data"].astype(bool)]
            yields: dict[str, list[float]] = {}
            variances: dict[str, list[float]] = {}
            for sample in SAMPLES:
                sample_frame = simulation[simulation["process_group"] == sample]
                if sample_frame.empty:
                    raise ContractError(
                        "TEMPLATE_SAMPLE_EMPTY", f"{channel_name} has no {sample} events"
                    )
                yields[sample], variances[sample] = _histogram(sample_frame, base_edges)
            edges, yields, variances = merge_nonpositive_bins(
                base_edges.tolist(), yields, variances
            )
            data = selected[selected["is_data"].astype(bool)]
            if observed:
                if data.empty:
                    raise ContractError(
                        "TEMPLATE_DATA_EMPTY", f"{channel_name} has no observed events"
                    )
                observation = np.histogram(
                    np.asarray(data["m4l"], dtype=np.float64),
                    bins=np.asarray(edges, dtype=np.float64),
                )[0].astype(float)
            else:
                observation = np.asarray(yields["irreducible_background"]) + np.asarray(
                    yields["reducible_background"]
                )
            templates[channel_name] = {
                "edges": edges,
                "yields": yields,
                "variances": variances,
                "observation": observation.tolist(),
            }
    return templates


def _normsys(name: str, uncertainty: float) -> dict[str, object]:
    return {
        "name": name,
        "type": "normsys",
        "data": {"lo": 1.0 - uncertainty, "hi": 1.0 + uncertainty},
    }


def build_workspace(
    templates: Mapping[str, Mapping[str, object]],
    luminosity_uncertainty: float = 0.021,
    signal_theory_uncertainty: float = 0.05,
    irreducible_uncertainty: float = 0.10,
    reducible_uncertainty: float = 0.50,
) -> dict[str, object]:
    """Build and validate the fixed six-channel HistFactory workspace."""

    channels: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    for channel_name in CHANNELS:
        if channel_name not in templates:
            raise ContractError("WORKSPACE_CHANNEL", f"missing channel {channel_name}")
        channel = templates[channel_name]
        yields = cast(Mapping[str, Sequence[float]], channel["yields"])
        variances = cast(Mapping[str, Sequence[float]], channel["variances"])
        samples: list[dict[str, object]] = []
        for sample_name in SAMPLES:
            modifiers: list[dict[str, object]] = [
                _normsys("lumi", luminosity_uncertainty),
                {
                    "name": f"stat_{channel_name}_{sample_name}",
                    "type": "staterror",
                    "data": np.sqrt(np.asarray(variances[sample_name])).tolist(),
                },
            ]
            if sample_name == "signal":
                modifiers.insert(0, {"name": "mu", "type": "normfactor", "data": None})
                modifiers.append(_normsys("signal_theory", signal_theory_uncertainty))
            elif sample_name == "irreducible_background":
                modifiers.append(_normsys("irreducible_norm", irreducible_uncertainty))
            else:
                modifiers.append(_normsys("reducible_norm", reducible_uncertainty))
            samples.append(
                {
                    "name": sample_name,
                    "data": list(yields[sample_name]),
                    "modifiers": modifiers,
                }
            )
        channels.append({"name": channel_name, "samples": samples})
        observations.append(
            {"name": channel_name, "data": list(cast(Sequence[float], channel["observation"]))}
        )
    workspace: dict[str, object] = {
        "channels": channels,
        "observations": observations,
        "measurements": [
            {
                "name": "measurement",
                "config": {
                    "poi": "mu",
                    "parameters": [
                        {"name": "mu", "inits": [1.0], "bounds": [[0.0, 10.0]]}
                    ],
                },
            }
        ],
        "version": "1.0.0",
    }
    try:
        pyhf.Workspace(workspace)
    except Exception as exc:
        raise ContractError("WORKSPACE_INVALID", str(exc)) from exc
    return workspace


def _asimov_data(
    model: Any, poi_value: float
) -> tuple[np.ndarray[Any, np.dtype[np.float64]], list[float]]:
    parameters = list(model.config.suggested_init())
    parameters[model.config.poi_index] = poi_value
    data = np.asarray(model.expected_data(parameters), dtype=np.float64)
    return data, parameters


def _twice_nll_at_poi(poi: float, data: np.ndarray[Any, np.dtype[np.float64]], model: Any) -> float:
    _, value = pyhf.infer.mle.fixed_poi_fit(
        poi, data, model, return_fitted_val=True
    )
    return float(np.asarray(value).reshape(-1)[0])


def _profile_sigma(
    mu_hat: float,
    minimum_nll: float,
    data: np.ndarray[Any, np.dtype[np.float64]],
    model: Any,
) -> float:
    step = max(0.02, 0.05 * max(1.0, abs(mu_hat)))
    right_nll = _twice_nll_at_poi(mu_hat + step, data, model)
    delta = right_nll - minimum_nll
    if not np.isfinite(delta) or delta <= 0:
        raise ContractError("FIT_CURVATURE", "profile likelihood has non-positive curvature")
    return float(step / np.sqrt(delta))


def fit_workspace(
    workspace_spec: Mapping[str, object],
    mode: str = "expected",
    freeze_sha256: str | None = None,
) -> dict[str, object]:
    """Fit a signal-plus-background Asimov dataset and report expected sensitivity."""

    if mode not in {"expected", "observed"}:
        raise ContractError("FIT_MODE", f"unsupported fit mode: {mode}")
    workspace = pyhf.Workspace(dict(workspace_spec))
    model = workspace.model()
    if mode == "expected":
        data, _ = _asimov_data(model, 1.0)
    else:
        if freeze_sha256 is None:
            raise ContractError("FIT_FREEZE", "observed fit requires a freeze hash")
        data = np.asarray(workspace.data(model), dtype=np.float64)
    fitted, minimum = pyhf.infer.mle.fit(data, model, return_fitted_val=True)
    parameters = np.asarray(fitted, dtype=np.float64)
    mu_hat = float(parameters[model.config.poi_index])
    minimum_nll = float(np.asarray(minimum).reshape(-1)[0])
    sigma = _profile_sigma(mu_hat, minimum_nll, data, model)
    p_value = float(
        np.asarray(pyhf.infer.hypotest(0.0, data, model, test_stat="q0")).reshape(-1)[0]
    )
    significance = float(norm.isf(max(p_value, np.finfo(float).tiny)))
    result: dict[str, object] = {
        "schema_version": "2.0.0",
        "fit_id": f"{mode}-{sha256_document(workspace_spec)[:12]}",
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace_sha256": sha256_document(workspace_spec),
        "channels": list(CHANNELS),
        "mu_hat": mu_hat,
        "mu_interval": [max(0.0, mu_hat - sigma), mu_hat + sigma],
        "significance": significance,
        "status": "completed",
    }
    if freeze_sha256 is not None:
        result["freeze_sha256"] = freeze_sha256
    validate_document(result, "fit-result")
    return result


def spurious_signal_sigma(workspace_spec: Mapping[str, object]) -> float:
    """Fit background-only Asimov data and express fitted signal in sigma units."""

    workspace = pyhf.Workspace(deepcopy(dict(workspace_spec)))
    model = workspace.model()
    data, _ = _asimov_data(model, 0.0)
    fitted, minimum = pyhf.infer.mle.fit(data, model, return_fitted_val=True)
    mu_hat = float(np.asarray(fitted)[model.config.poi_index])
    minimum_nll = float(np.asarray(minimum).reshape(-1)[0])
    sigma = _profile_sigma(mu_hat, minimum_nll, data, model)
    return abs(mu_hat) / sigma
