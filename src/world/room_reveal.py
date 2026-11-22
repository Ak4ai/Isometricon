"""Descobre o espaço fechado em que o jogador está (cômodo, caverna) para revelá-lo.

Sem OpenGL. A cada recálculo:

1. copia para uma janela de 48x32x48 células o que é sólido (chunks do terreno e construções);
2. marca as células com "teto" (algo estrutural acima delas) e separa o ar coberto do ar aberto ao céu;
3. inunda o ar coberto a partir do jogador (o fluxo para onde o céu começa, que é o lado de fora);
4. decide se é um espaço fechado de verdade: pouco aberto ao céu (um cômodo com paredes), ou com teto baixo
   cobrindo quase tudo em volta do jogador, mesmo de lados abertos (debaixo de um deck, de um alpendre fundo).
   É o critério do Isocraft (``StructuralRoomClassifier``): a "sala de frente aberta" entra com 80% de teto e
   só sai abaixo de 45%; um beiral estreito ou uma marquise não chegam lá;
5. devolve uma máscara: 255 no espaço do jogador, 128 na casca de 1 bloco de sólido ao redor (pelas faces), 64 no
   sólido que encosta só pela quina (cantos, a parede atrás de um piso), 0 no resto.

O shader usa a máscara para escurecer o que está fora e remover o que tapa a vista do espaço.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
from scipy import ndimage

from src.world.block import SHAPED_BLOCK_NAMES, SHAPED_LUT, BlockType
from src.world.chunk import Chunk3D

WINDOW = (48, 32, 48)          # células em x, y, z
BELOW_PLAYER = 10              # células da janela abaixo do pé do jogador
MIN_SPACE_CELLS = 6            # um vão menor que isso não é cômodo
ENTER_EXPOSURE = 0.20          # fração do espaço aberta ao céu: abaixo disso passa a ser "dentro"
RETAIN_EXPOSURE = 0.35         # e só deixa de ser "dentro" acima disto (histerese)
ROOF_RADIUS = 4                # raio (células, no plano) em volta do jogador onde se mede a cobertura do teto
ROOF_REACH = 8                 # o teto conta até tantas células acima da cabeça
ENTER_ROOF_COVERAGE = 0.80     # com tanto teto em volta é "dentro", mesmo com os lados abertos (Isocraft)
RETAIN_ROOF_COVERAGE = 0.45    # e deixa de ser abaixo disto
MIN_WALL_COVERAGE = 0.1875     # e precisa de alguma parede em volta: uma laje solta (marquise) não é cômodo
WALL_RAYS = 16                 # raios horizontais que procuram parede em volta do jogador
WALL_REACH = 8                 # até onde cada raio procura
INTERIOR = 255
SHELL = 128
EDGE = 64                      # sólido que só encosta no espaço pela quina: iluminado como o cômodo
OBJECT = 192                   # sólido com o espaço logo acima (móvel, degrau, piso): não é parede, não some na frente

# Blocos que não contam como teto (a copa de uma árvore não faz um cômodo)
_NOT_ROOF = (int(BlockType.LEAVES),)
_OPAQUE = tuple(int(b) for b in (BlockType.DIRT, BlockType.GRASS, BlockType.STONE, BlockType.WOOD))
# O que o personagem atravessa: ar, água e os enfeites com forma (plantas, tochas, escadas de mão, fogo)
_PASSABLE = (int(BlockType.AIR), int(BlockType.WATER), *(int(b) for b in SHAPED_BLOCK_NAMES))

_FACE_STRUCTURE = ndimage.generate_binary_structure(3, 1)  # vizinhança de 6 faces
_FULL_STRUCTURE = ndimage.generate_binary_structure(3, 3)  # as 26 vizinhas (faces, arestas e quinas)


@dataclass
class RoomMask:
    """Resultado de um cálculo: a máscara e o que se sabe sobre o espaço."""

    origin: Tuple[int, int, int]   # célula do mundo do canto (0, 0, 0) da janela
    data: np.ndarray               # uint8 [x, y, z]
    active: bool                   # o jogador está num espaço fechado
    cells: int                     # células de ar do espaço do jogador
    exposure: float                # fração delas aberta ao céu
    roof_coverage: float = 0.0     # fração das colunas em volta do jogador com teto baixo (ou parede)
    wall_coverage: float = 0.0     # fração dos raios horizontais que batem numa parede
    window: Optional["WindowCells"] = None  # o que há em cada célula (preenchido pelo rastreador)
    # (x, z) do mundo da porta em que o jogador estava parado: ela não contou, e o espaço pode ter juntado os dois
    # cômodos que ela separa; só vale enquanto ele está nessa coluna (ver RoomRevealTracker._same_room)
    door_column: Optional[Tuple[int, int]] = None


def window_origin(position) -> Tuple[int, int, int]:
    """Canto mínimo da janela: o jogador fica no meio de x/z e com algumas células abaixo."""
    x, y, z = (int(np.floor(float(v))) for v in position)
    return x - WINDOW[0] // 2, y - BELOW_PLAYER, z - WINDOW[2] // 2


@dataclass
class WindowCells:
    """O que há em cada célula da janela, todos os arrays indexados [x, y, z]."""

    solid: np.ndarray       # bool: o personagem não atravessa (tudo menos ar e água)
    roof: np.ndarray        # bool: sólido que fecha um espaço por cima (sem a folhagem)
    blocks: np.ndarray      # uint8: BlockType do terreno (0 onde só há construção)
    owner: np.ndarray       # int8: -1 terreno ou ar; i = índice da construção que ocupa a célula
    structures: list        # as construções, na ordem dos índices de ``owner``
    occupied: np.ndarray    # bool: há algo desenhado na célula (um sólido, ou um enfeite como tocha e tapete)
    culls: np.ndarray       # bool: cubo inteiro e opaco, o único que esconde a face do vizinho
    doors: Optional[np.ndarray] = None  # bool: portas das construções (abertas ou não): cada cômodo termina nelas
    details: Optional[np.ndarray] = None  # bool: móveis e enfeites das construções (ficam na casa de bonecas)
    shapes: Optional[np.ndarray] = None   # uint16: nos blocos das construções que não são cubo inteiro (laje, degrau,
                                          # cerca, placa), o número da forma deles (ver shadow_shapes); 0 no resto


def extract_window(
    origin: Tuple[int, int, int],
    chunks: Dict[Tuple[int, int, int], Chunk3D],
    structures: Iterable = (),
) -> Tuple[np.ndarray, np.ndarray]:
    """Devolve (sólido, teto) da janela, ambos bool [x, y, z]; ver ``extract_window_cells``."""
    cells = extract_window_cells(origin, chunks, structures)
    return cells.solid, cells.roof


def extract_window_cells(
    origin: Tuple[int, int, int],
    chunks: Dict[Tuple[int, int, int], Chunk3D],
    structures: Iterable = (),
) -> WindowCells:
    """Copia para a janela o que é sólido no terreno e nas construções.

    Sólido é o que o personagem não atravessa (tudo menos ar e água); teto é o sólido que fecha
    um espaço por cima (sólido sem a folhagem). Abaixo de y = 0 é o chão do mundo, sólido.
    """
    structures = list(structures)
    ox, oy, oz = origin
    sx, sy, sz = WINDOW
    blocks = np.zeros(WINDOW, dtype=np.uint8)
    size = Chunk3D.SIZE
    for (cx, cy, cz), chunk in chunks.items():
        x0, y0, z0 = cx * size, cy * size, cz * size
        lo = (max(ox, x0), max(oy, y0), max(oz, z0))
        hi = (min(ox + sx, x0 + size), min(oy + sy, y0 + size), min(oz + sz, z0 + size))
        if any(h <= l for l, h in zip(lo, hi)):
            continue
        src = chunk.blocks[lo[0] - x0:hi[0] - x0, lo[1] - y0:hi[1] - y0, lo[2] - z0:hi[2] - z0]
        blocks[lo[0] - ox:hi[0] - ox, lo[1] - oy:hi[1] - oy, lo[2] - oz:hi[2] - oz] = src

    solid = ~np.isin(blocks, _PASSABLE)
    roof = solid & ~np.isin(blocks, _NOT_ROOF)
    owner = np.full(WINDOW, -1, dtype=np.int8)
    culls = np.isin(blocks, _OPAQUE)

    floor_rows = max(0, min(sy, -oy))  # as camadas com y < 0
    if floor_rows:
        solid[:, :floor_rows, :] = True
        roof[:, :floor_rows, :] = True
        culls[:, :floor_rows, :] = True
    occupied = solid | SHAPED_LUT[blocks]   # os enfeites do terreno são desenhados, mas não são parede
    details = np.zeros(WINDOW, dtype=bool)
    from src.world.shadow_shapes import terrain_shapes
    shapes = terrain_shapes()[blocks]      # os enfeites do terreno (capim, flores, tocha) também fazem sombra
    terrain_solid = solid.copy()

    for index, placed in enumerate(structures):
        (bx0, by0, bz0), (bx1, by1, bz1) = placed.bounds()
        lo = (max(ox, bx0), max(oy, by0), max(oz, bz0))
        hi = (min(ox + sx, bx1 + 1), min(oy + sy, by1 + 1), min(oz + sz, bz1 + 1))
        if any(h <= l for l, h in zip(lo, hi)):
            continue
        # a máscara da construção é [y, z, x]; a janela é [x, y, z]
        window = (slice(lo[1] - by0, hi[1] - by0), slice(lo[2] - bz0, hi[2] - bz0), slice(lo[0] - bx0, hi[0] - bx0))
        part = placed._solid[window].transpose(2, 0, 1)
        shown = placed._occupied[window].transpose(2, 0, 1)
        cube = placed._culls[window].transpose(2, 0, 1)
        detail = placed.schematic.detail_mask[window].transpose(2, 0, 1)
        shape = placed.schematic.shadow_shape_mask[window].transpose(2, 0, 1)
        sel = (slice(lo[0] - ox, hi[0] - ox), slice(lo[1] - oy, hi[1] - oy), slice(lo[2] - oz, hi[2] - oz))
        solid[sel] |= part
        roof[sel] |= part
        occupied[sel] |= shown
        culls[sel] |= cube
        details[sel] |= detail
        shapes[sel] = np.where(shape != 0, shape, shapes[sel])
        owner[sel][shown] = index
    shapes[terrain_solid | culls] = 0     # um cubo inteiro na mesma célula (do terreno ou de outra construção) vence
    return WindowCells(solid, roof, blocks, owner, structures, occupied, culls, _door_cells(owner, structures, origin),
                       details, shapes)


def _door_cells(owner: np.ndarray, structures, origin) -> np.ndarray:
    """As células da janela ocupadas por portas das construções."""
    doors = np.zeros(owner.shape, dtype=bool)
    for index, placed in enumerate(structures):
        cells = np.argwhere(owner == index)
        if len(cells) == 0:
            continue
        local = cells + np.asarray(origin) - np.asarray(placed.origin)
        marks = placed.schematic.door_mask[local[:, 1], local[:, 2], local[:, 0]]
        doors[tuple(cells[marks].T)] = True
    return doors


def _covered(roof: np.ndarray) -> np.ndarray:
    """True nas células com teto em algum ponto acima delas (dentro da janela)."""
    from_here_up = np.logical_or.accumulate(roof[:, ::-1, :], axis=1)[:, ::-1, :]
    covered = np.zeros_like(roof)
    covered[:, :-1, :] = from_here_up[:, 1:, :]
    return covered


def compute_room(
    solid: np.ndarray,
    roof: np.ndarray,
    origin: Tuple[int, int, int],
    position,
    was_active: bool = False,
    doors: Optional[np.ndarray] = None,
    details: Optional[np.ndarray] = None,
) -> RoomMask:
    """Calcula a máscara do espaço em que o jogador (posição dos pés) está.

    ``doors``: as portas fecham o cômodo mesmo abertas (a sala ao lado, pela porta aberta, é outro cômodo e a
    parede entre as duas fica); só a porta em que o jogador está parado não conta."""
    mask = np.zeros(WINDOW, dtype=np.uint8)
    outside = RoomMask(origin, mask, False, 0, 1.0)

    cell = [int(np.floor(float(v))) - o for v, o in zip(position, origin)]
    if not all(0 <= c < s for c, s in zip(cell, WINDOW)):
        return outside
    # o pé pode estar dentro do bloco do piso: sobe até achar ar
    while cell[1] < WINDOW[1] - 1 and solid[cell[0], cell[1], cell[2]]:
        cell[1] += 1
    seed = tuple(cell)
    if solid[seed]:
        return outside
    door_column = None
    if doors is not None and doors.any():
        if doors[seed[0], :, seed[2]].any():
            door_column = (seed[0] + origin[0], seed[2] + origin[2])
        doors = doors.copy()
        doors[seed[0], :, seed[2]] = False
        solid = solid | doors

    covered = _covered(roof)
    air = ~solid
    if not covered[seed]:
        return outside  # céu aberto sobre a cabeça: ao ar livre

    # o espaço é o ar com teto ligado ao jogador; o ar sem teto é o lado de fora e para a inundação
    labels, _ = ndimage.label(air & covered, structure=_FACE_STRUCTURE)
    space = labels == labels[seed]
    cells = int(space.sum())

    sky_air = air & ~covered
    leaks = space & ndimage.binary_dilation(sky_air, structure=_FACE_STRUCTURE)
    exposure = float(leaks.sum()) / max(cells, 1)

    coverage = roof_coverage(solid, roof, seed)
    walls = wall_coverage(solid, seed)
    limit = RETAIN_EXPOSURE if was_active else ENTER_EXPOSURE
    roof_limit = RETAIN_ROOF_COVERAGE if was_active else ENTER_ROOF_COVERAGE
    open_front = coverage >= roof_limit and walls >= MIN_WALL_COVERAGE
    active = cells >= MIN_SPACE_CELLS and (exposure < limit or open_front)

    if active and exposure < limit:
        # um vão de porta sem a porta (ou uma janela sem vidro) é ar com teto colado ao céu: o cômodo termina nele,
        # como termina numa porta de verdade. Sem isso o vão entra no espaço do jogador e a parede em volta dele, que
        # "tapa" esse vão na vista da câmera, some junto: o buraco cresce além da porta. (O espaço aberto, como uma
        # varanda, vale pela cobertura e fica como está; a coluna do jogador também: quem está no vão está no cômodo.)
        doorway = leaks.copy()
        doorway[seed[0], :, seed[2]] = False
        space = space & ~doorway
    if active:
        # a borda: o sólido que encosta no espaço também pela quina (o canto da parede, a parede atrás do piso de
        # um mezanino ou na altura do teto). Só ilumina como o cômodo; o corte continua vendo a casca de faces.
        edge = ndimage.binary_dilation(space, structure=_FULL_STRUCTURE) & solid
        mask[edge] = EDGE
        shell = ndimage.binary_dilation(space, structure=_FACE_STRUCTURE) & solid
        mask[shell] = SHELL
        mask[space] = INTERIOR
        mask[(mask > 0) & (mask < INTERIOR) & _space_above_run(solid, space)] = OBJECT
        if details is not None:
            # os detalhes da casa (barril, baú, lanterna, alçapão...) encostados no cômodo também são móveis: a
            # casa de bonecas tira a parede da frente, não o que está dentro (o corredor de visão ainda os tira
            # quando tapam o personagem)
            mask[(mask > 0) & (mask < INTERIOR) & details] = OBJECT
    return RoomMask(origin, mask, active, cells, exposure, coverage, walls, door_column=door_column)


def _space_above_run(solid: np.ndarray, space: np.ndarray) -> np.ndarray:
    """Para cada célula: subindo pela coluna de sólidos dela, a primeira célula livre é o espaço do jogador.

    Separa o que está dentro do cômodo (móvel, degrau da escada, o piso) da parede: a parede termina no telhado
    ou no lado de fora, nunca com o cômodo em cima."""
    out = np.zeros(solid.shape, dtype=bool)
    above = np.zeros((solid.shape[0], solid.shape[2]), dtype=bool)  # o que vem em cima da célula y
    for y in range(solid.shape[1] - 1, -1, -1):
        out[:, y, :] = above
        above = np.where(solid[:, y, :], above, space[:, y, :])
    return out


def wall_coverage(solid: np.ndarray, seed) -> float:
    """Fração de ``WALL_RAYS`` raios horizontais, saindo dos pés, que batem num sólido (na altura dos pés ou da
    cabeça) em até ``WALL_REACH`` células: paredes, pilares, um tronco, o barranco."""
    x0, y0, z0 = seed
    head = min(y0 + 1, WINDOW[1] - 1)
    hits = 0
    for i in range(WALL_RAYS):
        angle = 2.0 * np.pi * i / WALL_RAYS
        dx, dz = float(np.cos(angle)), float(np.sin(angle))
        for step in range(1, 2 * WALL_REACH + 1):
            t = step * 0.5
            x, z = int(np.floor(x0 + 0.5 + dx * t)), int(np.floor(z0 + 0.5 + dz * t))
            if not (0 <= x < WINDOW[0] and 0 <= z < WINDOW[2]):
                break
            if solid[x, y0, z] or solid[x, head, z]:
                hits += 1
                break
    return hits / WALL_RAYS


def roof_coverage(solid: np.ndarray, roof: np.ndarray, seed) -> float:
    """Fração das colunas num disco de ``ROOF_RADIUS`` em volta de ``seed`` (o ar dos pés) cobertas.

    Uma coluna está coberta se tem teto acima da cabeça, até ``ROOF_REACH`` células, ou se é parede (sólido na
    altura dos pés ou da cabeça). A folhagem não é teto.
    """
    x0, y0, z0 = seed
    head = y0 + 1
    top = min(WINDOW[1], head + 1 + ROOF_REACH)
    covered = total = 0
    for dx in range(-ROOF_RADIUS, ROOF_RADIUS + 1):
        for dz in range(-ROOF_RADIUS, ROOF_RADIUS + 1):
            if dx * dx + dz * dz > ROOF_RADIUS * ROOF_RADIUS:
                continue
            x, z = x0 + dx, z0 + dz
            if not (0 <= x < WINDOW[0] and 0 <= z < WINDOW[2]):
                continue
            total += 1
            wall = solid[x, y0, z] or (head < WINDOW[1] and solid[x, head, z])
            if wall or roof[x, head + 1:top, z].any():
                covered += 1
    return covered / max(total, 1)


CEILING_RADIUS = 3      # colunas em volta do jogador onde se procura o teto do andar
CEILING_REACH = 10      # o teto do andar conta até tantas células acima da cabeça
FURNITURE_HEIGHT = 2     # o ar de uma coluna do andar pode começar até tantas células acima dos pés (móveis)
STORY_MIN_COVERAGE = 0.45  # só há "andar" com teto em boa parte da volta (um galho ou uma viga não fazem andar)


def story_ceiling(mask: RoomMask, position) -> Optional[int]:
    """A célula y (mundo) do teto do andar do jogador: o separador de cima do Isocraft (``StoryBand``).

    É o teto mais comum do cômodo: para cada coluna do espaço do jogador, o primeiro teto acima da cabeça com o
    espaço logo embaixo; vale a altura que mais colunas têm (no empate, a mais alta). Assim o corte é o mesmo em
    qualquer ponto do cômodo, e uma viga, um rebaixo ou a verga de uma porta não o fazem descer (nem um vão de
    pé-direito duplo o faz subir). Tudo dali para cima, em volta dele, pode sumir para mostrar o andar.

    Fora de um cômodo fechado (debaixo de uma cobertura), vale o teto mais baixo em volta do jogador. ``None`` ao
    ar livre, ou se o teto é pouco (menos que ``STORY_MIN_COVERAGE`` das colunas em volta) ou alto demais.
    """
    if mask is None or mask.window is None or mask.roof_coverage < STORY_MIN_COVERAGE:
        return None
    roof = mask.window.roof
    solid = mask.window.solid
    doors = mask.window.doors
    ox, oy, oz = mask.origin
    x0, y0, z0 = (int(np.floor(float(v))) - o for v, o in zip(position, mask.origin))
    if not (0 <= x0 < WINDOW[0] and 0 <= z0 < WINDOW[2] and 0 <= y0 < WINDOW[1]):
        return None
    while y0 < WINDOW[1] - 1 and solid[x0, y0, z0]:
        y0 += 1  # o pé dentro do piso
    first = y0 + 2  # acima da cabeça
    top = min(WINDOW[1], first + CEILING_REACH)
    if first >= top:
        return None
    room = _room_ceiling(mask, y0, first, top)
    if room is not None:
        return oy + room
    best = None
    for dx in range(-CEILING_RADIUS, CEILING_RADIUS + 1):
        for dz in range(-CEILING_RADIUS, CEILING_RADIUS + 1):
            x, z = x0 + dx, z0 + dz
            if not (0 <= x < WINDOW[0] and 0 <= z < WINDOW[2]):
                continue
            if solid[x, y0:first, z].any() or (doors is not None and doors[x, y0:first, z].any()):
                continue  # parede, móvel ou porta na altura do corpo: o que vem em cima não é o teto deste espaço
            hits = np.flatnonzero(roof[x, first:top, z])
            if hits.size and (best is None or hits[0] < best):
                best = int(hits[0])
    return None if best is None else oy + first + best


def _room_ceiling(mask: RoomMask, feet: int, first: int, top: int) -> Optional[int]:
    """O teto mais comum das colunas do cômodo neste andar (y da janela); ``None`` sem cômodo.

    Cada coluna conta pelo ar do cômodo que começa na altura dos pés (ou logo acima, sobre um móvel) e sobe até
    o primeiro bloco: esse bloco, se é teto, é o teto da coluna. O espaço do cômodo pode seguir pela escada até
    outro andar; só o ar que sai deste andar conta, e o teto mais comum deixa de fora o vão da escada."""
    if not mask.active:
        return None
    space = (mask.data == INTERIOR)[:, feet:top, :]
    roof = mask.window.roof[:, feet:top, :]
    starts = space[:, :FURNITURE_HEIGHT + 1, :]
    columns = starts.any(axis=1)
    if not columns.any():
        return None
    start = np.argmax(starts, axis=1)                       # a primeira célula de ar do cômodo da coluna
    rows = np.arange(space.shape[1])[None, :, None]
    above = (rows >= start[:, None, :]) & ~space            # o primeiro bloco depois desse ar
    ends = above.any(axis=1)
    end = np.argmax(above, axis=1)
    hit = np.take_along_axis(roof, end[:, None, :], axis=1)[:, 0, :]
    valid = columns & ends & hit & (feet + end >= first)
    if not valid.any():
        return None
    counts = np.bincount(feet + end[valid])
    return int(np.flatnonzero(counts == counts.max())[-1])


def story_center(mask: RoomMask, feet_y: int, cut_y: int):
    """O centro (x, z, no mundo) do cômodo no andar do jogador: a média das células do espaço entre os pés e o
    teto. É a referência de "frente" e "fundo" do corte, e não muda enquanto o jogador anda dentro do cômodo.
    ``None`` se não há espaço."""
    if mask is None or not mask.active:
        return None
    ox, oy, oz = mask.origin
    lo, hi = max(0, feet_y - oy), min(WINDOW[1], cut_y - oy)
    if hi <= lo:
        return None
    cells = np.argwhere(mask.data[:, lo:hi, :] == INTERIOR)
    if len(cells) == 0:
        return None
    return float(cells[:, 0].mean()) + ox + 0.5, float(cells[:, 2].mean()) + oz + 0.5


def _same_window(old: Optional["WindowCells"], new: "WindowCells", origin, old_origin,
                 blocks: bool = True) -> bool:
    """As duas janelas têm o mesmo de tudo o que a máscara e as tampas usam (com ``blocks=False``, sem olhar o tipo
    de cada bloco: a água que corre muda só isso, e a máscara não depende dela)."""
    if old is None or tuple(origin) != tuple(old_origin):
        return False
    return (np.array_equal(old.solid, new.solid) and np.array_equal(old.roof, new.roof)
            and np.array_equal(old.occupied, new.occupied)
            and (not blocks or np.array_equal(old.blocks, new.blocks))
            and np.array_equal(old.owner, new.owner)
            and (old.doors is None) == (new.doors is None)
            and (old.doors is None or np.array_equal(old.doors, new.doors)))


class RoomRevealTracker:
    """Recalcula a máscara quando preciso (o jogador mudou de célula, ou o mundo mudou)."""

    MIN_INTERVAL = 0.25  # segundos entre recálculos do mesmo estado

    def __init__(self, background: bool = False) -> None:
        """
        Args:
            background: calcula o cômodo numa thread à parte; até ficar pronto, ``update`` devolve a máscara
                anterior (o quadro não para os 10-25 ms do cálculo).
        """
        self.mask: Optional[RoomMask] = None
        self.version = 0  # sobe a cada máscara nova (o renderizador reenvia à GPU)
        self._key = None
        self._age = 0.0
        self._executor = None
        self._job = None
        if background:
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="room-reveal")

    @property
    def active(self) -> bool:
        return self.mask is not None and self.mask.active

    REUSE_MARGIN = (8, 3, 8)  # quanto o jogador pode se afastar do ponto de origem da janela sem refazê-la (sobram 16)

    def _same_room(self, cell, mask: Optional[RoomMask] = None) -> bool:
        """A célula nova está no espaço do cômodo ativo, e perto do meio da janela atual."""
        mask = self.mask if mask is None else mask
        if mask is None or not mask.active:
            return False
        if mask.door_column is not None and (cell[0], cell[2]) != mask.door_column:
            return False  # saiu da porta: o espaço (que juntava os dois cômodos) é refeito com ela fechando de novo
        local = [c - o for c, o in zip(cell, mask.origin)]
        if not all(0 <= v < size for v, size in zip(local, WINDOW)):
            return False
        home = (WINDOW[0] // 2, BELOW_PLAYER, WINDOW[2] // 2)  # onde fica o pé de quem abriu a janela
        if any(abs(v - h) > m for v, h, m in zip(local, home, self.REUSE_MARGIN)):
            return False
        return bool(mask.data[local[0], local[1], local[2]] == INTERIOR)

    def reset(self) -> None:
        self.mask, self._key = None, None
        self._job = None  # o resultado de um cálculo em andamento é de antes do reset: fica de fora
        self.version += 1

    def update(self, dt: float, position, chunks, world_revision: int, structures=()) -> RoomMask:
        """Devolve a máscara atual, recalculando se o jogador ou o mundo mudou."""
        structures = list(structures)
        cell = tuple(int(np.floor(float(v))) for v in position)
        key = (cell, world_revision, tuple((id(s), s.origin, getattr(s, "revision", 0)) for s in structures))
        self._age += dt
        if self._job is not None:
            if not self._job.done():
                return self.mask
            job, self._job = self._job, None
            self._adopt(job.result())
        if self.mask is not None and key == self._key:
            return self.mask
        if (self.mask is not None and key[2] == self._key[2] and key[1] == self._key[1]
                and self._same_room(cell)):
            # andou dentro do mesmo cômodo: o espaço é o mesmo (a inundação de qualquer célula dele dá o mesmo
            # resultado)
            self._key = key
            return self.mask
        left_door = self.mask is not None and self.mask.door_column is not None
        if self.mask is not None and self._age < self.MIN_INTERVAL and key[1:] == self._key[1:] and not left_door:
            return self.mask  # só andou: espera o intervalo mínimo (saindo de uma porta não: o cômodo troca já)
        args = (key, cell, tuple(float(v) for v in position), chunks, structures, self.mask, self._key)
        if self._executor is not None:
            self._job = self._executor.submit(self._compute, *args)
            return self.mask
        self._adopt(self._compute(*args))
        return self.mask

    def _compute(self, key, cell, position, chunks, structures, previous: Optional[RoomMask], previous_key):
        """O trabalho pesado (ler a janela do mundo e inundar o cômodo); não mexe no estado do rastreador."""
        if previous is not None and key[2] == previous_key[2] and self._same_room(cell, previous):
            # andou dentro do mesmo cômodo e o mundo mudou (a água correndo longe): confere a janela atual
            fresh = extract_window_cells(previous.origin, chunks, structures)
            if _same_window(previous.window, fresh, previous.origin, previous.origin, blocks=False):
                return "window", key, previous, fresh  # só a água mudou: a janela nova vai para as sombras
        origin = window_origin(position)
        window = extract_window_cells(origin, chunks, structures)
        if previous is not None and key[0] == previous_key[0] and _same_window(previous.window, window, origin,
                                                                                previous.origin, blocks=False):
            return "window", key, previous, window  # o mundo mudou longe ou só a água correu: o cômodo é o mesmo
        mask = compute_room(window.solid, window.roof, origin, position,
                            was_active=previous is not None and previous.active, doors=window.doors,
                            details=window.details)
        mask.window = window
        return "mask", key, mask, window

    def _adopt(self, result) -> None:
        kind, key, mask, window = result
        if kind == "window":
            if mask is not self.mask:
                return  # a máscara mudou enquanto a janela era lida (um reset): o resultado é velho
            mask.window = window
        else:
            self.mask = mask
            self.version += 1
        self._key, self._age = key, 0.0

    def close(self) -> None:
        """Encerra a thread do cálculo em segundo plano (se houver)."""
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
