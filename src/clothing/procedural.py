"""Animação procedural por papéis: o jogo cria o andar de um modelo (.glb) a partir de quem é perna, braço, cabeça...

Em vez de um clipe por modelo, diz-se, uma vez, o papel dos ossos (``Roles``, achado sozinho por ``auto_roles`` ou
escrito num JSON) e escolhe-se um perfil de movimento (``bipede``, ``quadrupede``, ``rastejante`` ou ``flutuante``).
O ``ProceduralAnimator`` gera as rotações a cada quadro e o ``Rig`` as transforma nas matrizes de pele.

Eixos do modelo (depois de normalizado): x para o lado, y para cima e z para a frente. As rotações são em volta
desses eixos, então nada depende de como o exportador orientou os ossos.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .rig import Rig, rotation_matrix

PROFILE_NAMES = ("bipede", "quadrupede", "rastejante", "flutuante")
LEFT, RIGHT = 1, -1   # um personagem virado para +z tem o lado esquerdo em +x


class RolesError(ValueError):
    """O arquivo de papéis não bate com o esqueleto do modelo."""


@dataclass
class Limb:
    """Uma perna, um braço ou uma cauda: a cadeia de ossos da raiz do membro até a ponta."""

    chain: List[int]
    side: int = 0        # +1 esquerda (+x), -1 direita (-x), 0 no meio
    end: int = 0         # +1 da frente (+z), -1 de trás (-z), 0 se não importa


@dataclass
class Roles:
    spine: List[int] = field(default_factory=list)     # da raiz até o peito
    head: List[int] = field(default_factory=list)
    legs: List[Limb] = field(default_factory=list)
    arms: List[Limb] = field(default_factory=list)
    tail: List[int] = field(default_factory=list)
    profile: str = "bipede"

    # ---- arquivo
    def to_dict(self, rig: Rig) -> dict:
        name = lambda chain: [rig.names[i] for i in chain]
        limb = lambda l: {"ossos": name(l.chain), "lado": {LEFT: "esq", RIGHT: "dir", 0: "meio"}[l.side],
                          "ponta": {1: "frente", -1: "tras", 0: "nenhuma"}[l.end]}
        return {"perfil": self.profile, "coluna": name(self.spine), "cabeca": name(self.head),
                "pernas": [limb(l) for l in self.legs], "bracos": [limb(l) for l in self.arms],
                "cauda": name(self.tail)}

    @classmethod
    def from_dict(cls, rig: Rig, data: dict) -> "Roles":
        def bones(names, where):
            result = []
            for name in names or []:
                try:
                    result.append(rig.index(name))
                except KeyError as error:
                    raise RolesError(f"{where}: não há um osso chamado '{name}' neste modelo.") from error
            return result

        def limbs(items, where):
            out = []
            for item in items or []:
                names = item["ossos"] if isinstance(item, dict) else item
                side = {"esq": LEFT, "dir": RIGHT}.get(item.get("lado", "meio"), 0) if isinstance(item, dict) else 0
                end = {"frente": 1, "tras": -1}.get(item.get("ponta", "nenhuma"), 0) if isinstance(item, dict) else 0
                chain = bones(names, where)
                if chain:
                    out.append(Limb(chain, side, end))
            return out

        profile = data.get("perfil", "bipede")
        if profile not in PROFILE_NAMES:
            raise RolesError(f"Perfil '{profile}' não existe; use um de: {', '.join(PROFILE_NAMES)}.")
        return cls(spine=bones(data.get("coluna"), "coluna"), head=bones(data.get("cabeca"), "cabeça"),
                   legs=limbs(data.get("pernas"), "pernas"), arms=limbs(data.get("bracos"), "braços"),
                   tail=bones(data.get("cauda"), "cauda"), profile=profile)

    def save(self, rig: Rig, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(rig), handle, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, rig: Rig, path: str) -> "Roles":
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return cls.from_dict(rig, json.load(handle))
        except (OSError, ValueError) as error:
            if isinstance(error, RolesError):
                raise
            raise RolesError(f"Não consegui ler o arquivo de papéis: {error}") from error


# --------------------------------------------------------------------------------------------- detecção
def _subtree(rig: Rig, bone: int) -> int:
    return 1 + sum(_subtree(rig, c) for c in rig.children[bone])


def auto_roles(rig: Rig, height: Optional[float] = None) -> Roles:
    """Acha os papéis pela forma do esqueleto: pernas pendem de ossos baixos e terminam perto do chão, braços saem do
    peito para os lados, a cabeça é o ramo central de cima, a cauda sai para trás. É um palpite; um JSON corrige."""
    positions = rig.rest_positions
    floor = float(positions[:, 1].min())
    top = float(positions[:, 1].max())
    height = float(height) if height else max((top - floor) * 1.15, 1e-6)
    roles = Roles()
    if not len(rig):
        return roles

    def y_of(b):
        return float(positions[b, 1]) - floor

    # o tronco: da raiz até o primeiro osso com mais de um filho
    root = rig.roots[0]
    spine, hub = [root], root
    while len(rig.children[hub]) == 1:
        hub = rig.children[hub][0]
        spine.append(hub)
    legs: List[Limb] = []
    arms: List[Limb] = []
    tail: List[int] = []
    head: List[int] = []

    while len(rig.children[hub]) >= 2:
        kids = sorted(rig.children[hub], key=lambda c: -_subtree(rig, c))
        hub_pos = positions[hub]
        low_hub = y_of(hub) < 0.6 * height
        carry = kids[0] if low_hub else None          # num quadril baixo, o maior ramo continua o tronco
        for kid in kids:
            if kid == carry:
                continue
            chain = rig.chain_from(kid)
            tip = positions[chain[-1]]
            lateral = tip[0] - hub_pos[0]
            behind = hub_pos[2] - tip[2]
            low_tip = (tip[1] - floor) < 0.35 * height
            # a ponta encosta no chão e o ramo não sai do peito de um bicho em pé (um braço comprido também chega ao chão)
            on_floor = (tip[1] - floor) < 0.12 * height and y_of(hub) < 0.72 * height
            if len(chain) >= 2 and (on_floor or (low_hub and low_tip)):
                legs.append(Limb(chain, LEFT if lateral >= 0 else RIGHT, 0))
            elif behind > 0.25 * height and not low_tip:
                tail = tail or chain
            elif not low_hub and abs(lateral) > 0.15 * height and len(chain) >= 2:
                arms.append(Limb(chain, LEFT if lateral >= 0 else RIGHT, 0))
            elif not low_hub and not head:
                head = chain
        if carry is None:
            break
        spine.append(carry)
        hub = carry
        while len(rig.children[hub]) == 1:
            hub = rig.children[hub][0]
            spine.append(hub)

    if not head and len(spine) >= 3:
        head = spine[-2:]
    # frente e trás das pernas, para os quadrúpedes: pela posição em z do início da perna
    if legs:
        middle = float(np.median([positions[l.chain[0], 2] for l in legs]))
        for limb in legs:
            limb.end = 1 if positions[limb.chain[0], 2] > middle + 1e-6 else -1
    roles.spine, roles.head, roles.legs, roles.arms, roles.tail = spine, head, legs, arms, tail
    roles.profile = suggest_profile(roles)
    return roles


def suggest_profile(roles: Roles) -> str:
    count = len(roles.legs)
    if count == 0:
        return "flutuante"
    if count == 2:
        return "bipede"
    if count == 4:
        return "quadrupede"
    return "rastejante" if count >= 5 else "bipede"


# --------------------------------------------------------------------------------------------- movimento
@dataclass
class _Pose:
    """As rotações e o deslocamento do corpo que um perfil produz em um instante."""

    rig: Rig
    rotations: np.ndarray
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def turn(self, bone: int, axis: Sequence[float], angle: float) -> None:
        if abs(angle) > 1e-9:
            self.rotations[bone] = rotation_matrix(axis, angle) @ self.rotations[bone]

    def swing(self, bone: int, degrees: float) -> None:
        """Balança para a frente (+) ou para trás (-): o que pende do osso vai para +z."""
        self.turn(bone, (1.0, 0.0, 0.0), -math.radians(degrees))

    def lean(self, bone: int, degrees: float) -> None:
        """Inclina o que está acima do osso para a frente (+)."""
        self.turn(bone, (1.0, 0.0, 0.0), math.radians(degrees))

    def twist(self, bone: int, degrees: float) -> None:
        """Gira em volta do eixo vertical."""
        self.turn(bone, (0.0, 1.0, 0.0), math.radians(degrees))

    def roll(self, bone: int, degrees: float) -> None:
        """Tomba para o lado (em volta do eixo da frente)."""
        self.turn(bone, (0.0, 0.0, 1.0), math.radians(degrees))


def _spread(chain: Sequence[int], total: float) -> List[Tuple[int, float]]:
    """Reparte ``total`` graus pelos ossos de uma cadeia (cada osso leva a mesma parte)."""
    return [(b, total / max(len(chain), 1)) for b in chain]


def _limb_cycle(pose: _Pose, limb: Limb, phase: float, swing: float, knee: float, walk: float) -> None:
    """Uma perna (ou braço) andando: o primeiro osso balança, o segundo dobra enquanto vai para a frente, o último
    compensa para a ponta não rasgar o chão."""
    chain = limb.chain
    angle = 2.0 * math.pi * phase
    forward = swing * walk * math.sin(angle)
    pose.swing(chain[0], forward)
    if len(chain) > 1:
        bend = knee * walk * max(0.0, math.cos(angle))       # dobra enquanto o membro avança
        pose.lean(chain[1], bend)
        if len(chain) > 2:
            pose.swing(chain[-1], 0.45 * (forward - bend))


def _body_motion(pose: _Pose, roles: Roles, t: float, phase: float, walk: float, height: float,
                 twist: float, lean: float, bob: float, wave: float = 0.0) -> None:
    """O que o tronco faz em todo perfil: respira parado, e ao andar balança, gira e sobe e desce."""
    angle = 2.0 * math.pi * phase
    breath = math.sin(t * 1.6) * 1.2 * (1.0 - walk)
    spine = roles.spine
    for index, bone in enumerate(spine):
        share = (index + 1) / max(len(spine), 1)
        pose.lean(bone, (lean * walk + breath) / max(len(spine), 1))
        pose.twist(bone, twist * walk * math.sin(angle) / max(len(spine), 1))
        if wave:   # ondulação que corre pela coluna (rastejante)
            pose.twist(bone, wave * walk * math.sin(angle - 2.2 * share))
    pose.offset[1] += bob * height * walk * math.cos(2.0 * angle) + 0.004 * height * math.sin(t * 1.6) * (1.0 - walk)
    for bone in roles.head:            # a cabeça compensa o giro do tronco
        pose.twist(bone, -0.5 * twist * walk * math.sin(angle) / max(len(roles.head), 1))
        pose.lean(bone, -0.6 * lean * walk / max(len(roles.head), 1) - 0.8 * breath)
    for index, bone in enumerate(roles.tail):
        pose.twist(bone, (10.0 * walk + 4.0) * math.sin(angle - 0.8 * index - 0.6) / max(len(roles.tail), 1) * 2.0)


def pose_bipede(pose: _Pose, roles: Roles, t: float, phase: float, walk: float, height: float) -> None:
    _body_motion(pose, roles, t, phase, walk, height, twist=7.0, lean=5.0, bob=0.012)
    for limb in roles.legs:
        _limb_cycle(pose, limb, phase + (0.0 if limb.side >= 0 else 0.5), 25.0, 28.0, walk)
    for limb in roles.arms:                # braços contra as pernas do mesmo lado
        _limb_cycle(pose, limb, phase + (0.5 if limb.side >= 0 else 0.0), 20.0, 14.0, walk)
        for bone in limb.chain[:1]:
            pose.roll(bone, limb.side * 4.0 * math.sin(t * 1.4) * (1.0 - walk))


def pose_quadrupede(pose: _Pose, roles: Roles, t: float, phase: float, walk: float, height: float) -> None:
    _body_motion(pose, roles, t, phase, walk, height, twist=5.0, lean=2.0, bob=0.01, wave=1.5)
    for limb in roles.legs:                # passo diagonal: dianteira de um lado com a traseira do outro
        diagonal = 0.0 if (limb.side >= 0) == (limb.end >= 0) else 0.5
        _limb_cycle(pose, limb, phase + diagonal, 26.0 if limb.end >= 0 else 24.0, 30.0, walk)
    for limb in roles.arms:
        _limb_cycle(pose, limb, phase + 0.5, 14.0, 10.0, walk)


def pose_rastejante(pose: _Pose, roles: Roles, t: float, phase: float, walk: float, height: float) -> None:
    _body_motion(pose, roles, t, phase, walk, height, twist=4.0, lean=0.0, bob=0.006, wave=8.0)
    for number, limb in enumerate(roles.legs):   # passo alternado, em trios
        _limb_cycle(pose, limb, phase + (0.0 if number % 2 == 0 else 0.5), 22.0, 24.0, walk)
    for number, limb in enumerate(roles.arms):
        _limb_cycle(pose, limb, phase + (0.5 if number % 2 == 0 else 0.0), 16.0, 10.0, walk)


def pose_flutuante(pose: _Pose, roles: Roles, t: float, phase: float, walk: float, height: float) -> None:
    angle = 2.0 * math.pi * phase
    pose.offset[1] += 0.045 * height * math.sin(t * 1.8)      # paira subindo e descendo, parado ou andando
    for bone in roles.spine:
        pose.lean(bone, (9.0 * walk + 1.5 * math.sin(t * 1.1)) / max(len(roles.spine), 1))
        pose.twist(bone, 4.0 * math.sin(t * 0.9) / max(len(roles.spine), 1))
    for bone in roles.head:
        pose.lean(bone, -4.0 * walk + 2.0 * math.sin(t * 1.5))
    for number, limb in enumerate(roles.arms + roles.legs):   # os membros balançam soltos e arrastam para trás
        for index, bone in enumerate(limb.chain):
            pose.swing(bone, (-8.0 * walk + 6.0 * math.sin(t * 1.7 + 0.7 * index + number)) / (1 + index))
            pose.roll(bone, limb.side * 5.0 * math.sin(t * 1.3 + number))
    for index, bone in enumerate(roles.tail):
        pose.twist(bone, 14.0 * math.sin(angle * 0.5 + t * 1.2 - 0.7 * index) / max(len(roles.tail), 1) * 2.0)


PROFILES = {"bipede": pose_bipede, "quadrupede": pose_quadrupede, "rastejante": pose_rastejante,
            "flutuante": pose_flutuante}


class ProceduralAnimator:
    """Gera, a cada quadro, as matrizes de pele de um modelo com esqueleto."""

    REFERENCE_SPEED = 3.0     # m/s com que o andar chega ao máximo
    CYCLE_HZ = 1.15           # ciclos de passo por segundo no andar normal

    def __init__(self, rig: Rig, roles: Roles, height: float = 1.8, profile: Optional[str] = None) -> None:
        if profile is not None and profile not in PROFILES:
            raise RolesError(f"Perfil '{profile}' não existe; use um de: {', '.join(PROFILES)}.")
        self.rig = rig
        self.roles = roles
        self.height = float(height)
        self.profile = profile or roles.profile
        self.time = 0.0
        self.phase = 0.0
        self.walk = 0.0                     # 0 parado, 1 andando; suaviza a troca
        self._matrices = rig.solve()

    @property
    def matrices(self) -> np.ndarray:
        """(J, 4, 4) float32, prontas para ``u_Bones``."""
        return self._matrices

    def update(self, dt: float, speed: float = 0.0) -> np.ndarray:
        """Avança ``dt`` segundos com o modelo andando a ``speed`` (m/s; 0 = parado)."""
        dt = max(float(dt), 0.0)
        self.time += dt
        target = min(max(speed / self.REFERENCE_SPEED, 0.0), 1.0)
        self.walk += (target - self.walk) * (1.0 - 0.5 ** (dt / 0.10))
        if abs(target - self.walk) < 0.002:
            self.walk = target
        self.phase = (self.phase + dt * self.CYCLE_HZ * (0.6 + 0.8 * self.walk) * (1.0 if self.walk > 0.02 else 0.0)) % 1.0
        pose = _Pose(self.rig, self.rig.identity_rotations())
        PROFILES[self.profile](pose, self.roles, self.time, self.phase, self.walk, self.height)
        self._matrices = self.rig.solve(pose.rotations, pose.offset).astype(np.float32)
        return self._matrices
