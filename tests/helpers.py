from __future__ import annotations

import math

import numpy as np
import pandas as pd


def synthetic_event_frame(size: int = 240) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    splits = ("train", "calibration", "validation", "test")
    for index in range(size):
        target = index % 2
        split = splits[min(index * 4 // size, 3)]
        mass = 106.0 + (index % 53)
        channel = ("4e", "4mu", "2e2mu")[index % 3]
        discriminant = 8.0 if target else -8.0
        rows.append(
            {
                "event_id": f"{index:064x}",
                "dataset_id": f"process-{target}",
                "file_checksum": "a" * 64,
                "entry_index": index,
                "is_data": False,
                "process_group": "signal" if target else "irreducible_background",
                "channel": channel,
                "split": split,
                "target": target,
                "w_yield": 1.0 if index % 7 else -0.2,
                "w_train": 0.5 / (size / 2),
                "m4l": mass,
                "m_z1": 80.0 + 0.2 * discriminant,
                "m_z2": 30.0 + discriminant,
                "h_pt": 20.0 + discriminant,
                "met": 10.0 + 0.5 * discriminant,
                "jet_n": index % 3,
                "leading_jet_pt": 25.0 if index % 3 else 0.0,
                "dijet_mass": 60.0 if index % 3 == 2 else 0.0,
                "lep_pt": [40.0, 30.0, 20.0, 10.0],
                "z1_delta_eta": 0.2 + 0.01 * discriminant,
                "z1_delta_phi": math.pi - 0.1,
                "z1_delta_r": 2.0,
                "z2_delta_eta": -0.3,
                "z2_delta_phi": -math.pi + 0.2,
                "z2_delta_r": 1.5,
                "costheta_star": np.tanh(discriminant / 20.0),
                "costheta1": 0.2,
                "costheta2": -0.4,
                "phi": 0.5,
                "phi1": -0.7,
            }
        )
    return pd.DataFrame(rows)
