"""Strict yield and training-weight semantics."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any, cast

from .contracts import ContractError

MC_METADATA = (
    "xsec_pb",
    "kfactor",
    "filter_efficiency",
    "sum_of_generator_weights",
    "mcWeight",
    "ScaleFactor_PILEUP",
    "ScaleFactor_ELE",
    "ScaleFactor_MUON",
    "ScaleFactor_LepTRIGGER",
)


def yield_weight(event: Mapping[str, object], luminosity_pb: float) -> float:
    """Compute the signed formal yield weight or fail closed."""

    values: dict[str, float] = {}
    for name in MC_METADATA:
        if name not in event or event[name] is None:
            raise ContractError("WEIGHT_MISSING", f"missing {name}")
        value = float(cast(Any, event[name]))
        if not math.isfinite(value):
            raise ContractError("WEIGHT_NONFINITE", f"{name} is not finite")
        values[name] = value
    if not math.isfinite(luminosity_pb) or luminosity_pb <= 0:
        raise ContractError("WEIGHT_LUMINOSITY", "luminosity must be finite and positive")
    sumw = values["sum_of_generator_weights"]
    if sumw == 0:
        raise ContractError("WEIGHT_SUMW", "sum of generator weights is zero")
    return (
        luminosity_pb
        * values["xsec_pb"]
        * values["kfactor"]
        * values["filter_efficiency"]
        / sumw
        * values["mcWeight"]
        * values["ScaleFactor_PILEUP"]
        * values["ScaleFactor_ELE"]
        * values["ScaleFactor_MUON"]
        * values["ScaleFactor_LepTRIGGER"]
    )


def attach_training_weights(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Normalize absolute signal/background training weight to 0.5 each."""

    output = [dict(row) for row in rows]
    totals: defaultdict[int, float] = defaultdict(float)
    for row in output:
        if bool(row["is_data"]):
            row["target"] = None
            row["w_train"] = None
            continue
        target = int(cast(Any, row["target"]))
        if target not in (0, 1):
            raise ContractError("WEIGHT_TARGET", f"invalid simulation target: {target}")
        weight = float(cast(Any, row["w_yield"]))
        if not math.isfinite(weight):
            raise ContractError("WEIGHT_NONFINITE", "w_yield is not finite")
        if str(row.get("sample_role", "nominal")) != "nominal":
            row["w_train"] = None
            continue
        totals[target] += abs(weight)
    for target in (0, 1):
        if totals[target] <= 0:
            raise ContractError("WEIGHT_CLASS_EMPTY", f"class {target} has no absolute weight")
    for row in output:
        if not bool(row["is_data"]) and str(row.get("sample_role", "nominal")) == "nominal":
            target = int(cast(Any, row["target"]))
            row["w_train"] = abs(float(cast(Any, row["w_yield"]))) * 0.5 / totals[target]
    return output
