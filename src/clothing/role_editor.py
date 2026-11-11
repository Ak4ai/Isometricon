"""Os papéis dos ossos osso por osso: o que a tela de criação mostra e deixa mudar com um clique.

``Roles`` (procedural.py) guarda cadeias: a perna é uma lista de ossos com lado e ponta. Na tela cada osso tem um rótulo
só ("perna", "braço"...). Aqui se passa de um para o outro: ``labels_from_roles`` pinta os ossos com os papéis achados,
e ``roles_from_labels`` refaz as cadeias depois de o usuário trocar o rótulo de um osso.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from .procedural import LEFT, RIGHT, Limb, Roles, suggest_profile
from .rig import Rig

LABELS = ("perna", "braco", "cabeca", "coluna", "cauda", "nenhum")
TITLES = {"perna": "Perna", "braco": "Braço", "cabeca": "Cabeça", "coluna": "Coluna", "cauda": "Cauda", "nenhum": "Nenhum"}
COLOURS: Dict[str, Tuple[int, int, int]] = {
    "perna": (80, 170, 255), "braco": (120, 230, 120), "cabeca": (255, 200, 70),
    "coluna": (235, 235, 240), "cauda": (255, 120, 200), "nenhum": (120, 120, 130)}


def labels_from_roles(rig: Rig, roles: Roles) -> List[str]:
    """Um rótulo por osso, a partir dos papéis (quem não aparece em nenhum é "nenhum")."""
    labels = ["nenhum"] * len(rig)
    for label, bones in (("coluna", roles.spine), ("cabeca", roles.head), ("cauda", roles.tail)):
        for bone in bones:
            labels[bone] = label
    for label, limbs in (("perna", roles.legs), ("braco", roles.arms)):
        for limb in limbs:
            for bone in limb.chain:
                labels[bone] = label
    return labels


def _chains(rig: Rig, bones: List[int]) -> List[List[int]]:
    """Cadeias de ossos ligados entre si (pai e filho), do mais alto para a ponta, seguindo o ramo maior."""
    members, used, chains = set(bones), set(), []

    def size(bone: int) -> int:
        return 1 + sum(size(c) for c in rig.children[bone] if c in members)

    for bone in bones:               # ``bones`` vem com os pais antes dos filhos
        if bone in used:
            continue
        chain = [bone]
        used.add(bone)
        while True:
            kids = [c for c in rig.children[chain[-1]] if c in members and c not in used]
            if not kids:
                break
            chain.append(max(kids, key=size))
            used.add(chain[-1])
        chains.append(chain)
    return chains


def roles_from_labels(rig: Rig, labels: List[str], previous: Optional[Roles] = None) -> Roles:
    """Refaz os papéis (cadeias, lados, perfil) a partir de um rótulo por osso.

    ``previous`` empresta o lado e a ponta de um membro que já existia e o perfil, quando o número de pernas não mudou.
    """
    positions = rig.rest_positions
    depth = {bone: number for number, bone in enumerate(rig.order)}
    of = lambda label: sorted((b for b in range(len(rig)) if labels[b] == label), key=depth.__getitem__)
    roles = Roles(spine=of("coluna"), head=of("cabeca"), tail=of("cauda"))
    centre = float(np.median(positions[roles.spine, 0])) if roles.spine else float(positions[rig.roots[0], 0])
    known: Dict[int, Limb] = {}
    if previous is not None:
        for limb in previous.legs + previous.arms:
            known.setdefault(limb.chain[0], limb)

    def limb_of(chain: List[int]) -> Limb:
        old = known.get(chain[0])
        if old is not None:
            return Limb(chain, old.side, old.end)
        return Limb(chain, LEFT if positions[chain[0], 0] - centre >= 0 else RIGHT, 0)

    roles.legs = [limb_of(c) for c in _chains(rig, of("perna"))]
    roles.arms = [limb_of(c) for c in _chains(rig, of("braco"))]
    if roles.legs:   # frente e trás das pernas: a posição em z do começo de cada uma
        middle = float(np.median([positions[l.chain[0], 2] for l in roles.legs]))
        for limb in roles.legs:
            if limb.chain[0] not in known:
                limb.end = 1 if positions[limb.chain[0], 2] > middle + 1e-6 else -1
    if previous is not None and len(previous.legs) == len(roles.legs):
        roles.profile = previous.profile
    else:
        roles.profile = suggest_profile(roles)
    return roles


def screen_positions(points: np.ndarray, model: np.ndarray, view: np.ndarray, projection: np.ndarray,
                     rect: Tuple[float, float, float, float]) -> Tuple[np.ndarray, np.ndarray]:
    """Onde pontos 3D (do modelo) caem na janela, em pixels, e a profundidade de cada um (maior = mais perto)."""
    seen = np.asarray(view, dtype=np.float64) @ np.asarray(model, dtype=np.float64)
    eye = np.asarray(points, dtype=np.float64) @ seen[:3, :3].T + seen[:3, 3]
    clip = np.column_stack((eye, np.ones(len(eye)))) @ np.asarray(projection, dtype=np.float64).T
    ndc = clip[:, :2] / np.where(np.abs(clip[:, 3:4]) < 1e-12, 1e-12, clip[:, 3:4])
    x0, y0, x1, y1 = rect
    xy = np.column_stack((x0 + (ndc[:, 0] * 0.5 + 0.5) * (x1 - x0), y0 + (0.5 - ndc[:, 1] * 0.5) * (y1 - y0)))
    return xy, eye[:, 2]


def posed_positions(rig: Rig, matrices: Optional[np.ndarray]) -> np.ndarray:
    """Onde cada osso está agora (no espaço do modelo): a pose dele (matriz de pele) aplicada à posição de montagem."""
    rest = rig.rest_positions
    if matrices is None:
        return rest
    skin = np.asarray(matrices, dtype=np.float64)
    return np.einsum("jab,jb->ja", skin[:, :3, :3], rest) + skin[:, :3, 3]


def bone_at(xy: np.ndarray, depth: np.ndarray, x: float, y: float, radius: float = 12.0) -> Optional[int]:
    """O osso cujo ponto está sob (x, y) (até ``radius`` pixels), o mais perto da câmera se há vários; ``None`` se nenhum."""
    near = np.flatnonzero(((xy - np.array([x, y])) ** 2).sum(axis=1) <= radius * radius)
    if not len(near):
        return None
    return int(near[np.argmax(depth[near])])


def overlay_image(size: Tuple[int, int], origin: Tuple[float, float], xy: np.ndarray, parents: np.ndarray,
                  labels: List[str], hover: Optional[int] = None, names: Optional[List[str]] = None):
    """Imagem RGBA (do tamanho da cena, com o canto em ``origin`` na janela): linhas pai-filho e um ponto por osso,
    na cor do papel dele; o osso sob o mouse fica maior e mostra o nome."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (max(int(size[0]), 1), max(int(size[1]), 1)), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    local = np.asarray(xy, dtype=np.float64) - np.asarray(origin, dtype=np.float64)
    for bone, parent in enumerate(parents):
        if parent >= 0:
            pen.line((*local[parent], *local[bone]), fill=(*COLOURS[labels[bone]], 200), width=3)
    for bone in range(len(labels)):
        radius = 8 if bone == hover else 5
        x, y = local[bone]
        pen.ellipse((x - radius - 1, y - radius - 1, x + radius + 1, y + radius + 1), fill=(15, 15, 20, 255))
        pen.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*COLOURS[labels[bone]], 255))
    if hover is not None and names is not None:
        x, y = local[hover]
        text = f"{names[hover]}: {TITLES[labels[hover]]}"
        pen.rectangle((x + 12, y - 11, x + 16 + 7 * len(text), y + 9), fill=(15, 15, 20, 220))
        pen.text((x + 15, y - 8), text, fill=(240, 240, 245, 255))
    return image


__all__ = ["LABELS", "TITLES", "COLOURS", "labels_from_roles", "roles_from_labels", "screen_positions",
           "posed_positions", "bone_at", "overlay_image"]
