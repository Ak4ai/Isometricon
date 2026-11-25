"""Sombras do sol: a textura 3D dos blocos sólidos ao redor do jogador, para o shader lançar raios.

O shader do mundo, para cada pixel, anda de ``u_ShadowSteps`` passos na direção do sol e olha, nesta textura,
se há um bloco no caminho. A janela é a mesma de ``src/world/room_reveal.py`` (48x32x48 células em volta do
jogador), então não custa uma varredura nova: usa-se a janela que o rastreador já calculou.

Com a distância das sombras acima de 1 chunk (Configurações > Gráficos), a janela é outra, maior e só das sombras
(``far_window_size``): lida dos chunks carregados numa thread, refeita quando o jogador se afasta do meio dela ou o
mundo muda.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

import numpy as np
import OpenGL.GL as gl

from src.world.block import BlockType
from src.world.room_reveal import WINDOW, RoomRevealTracker, extract_window_cells
from src.world.shadow_shapes import TABLE

SHADOW_UNIT = 3  # unidade de textura da máscara de sombra (0 atlas, 2 máscara do espaço)
HORIZON_UNIT = 4  # unidade do mapa de alturas por quadrante (column_horizons)
SHAPES_UNIT = 10  # unidade da tabela das formas dos blocos parciais (shadow_shapes)
PLANTS_UNIT = 11  # unidade dos desenhos das plantas (shadow_shapes.plant_masks)
SHAPE_IDS_UNIT = 12  # unidade da textura 3D com o número da forma de cada célula parcial
EMPTY_UNIT = 14      # unidade da textura 3D do ar vazio em volta de cada célula (empty_distances)
EMPTY_MAX = 8        # o maior pulo do raio, em células


SOFT_SPREAD = 0.15  # o raio do disco do cone borrado do shader (softSun); a nítida (0.08) cabe dentro dele
# na textura (um byte por célula, que o raio lê a cada passo): o shader lê sólido > 0.94, parcial (laje, cerca, placa)
# entre 0.82 e 0.94, planta em cruz entre 0.70 e 0.82 e água entre 0.25 e 0.6. O número da forma dos parciais e das
# plantas (shadow_shapes) fica noutra textura, lida só nessas células
SOLID_VALUE, PARTIAL_VALUE, PLANT_VALUE, WATER_VALUE = 255, 224, 192, 128


# O detalhe da sombra (Configurações > Gráficos), do mais leve ao mais pesado
DETAIL_CUBES, DETAIL_SHAPES, DETAIL_PLANTS, DETAIL_FULL = 0, 1, 2, 3
# O capim: está em quase todo bloco de grama, e contando como obstáculo sobe o mapa de alturas das colunas
# (column_horizons) em um bloco no chão todo; o raio de cada pixel do chão, que parava no primeiro passo, tem de
# andar várias células. Só no detalhe completo. Vale para a cobertura do chão de todo bioma: na taiga são as
# samambaias e o arbusto de frutinhas (deixá-los de fora custava ~1 ms por quadro a mais que na planície).
HEAVY_PLANTS = ("minecraft:short_grass", "minecraft:fern", "minecraft:large_fern[half=lower]",
                "minecraft:large_fern[half=upper]", "minecraft:sweet_berry_bush[age=3]")


def detail_shapes(shapes: np.ndarray, detail: int) -> np.ndarray:
    """As formas que contam no nível de detalhe: nenhuma no leve (os sólidos viram cubos inteiros, como antes),
    sem plantas nas formas, sem o capim nas plantas, tudo no completo."""
    if detail <= DETAIL_CUBES:
        return np.zeros_like(shapes)
    flags = TABLE.plant_flags()
    if detail == DETAIL_SHAPES:
        return np.where(flags[shapes], 0, shapes).astype(shapes.dtype)
    if detail == DETAIL_PLANTS:
        heavy = [TABLE.id_for(name) for name in HEAVY_PLANTS]
        return np.where(np.isin(shapes, heavy), 0, shapes).astype(shapes.dtype)
    return shapes


def mask_values(window, detail: int = DETAIL_FULL) -> np.ndarray:
    """O valor de cada célula da janela: sólido (bloqueia o sol), parcial, planta, água (a luz atravessa tingida)
    ou ar."""
    values = np.where(window.solid, SOLID_VALUE, 0).astype(np.uint8)
    values[(window.blocks == int(BlockType.WATER)) & ~window.solid] = WATER_VALUE
    shapes = getattr(window, 'shapes', None)
    if shapes is not None:
        shapes = detail_shapes(shapes, detail)
        values[shapes != 0] = PARTIAL_VALUE      # sólido ou não (a placa, a tocha): tapa só onde tem caixa
        values[TABLE.plant_flags()[shapes]] = PLANT_VALUE
    return values


def shape_texels(window, detail: int = DETAIL_FULL) -> np.ndarray:
    """[x, y, z, 2]: o número da forma de cada célula parcial ou planta (byte de baixo, byte de cima); 0 no resto."""
    shapes = getattr(window, 'shapes', None)
    shape = (detail_shapes(shapes, detail).astype(np.uint16) if shapes is not None
             else np.zeros(window.solid.shape, np.uint16))
    return np.stack([(shape & 0xFF).astype(np.uint8), (shape >> 8).astype(np.uint8)], axis=-1)


def quadrant_channel(step_x: int, step_z: int) -> int:
    """O canal de ``column_horizons`` do rumo do raio: 0 (+x +z), 1 (+x -z), 2 (-x +z), 3 (-x -z)."""
    return (0 if step_x > 0 else 2) + (0 if step_z > 0 else 1)


def column_horizons(values: np.ndarray, rise: float = 0.0) -> np.ndarray:
    """Para cada coluna (x, z) e cada quadrante de rumo, a altura a partir da qual o raio do sol já não encontra mais
    nada: ``values`` é [x, y, z]; o resultado é [x, z, 4], inteiros >= 0.

    O raio anda sempre no mesmo sentido em x e em z, então só visita colunas do seu quadrante à frente; e, se sobe
    pelo menos ``rise`` por célula andada no plano, chega a uma coluna a uma distância d já ``rise * d`` mais alto.
    Uma coluna q à frente de p só o tapa se a célula ocupada (sólido ou água) mais alta dela, H(q), fica na altura em
    que ele passa por ela. Estando na célula de altura y >= o valor de p, nenhuma tapa: o shader para ali, com a mesma
    luz que teria no fim do caminho. Com ``rise`` 0 o valor é só 1 + o H mais alto do quadrante.

    A distância no plano entre as células p e q é pelo menos ((|dx| - 1)+ + (|dz| - 1)+) / raiz(2) (a soma das folgas
    em cada eixo); com ela o máximo fica separável: um máximo com desconto em x e depois em z.
    """
    filled = values > 0
    heights = np.arange(values.shape[1], dtype=np.int32)[None, :, None]
    tops = np.where(filled, heights, -1).max(axis=1).astype(np.float64) + 1.0      # [x, z]: H + 1 (0 vazia)
    k = max(float(rise), 0.0) / np.sqrt(2.0)                                       # desconto por célula de folga

    def ahead_max(v: np.ndarray, axis: int, forward: bool) -> np.ndarray:
        """max sobre j à frente de i (j >= i se ``forward``) de v[j] - k * (|j - i| - 1)+, ao longo de ``axis``."""
        index = np.arange(v.shape[axis], dtype=np.float64)
        index = index[:, None] if axis == 0 else index[None, :]
        if forward:   # g(i) = max_{j >= i} v[j] - k (j - i); o resultado é max(v[i], g(i + 1))
            g = np.flip(np.maximum.accumulate(np.flip(v - k * index, axis), axis=axis), axis) + k * index
            nxt = np.concatenate([np.take(g, range(1, v.shape[axis]), axis=axis),
                                  np.full_like(np.take(g, [0], axis=axis), -np.inf)], axis=axis)
        else:         # g(i) = max_{j <= i} v[j] - k (i - j); o resultado é max(v[i], g(i - 1))
            g = np.maximum.accumulate(v + k * index, axis=axis) - k * index
            nxt = np.concatenate([np.full_like(np.take(g, [0], axis=axis), -np.inf),
                                  np.take(g, range(0, v.shape[axis] - 1), axis=axis)], axis=axis)
        return np.maximum(v, nxt)

    out = np.empty(tops.shape + (4,), dtype=np.int32)
    for step_x in (1, -1):
        along_x = ahead_max(tops, 0, step_x > 0)
        for step_z in (1, -1):
            bound = ahead_max(along_x, 1, step_z > 0)
            out[..., quadrant_channel(step_x, step_z)] = np.clip(np.ceil(bound - 1e-9), 0, 255)
    return out


def cone_rise(sun_direction, spread: float = SOFT_SPREAD) -> float:
    """A menor subida por célula andada no plano (dy / |dxz|) entre os raios do cone em volta de ``sun_direction``,
    com uma folga; 0 se o cone chega ao horizonte. O shader confere de novo, raio a raio (ver traceSun)."""
    sun = np.asarray(sun_direction, dtype=np.float64)
    sun = sun / np.linalg.norm(sun)
    t1 = np.cross(sun, (0.0, 1.0, 0.0))
    if np.linalg.norm(t1) < 1e-6:
        return 0.0
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(sun, t1)
    angles = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)[:, None]
    rays = sun + (t1 * np.cos(angles) + t2 * np.sin(angles)) * spread
    rise = rays[:, 1] / np.maximum(np.linalg.norm(rays[:, [0, 2]], axis=1), 1e-9)
    return max(float(rise.min()) * 0.98, 0.0)


FAR_HEIGHT = 56        # a altura da janela grande (as sequoias passam de 30 blocos)
FAR_BELOW = 16         # células dela abaixo do pé do jogador
FAR_RECENTER = 8       # o jogador andou isto do meio dela: refaz
FAR_MIN_INTERVAL = 0.5  # segundos entre duas leituras por o mundo ter mudado


def far_window_size(distance: int) -> Tuple[int, int, int]:
    """O tamanho da janela das sombras para ``distance`` chunks em volta: 1 é a janela do cômodo (48 x 48); cada
    chunk a mais soma 16 blocos para cada lado."""
    distance = max(1, int(distance))
    if distance == 1:
        return WINDOW
    side = WINDOW[0] + 32 * (distance - 1)
    return side, FAR_HEIGHT, side


def far_window_origin(position, size) -> Tuple[int, int, int]:
    x, y, z = (int(np.floor(float(v))) for v in position)
    return x - size[0] // 2, y - FAR_BELOW, z - size[2] // 2


def empty_distances(values: np.ndarray, cap: int = EMPTY_MAX) -> np.ndarray:
    """[x, y, z] uint8: para cada célula, o maior n (até ``cap``) tal que o cubo de células a menos de n passos dela em
    x, y e z (distância de Chebyshev) só tem ar. 0 numa célula ocupada (sólido, parcial, planta ou água: o raio tem de
    passar por ela célula a célula). Fora da janela conta como ar (o sol está livre lá)."""
    from scipy.ndimage import distance_transform_cdt
    occupied = values > 0
    if not occupied.any():
        return np.full(values.shape, cap, dtype=np.uint8)
    distance = distance_transform_cdt(~occupied, metric='chessboard')
    return np.minimum(distance, cap).astype(np.uint8)


def prepare_window(window, detail: int, rise: float):
    """O que sobe para a GPU, no formato das texturas: a máscara (z, y, x), os números das formas (z, y, x, 2), os
    horizontes das colunas (z, x, 4) e o ar vazio em volta de cada célula (z, y, x)."""
    values = mask_values(window, detail)
    data = np.ascontiguousarray(values.transpose(2, 1, 0))
    ids = np.ascontiguousarray(shape_texels(window, detail).transpose(2, 1, 0, 3))
    horizons = np.ascontiguousarray(column_horizons(values, rise).astype(np.uint8).transpose(1, 0, 2))
    empty = np.ascontiguousarray(empty_distances(values).transpose(2, 1, 0))
    return data, ids, horizons, empty


class SunShadowRenderer:
    """Mantém a textura de blocos sólidos e os uniforms das sombras."""

    def __init__(self, strength: float = 1.0, sun_direction=(0.55, 0.26, 0.7)) -> None:
        self.enabled = True
        self.sun_direction = tuple(float(v) for v in sun_direction)   # o u_LightDir do terreno (cast_shadow usa)
        # a subida mínima dos raios do sol (o u_LightDir do terreno, girado só em torno de y: a elevação não muda);
        # se o sol for outro, o shader só deixa de usar o atalho nos raios que sobem menos
        self.rise = cone_rise(sun_direction)
        self.quality = 2   # 0 baixa (um raio), 1 média, 2 alta: ver u_ShadowQuality no shader
        self.detail = DETAIL_PLANTS  # o que faz sombra pela forma (ver set_detail)
        self.steps = 56    # até quantas células o raio procura o que tapa o sol
        self.strength = float(strength)  # 0 sem sombra, 1 sombra inteira
        self.texture_id = 0
        self.horizon_id = 0  # textura 2D RGBA: column_horizons + 1, um quadrante por canal
        self.shapes_id = 0   # textura 2D RGBA32F: a tabela das formas (shadow_shapes.TABLE)
        self.plants_id = 0   # textura 2D R8: os desenhos das plantas
        self.shape_ids_id = 0  # textura 3D RG8: o número da forma de cada célula parcial
        self.empty_id = 0      # textura 3D R8: o ar vazio em volta de cada célula (empty_distances)
        self._shapes_revision = -1
        self._uploaded = None  # as células da janela que estão na GPU
        self._origin = (0, 0, 0)
        self._size = WINDOW    # o tamanho da janela na GPU (as texturas são alocadas nele)
        self.distance = 1      # chunks em volta do jogador com sombra (1: a janela do cômodo)
        self._executor = None  # a leitura da janela grande, fora do quadro
        self._job = None
        self._far_key = None   # (distância, detalhe, origem, revisão do mundo, construções) da janela grande pronta
        self._far_time = -1e9

    def set_detail(self, detail: int, shader=None) -> None:
        """Troca o detalhe da sombra: refaz a máscara e, se dado o shader do mundo, troca a variante dele (no leve,
        sem o caminho das formas)."""
        detail = max(DETAIL_CUBES, min(DETAIL_FULL, int(detail)))
        if shader is not None:
            shader.set_define("SHADOW_SHAPES", detail != DETAIL_CUBES)
        if detail != self.detail:
            self.detail = detail
            self._uploaded = None     # a mesma janela, outra máscara
            self._far_key = None

    def set_distance(self, distance: int) -> None:
        """Até quantos chunks em volta há sombra (Configurações > Gráficos > Distância das sombras)."""
        distance = max(1, min(8, int(distance)))
        if distance != self.distance:
            self.distance = distance
            self._uploaded = None
            self._far_key = None

    def update(self, tracker: RoomRevealTracker, position=None, chunks=None, revision=None, structures=()) -> None:
        """Envia a janela de blocos sólidos para a GPU: a que o rastreador calculou ou, com a distância acima de 1
        chunk (e os chunks dados), a janela grande das sombras."""
        if not self.enabled:
            return
        if self.distance > 1 and chunks is not None and position is not None:
            self._update_far(position, chunks, revision, list(structures))
            return
        mask = tracker.mask
        if mask is None or mask.window is None or mask.window is self._uploaded:
            return
        self._upload(mask.window, mask.origin, WINDOW, *prepare_window(mask.window, self.detail, self.rise))

    def _update_far(self, position, chunks, revision, structures) -> None:
        if self._job is not None:
            if not self._job.done():
                return
            job, self._job = self._job, None
            key, window, origin, size, arrays = job.result()
            if key[:2] == (self.distance, self.detail):
                self._upload(window, origin, size, *arrays)
                self._far_key = key
        size = far_window_size(self.distance)
        built = self._far_key
        x, y, z = (float(v) for v in position)
        if built is not None:
            ox, oy, oz = built[2]
            off = max(abs(x - (ox + size[0] / 2)), abs(z - (oz + size[2] / 2)), abs(y - (oy + FAR_BELOW)))
            same_world = built[3] == revision and built[4] == self._structure_key(structures)
            if off < FAR_RECENTER and (same_world or time.monotonic() - self._far_time < FAR_MIN_INTERVAL):
                return
            origin = built[2] if off < FAR_RECENTER else far_window_origin(position, size)
        else:
            origin = far_window_origin(position, size)
        self._far_time = time.monotonic()
        key = (self.distance, self.detail, origin, revision, self._structure_key(structures))
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sun-shadows")
        detail, rise = self.detail, self.rise

        def build():
            window = extract_window_cells(origin, chunks, structures, size)
            return key, window, origin, size, prepare_window(window, detail, rise)

        self._job = self._executor.submit(build)

    @staticmethod
    def _structure_key(structures):
        return tuple((id(s), s.origin, getattr(s, "revision", 0)) for s in structures)

    def _upload(self, window, origin, size, data, ids, horizons, empty) -> None:
        if tuple(size) != tuple(self._size):
            self.delete()
            self._size = tuple(size)
        self._ensure_texture()
        sx, sy, sz = self._size
        # a janela é [x, y, z]; a textura 3D quer (profundidade z, altura y, largura x)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexSubImage3D(gl.GL_TEXTURE_3D, 0, 0, 0, 0, sx, sy, sz, gl.GL_RED, gl.GL_UNSIGNED_BYTE, data)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHAPE_IDS_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.shape_ids_id)
        gl.glTexSubImage3D(gl.GL_TEXTURE_3D, 0, 0, 0, 0, sx, sy, sz, gl.GL_RG, gl.GL_UNSIGNED_BYTE, ids)
        gl.glActiveTexture(gl.GL_TEXTURE0 + EMPTY_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.empty_id)
        gl.glTexSubImage3D(gl.GL_TEXTURE_3D, 0, 0, 0, 0, sx, sy, sz, gl.GL_RED, gl.GL_UNSIGNED_BYTE, empty)
        # [x, z, 4] -> a textura 2D quer (altura z, largura x, canais)
        gl.glActiveTexture(gl.GL_TEXTURE0 + HORIZON_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.horizon_id)
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, sx, sz, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, horizons)
        if TABLE.revision != self._shapes_revision:
            table = TABLE.texels()
            gl.glActiveTexture(gl.GL_TEXTURE0 + SHAPES_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.shapes_id)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, table.shape[1], table.shape[0], 0, gl.GL_RGBA,
                            gl.GL_FLOAT, table)
            masks = TABLE.plant_masks()
            gl.glActiveTexture(gl.GL_TEXTURE0 + PLANTS_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.plants_id)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_R8, masks.shape[1], masks.shape[0], 0, gl.GL_RED,
                            gl.GL_UNSIGNED_BYTE, masks)
            self._shapes_revision = TABLE.revision
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self._uploaded = window
        self._origin = origin

    def _ensure_texture(self) -> None:
        if self.texture_id:
            return
        self.texture_id = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_3D, name, value)
        sx, sy, sz = self._size
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage3D(gl.GL_TEXTURE_3D, 0, gl.GL_R8, sx, sy, sz, 0, gl.GL_RED, gl.GL_UNSIGNED_BYTE,
                        np.zeros((sz, sy, sx), dtype=np.uint8))
        self.shape_ids_id = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHAPE_IDS_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.shape_ids_id)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_3D, name, value)
        gl.glTexImage3D(gl.GL_TEXTURE_3D, 0, gl.GL_RG8, sx, sy, sz, 0, gl.GL_RG, gl.GL_UNSIGNED_BYTE,
                        np.zeros((sz, sy, sx, 2), dtype=np.uint8))
        self.empty_id = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0 + EMPTY_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.empty_id)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_3D, name, value)
        gl.glTexImage3D(gl.GL_TEXTURE_3D, 0, gl.GL_R8, sx, sy, sz, 0, gl.GL_RED, gl.GL_UNSIGNED_BYTE,
                        np.zeros((sz, sy, sx), dtype=np.uint8))
        self.horizon_id = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0 + HORIZON_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.horizon_id)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, sx, sz, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                        np.zeros((sz, sx, 4), dtype=np.uint8))
        self.shapes_id, self.plants_id = gl.glGenTextures(2)
        for unit, texture in ((SHAPES_UNIT, self.shapes_id), (PLANTS_UNIT, self.plants_id)):
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                                (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    @property
    def active(self) -> bool:
        return self.enabled and self._uploaded is not None

    def apply(self, shader, base_model: np.ndarray) -> None:
        """Liga as sombras no shader do mundo (antes de desenhar o terreno e as construções)."""
        # a água usa a matriz mesmo sem sombras (a normal das ondas vai do mundo para o espaço desenhado)
        inverse_model = np.linalg.inv(np.asarray(base_model, dtype=np.float64)).astype(np.float32)
        shader.set_mat4("u_ShadowInvModel", inverse_model)
        if not self.active:
            shader.set_float("u_ShadowStrength", 0.0)
            return
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0 + HORIZON_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.horizon_id)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHAPES_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.shapes_id)
        gl.glActiveTexture(gl.GL_TEXTURE0 + PLANTS_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.plants_id)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHAPE_IDS_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.shape_ids_id)
        gl.glActiveTexture(gl.GL_TEXTURE0 + EMPTY_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.empty_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        shader.set_int("u_ShadowMask", SHADOW_UNIT)
        shader.set_int("u_ShadowEmpty", EMPTY_UNIT)
        shader.set_int("u_ShadowShapeIds", SHAPE_IDS_UNIT)
        shader.set_int("u_ShadowShapes", SHAPES_UNIT)
        shader.set_int("u_ShadowPlants", PLANTS_UNIT)
        shader.set_int("u_ShadowHorizon", HORIZON_UNIT)
        shader.set_float("u_ShadowHorizonRise", self.rise)
        shader.set_int("u_ShadowSteps", int(self.steps))
        shader.set_int("u_ShadowQuality", int(self.quality))
        shader.set_vec3("u_ShadowOrigin", float(self._origin[0]), float(self._origin[1]), float(self._origin[2]))
        shader.set_vec3("u_ShadowSize", *(float(v) for v in self._size))
        shader.set_float("u_ShadowStrength", self.strength)

    @staticmethod
    def disable(shader) -> None:
        shader.set_float("u_ShadowStrength", 0.0)

    def delete(self) -> None:
        if self.texture_id:
            ids = [t for t in (self.texture_id, self.horizon_id, self.shape_ids_id, self.shapes_id, self.plants_id,
                               self.empty_id) if t]
            gl.glDeleteTextures(len(ids), ids)
            self.texture_id = self.horizon_id = self.shape_ids_id = self.shapes_id = self.plants_id = 0
            self.empty_id = 0
            self._shapes_revision = -1
        self._uploaded = None

    def shutdown(self) -> None:
        self.delete()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
