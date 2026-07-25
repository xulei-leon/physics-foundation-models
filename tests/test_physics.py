from __future__ import annotations

import math

import pytest

from particleml.physics import (
    FourVector,
    Lepton,
    Selection,
    delta_phi,
    pair_four_leptons,
    select_four_lepton_event,
)


def _lepton(
    index: int,
    pt: float,
    phi: float,
    charge: int,
    flavor: int,
    eta: float = 0.0,
) -> Lepton:
    return Lepton(index, pt, eta, phi, pt * math.cosh(eta), charge, flavor, True, True, True)


def golden_leptons() -> list[Lepton]:
    return [
        _lepton(0, 40.0, 0.0, 1, 11),
        _lepton(1, 40.0, math.pi, -1, 11),
        _lepton(2, 22.5, math.pi / 2, 1, 13),
        _lepton(3, 22.5, -math.pi / 2, -1, 13),
    ]


def test_known_four_vectors_give_golden_masses() -> None:
    result = select_four_lepton_event(golden_leptons(), {"trigE": True})
    assert result is not None
    assert result["m4l"] == pytest.approx(125.0)
    assert result["m_z1"] == pytest.approx(80.0)
    assert result["m_z2"] == pytest.approx(45.0)
    assert result["channel"] == "2e2mu"


@pytest.mark.parametrize(
    ("flavors", "expected"),
    [((11, 11, 11, 11), "4e"), ((13, 13, 13, 13), "4mu")],
)
def test_same_flavor_channels_and_ambiguous_pairing_are_deterministic(
    flavors: tuple[int, int, int, int], expected: str
) -> None:
    leptons = [
        _lepton(0, 40.0, 0.0, 1, flavors[0]),
        _lepton(1, 40.0, math.pi, -1, flavors[1]),
        _lepton(2, 22.5, math.pi / 2, 1, flavors[2]),
        _lepton(3, 22.5, -math.pi / 2, -1, flavors[3]),
    ]
    first = pair_four_leptons(leptons)
    second = pair_four_leptons(list(reversed(leptons)))
    assert first == second
    result = select_four_lepton_event(leptons, {"trigM": True})
    assert result is not None
    assert result["channel"] == expected


def test_phi_wrap_and_mass_roundoff() -> None:
    assert delta_phi(-math.pi + 0.1, math.pi - 0.1) == pytest.approx(0.2)
    vector = FourVector(1.0, 0.0, 0.0, 1.0 - 1e-12)
    assert vector.mass == pytest.approx(0.0)


def test_trigger_id_isolation_and_strict_pt_boundaries() -> None:
    leptons = golden_leptons()
    assert select_four_lepton_event(leptons, {}) is None
    failed_id = list(leptons)
    failed_id[0] = Lepton(**{**failed_id[0].__dict__, "tight_id": False})
    assert select_four_lepton_event(failed_id, {"trigE": True}) is None
    boundary = list(leptons)
    boundary[3] = _lepton(3, 7.0, -math.pi / 2, -1, 13)
    assert select_four_lepton_event(boundary, {"trigE": True}) is None


def test_analysis_upper_boundary_is_exclusive() -> None:
    selection = Selection(analysis_min_gev=125.0, analysis_max_gev=125.0)
    assert select_four_lepton_event(golden_leptons(), {"trigE": True}, selection) is None
