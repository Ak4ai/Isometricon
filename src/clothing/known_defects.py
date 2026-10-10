"""Roupas do catálogo com defeito conhecido em algum corpo.

São as peças que a bateria de robustez (``scripts/audit_animation_robustness.py``) reprova e que,
conferidas por imagem, têm mesmo o defeito (rodada de 09/10/2026, igual à de 07/10). O editor
marca o card delas e o chat avisa ao vestir: a peça continua podendo ser usada.

Ficam de fora as reprovações que a conferência por imagem mostrou serem falso alarme da medida de
buraco (Baby Shark, Goose Duck, Realistic Dinosaur, terno Mafioso: forro do capuz, a abertura da
própria fantasia). Quando uma peça for corrigida ou a bateria mudar de veredito, atualize aqui.
"""
from typing import Dict

TORN = "o tecido rasga ao andar"
PIERCED = "a pele atravessa o tecido ao andar"
NECK_HOLE = "buraco no pescoço"

# asset id -> body ("female", "male") -> what is wrong there
KNOWN_DEFECTS: Dict[str, Dict[str, str]] = {
    "107758405066471": {"male": TORN},                         # Sully Wazowski Costume
    "104294938310972": {"male": TORN},                         # Realistic White Pigeon Costume
    "93303265717630": {"male": TORN},                          # Strawberry Onesie
    "12294031222": {"male": PIERCED},                          # Blue Fish Suit Salmon Costume: the arm through its side
    "18135693306": {"female": PIERCED, "male": PIERCED},       # White Side Slit Long Skirt: the leg through the cloth
    "16185652164": {"female": NECK_HOLE, "male": NECK_HOLE},   # Oversized Knitted Sweater w/ Bow
}


def defect_of(asset_id, body) -> str:
    """O defeito conhecido de uma peça neste corpo ("" quando não há)."""
    name = "female" if str(getattr(body, "value", body)).lower() in ("female", "feminino", "fem", "f", "mulher", "woman") else "male"
    return KNOWN_DEFECTS.get(str(asset_id).strip(), {}).get(name, "")
