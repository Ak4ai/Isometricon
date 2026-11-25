"""As opções de criação de um mundo (tela "Uma nova aventura"), em porcentagens de 0 a 100, e o gerador delas.

Cada mundo guarda as opções em ``world["terrain"]``. Sem opções (mundos de antes desta tela), o gerador é o de
sempre; com as opções nos valores padrão, também é o de sempre, menos a água, que passa a ser uma porcentagem do
chão coberto (o nível do mar sai das alturas da própria seed).

- ``cavernas``: a chance de cada coluna de chunks ter túneis (0 desliga as cavernas; 60 é o de sempre).
- ``planicie``: o quanto o relevo é plano (100 é chão liso; 25 é o de sempre).
- ``agua``: a parte do chão perto do começo que fica embaixo d'água.
- ``vegetacao``: a densidade de capim, flores e cogumelos (50 é o de sempre, 100 é o dobro).
- ``relevo``: o tamanho dos morros e vales (0 miúdos, 100 largos; 50 é o de sempre).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, Mapping, Optional

import numpy as np

# (chave, rótulo, padrão, texto curto do que o valor faz)
OPTIONS = (
    ('cavernas', 'Cavernas', 60, 'Quantos túneis há embaixo da terra'),
    ('planicie', 'Planície', 25, 'O quanto o relevo é plano'),
    ('agua', 'Água', 20, 'A parte do chão coberta por lagos e mares'),
    ('vegetacao', 'Vegetação', 50, 'Capim, flores e cogumelos'),
    ('relevo', 'Tamanho do relevo', 50, 'Morros miúdos ou largos'),
)
KEYS = tuple(key for key, *_ in OPTIONS)

# O bioma do mundo inteiro (uma escolha, não uma porcentagem); sem a chave, planície, como os mundos de antes
BIOMES = ('planicie', 'deserto', 'taiga')
BIOME_LABELS = {'planicie': 'Planície', 'deserto': 'Deserto', 'taiga': 'Taiga'}
DEFAULT_BIOME = 'planicie'


def water_default(biome: str) -> int:
    """O padrão da barra "Água" do bioma: o deserto quase sem água (um oásis raro)."""
    return 5 if biome == 'deserto' else 20

LEGACY_AMPLITUDE = 6.0
MAX_AMPLITUDE = 8.0            # com planície 0
BASE_FREQUENCY = 1 / 24
SAMPLE_RADIUS = 96             # o nível do mar sai das alturas deste quadrado em volta do começo
SAMPLE_STEP = 3
DUNE_AMPLITUDE = 1.3
DUNE_FREQUENCY = 0.7


def defaults() -> Dict[str, Any]:
    return dict({key: default for key, _, default, _ in OPTIONS}, bioma=DEFAULT_BIOME)


def clean(options: Optional[Mapping[str, Any]]) -> Optional[Dict[str, int]]:
    """As opções válidas (inteiros de 0 a 100, as que faltam no padrão); None continua None (o gerador de sempre)."""
    if options is None:
        return None
    out = defaults()
    biome = options.get('bioma', DEFAULT_BIOME)
    out['bioma'] = biome if biome in BIOMES else DEFAULT_BIOME
    for key in KEYS:
        try:
            value = round(float(options.get(key, out[key])))
        except (TypeError, ValueError):
            continue
        out[key] = max(0, min(100, value))
    return out


def sea_level_for(heights: np.ndarray, share: float) -> int:
    """O nível do mar que deixa ``share`` (0 a 1) das colunas embaixo d'água (a água cobre quem fica abaixo dele)."""
    heights = np.asarray(heights).ravel()
    low, high = int(heights.min()), int(heights.max()) + 1
    levels = np.arange(low, high + 1)
    covered = np.array([(heights < level).mean() for level in levels])
    return int(levels[int(np.argmin(np.abs(covered - share)))])


@lru_cache(maxsize=64)
def _settings(seed: int, options_key: str) -> tuple:
    from src.world.terrain import TerrainGenerator
    options = json.loads(options_key)
    amplitude = MAX_AMPLITUDE * (1 - options['planicie'] / 100)
    frequency = BASE_FREQUENCY * 2 ** ((50 - options['relevo']) / 50)
    if options.get('bioma') == 'deserto':      # dunas: mais altas e mais largas que os morros da planície
        amplitude *= DUNE_AMPLITUDE
        frequency *= DUNE_FREQUENCY
    shape = TerrainGenerator(seed=seed, amplitude=amplitude, frequency=frequency)
    grid = np.arange(-SAMPLE_RADIUS, SAMPLE_RADIUS + 1, SAMPLE_STEP)
    sea_level = sea_level_for(shape.heights(grid[:, None], grid[None, :]), options['agua'] / 100)
    return (('amplitude', amplitude), ('frequency', frequency), ('sea_level', sea_level),
            ('enable_caves', options['cavernas'] > 0), ('cave_chance', options['cavernas'] / 100),
            ('vegetation_density', options['vegetacao'] / 50), ('biome', options.get('bioma', DEFAULT_BIOME)))


def generator_settings(seed: int, options: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Os argumentos do ``TerrainGenerator`` (além da seed) para estas opções."""
    options = clean(options)
    if options is None:
        return {'enable_caves': True}
    return dict(_settings(int(seed), json.dumps(options, sort_keys=True)))


def make_generator(seed: int, options: Optional[Mapping[str, Any]] = None, vegetation: bool = True):
    """O gerador do mundo: a seed e as opções de criação (None: o de sempre)."""
    from src.world.terrain import TerrainGenerator
    return TerrainGenerator(seed=seed, vegetation=vegetation, **generator_settings(seed, options))
