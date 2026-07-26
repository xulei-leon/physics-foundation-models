"""DDT conditional-CDF calibration and mass-sculpting gates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from scipy.stats import spearmanr  # type: ignore[import-untyped]

from .contracts import ContractError


def effective_count(weights: np.ndarray[Any, np.dtype[np.float64]]) -> float:
    """Return the standard effective sample size for non-negative weights."""

    if np.any(weights < 0) or not np.isfinite(weights).all():
        raise ContractError("DDT_WEIGHT", "DDT weights must be finite and non-negative")
    denominator = float(np.sum(weights**2))
    return 0.0 if denominator == 0 else float(np.sum(weights) ** 2 / denominator)


@dataclass(frozen=True)
class ConditionalCDFBin:
    """One mass interval and its weighted empirical score CDF."""

    channel: str
    low: float
    high: float
    score_knots: np.ndarray[Any, np.dtype[np.float64]]
    cdf_knots: np.ndarray[Any, np.dtype[np.float64]]
    n_eff: float

    def transform(
        self, scores: np.ndarray[Any, np.dtype[np.float64]]
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        return np.asarray(
            np.interp(scores, self.score_knots, self.cdf_knots, left=0.0, right=1.0),
            dtype=np.float64,
        )


@dataclass(frozen=True)
class DDTCalibrator:
    """Channel-conditional empirical CDF with deterministic adaptive mass bins."""

    bins: tuple[ConditionalCDFBin, ...]
    mass_min: float
    mass_max: float
    initial_width: float
    minimum_effective_events: float

    def to_document(self) -> dict[str, object]:
        """Serialize the fitted calibration without executable state."""

        return {
            "schema_version": "2.1.0",
            "mass_min": self.mass_min,
            "mass_max": self.mass_max,
            "initial_width": self.initial_width,
            "minimum_effective_events": self.minimum_effective_events,
            "bins": [
                {
                    "channel": item.channel,
                    "low": item.low,
                    "high": item.high,
                    "score_knots": item.score_knots.tolist(),
                    "cdf_knots": item.cdf_knots.tolist(),
                    "n_eff": item.n_eff,
                }
                for item in self.bins
            ],
        }

    @classmethod
    def from_document(cls, document: dict[str, object]) -> DDTCalibrator:
        """Restore a serialized calibration with structural checks."""

        raw_bins = document.get("bins")
        if document.get("schema_version") != "2.1.0" or not isinstance(raw_bins, list):
            raise ContractError("DDT_DOCUMENT", "invalid DDT calibration document")
        bins: list[ConditionalCDFBin] = []
        for raw in raw_bins:
            if not isinstance(raw, dict):
                raise ContractError("DDT_DOCUMENT", "DDT bin must be an object")
            bins.append(
                ConditionalCDFBin(
                    str(raw["channel"]),
                    float(raw["low"]),
                    float(raw["high"]),
                    np.asarray(raw["score_knots"], dtype=np.float64),
                    np.asarray(raw["cdf_knots"], dtype=np.float64),
                    float(raw["n_eff"]),
                )
            )
        return cls(
            tuple(bins),
            float(cast(Any, document["mass_min"])),
            float(cast(Any, document["mass_max"])),
            float(cast(Any, document["initial_width"])),
            float(cast(Any, document["minimum_effective_events"])),
        )

    @classmethod
    def fit(
        cls,
        scores: np.ndarray[Any, np.dtype[np.float64]],
        masses: np.ndarray[Any, np.dtype[np.float64]],
        channels: np.ndarray[Any, np.dtype[np.str_]],
        weights: np.ndarray[Any, np.dtype[np.float64]],
        mass_min: float = 105.0,
        mass_max: float = 160.0,
        initial_width: float = 5.0,
        minimum_effective_events: float = 200.0,
    ) -> DDTCalibrator:
        """Fit only from caller-supplied calibration-background arrays."""

        if not (len(scores) == len(masses) == len(channels) == len(weights)):
            raise ContractError("DDT_LENGTH", "DDT calibration arrays have different lengths")
        if len(scores) == 0:
            raise ContractError("DDT_EMPTY", "DDT calibration sample is empty")
        if not np.isfinite(scores).all() or not np.isfinite(masses).all():
            raise ContractError("DDT_NONFINITE", "DDT calibration values are not finite")
        if initial_width <= 0 or minimum_effective_events <= 0:
            raise ContractError("DDT_CONFIG", "DDT bin width and n_eff threshold must be positive")
        all_bins: list[ConditionalCDFBin] = []
        for channel in sorted(set(channels.tolist())):
            channel_mask = channels == channel
            all_bins.extend(
                _fit_channel_bins(
                    channel,
                    scores[channel_mask],
                    masses[channel_mask],
                    weights[channel_mask],
                    mass_min,
                    mass_max,
                    initial_width,
                    minimum_effective_events,
                )
            )
        return cls(
            tuple(all_bins),
            mass_min,
            mass_max,
            initial_width,
            minimum_effective_events,
        )

    @classmethod
    def fit_from_frame(
        cls,
        frame: pd.DataFrame,
        minimum_effective_events: float = 200.0,
        initial_width: float = 5.0,
    ) -> DDTCalibrator:
        """Enforce calibration-background simulation provenance before fitting."""

        required = {
            "raw_score",
            "m4l",
            "channel",
            "w_train",
            "split",
            "target",
            "is_data",
        }
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ContractError("DDT_COLUMNS", f"missing columns: {', '.join(missing)}")
        allowed = (
            (~frame["is_data"].astype(bool))
            & (frame["target"] == 0)
            & (frame["split"] == "calibration")
        )
        if not allowed.all():
            raise ContractError(
                "DDT_PROVENANCE",
                "DDT fitting input must contain calibration-background simulation only",
            )
        return cls.fit(
            np.asarray(frame["raw_score"], dtype=np.float64),
            np.asarray(frame["m4l"], dtype=np.float64),
            np.asarray(frame["channel"].astype(str), dtype=np.str_),
            np.asarray(frame["w_train"], dtype=np.float64),
            initial_width=initial_width,
            minimum_effective_events=minimum_effective_events,
        )

    def transform(
        self,
        scores: np.ndarray[Any, np.dtype[np.float64]],
        masses: np.ndarray[Any, np.dtype[np.float64]],
        channels: np.ndarray[Any, np.dtype[np.str_]],
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        """Apply the fitted channel and mass conditional CDF."""

        if not (len(scores) == len(masses) == len(channels)):
            raise ContractError("DDT_LENGTH", "DDT application arrays have different lengths")
        output = np.full(len(scores), np.nan, dtype=np.float64)
        for fitted_bin in self.bins:
            mask = (
                (channels == fitted_bin.channel)
                & (masses >= fitted_bin.low)
                & (masses < fitted_bin.high)
            )
            output[mask] = fitted_bin.transform(scores[mask])
        if np.isnan(output).any():
            raise ContractError("DDT_COVERAGE", "no fitted DDT bin covers one or more events")
        return output


def _empirical_cdf(
    scores: np.ndarray[Any, np.dtype[np.float64]],
    weights: np.ndarray[Any, np.dtype[np.float64]],
) -> tuple[np.ndarray[Any, np.dtype[np.float64]], np.ndarray[Any, np.dtype[np.float64]]]:
    order = np.argsort(scores, kind="mergesort")
    ordered_scores = scores[order]
    ordered_weights = weights[order]
    unique_scores, starts = np.unique(ordered_scores, return_index=True)
    group_weights = np.add.reduceat(ordered_weights, starts)
    total = float(np.sum(group_weights))
    if total <= 0:
        raise ContractError("DDT_WEIGHT", "DDT bin has no positive calibration weight")
    cumulative_before = np.cumsum(group_weights) - group_weights
    midranks = (cumulative_before + 0.5 * group_weights) / total
    return (
        np.asarray(unique_scores, dtype=np.float64),
        np.asarray(midranks, dtype=np.float64),
    )


def _make_bin(
    channel: str,
    low: float,
    high: float,
    scores: np.ndarray[Any, np.dtype[np.float64]],
    masses: np.ndarray[Any, np.dtype[np.float64]],
    weights: np.ndarray[Any, np.dtype[np.float64]],
) -> ConditionalCDFBin:
    mask = (masses >= low) & (masses < high)
    selected_scores = scores[mask]
    selected_weights = weights[mask]
    knots, cdf = _empirical_cdf(selected_scores, selected_weights)
    return ConditionalCDFBin(
        channel,
        low,
        high,
        knots,
        cdf,
        effective_count(selected_weights),
    )


def _fit_channel_bins(
    channel: str,
    scores: np.ndarray[Any, np.dtype[np.float64]],
    masses: np.ndarray[Any, np.dtype[np.float64]],
    weights: np.ndarray[Any, np.dtype[np.float64]],
    mass_min: float,
    mass_max: float,
    width: float,
    minimum_effective_events: float,
) -> list[ConditionalCDFBin]:
    if np.any((masses < mass_min) | (masses >= mass_max)):
        raise ContractError(
            "DDT_MASS_RANGE", f"{channel} calibration mass is outside analysis range"
        )
    edges = np.arange(mass_min, mass_max + width / 2.0, width)
    groups: list[tuple[float, float]] = []
    start = 0
    while start < len(edges) - 1:
        end = start + 1
        while end < len(edges):
            mask = (masses >= edges[start]) & (masses < edges[end])
            if effective_count(weights[mask]) >= minimum_effective_events:
                break
            end += 1
        if end >= len(edges):
            if not groups:
                raise ContractError(
                    "DDT_NEFF",
                    f"{channel} has fewer than {minimum_effective_events} effective events",
                )
            previous_low, _ = groups.pop()
            groups.append((previous_low, mass_max))
            break
        groups.append((float(edges[start]), float(edges[end])))
        start = end
    return [
        _make_bin(channel, low, high, scores, masses, weights) for low, high in groups
    ]


def ddt_category(score: float, threshold: float = 0.8) -> str:
    """Map the DDT score to the fixed low/high category."""

    if not 0.0 <= score <= 1.0:
        raise ContractError("DDT_SCORE_RANGE", "DDT score is outside [0, 1]")
    return "low" if score < threshold else "high"


def spearman_gate(
    scores: np.ndarray[Any, np.dtype[np.float64]],
    masses: np.ndarray[Any, np.dtype[np.float64]],
    maximum_absolute_rho: float = 0.05,
) -> tuple[float | None, bool]:
    """Evaluate the unweighted rank-correlation gate."""

    if len(scores) < 3:
        raise ContractError("DDT_GATE_SAMPLE", "Spearman gate requires at least three events")
    if np.all(scores == scores[0]) or np.all(masses == masses[0]):
        return None, False
    result = spearmanr(scores, masses)
    rho = float(result.statistic)
    if not np.isfinite(rho):
        return None, False
    return rho, abs(rho) < maximum_absolute_rho


def sideband_acceptance_gate(
    frame: pd.DataFrame,
    threshold: float = 0.8,
    minimum: float = 0.15,
    maximum: float = 0.25,
    bin_width: float = 5.0,
    bin_ranges: Sequence[Mapping[str, object]] | None = None,
    analysis_min: float = 105.0,
    analysis_max: float = 160.0,
    signal_min: float = 120.0,
    signal_max: float = 130.0,
) -> tuple[dict[str, float], bool]:
    """Check high-score acceptance in every populated channel/sideband bin."""

    sideband = ((frame["m4l"] >= analysis_min) & (frame["m4l"] < signal_min)) | (
        (frame["m4l"] >= signal_max) & (frame["m4l"] < analysis_max)
    )
    selected = frame.loc[sideband].copy()
    if selected.empty:
        raise ContractError("DDT_GATE_SAMPLE", "sideband acceptance sample is empty")
    acceptances: dict[str, float] = {}
    groups: list[tuple[str, pd.DataFrame]] = []
    if bin_ranges is None:
        selected["mass_bin"] = (
            np.floor((selected["m4l"].astype(float) - analysis_min) / bin_width).astype(
                int
            )
        )
        groups = [
            (f"{channel}:{int(mass_bin)}", group)
            for (channel, mass_bin), group in selected.groupby(
                ["channel", "mass_bin"],
                sort=True,
            )
        ]
    else:
        for item in bin_ranges:
            channel = str(item["channel"])
            low = float(str(item["low"]))
            upper = float(str(item["high"]))
            group = selected[
                (selected["channel"].astype(str) == channel)
                & (selected["m4l"].astype(float) >= low)
                & (selected["m4l"].astype(float) < upper)
            ]
            if not group.empty:
                groups.append((f"{channel}:{low:g}:{upper:g}", group))
    for label, group in groups:
        if "w_yield" in group and not group["is_data"].astype(bool).all():
            weights = np.abs(np.asarray(group["w_yield"], dtype=np.float64))
        else:
            weights = np.ones(len(group), dtype=np.float64)
        total = float(np.sum(weights))
        if total <= 0:
            continue
        high_mask = np.asarray(group["ddt_score"], dtype=np.float64) >= threshold
        acceptance = float(np.sum(weights[high_mask]) / total)
        acceptances[label] = acceptance
    passed = bool(acceptances) and all(
        minimum <= acceptance <= maximum for acceptance in acceptances.values()
    )
    return acceptances, passed


def evaluate_decorrelation_gates(
    background_mc: pd.DataFrame,
    data_sideband: pd.DataFrame,
    spurious_signal_sigma: float,
    maximum_absolute_rho: float = 0.05,
    threshold: float = 0.8,
    acceptance_minimum: float = 0.15,
    acceptance_maximum: float = 0.25,
    maximum_spurious_signal_sigma: float = 0.2,
    bin_ranges: Sequence[Mapping[str, object]] | None = None,
    analysis_min: float = 105.0,
    analysis_max: float = 160.0,
    signal_min: float = 120.0,
    signal_max: float = 130.0,
) -> dict[str, object]:
    """Evaluate every hard gate and return an unblinding-ready record."""

    mc_rho, mc_passed = spearman_gate(
        np.asarray(background_mc["ddt_score"], dtype=np.float64),
        np.asarray(background_mc["m4l"], dtype=np.float64),
        maximum_absolute_rho,
    )
    data_rho, data_passed = spearman_gate(
        np.asarray(data_sideband["ddt_score"], dtype=np.float64),
        np.asarray(data_sideband["m4l"], dtype=np.float64),
        maximum_absolute_rho,
    )
    mc_acceptance, mc_acceptance_passed = sideband_acceptance_gate(
        background_mc,
        threshold=threshold,
        minimum=acceptance_minimum,
        maximum=acceptance_maximum,
        bin_ranges=bin_ranges,
        analysis_min=analysis_min,
        analysis_max=analysis_max,
        signal_min=signal_min,
        signal_max=signal_max,
    )
    data_acceptance, data_acceptance_passed = sideband_acceptance_gate(
        data_sideband,
        threshold=threshold,
        minimum=acceptance_minimum,
        maximum=acceptance_maximum,
        bin_ranges=bin_ranges,
        analysis_min=analysis_min,
        analysis_max=analysis_max,
        signal_min=signal_min,
        signal_max=signal_max,
    )
    spurious_value = abs(spurious_signal_sigma)
    spurious_passed = spurious_value < maximum_spurious_signal_sigma
    return {
        "mc_spearman": {
            "value": mc_rho,
            "maximum_absolute": maximum_absolute_rho,
            "passed": mc_passed,
        },
        "data_sideband_spearman": {
            "value": data_rho,
            "maximum_absolute": maximum_absolute_rho,
            "passed": data_passed,
        },
        "sideband_acceptance": {
            "values": {
                **{f"mc:{key}": value for key, value in mc_acceptance.items()},
                **{f"data:{key}": value for key, value in data_acceptance.items()},
            },
            "minimum": acceptance_minimum,
            "maximum": acceptance_maximum,
            "passed": mc_acceptance_passed and data_acceptance_passed,
        },
        "spurious_signal": {
            "value_sigma": spurious_value,
            "maximum_sigma": maximum_spurious_signal_sigma,
            "passed": spurious_passed,
        },
        "all_passed": (
            mc_passed
            and data_passed
            and mc_acceptance_passed
            and data_acceptance_passed
            and spurious_passed
        ),
    }
