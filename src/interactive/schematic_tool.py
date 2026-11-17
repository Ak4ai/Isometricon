"""Colocar construções (.schem) no terreno: prévia em holograma, ajuste pelo teclado e fixação.

Fluxo: ``/schem load <nome>`` abre a prévia translúcida na frente do jogador; as setas movem
na horizontal, Shift+↑/↓ muda a altura, Enter fixa (a construção passa a ter colisão) e Esc
cancela. Os comandos do chat chamam ``SchematicTool``; o teclado e o desenho ficam a cargo do
laço principal (``handle_key`` e ``draw``).
"""

import math
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import glfw
import numpy as np

from src.world.block_rotation import rotate_schematic
from src.world.schematic import Schematic
from src.world.structure_layer import BlockLookup, PlacedStructure, StructureLayer
from src.world.structure_mesher import StructureMesher
from src.world.structure_sources import SHOWCASE_NAMES, entry_for_text, load_entry

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMATICS_DIR = os.path.join(PROJECT_ROOT, "assets", "schematics")

ALPHA_HOLOGRAM = 0.45
FRONT_DISTANCE = 3  # blocos entre o jogador e a borda da prévia ao abrir

HELP_TEXT = "Setas movem · Shift+↑/↓ muda a altura · Enter fixa · Esc cancela"


@dataclass
class Preview:
    """A construção que está sendo posicionada."""

    name: str
    schematic: Schematic          # já girada
    mesh: object
    origin: List[int]
    entry: Optional[dict] = None  # de onde veio (para salvar)
    rotation: int = 0
    base: Optional[Schematic] = None  # sem giro: cada volta parte dela


def snap_axis(vector) -> Tuple[int, int]:
    """O eixo X ou Z (com sinal) para onde um vetor horizontal mais aponta: (dx, dz)."""
    x, z = float(vector[0]), float(vector[2])
    if abs(x) >= abs(z):
        return (1 if x >= 0 else -1, 0)
    return (0, 1 if z >= 0 else -1)


class StructureMeshes:
    """As malhas de uma construção: o corpo, que não muda, as portas à parte, refeitas ao abrir ou fechar, e os baús,
    também à parte, refeitos enquanto a tampa de um deles se move."""

    def __init__(self, schematic: Schematic, uv_lookup) -> None:
        from src.rendering.mesh import TexturedMesh
        from src.world.chests import is_chest
        from src.world.doors import is_door

        self.schematic = schematic
        self.uv_lookup = uv_lookup
        names = np.unique(schematic.grid) if schematic.grid.size else []
        door_names = [n for n in names if is_door(n)]
        chest_names = [n for n in names if is_chest(n)]
        self.door_cells = np.isin(schematic.grid, door_names) if door_names else None
        self.chest_cells = np.isin(schematic.grid, chest_names) if chest_names else None
        body = None
        for cells in (self.door_cells, self.chest_cells):
            if cells is not None:
                body = ~cells if body is None else body & ~cells
        self.main = TexturedMesh(*StructureMesher.build_arrays(schematic, uv_lookup, center=False, cells=body))
        self.doors = None
        self.chests = None
        self.rebuild_doors()
        self.rebuild_chests()

    def rebuild_doors(self) -> None:
        from src.rendering.mesh import TexturedMesh
        if self.door_cells is None:
            return
        vertices, indices = StructureMesher.build_arrays(self.schematic, self.uv_lookup, center=False,
                                                         cells=self.door_cells, cull=False)
        if self.doors is None:
            self.doors = TexturedMesh(vertices, indices)
        else:
            self.doors.update_buffers(vertices, indices)

    def rebuild_chests(self, lids=None) -> None:
        """Refaz a malha dos baús; ``lids`` mapeia a célula local (x, y, z) de um baú ao quanto a tampa abriu (0 a 1)."""
        from src.rendering.mesh import TexturedMesh
        if self.chest_cells is None:
            return
        vertices, indices = StructureMesher.build_arrays(self.schematic, self.uv_lookup, center=False,
                                                         cells=self.chest_cells, chest_open=lids)
        if self.chests is None:
            self.chests = TexturedMesh(vertices, indices)
        else:
            self.chests.update_buffers(vertices, indices)

    def draw(self, shader=None) -> None:
        self.main.draw()
        if self.chests is not None:
            self.chests.draw()
        if self.doors is not None:
            # as portas escapam dos cortes de visão (cômodo, andar, corredor): sempre se vê por onde se entra
            if shader is not None:
                shader.set_bool("u_KeepVisible", True)
            self.doors.draw()
            if shader is not None:
                shader.set_bool("u_KeepVisible", False)

    def delete(self) -> None:
        for mesh in (self.main, self.doors, self.chests):
            if mesh is not None:
                mesh.delete()
        self.main = self.doors = self.chests = None


class SchematicTool:
    """Carrega, posiciona e fixa construções no mundo."""

    def __init__(
        self,
        layer: Optional[StructureLayer] = None,
        ground_height: Optional[Callable[[float, float], int]] = None,
        player_position: Optional[Callable[[], Tuple[float, float, float]]] = None,
        view_axes: Optional[Callable[[], Tuple[np.ndarray, np.ndarray]]] = None,
        mesh_factory: Optional[Callable[[Schematic], object]] = None,
        schematics_dir: str = SCHEMATICS_DIR,
    ) -> None:
        self.layer = layer if layer is not None else StructureLayer()
        self.ground_height = ground_height or (lambda x, z: 0)
        self.player_position = player_position or (lambda: (0.0, 0.0, 0.0))
        self.view_axes = view_axes or (lambda: (np.array([0.0, 0.0, -1.0]), np.array([1.0, 0.0, 0.0])))
        self.schematics_dir = schematics_dir
        self.preview: Optional[Preview] = None
        self.notify: Callable[[str], None] = lambda text: None
        # avisos ao mundo: a construção fixada tira o terreno da caixa dela; ao sair, ele volta
        self.on_place: Callable[[object], None] = lambda placed: None
        self.on_remove: Callable[[object], None] = lambda placed: None
        # qualquer mudança no que está fixado (fixar, tirar, girar, limpar, porta): quem salva escuta aqui
        self.on_change: Callable[[], None] = lambda: None
        self._mesh_factory = mesh_factory or self._build_mesh
        self._atlas = None  # SchematicAtlas, criado na primeira construção (precisa de OpenGL)

    # ------------------------------------------------------------------ consulta
    @property
    def active(self) -> bool:
        return self.preview is not None

    def names(self) -> List[str]:
        """Nomes (sem .schem) das construções da pasta assets/schematics."""
        try:
            files = os.listdir(self.schematics_dir)
        except OSError:
            return []
        return sorted(os.path.splitext(f)[0] for f in files if f.lower().endswith(".schem"))

    def resolve(self, text: str) -> Optional[str]:
        """Caminho do arquivo para um nome da pasta ou um caminho (com ou sem aspas)."""
        text = text.strip().strip("\"'").strip()
        if not text:
            return None
        candidates = [text, text + ".schem",
                      os.path.join(self.schematics_dir, text), os.path.join(self.schematics_dir, text + ".schem")]
        return next((p for p in candidates if os.path.isfile(p)), None)

    def lookup(self, base: BlockLookup, x: int, y: int, z: int):
        """Bloco na célula, vendo também as construções fixadas (usado pela colisão)."""
        return self.layer.wrap_lookup(base)(x, y, z)

    # ------------------------------------------------------------------ comandos
    def load(self, text: str, origin: Optional[Tuple[int, int, int]] = None) -> Tuple[bool, str]:
        """Abre a prévia de uma construção. ``origin`` é o canto mínimo; sem ele, vai à frente do jogador."""
        clean = text.strip().strip("\"'").strip()
        if clean.lower() in SHOWCASE_NAMES:
            entry = {"kind": "formas"}
        elif clean.lower().endswith(".json"):
            entry = entry_for_text(clean, self.schematics_dir)
        else:
            path = self.resolve(text)
            entry = None if path is None else {"kind": "schem", "name": self._schem_name(path)}
        if entry is None:
            return False, f"Construção '{text.strip()}' não encontrada. /schem list mostra as disponíveis."
        return self.load_entry(entry, origin)

    def _schem_name(self, path: str) -> str:
        """O nome da pasta, se o arquivo é de lá; senão o caminho inteiro (para salvar e achar de novo)."""
        stem = os.path.splitext(os.path.basename(path))[0]
        inside = os.path.join(self.schematics_dir, stem + ".schem")
        if not os.path.isfile(path):
            return stem
        if os.path.isfile(inside) and os.path.samefile(inside, path):
            return stem
        return os.path.abspath(path)

    def schematic_for(self, entry: dict) -> Schematic:
        """A construção (sem giro) de uma entrada; levanta se não dá para carregar."""
        if entry.get("kind") == "schem":
            path = self.resolve(str(entry.get("name", "")))
            if path is None:
                raise FileNotFoundError(f"Construção '{entry.get('name')}' não encontrada.")
            return Schematic.load_from_file(path)
        return load_entry(entry, self.schematics_dir)

    def load_entry(self, entry: dict, origin: Optional[Tuple[int, int, int]] = None) -> Tuple[bool, str]:
        """Abre a prévia de uma entrada da biblioteca (``src/world/structure_sources.py``)."""
        try:
            schematic = self.schematic_for(entry)
        except FileNotFoundError:
            return False, f"Construção '{entry.get('name', '?')}' não encontrada. /schem list mostra as disponíveis."
        except Exception as error:  # arquivo corrompido ou formato desconhecido
            return False, f"Não consegui ler '{entry.get('name', '?')}': {error}"
        self.cancel(silent=True)
        mesh = self._mesh_factory(schematic)
        start = list(origin) if origin is not None else self._default_origin(schematic)
        self.preview = Preview(schematic.name, schematic, mesh, start, dict(entry), 0, schematic)
        return True, (f"{schematic.name} ({schematic.width}x{schematic.height}x{schematic.length}) em prévia. "
                      f"{HELP_TEXT}.")

    def _default_origin(self, schematic: Schematic) -> List[int]:
        """Canto mínimo que põe a construção no chão, à frente do jogador."""
        px, _, pz = self.player_position()
        forward, _ = self.view_axes()
        dx, dz = snap_axis(forward)
        # a distância conta da borda da construção, não do centro
        reach = FRONT_DISTANCE + (schematic.width if dx else schematic.length) / 2.0
        cx, cz = px + dx * reach, pz + dz * reach
        x = int(math.floor(cx - schematic.width / 2.0))
        z = int(math.floor(cz - schematic.length / 2.0))
        y = int(self.ground_height(cx, cz)) + 1
        return [x, y, z]

    def move(self, dx: int = 0, dy: int = 0, dz: int = 0) -> None:
        if self.preview is not None:
            origin = self.preview.origin
            origin[0] += dx
            origin[1] += dy
            origin[2] += dz

    @staticmethod
    def _anchor(origin, schematic: Schematic) -> Tuple[int, int, int]:
        """O bloco do meio da base (o que o mouse aponta), a partir do canto mínimo."""
        return (origin[0] + schematic.width // 2, origin[1], origin[2] + schematic.length // 2)

    @staticmethod
    def _corner(anchor, schematic: Schematic) -> List[int]:
        return [anchor[0] - schematic.width // 2, anchor[1], anchor[2] - schematic.length // 2]

    def aim(self, cell: Tuple[int, int, int]) -> None:
        """Põe a prévia com o meio da base em cima do bloco ``cell`` (o que o mouse aponta)."""
        if self.preview is not None:
            self.preview.origin = self._corner((int(cell[0]), int(cell[1]) + 1, int(cell[2])), self.preview.schematic)

    def rotate_preview(self) -> None:
        """Gira a prévia 90° em volta do meio da base."""
        p = self.preview
        if p is None:
            return
        anchor = self._anchor(p.origin, p.schematic)
        p.rotation = (p.rotation + 1) % 4
        p.schematic = rotate_schematic(p.base if p.base is not None else p.schematic, p.rotation)
        self._delete_mesh(p.mesh)
        p.mesh = self._mesh_factory(p.schematic)
        p.origin = self._corner(anchor, p.schematic)

    def fits(self, player_box=None) -> bool:
        """Se a prévia cabe: não ocupa bloco de outra construção nem a caixa do jogador ((x0, y0, z0), (x1, y1, z1))."""
        p = self.preview
        if p is None:
            return False
        cells = np.argwhere(p.schematic.occupied_mask)[:, [2, 0, 1]] + np.asarray(p.origin)   # (x, y, z) do mundo
        if len(cells) == 0:
            return False
        low, high = cells.min(axis=0), cells.max(axis=0)
        for placed in self.layer.structures:
            a, b = placed.bounds()
            if (np.asarray(b) < low).any() or (np.asarray(a) > high).any():
                continue   # as caixas nem se encostam
            if any(placed.occupies(int(x), int(y), int(z)) for x, y, z in cells):
                return False
        if player_box is not None:
            (x0, y0, z0), (x1, y1, z1) = player_box
            inside = ((cells[:, 0] >= x0) & (cells[:, 0] <= x1) & (cells[:, 1] >= y0) & (cells[:, 1] <= y1)
                      & (cells[:, 2] >= z0) & (cells[:, 2] <= z1))
            if inside.any():
                return False
        return True

    def confirm(self) -> Tuple[bool, str]:
        """Fixa a prévia no mundo: a malha fica opaca e passa a ter colisão."""
        if self.preview is None:
            return False, "Nenhuma construção em prévia. Use /schem load <nome>."
        p, self.preview = self.preview, None
        placed = self.layer.add(p.name, p.schematic, tuple(p.origin), p.mesh, rotation=p.rotation, entry=p.entry)
        self.on_place(placed)
        self.on_change()
        return True, f"{p.name} fixada em x={p.origin[0]} y={p.origin[1]} z={p.origin[2]}."

    def cancel(self, silent: bool = False) -> Tuple[bool, str]:
        if self.preview is None:
            return False, "Nenhuma construção em prévia."
        self._delete_mesh(self.preview.mesh)
        self.preview = None
        return True, "" if silent else "Prévia cancelada."

    def remove(self, placed: PlacedStructure) -> Tuple[bool, str]:
        """Tira uma construção fixada qualquer (o terreno da caixa volta)."""
        if not self.layer.remove(placed):
            return False, "Essa construção não está no mundo."
        self._delete_mesh(placed.mesh)
        self.on_remove(placed)
        self.on_change()
        return True, f"{placed.name} removida."

    def remove_last(self) -> Tuple[bool, str]:
        if not self.layer.structures:
            return False, "Não há construções fixadas."
        return self.remove(self.layer.structures[-1])

    def rotate_placed(self, placed: PlacedStructure) -> Tuple[bool, str]:
        """Gira 90° uma construção fixada, em volta do meio da base; portas abertas continuam abertas."""
        index = next((i for i, item in enumerate(self.layer.structures) if item is placed), None)
        if index is None:
            return False, "Essa construção não está no mundo."
        anchor = self._anchor(placed.origin, placed.schematic)
        rotated = rotate_schematic(placed.schematic, 1)     # parte da grade atual: leva as portas como estão
        self.layer.remove(placed)
        self._delete_mesh(placed.mesh)
        self.on_remove(placed)
        new = self.layer.add(placed.name, rotated, tuple(self._corner(anchor, rotated)), self._mesh_factory(rotated),
                             rotation=(placed.rotation + 1) % 4, entry=placed.entry)
        self.layer.structures.insert(index, self.layer.structures.pop())   # mantém o lugar na lista
        self.on_place(new)
        self.on_change()
        return True, f"{placed.name} girada."

    def clear(self) -> Tuple[bool, str]:
        """Tira a prévia e todas as construções fixadas."""
        self.cancel(silent=True)
        removed = self.layer.clear()
        for placed in removed:
            self._delete_mesh(placed.mesh)
            self.on_remove(placed)
        if removed:
            self.on_change()
        return True, f"{len(removed)} construção(ões) removida(s)."

    def describe(self) -> List[str]:
        """Linhas para o /schem info: a prévia e as construções fixadas."""
        lines = []
        if self.preview is not None:
            o = self.preview.origin
            lines.append(f"Prévia: {self.preview.name} em x={o[0]} y={o[1]} z={o[2]}")
        for i, s in enumerate(self.layer.structures, 1):
            lines.append(f"{i}. {s.name} em x={s.origin[0]} y={s.origin[1]} z={s.origin[2]}")
        return lines

    # ------------------------------------------------------------------ portas
    def door_near(self, position):
        """A porta de uma construção fixada ao alcance de ``position`` (pés do jogador), ou ``None``."""
        from src.world.doors import find_door
        return find_door(self.layer.structures, position)

    def set_chest_lid(self, chest, amount: float) -> None:
        """Põe a tampa do baú ``chest`` (ChestRef) em ``amount`` (0 fechada, 1 toda aberta) e refaz a malha dos baús."""
        mesh = chest.structure.mesh
        if hasattr(mesh, "rebuild_chests"):
            mesh.rebuild_chests({chest.local: float(amount)} if amount > 0.0 else None)

    def toggle_door(self, door, player_cells=()) -> bool:
        """Abre ou fecha a porta e refaz a malha da construção. Não fecha em cima do jogador.

        Devolve True se a porta mudou.
        """
        from src.world.doors import toggle_door
        if door.is_open and set(door.cells()) & set(player_cells):
            return False  # fechar prenderia o personagem dentro da porta
        toggle_door(door)
        self.on_change()
        placed = door.structure
        if hasattr(placed.mesh, "rebuild_doors"):
            placed.mesh.rebuild_doors()       # só a malha pequena das portas (a casa inteira leva quase 1 s)
        elif placed.mesh is not None and hasattr(placed.mesh, "delete"):
            old = placed.mesh
            placed.mesh = self._mesh_factory(placed.schematic)
            old.delete()
        return True

    # ------------------------------------------------------------------ teclado
    def handle_key(self, key: int, action: int, mods: int) -> bool:
        """Consome as teclas da prévia (setas, Enter, Esc) enquanto ela existe."""
        if self.preview is None:
            return False
        arrows = (glfw.KEY_UP, glfw.KEY_DOWN, glfw.KEY_LEFT, glfw.KEY_RIGHT)
        confirm_keys = (glfw.KEY_ENTER, glfw.KEY_KP_ENTER)
        if key not in arrows + confirm_keys + (glfw.KEY_ESCAPE,):
            return False
        if action == glfw.RELEASE:
            return True
        if key in confirm_keys:
            if action == glfw.PRESS:
                self.notify(self.confirm()[1])
        elif key == glfw.KEY_ESCAPE:
            if action == glfw.PRESS:
                self.notify(self.cancel()[1])
        elif mods & glfw.MOD_SHIFT and key in (glfw.KEY_UP, glfw.KEY_DOWN):
            self.move(dy=1 if key == glfw.KEY_UP else -1)
        elif key in arrows:
            forward, _ = self.view_axes()
            fx, fz = snap_axis(forward)
            rx, rz = -fz, fx  # a direita é sempre a perpendicular de "para cima" (nunca o mesmo eixo)
            if key == glfw.KEY_UP:
                self.move(dx=fx, dz=fz)
            elif key == glfw.KEY_DOWN:
                self.move(dx=-fx, dz=-fz)
            elif key == glfw.KEY_RIGHT:
                self.move(dx=rx, dz=rz)
            else:
                self.move(dx=-rx, dz=-rz)
        return True

    # ------------------------------------------------------------------ desenho (OpenGL)
    def atlas_if_ready(self):
        """O atlas das construções, se já foi criado (não cria um só para consultar)."""
        return self._atlas

    def ensure_atlas(self):
        """O atlas das construções, criado agora se ainda não existe (precisa de OpenGL).

        As tampas dos cortes da revelação de cômodo usam este atlas: os objetos e o mapa do editor, que não passam por um
        ``/schem``, o pedem por aqui para as tampas deles aparecerem."""
        return self._ensure_atlas()

    def _ensure_atlas(self):
        if self._atlas is None:
            from src.rendering.schematic_atlas import SchematicAtlas
            self._atlas = SchematicAtlas(create_gl=True)
        return self._atlas

    def _build_mesh(self, schematic: Schematic):
        return StructureMeshes(schematic, self._ensure_atlas().get_uv)

    @staticmethod
    def _delete_mesh(mesh) -> None:
        if mesh is not None and hasattr(mesh, "delete"):
            mesh.delete()

    def draw(self, shader, base_model: np.ndarray, time: float, *, solids: bool = True, preview: bool = True) -> None:
        """Desenha as construções fixadas (opacas) e a prévia (holograma), com o shader do mundo.

        ``solids`` e ``preview`` escolhem as partes: o jogo desenha as fixadas nas passadas opacas (a de profundidade
        e a de cor) e o holograma, translúcido, depois.
        """
        if not (solids and self.layer.structures) and not (preview and self.preview is not None):
            return
        import OpenGL.GL as gl
        from src.math import mat4_translate

        atlas = self._ensure_atlas()
        # Os blocos têm o centro nas coordenadas inteiras da malha; as células do mundo, o canto
        shader.set_bool("u_UndergroundMode", False)
        shader.set_bool("u_WaterMode", False)
        shader.set_int("u_CutawayPass", 0)
        shader.set_bool("u_Skinned", False)
        atlas.bind(0)
        shader.set_int("u_TextureAtlas", 0)

        for placed in (self.layer.structures if solids else ()):
            if placed.mesh is not None:
                ox, oy, oz = placed.origin
                shader.set_mat4("u_Model", base_model @ mat4_translate(ox + 0.5, oy + 0.5, oz + 0.5))
                if isinstance(placed.mesh, StructureMeshes):
                    placed.mesh.draw(shader)
                else:
                    placed.mesh.draw()

        if preview and self.preview is not None:
            ox, oy, oz = self.preview.origin
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
            shader.set_float("u_Alpha", ALPHA_HOLOGRAM + 0.10 * math.sin(time * 4.0))
            shader.set_mat4("u_Model", base_model @ mat4_translate(ox + 0.5, oy + 0.5, oz + 0.5))
            self.preview.mesh.draw()
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisable(gl.GL_BLEND)
            shader.set_float("u_Alpha", 1.0)

    def delete(self) -> None:
        """Libera as malhas e o atlas da GPU."""
        self.clear()
        if self._atlas is not None:
            self._atlas.delete()
            self._atlas = None
