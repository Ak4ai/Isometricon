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

from src.world.schematic import Schematic
from src.world.structure_layer import BlockLookup, PlacedStructure, StructureLayer
from src.world.structure_mesher import StructureMesher

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMATICS_DIR = os.path.join(PROJECT_ROOT, "assets", "schematics")

ALPHA_HOLOGRAM = 0.45
FRONT_DISTANCE = 3  # blocos entre o jogador e a borda da prévia ao abrir

HELP_TEXT = "Setas movem · Shift+↑/↓ muda a altura · Enter fixa · Esc cancela"


@dataclass
class Preview:
    """A construção que está sendo posicionada."""

    name: str
    schematic: Schematic
    mesh: object
    origin: List[int]


def snap_axis(vector) -> Tuple[int, int]:
    """O eixo X ou Z (com sinal) para onde um vetor horizontal mais aponta: (dx, dz)."""
    x, z = float(vector[0]), float(vector[2])
    if abs(x) >= abs(z):
        return (1 if x >= 0 else -1, 0)
    return (0, 1 if z >= 0 else -1)


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
        path = self.resolve(text)
        if path is None:
            return False, f"Construção '{text.strip()}' não encontrada. /schem list mostra as disponíveis."
        try:
            schematic = Schematic.load_from_file(path)
        except Exception as error:  # arquivo corrompido ou formato desconhecido
            return False, f"Não consegui ler '{os.path.basename(path)}': {error}"
        self.cancel(silent=True)
        mesh = self._mesh_factory(schematic)
        start = list(origin) if origin is not None else self._default_origin(schematic)
        self.preview = Preview(schematic.name, schematic, mesh, start)
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

    def confirm(self) -> Tuple[bool, str]:
        """Fixa a prévia no mundo: a malha fica opaca e passa a ter colisão."""
        if self.preview is None:
            return False, "Nenhuma construção em prévia. Use /schem load <nome>."
        p, self.preview = self.preview, None
        self.layer.add(p.name, p.schematic, tuple(p.origin), p.mesh)
        return True, f"{p.name} fixada em x={p.origin[0]} y={p.origin[1]} z={p.origin[2]}."

    def cancel(self, silent: bool = False) -> Tuple[bool, str]:
        if self.preview is None:
            return False, "Nenhuma construção em prévia."
        self._delete_mesh(self.preview.mesh)
        self.preview = None
        return True, "" if silent else "Prévia cancelada."

    def remove_last(self) -> Tuple[bool, str]:
        removed = self.layer.remove_last()
        if removed is None:
            return False, "Não há construções fixadas."
        self._delete_mesh(removed.mesh)
        return True, f"{removed.name} removida."

    def clear(self) -> Tuple[bool, str]:
        """Tira a prévia e todas as construções fixadas."""
        self.cancel(silent=True)
        removed = self.layer.clear()
        for placed in removed:
            self._delete_mesh(placed.mesh)
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
    def _ensure_atlas(self):
        if self._atlas is None:
            from src.rendering.schematic_atlas import SchematicAtlas
            self._atlas = SchematicAtlas(create_gl=True)
        return self._atlas

    def _build_mesh(self, schematic: Schematic):
        from src.rendering.mesh import TexturedMesh
        atlas = self._ensure_atlas()
        vertices, indices = StructureMesher.build_arrays(schematic, atlas.get_uv, center=False)
        return TexturedMesh(vertices, indices)

    @staticmethod
    def _delete_mesh(mesh) -> None:
        if mesh is not None and hasattr(mesh, "delete"):
            mesh.delete()

    def draw(self, shader, base_model: np.ndarray, time: float) -> None:
        """Desenha as construções fixadas (opacas) e a prévia (holograma), com o shader do mundo."""
        if not self.layer.structures and self.preview is None:
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

        for placed in self.layer.structures:
            if placed.mesh is not None:
                ox, oy, oz = placed.origin
                shader.set_mat4("u_Model", base_model @ mat4_translate(ox + 0.5, oy + 0.5, oz + 0.5))
                placed.mesh.draw()

        if self.preview is not None:
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
