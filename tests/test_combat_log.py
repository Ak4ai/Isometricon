"""O texto do registro de combate: cada evento vira uma linha legível com a conta da rolagem."""
from src.combat.bestiary import BESTIARY, PlayerSheet, spawn
from src.combat.dice import FixedDice
from src.combat.engine import CombatSession
from src.combat.log import action_label, format_event


def session(values):
    player = PlayerSheet().combatant((0.0, 0.0, 0.0))
    zombie = spawn(BESTIARY["zumbi"], "zumbi", (1.0, 0.0, 0.0))
    return CombatSession([player, zombie], dice=FixedDice(values)), player, zombie


def lines(s):
    name = lambda cid: s.get(cid).name if s.get(cid) else (cid or "")
    player = lambda cid: bool(s.get(cid) and s.get(cid).is_player)
    return [format_event(e, name, player) for e in s.events]


def test_start_lists_initiative():
    s, _, _ = session([15, 3])
    first = lines(s)[0]
    assert "Combate" in first.text and "Você 16" in first.text and "Zumbi 2" in first.text


def test_hit_line_shows_damage_and_roll():
    s, _, zombie = session([15, 3, 12, 4])
    s.act("atacar")
    hit = [l for l in lines(s) if l and "acertou" in l.text][0]
    assert "Zumbi" in hit.text and "de dano" in hit.text and "vs CA" in hit.text
    assert "Dano: 1d6" in hit.detail


def test_miss_fumble_and_critical_lines():
    s, _, zombie = session([15, 3, 1])
    s.act("atacar")
    assert "FALHA CRÍTICA" in lines(s)[-1].text
    s, _, zombie = session([15, 3, 2])
    s.act("atacar")
    assert "errou" in [l for l in lines(s) if l][-1].text
    s, _, zombie = session([15, 3, 20, 3, 3])
    s.act("atacar")
    assert "CRÍTICO" in [l for l in lines(s) if l and "CRÍTICO" in l.text][0].text


def test_refusal_and_end_lines():
    s, player, zombie = session([15, 3])
    zombie.position = [9.0, 0.0, 0.0]
    s.act("atacar")
    assert lines(s)[-1].text.startswith("✖ Fora de alcance")
    s.act("fugir")
    texts = [l.text for l in lines(s) if l]
    assert any("saiu do combate" in t for t in texts) and texts[-1].startswith("Você fugiu")


def test_movement_and_turn_events_are_silent():
    s, _, _ = session([15, 3])
    s.spend_movement(1.0)
    assert format_event(s.events[1], lambda c: c, lambda c: False) is None       # "turno"


def test_action_labels():
    assert action_label("golpe_pesado") == "Golpe Pesado" and action_label("fugir") == "Fugir"
