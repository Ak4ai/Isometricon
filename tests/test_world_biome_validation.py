"""Um mundo com bioma abre de novo: a validação do save aceita o bioma, que é o único texto das opções do terreno.

Regressão: ``validate_world_state`` exigia número em toda opção do terreno, e o ``bioma`` ("planicie", "deserto",
"taiga") é texto. Todo mundo criado com as opções padrão sumia da lista e não reabria (o teste de pacote do CI
pegou: "Opções inválidas no mundo (terrain)").
"""
import pytest

from src.core.game_storage import WorldLibrary, validate_world_state
from src.world.terrain_options import BIOMES, defaults


@pytest.mark.parametrize("biome", BIOMES)
def test_mundo_com_bioma_abre_de_novo(tmp_path, biome):
    library = WorldLibrary(tmp_path)
    options = dict(defaults(), bioma=biome)
    world = library.create("Aventura", 42, options)
    assert library.load(world["id"])["terrain"]["bioma"] == biome
    assert [item["id"] for item in library.list()] == [world["id"]]      # e continua na lista de mundos


def test_mundo_com_as_opcoes_padrao_valida():
    validate_world_state({"seed": 42, "terrain": defaults()})


def test_bioma_desconhecido_e_recusado():
    for bad in ("lava", "", 3, None):
        with pytest.raises(ValueError, match="terrain"):
            validate_world_state({"seed": 42, "terrain": dict(defaults(), bioma=bad)})


def test_as_outras_opcoes_do_terreno_seguem_numericas():
    with pytest.raises(ValueError, match="terrain"):
        validate_world_state({"seed": 42, "terrain": dict(defaults(), relevo="alto")})
    with pytest.raises(ValueError, match="ambiente"):
        validate_world_state({"seed": 42, "ambiente": {"hour": "meio-dia"}})
