"""Os corpos dos NPCs no mundo: um personagem montado (o mesmo do ``/skin``) para cada NPC do combate.

O ``CombatController`` guarda os NPCs como fichas do tabuleiro (posição, para onde olham, se andam ou caíram); aqui
cada ficha com aparência (``npc["personagem"]``, o que ``character_save.to_dict`` grava) ganha um ``CharacterModel``
montado em segundo plano, com o cache de montagem dele (``npc_<id>``), e um ``CharacterAnimator`` que anda quando a
ficha anda. Enquanto o corpo monta, a miniatura do tabuleiro aparece no lugar (``ready``).

O corpo que a tela de criação acabou de montar entra pronto (``adopt``), sem montar de novo.

Um NPC com ``npc["modelo"]`` (a escolha do ``/skin modelo``: arquivo, altura, giro, perfil) usa o modelo .glb
personalizado no lugar do corpo montado; se o arquivo sumiu, volta ao corpo montado.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Set

import numpy as np

from src.math import mat4_rotate_x, mat4_rotate_y, mat4_translate

FALL_TILT = math.radians(84.0)   # o NPC caído fica deitado de costas


def look_key(look: Optional[Dict[str, Any]], choice: Optional[Dict[str, Any]] = None) -> str:
    """Uma assinatura da aparência (e do modelo .glb): quando muda (``/npc editar``), o corpo é montado de novo."""
    return json.dumps(look or {} if choice is None else {"personagem": look, "modelo": choice},
                      sort_keys=True, default=str)


class CustomHolder:
    """Quem guarda o modelo .glb do NPC na tela de criação (o ``/skin modelo`` põe nele, não no personagem)."""

    def __init__(self, model: Any = None) -> None:
        self.custom_model = model

    def set_custom_model(self, model: Any) -> Any:
        previous, self.custom_model = self.custom_model, model
        return previous


def build_custom(choice: Dict[str, Any]) -> Any:
    """O modelo .glb da escolha do NPC, ou None (o arquivo sumiu ou não abre)."""
    from src.interactive.skin_commands import build_custom_model
    model, note = build_custom_model(choice)
    if model is None:
        print(f"[NPC] {note}")
    return model


def npc_matrix(position, yaw: float, fallen: float = 0.0, fall_seconds: float = 1.0) -> np.ndarray:
    """Onde o corpo do NPC é desenhado: no pé dele, virado para ``yaw`` e tombando enquanto cai."""
    tilt = FALL_TILT * min(1.0, fallen / fall_seconds) if fallen else 0.0
    matrix = mat4_translate(float(position[0]), float(position[1]), float(position[2])) @ mat4_rotate_y(yaw)
    return matrix @ mat4_rotate_x(-tilt) if tilt else matrix


def build_model(npc_id: str, look: Optional[Dict[str, Any]], body: str = "masculino") -> Any:
    """Um corpo novo para o NPC: o salvo (``look``) ou o padrão do sexo pedido, montado em segundo plano."""
    from src.clothing import character_save
    from src.clothing.character_model import CharacterModel
    from src.clothing.customization import AvatarCustomization, BodyType
    if look:
        arguments = character_save.model_arguments(look)
    else:
        female = body.lower() in ("feminino", "female", "f", "mulher")
        arguments = {"customization": AvatarCustomization(body_type=BodyType.FEMALE if female else BodyType.MALE)}
    return CharacterModel(create_mesh=True, async_loading=True, cache_name=f"npc_{npc_id}", **arguments)


@dataclass
class NpcBody:
    model: Any               # o corpo montado (None quando o NPC só tem o modelo .glb)
    animator: Any
    key: str
    custom: Any = None       # o modelo .glb, desenhado no lugar do corpo montado

    @property
    def loading(self) -> bool:
        return self.custom is None and (self.model is None or bool(getattr(self.model, "is_loading", False)))

    def delete(self) -> None:
        for part in (self.model, self.custom):
            if part is not None:
                part.delete()


class NpcModels:
    def __init__(self, factory: Callable[[str, Optional[Dict[str, Any]]], Any] = build_model,
                 animator: Optional[Callable[[Any], Any]] = None,
                 custom_factory: Callable[[Dict[str, Any]], Any] = build_custom) -> None:
        self.factory = factory
        self.animator = animator     # None: o CharacterAnimator do jogo
        self.custom_factory = custom_factory
        self.bodies: Dict[str, NpcBody] = {}

    def adopt(self, npc_id: str, model: Any, animator: Any, look: Optional[Dict[str, Any]],
              custom: Any = None, choice: Optional[Dict[str, Any]] = None) -> None:
        """Põe um corpo já montado (o da tela de criação, e o modelo .glb dele, se há) no NPC ``npc_id``."""
        old = self.bodies.get(npc_id)
        if old is not None:
            for part in (old.model, old.custom):
                if part is not None and part is not model and part is not custom:
                    part.delete()
        self.bodies[npc_id] = NpcBody(model, animator, look_key(look, choice), custom)

    def release(self, npc_id: str) -> Optional[NpcBody]:
        """Tira o corpo do NPC daqui sem apagá-lo (a tela de criação passa a cuidar dele)."""
        return self.bodies.pop(npc_id, None)

    def ready(self, npc_id: str) -> bool:
        body = self.bodies.get(npc_id)
        return body is not None and not body.loading

    def ready_ids(self) -> Set[str]:
        return {npc_id for npc_id in self.bodies if self.ready(npc_id)}

    def sync(self, controller: Any, dt: float, skip: Optional[str] = None) -> None:
        """Um corpo para cada NPC do combate (menos ``skip``, o que está na tela de criação); some quem saiu."""
        if self.animator is None:
            from src.clothing.character_animation import CharacterAnimator
            self.animator = lambda model: CharacterAnimator(model, walking=False)
        present = set()
        for token in controller.enemies:
            if token.npc is None or token.id == skip:
                continue
            present.add(token.id)
            look, choice = token.npc.get("personagem"), token.npc.get("modelo")
            key = look_key(look, choice)
            body = self.bodies.get(token.id)
            if body is None or body.key != key:
                if body is not None:
                    body.delete()
                custom = self.custom_factory(choice) if choice else None
                model = None if custom is not None else self.factory(token.id, look)
                body = self.bodies[token.id] = NpcBody(model, self.animator(model) if model is not None else None,
                                                        key, custom)
            walking = token.walking and not token.fallen
            if body.custom is not None:
                body.custom.update(dt, token.creature.speed if walking else 0.0)
                continue
            body.model.poll()
            if not getattr(body.model, "is_loading", False):
                body.animator.walking = walking
                body.animator.update(dt)
        for npc_id in [i for i in self.bodies if i not in present and i != skip]:
            self.bodies.pop(npc_id).delete()

    def draw(self, shader: Any, model: np.ndarray, controller: Any, fall_seconds: float = 1.0) -> None:
        for token in controller.enemies:
            body = self.bodies.get(token.id) if token.npc is not None else None
            if body is None or body.loading:
                continue
            (body.custom or body.model).draw(shader, model @ npc_matrix(token.shown, token.yaw, token.fallen, fall_seconds))

    def delete(self) -> None:
        for body in self.bodies.values():
            body.delete()
        self.bodies.clear()
