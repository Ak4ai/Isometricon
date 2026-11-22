"""As fichas dos inimigos e a ficha de combate do personagem (sem OpenGL).

No mod cada número saía dos atributos do Minecraft (o acerto do mob era metade do dano). Aqui cada criatura é uma
ficha de dados; ``spawn`` cria um ``Combatant`` dela numa posição.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

from src.combat.actions import STARTING_KIT
from src.combat.combatant import ENEMIES, MOB_REACH, PLAYER_REACH, PLAYERS, Combatant
from src.combat.effects import Effect
from src.combat.stats import ARMORS, WEAPONS, Abilities


@dataclass(frozen=True)
class Creature:
    key: str
    name: str
    scores: Dict[str, int]
    max_hp: int
    weapon: str
    armor: str = "nenhuma"
    speed: float = 8.0
    width: float = 0.6                  # largura do corpo, em blocos: criatura larga alcança mais longe
    proficiency: int = 2
    ai: str = "agressivo"
    skills: Tuple[str, ...] = ()
    on_hit: Optional[Effect] = None
    color: Tuple[int, int, int] = (200, 200, 200)   # cor da miniatura no tabuleiro
    height: float = 1.8
    aliases: Tuple[str, ...] = field(default=())


BESTIARY: Dict[str, Creature] = {
    "zumbi": Creature("zumbi", "Zumbi", {"for": 14, "des": 8, "con": 14, "sab": 6}, 22, "pancada",
                      speed=6.0, color=(92, 140, 84)),
    "esqueleto": Creature("esqueleto", "Esqueleto arqueiro", {"for": 10, "des": 14, "con": 12, "sab": 8}, 16, "arco",
                          armor="couro", ai="atirador", color=(214, 214, 200), aliases=("arqueiro",)),
    "aranha": Creature("aranha", "Aranha", {"for": 12, "des": 16, "con": 12, "sab": 10}, 16, "mordida",
                       speed=10.0, width=1.4, ai="covarde", on_hit=Effect("veneno", 2, 1), color=(70, 52, 52),
                       height=0.9),
    "slime": Creature("slime", "Slime", {"for": 12, "des": 6, "con": 16, "sab": 4}, 20, "pancada",
                      speed=5.0, width=1.0, color=(110, 200, 90), height=1.0),
    "bandido": Creature("bandido", "Bandido", {"for": 13, "des": 14, "con": 12, "sab": 10}, 18, "espada",
                        armor="couro_batido", ai="covarde", skills=("golpe_pesado",), color=(150, 96, 60)),
    "guarda": Creature("guarda", "Guarda", {"for": 14, "des": 12, "con": 14, "sab": 10}, 22, "espada",
                       armor="cota", skills=("golpe_pesado",), color=(90, 110, 150), aliases=("aliado",)),
    "ogro": Creature("ogro", "Ogro", {"for": 18, "des": 8, "con": 16, "sab": 7}, 45, "machado",
                     armor="cota", speed=7.0, width=1.2, skills=("golpe_pesado",), color=(150, 120, 80),
                     height=2.6),
}


def find_creature(name: str) -> Optional[Creature]:
    key = name.strip().lower()
    if key in BESTIARY:
        return BESTIARY[key]
    for creature in BESTIARY.values():
        if key in creature.aliases or key == creature.name.lower():
            return creature
    return None


def spawn(creature: Creature, combatant_id: str, position: Sequence[float], name: Optional[str] = None,
          ally: bool = False) -> Combatant:
    """Um combatente da ficha ``creature``; ``ally`` o põe do lado dos jogadores (jogado pela IA)."""
    return Combatant(
        id=combatant_id, name=name or creature.name, team=PLAYERS if ally else ENEMIES, ally=ally,
        abilities=Abilities(dict(creature.scores)),
        max_hp=creature.max_hp, armor=ARMORS[creature.armor], weapon=WEAPONS[creature.weapon],
        position=list(position), speed=creature.speed, base_reach=MOB_REACH + (creature.width - 0.6),
        proficiency=creature.proficiency, skills=creature.skills, on_hit=creature.on_hit, ai=creature.ai,
        kind=creature.key,
    )


PLAYER_SCORES = {"for": 14, "des": 13, "con": 14, "sab": 12}
PLAYER_SKILLS = ("golpe_pesado", "ataque_furtivo", "escudo_divino", "foco_espiritual")


@dataclass
class PlayerSheet:
    """A ficha que o personagem leva de um combate para o outro (o mundo a salva): atributos, arma, armadura e itens."""

    name: str = "Você"
    scores: Dict[str, int] = field(default_factory=lambda: dict(PLAYER_SCORES))
    level: int = 1
    weapon: str = "espada_curta"
    armor: str = "couro"
    items: Dict[str, int] = field(default_factory=lambda: dict(STARTING_KIT))
    hp: Optional[float] = None          # None: vida cheia

    @property
    def max_hp(self) -> int:
        """20 de base mais 2 por ponto de modificador de CON, e 5 + CON por nível acima do primeiro."""
        con = Abilities(dict(self.scores)).mod("con")
        return max(1, 20 + 2 * con + (self.level - 1) * max(1, 5 + con))

    def combatant(self, position: Sequence[float], combatant_id: str = "jogador") -> Combatant:
        hp = self.max_hp if self.hp is None else max(1.0, min(float(self.hp), self.max_hp))
        return Combatant(
            id=combatant_id, name=self.name, team=PLAYERS, abilities=Abilities(dict(self.scores)),
            max_hp=self.max_hp, hp=hp, armor=ARMORS.get(self.armor, ARMORS["nenhuma"]),
            weapon=WEAPONS.get(self.weapon, WEAPONS["soco"]), position=list(position), base_reach=PLAYER_REACH,
            level=self.level, skills=PLAYER_SKILLS, items=self.items, kind="jogador",
        )

    def to_dict(self) -> dict:
        return {"scores": dict(self.scores), "level": self.level, "weapon": self.weapon, "armor": self.armor,
                "items": dict(self.items), "hp": self.hp}

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "PlayerSheet":
        sheet = cls()
        if not isinstance(data, dict):
            return sheet
        scores = data.get("scores")
        if isinstance(scores, dict):
            for key, value in scores.items():
                if key in sheet.scores and isinstance(value, int) and 1 <= value <= 30:
                    sheet.scores[key] = value
        level = data.get("level")
        if isinstance(level, int) and 1 <= level <= 20:
            sheet.level = level
        if data.get("weapon") in WEAPONS:
            sheet.weapon = data["weapon"]
        if data.get("armor") in ARMORS:
            sheet.armor = data["armor"]
        items = data.get("items")
        if isinstance(items, dict):
            sheet.items = {k: v for k, v in items.items() if isinstance(v, int) and v > 0}
        hp = data.get("hp")
        if isinstance(hp, (int, float)) and hp > 0:
            sheet.hp = float(hp)
        return sheet
