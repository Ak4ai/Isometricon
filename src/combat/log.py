"""O texto do registro de combate: cada ``Event`` vira uma linha colorida e uma explicação da rolagem (sem OpenGL).

No mod o texto já nascia com os códigos de cor ``§`` e as dicas embutidas no meio da regra. Aqui a regra só anota
eventos; esta função os escreve. ``Line.segments`` são pedaços (texto, cor); ``Line.detail`` explica a conta (a dica
que o mod mostrava ao passar o mouse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from src.combat.actions import ITEMS, SKILLS
from src.combat.effects import EFFECT_NAMES

Color = Tuple[int, int, int]
ALLY: Color = (85, 255, 85)
FOE: Color = (255, 110, 110)
TEXT: Color = (210, 210, 210)
DIM: Color = (150, 150, 150)
GOLD: Color = (255, 200, 60)
DAMAGE: Color = (255, 85, 85)
HEAL: Color = (120, 255, 140)
BLUE: Color = (110, 170, 255)
NUMBER: Color = (120, 220, 255)

OUTCOME_TEXT = {"vitoria": ("Vitória!", GOLD), "derrota": ("Você desmaiou...", DAMAGE), "fuga": ("Você fugiu.", BLUE)}


@dataclass
class Line:
    segments: List[Tuple[str, Color]] = field(default_factory=list)
    detail: str = ""

    def add(self, text: str, color: Color = TEXT) -> "Line":
        self.segments.append((text, color))
        return self

    @property
    def text(self) -> str:
        return "".join(text for text, _ in self.segments)


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def format_event(event, name_of: Callable[[Optional[str]], str], is_player: Callable[[Optional[str]], bool]
                 ) -> Optional[Line]:
    """A linha do registro para ``event`` (None para os eventos que não aparecem, como movimento e início de vez)."""
    def who(cid: Optional[str]) -> Tuple[str, Color]:
        return name_of(cid), (ALLY if is_player(cid) else FOE)

    kind, data = event.kind, event.data
    line = Line()
    if kind == "inicio":
        line.add("⚔ Combate! ", GOLD).add("Iniciativa: ", DIM)
        for i, (cid, init) in enumerate(data["order"]):
            line.add(("" if i == 0 else ", ") + name_of(cid), ALLY if is_player(cid) else FOE).add(f" {init}", NUMBER)
        if data.get("surprise"):
            line.add(" — ataque surpresa!", GOLD)
        return line
    if kind == "entrou":
        return line.add(*who(event.actor)).add(" entrou no combate ", TEXT).add(f"(iniciativa {data['initiative']})", DIM)
    if kind == "ataque":
        r = data["result"]
        line.add(*who(event.actor))
        if r.label != "Ataque":
            line.add(f" [{r.label}]", GOLD)
        roll = f" (d20 {r.d20}{r.attack_bonus:+d} = {r.total} vs CA {r.armor_class})"
        if len(r.d20_rolls) > 1:
            roll = f" (d20 {r.d20_rolls[0]}|{r.d20_rolls[1]}→{r.d20}{r.attack_bonus:+d} = {r.total} vs CA {r.armor_class})"
        if r.fumble:
            line.add(" FALHA CRÍTICA!", DAMAGE).add(" (1 natural)", DIM)
            line.detail = "Um 1 natural no d20 erra sempre, seja qual for o bônus."
            return line
        if not r.hit:
            line.add(" errou ", DIM).add(name_of(event.target), DIM).add(roll, DIM)
            line.detail = f"d20 {r.d20} + bônus {r.attack_bonus:+d} = {r.total}, menor que a CA {r.armor_class}."
            return line
        if r.critical:
            line.add(" ★ CRÍTICO em ", GOLD)
        else:
            line.add(" acertou ", TEXT)
        line.add(name_of(event.target), FOE if is_player(event.actor) else ALLY)
        line.add(f": {r.damage} de dano", DAMAGE).add(f" {r.damage_type}", DIM)
        if r.absorbed:
            line.add(f" ({_fmt(r.absorbed)} absorvido)", GOLD)
        if r.applied_effect:
            line.add(f" + {EFFECT_NAMES[r.applied_effect]}", (180, 120, 255))
        line.add(roll if not r.critical else f" (d20 20 vs CA {r.armor_class})", DIM)
        dice = " + ".join(str(v) for v in r.damage_rolls)
        line.detail = (f"Dano: {r.dice} → [{dice}] = {r.raw_damage}; a armadura do alvo segurou "
                       f"{r.reduced_by_armor} → {r.damage}." + (" O crítico dobrou os dados." if r.critical else ""))
        return line
    if kind == "derrotado":
        return line.add("★ ", GOLD).add(*who(event.actor)).add(" caiu!", GOLD)
    if kind == "defesa":
        return line.add(*who(event.actor)).add(" assume postura defensiva ", BLUE).add(f"(CA {data['armor_class']})", DIM)
    if kind == "escudo":
        return line.add(*who(event.actor)).add(" [Escudo Divino]", GOLD).add(
            f" +{data['temp_hp']} de vida temporária e +5 CA", BLUE)
    if kind == "disparada":
        return line.add(*who(event.actor)).add(" ➜ disparou!", GOLD).add(f" ({_fmt(data['movement'])} blocos)", DIM)
    if kind == "cura":
        source = {"regeneracao": "Regeneração", "foco_espiritual": "Foco Espiritual"}.get(data.get("source"), "")
        line.add(*who(event.actor)).add(f" recuperou {_fmt(data['amount'])} de vida", HEAL)
        if source:
            line.add(f" ({source})", DIM)
        if data.get("source") == "foco_espiritual":
            line.detail = f"1d10 [{data['rolls'][0]}] + nível {data['bonus']}."
        return line
    if kind == "dano_efeito":
        return line.add(*who(event.actor)).add(f" sofreu {_fmt(data['amount'])} de ", DAMAGE).add(
            EFFECT_NAMES.get(data["source"], data["source"]), (180, 120, 255))
    if kind == "efeito_fim":
        return line.add(*who(event.actor)).add(f": {EFFECT_NAMES[data['effect']]} passou", DIM)
    if kind == "atordoado":
        return line.add(*who(event.actor)).add(" está atordoado e perde a vez", DIM)
    if kind == "item":
        item = ITEMS[data["item"]]
        line.add(*who(event.actor)).add(f" usou {item.name}", HEAL)
        if data["healed"]:
            line.add(f": +{_fmt(data['healed'])} de vida", HEAL)
            line.detail = f"{item.heal} → [{' + '.join(str(v) for v in data['rolls'])}]{item.heal.bonus:+d}."
        return line
    if kind == "fuga":
        line.add(*who(event.actor))
        if data["dc"] is None:
            return line.add(" saiu do combate sem ninguém no caminho", BLUE)
        total = data["d20"] + data["bonus"]
        if data["success"]:
            line.add(" escapou!", BLUE)
        else:
            line.add(" tentou fugir e não conseguiu", DIM)
        line.add(f" (d20 {data['d20']}{data['bonus']:+d} = {total} vs CD {data['dc']})", DIM)
        line.detail = "CD de fuga: 10 + 3 por inimigo corpo a corpo que te alcança."
        return line
    if kind == "fugiu":
        return line.add(*who(event.actor)).add(" se afastou e saiu do combate", BLUE)
    if kind == "recusado":
        return line.add("✖ ", DAMAGE).add(data["reason"][:1].upper() + data["reason"][1:], DIM)
    if kind == "fim":
        text, color = OUTCOME_TEXT[data["outcome"]]
        return line.add(text, color).add(f" ({data['round']} rodada{'s' if data['round'] > 1 else ''})", DIM)
    return None


def action_label(key: str) -> str:
    if key in SKILLS:
        return SKILLS[key].name
    return {"atacar": "Atacar", "defender": "Defender", "disparada": "Disparada", "fugir": "Fugir",
            "usar_item": "Usar item"}.get(key, key)
