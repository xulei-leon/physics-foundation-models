"""Four-lepton kinematics, deterministic SFOS pairing, and fixed selection."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .contracts import ContractError

Z_MASS_GEV = 91.1876


class PhysicsError(ValueError):
    """Raised when an event has inconsistent physical inputs."""


@dataclass(frozen=True)
class FourVector:
    """Cartesian four-vector in GeV."""

    px: float
    py: float
    pz: float
    energy: float

    @classmethod
    def from_pt_eta_phi_energy(
        cls, pt: float, eta: float, phi: float, energy: float
    ) -> FourVector:
        if not all(math.isfinite(value) for value in (pt, eta, phi, energy)):
            raise PhysicsError("non-finite four-vector component")
        if pt < 0 or energy < 0:
            raise PhysicsError("negative transverse momentum or energy")
        return cls(pt * math.cos(phi), pt * math.sin(phi), pt * math.sinh(eta), energy)

    def __add__(self, other: FourVector) -> FourVector:
        return FourVector(
            self.px + other.px,
            self.py + other.py,
            self.pz + other.pz,
            self.energy + other.energy,
        )

    @property
    def pt(self) -> float:
        return math.hypot(self.px, self.py)

    @property
    def mass(self) -> float:
        mass_squared = self.energy**2 - self.px**2 - self.py**2 - self.pz**2
        if mass_squared < -1e-7:
            raise PhysicsError(f"unphysical four-vector mass squared: {mass_squared}")
        return math.sqrt(max(0.0, mass_squared))

    @property
    def spatial(self) -> tuple[float, float, float]:
        return (self.px, self.py, self.pz)

    def boost_to_frame(self, beta: tuple[float, float, float]) -> FourVector:
        """Lorentz-transform into a frame moving with velocity beta."""

        beta_squared = _dot(beta, beta)
        if beta_squared >= 1.0:
            raise PhysicsError("Lorentz boost velocity is not subluminal")
        if beta_squared == 0:
            return self
        gamma = 1.0 / math.sqrt(1.0 - beta_squared)
        beta_dot_p = _dot(beta, self.spatial)
        factor = (gamma - 1.0) * beta_dot_p / beta_squared - gamma * self.energy
        return FourVector(
            self.px + factor * beta[0],
            self.py + factor * beta[1],
            self.pz + factor * beta[2],
            gamma * (self.energy - beta_dot_p),
        )


@dataclass(frozen=True)
class Lepton:
    """Selected electron or muon candidate."""

    index: int
    pt: float
    eta: float
    phi: float
    energy: float
    charge: int
    flavor: int
    tight_id: bool
    loose_iso: bool
    trigger_matched: bool

    @property
    def vector(self) -> FourVector:
        return FourVector.from_pt_eta_phi_energy(self.pt, self.eta, self.phi, self.energy)


@dataclass(frozen=True)
class Pair:
    """One same-flavour opposite-sign dilepton candidate."""

    indices: tuple[int, int]
    mass: float


@dataclass(frozen=True)
class Pairing:
    """Deterministically ordered Z1 and Z2 candidates."""

    z1: Pair
    z2: Pair


@dataclass(frozen=True)
class Selection:
    """Fixed v1 selection thresholds."""

    ordered_pt_min_gev: tuple[float, float, float, float] = (20.0, 15.0, 10.0, 7.0)
    electron_abs_eta_max: float = 2.47
    muon_abs_eta_max: float = 2.7
    z1_min_gev: float = 50.0
    z1_max_gev: float = 106.0
    z2_min_gev: float = 12.0
    z2_max_gev: float = 115.0
    sfos_min_gev: float = 5.0
    analysis_min_gev: float = 105.0
    analysis_max_gev: float = 160.0
    z_mass_gev: float = Z_MASS_GEV


def delta_phi(left: float, right: float) -> float:
    """Return the signed wrapped azimuthal difference in [-pi, pi)."""

    return (left - right + math.pi) % (2.0 * math.pi) - math.pi


def delta_r(left: Lepton, right: Lepton) -> float:
    """Compute angular distance."""

    return math.hypot(left.eta - right.eta, delta_phi(left.phi, right.phi))


def _is_sfos(left: Lepton, right: Lepton) -> bool:
    return abs(left.flavor) == abs(right.flavor) and left.charge * right.charge == -1


def _pair(left: Lepton, right: Lepton) -> Pair:
    low, high = sorted((left.index, right.index))
    indices = (low, high)
    return Pair(indices, (left.vector + right.vector).mass)


def all_sfos_pairs(leptons: Sequence[Lepton]) -> tuple[Pair, ...]:
    """Return all SFOS pairs in lexicographic index order."""

    pairs = [
        _pair(left, right)
        for left, right in itertools.combinations(leptons, 2)
        if _is_sfos(left, right)
    ]
    return tuple(sorted(pairs, key=lambda candidate: candidate.indices))


def pair_four_leptons(
    leptons: Sequence[Lepton], z_mass_gev: float = Z_MASS_GEV
) -> Pairing:
    """Choose two disjoint SFOS pairs with a deterministic Z1 tie-break."""

    if len(leptons) != 4:
        raise PhysicsError("pairing requires exactly four leptons")
    by_index = {lepton.index: lepton for lepton in leptons}
    if len(by_index) != 4:
        raise PhysicsError("lepton indices must be unique")
    candidates: list[Pairing] = []
    seen_partitions: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for first in all_sfos_pairs(leptons):
        remaining = sorted(set(by_index) - set(first.indices))
        if len(remaining) != 2:
            continue
        second_left, second_right = (by_index[index] for index in remaining)
        if not _is_sfos(second_left, second_right):
            continue
        second = _pair(second_left, second_right)
        ordered_pairs = sorted((first.indices, second.indices))
        partition = (ordered_pairs[0], ordered_pairs[1])
        if partition in seen_partitions:
            continue
        seen_partitions.add(partition)
        ordered = sorted(
            (first, second),
            key=lambda pair: (abs(pair.mass - z_mass_gev), pair.indices),
        )
        candidates.append(Pairing(ordered[0], ordered[1]))
    if not candidates:
        raise PhysicsError("no disjoint SFOS pairing")
    return min(
        candidates,
        key=lambda item: (
            abs(item.z1.mass - z_mass_gev),
            item.z1.indices,
            item.z2.indices,
        ),
    )


def final_state(leptons: Sequence[Lepton]) -> str:
    """Return the three-channel final-state label."""

    electrons = sum(abs(lepton.flavor) == 11 for lepton in leptons)
    muons = sum(abs(lepton.flavor) == 13 for lepton in leptons)
    if electrons == 4:
        return "4e"
    if muons == 4:
        return "4mu"
    if electrons == 2 and muons == 2:
        return "2e2mu"
    raise PhysicsError("only 4e, 4mu, and 2e2mu final states are allowed")


def _sum_vectors(vectors: Iterable[FourVector]) -> FourVector:
    total = FourVector(0.0, 0.0, 0.0, 0.0)
    for vector in vectors:
        total = total + vector
    return total


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _cross(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    magnitude = _norm(vector)
    if magnitude == 0:
        return (0.0, 0.0, 0.0)
    return (
        vector[0] / magnitude,
        vector[1] / magnitude,
        vector[2] / magnitude,
    )


def _divide_vector(
    vector: tuple[float, float, float], denominator: float
) -> tuple[float, float, float]:
    return (
        vector[0] / denominator,
        vector[1] / denominator,
        vector[2] / denominator,
    )


def _negate_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return (-vector[0], -vector[1], -vector[2])


def _signed_plane_angle(
    left_normal: tuple[float, float, float],
    right_normal: tuple[float, float, float],
    axis: tuple[float, float, float],
) -> float:
    left = _unit(left_normal)
    right = _unit(right_normal)
    if _norm(left) == 0 or _norm(right) == 0:
        return 0.0
    return math.atan2(_dot(axis, _cross(left, right)), _dot(left, right))


def decay_angles(leptons: Sequence[Lepton], pairing: Pairing) -> dict[str, float]:
    """Compute a deterministic five-angle H-to-ZZ parameterization."""

    by_index = {lepton.index: lepton for lepton in leptons}
    z1_leptons = sorted(
        (by_index[index] for index in pairing.z1.indices),
        key=lambda lepton: (lepton.charge != -1, lepton.index),
    )
    z2_leptons = sorted(
        (by_index[index] for index in pairing.z2.indices),
        key=lambda lepton: (lepton.charge != -1, lepton.index),
    )
    z1 = _sum_vectors(lepton.vector for lepton in z1_leptons)
    z2 = _sum_vectors(lepton.vector for lepton in z2_leptons)
    higgs = z1 + z2
    if higgs.energy <= 0 or z1.energy <= 0 or z2.energy <= 0:
        raise PhysicsError("decay-angle boost requires positive energy")
    beta_h = _divide_vector(higgs.spatial, higgs.energy)
    h_leptons = [lepton.vector.boost_to_frame(beta_h) for lepton in z1_leptons + z2_leptons]
    z1_h = h_leptons[0] + h_leptons[1]
    z1_axis = _unit(z1_h.spatial)
    costheta_star = max(-1.0, min(1.0, z1_axis[2]))

    beta_z1 = _divide_vector(z1.spatial, z1.energy)
    beta_z2 = _divide_vector(z2.spatial, z2.energy)
    l1_z1 = z1_leptons[0].vector.boost_to_frame(beta_z1)
    other_z1 = z2.boost_to_frame(beta_z1)
    l2_z2 = z2_leptons[0].vector.boost_to_frame(beta_z2)
    other_z2 = z1.boost_to_frame(beta_z2)
    costheta1 = _dot(_unit(l1_z1.spatial), _unit(_negate_vector(other_z1.spatial)))
    costheta2 = _dot(_unit(l2_z2.spatial), _unit(_negate_vector(other_z2.spatial)))

    plane1 = _cross(h_leptons[0].spatial, h_leptons[1].spatial)
    plane2 = _cross(h_leptons[2].spatial, h_leptons[3].spatial)
    phi = _signed_plane_angle(plane1, plane2, z1_axis)
    production_plane = _cross((0.0, 0.0, 1.0), z1_axis)
    phi1 = _signed_plane_angle(production_plane, plane1, z1_axis)
    return {
        "costheta_star": costheta_star,
        "costheta1": max(-1.0, min(1.0, costheta1)),
        "costheta2": max(-1.0, min(1.0, costheta2)),
        "phi": phi,
        "phi1": phi1,
    }


def selection_from_config(config: Mapping[str, object]) -> Selection:
    """Construct selection thresholds from the strict analysis config."""

    selection = config["selection"]
    blinding = config["blinding"]
    if not isinstance(selection, Mapping) or not isinstance(blinding, Mapping):
        raise ContractError("CONFIG_SELECTION", "selection and blinding must be mappings")
    ordered = selection["ordered_pt_min_gev"]
    if not isinstance(ordered, list) or len(ordered) != 4:
        raise ContractError("CONFIG_SELECTION", "ordered_pt_min_gev must have four values")
    return Selection(
        ordered_pt_min_gev=tuple(float(value) for value in ordered),  # type: ignore[arg-type]
        electron_abs_eta_max=float(selection["electron_abs_eta_max"]),
        muon_abs_eta_max=float(selection["muon_abs_eta_max"]),
        z1_min_gev=float(selection["z1_min_gev"]),
        z1_max_gev=float(selection["z1_max_gev"]),
        z2_min_gev=float(selection["z2_min_gev"]),
        z2_max_gev=float(selection["z2_max_gev"]),
        sfos_min_gev=float(selection["sfos_min_gev"]),
        analysis_min_gev=float(blinding["analysis_min_gev"]),
        analysis_max_gev=float(blinding["analysis_max_gev"]),
        z_mass_gev=float(selection["z_mass_gev"]),
    )


def select_four_lepton_event(
    leptons: Sequence[Lepton],
    trigger_flags: Mapping[str, bool],
    selection: Selection = Selection(),
) -> dict[str, object] | None:
    """Apply fixed preselection and return selected event kinematics."""

    if len(leptons) != 4:
        return None
    ordered = sorted(leptons, key=lambda lepton: (-lepton.pt, lepton.index))
    if any(
        lepton.pt <= threshold
        for lepton, threshold in zip(ordered, selection.ordered_pt_min_gev, strict=True)
    ):
        return None
    for lepton in ordered:
        limit = (
            selection.electron_abs_eta_max
            if abs(lepton.flavor) == 11
            else selection.muon_abs_eta_max
            if abs(lepton.flavor) == 13
            else None
        )
        if limit is None or abs(lepton.eta) >= limit:
            return None
        if not lepton.tight_id or not lepton.loose_iso:
            return None
    if sum(lepton.charge for lepton in ordered) != 0:
        return None
    if not any(lepton.trigger_matched for lepton in ordered):
        return None
    trigger_names = ("trigE", "trigM", "trigDE", "trigDM", "trigML")
    if not any(bool(trigger_flags.get(name, False)) for name in trigger_names):
        return None
    try:
        pairing = pair_four_leptons(ordered, selection.z_mass_gev)
    except PhysicsError:
        return None
    if any(pair.mass <= selection.sfos_min_gev for pair in all_sfos_pairs(ordered)):
        return None
    if not selection.z1_min_gev < pairing.z1.mass < selection.z1_max_gev:
        return None
    if not selection.z2_min_gev < pairing.z2.mass < selection.z2_max_gev:
        return None
    four_lepton = _sum_vectors(lepton.vector for lepton in ordered)
    m4l = four_lepton.mass
    if not selection.analysis_min_gev <= m4l < selection.analysis_max_gev:
        return None
    by_index = {lepton.index: lepton for lepton in ordered}
    z1_leptons = [by_index[index] for index in pairing.z1.indices]
    z2_leptons = [by_index[index] for index in pairing.z2.indices]
    angles = decay_angles(ordered, pairing)
    return {
        **angles,
        "channel": final_state(ordered),
        "m4l": m4l,
        "m_z1": pairing.z1.mass,
        "m_z2": pairing.z2.mass,
        "h_pt": four_lepton.pt,
        "z1_indices": list(pairing.z1.indices),
        "z2_indices": list(pairing.z2.indices),
        "lep_pt": [lepton.pt for lepton in ordered],
        "lep_eta": [lepton.eta for lepton in ordered],
        "lep_phi": [lepton.phi for lepton in ordered],
        "lep_energy": [lepton.energy for lepton in ordered],
        "lep_charge": [lepton.charge for lepton in ordered],
        "lep_flavor": [lepton.flavor for lepton in ordered],
        "z1_delta_eta": z1_leptons[0].eta - z1_leptons[1].eta,
        "z1_delta_phi": delta_phi(z1_leptons[0].phi, z1_leptons[1].phi),
        "z1_delta_r": delta_r(z1_leptons[0], z1_leptons[1]),
        "z2_delta_eta": z2_leptons[0].eta - z2_leptons[1].eta,
        "z2_delta_phi": delta_phi(z2_leptons[0].phi, z2_leptons[1].phi),
        "z2_delta_r": delta_r(z2_leptons[0], z2_leptons[1]),
    }
