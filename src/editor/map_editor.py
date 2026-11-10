"""Controlador do editor de mapa/objetos voxel (modo ``--map-editor``).

O editor é aditivo ao motor: usa a mesma câmera, o mesmo shader iluminado e o
mesmo ``TexturedMesh``. A plataforma tem shader próprio; os voxels editados
formam uma malha reconstruída após cada operação.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

import glfw
import numpy as np
import OpenGL.GL as gl

from src.camera import IsometricCamera
from src.editor.editor_hud import EditorHud
from src.editor.material_atlas import MaterialAtlas
from src.editor.object_mesher import ObjectMeshData, build_mesh_data
from src.editor.platform import PlatformRenderer
from src.editor.voxel_object import MAX_DIM, VoxelMaterial, VoxelObject
from src.interaction import raycast_voxels, screen_to_world_ray
from src.interactive.highlight import BlockHighlightRenderer
from src.math import mat4_translate, vec3
from src.rendering.mesh import TexturedMesh
from src.world import BlockType

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = ("build", "erase", "paint", "stamp")
TOOL_LABELS = {"build": "Construir", "erase": "Apagar", "paint": "Pintar", "stamp": "Carimbar objeto"}
PALETTE = (
    ("Branco", (245, 245, 245)),
    ("Cinza", (150, 150, 150)),
    ("Preto", (35, 35, 35)),
    ("Vermelho", (205, 55, 55)),
    ("Laranja", (235, 135, 45)),
    ("Amarelo", (235, 205, 65)),
    ("Verde", (65, 165, 80)),
    ("Ciano", (55, 180, 190)),
    ("Azul", (55, 95, 205)),
    ("Roxo", (135, 70, 190)),
    ("Rosa", (225, 110, 165)),
    ("Marrom", (125, 85, 55)),
    ("Azul-claro", (120, 180, 240)),
    ("Verde-claro", (150, 220, 130)),
    ("Bege", (215, 195, 160)),
    ("Vinho", (120, 35, 60)),
)
MAX_UNDO = 50


class _ObjectProvider:
    """VoxelLookup sobre o objeto em edição, para o DDA do picking."""

    def __init__(self, obj: VoxelObject) -> None:
        self.obj = obj

    def get_block_at(self, x: int, y: int, z: int) -> BlockType:
        if self.obj.in_bounds(x, y, z) and self.obj.get(x, y, z) >= 0:
            return BlockType.STONE
        return BlockType.AIR


class MapEditor:
    """Estado, entrada, malha e HUD do editor de mapa."""

    def __init__(
        self,
        camera: IsometricCamera | None = None,
        map_path: str | None = None,
        create_gl: bool = True,
        library_dir: str | None = None,
    ) -> None:
        self.create_gl = bool(create_gl)
        self.camera = camera
        self.save_path = os.path.abspath(map_path or os.path.join(PROJECT_ROOT, "saves", "mapa.json"))
        self.export_path = os.path.join(PROJECT_ROOT, "saves", "objeto.json")
        self.library_dir = os.path.abspath(library_dir or os.path.join(PROJECT_ROOT, "assets", "objects"))
        self.map = VoxelObject((16, 16, 16), "mapa", "map")
        self.atlas = MaterialAtlas(create_gl=self.create_gl)
        self.platform = PlatformRenderer() if self.create_gl else None
        self.highlight = BlockHighlightRenderer() if self.create_gl else None
        self.hud = EditorHud() if self.create_gl else None
        self.mesh: TexturedMesh | None = None
        self.preview_mesh: TexturedMesh | None = None
        self.mesh_data: ObjectMeshData = ObjectMeshData(np.empty((0, 11), np.float32), np.empty(0, np.uint32), 0)
        self.preview_data: ObjectMeshData = self.mesh_data
        self.tool = "build"
        self.colour_index = 0
        self.texture_index = 0
        self.cursor: tuple[int, int, int] | None = None
        self.cursor_normal: tuple[int, int, int] = (0, 0, 0)
        self.stamp: VoxelObject | None = None
        self.stamp_name = ""
        self.stamp_rotation = 0
        self.library_index = -1
        self.status = "Clique na plataforma para construir. Tab troca a ferramenta."
        self.show_grid = True
        self.click_pending = False
        self.undo_stack: list[VoxelObject] = []
        self.redo_stack: list[VoxelObject] = []
        self._mesh_dirty = True
        self._preview_dirty = True
        self._show_path = map_path
        if map_path and os.path.exists(map_path):
            try:
                self.map = VoxelObject.load(map_path)
                self.map.kind = "map"
                self.status = f"Mapa carregado: {os.path.basename(map_path)}"
            except Exception as exc:
                self.status = f"Falha ao carregar mapa: {exc}"
        if camera is not None:
            self.bind_camera(camera)
        self._rebuild_mesh()
        self._rebuild_preview()
        self._update_hud()

    # ------------------------------------------------------------------
    # Câmera, material e estado
    # ------------------------------------------------------------------
    @property
    def grid_size(self) -> tuple[int, int, int]:
        return self.map.size

    @property
    def colour(self) -> tuple[int, int, int]:
        return PALETTE[self.colour_index][1]

    @property
    def texture(self) -> str:
        return self.atlas.tile_names[self.texture_index]

    def bind_camera(self, camera: IsometricCamera) -> None:
        self.camera = camera
        width, height, depth = self.map.size
        camera.target = vec3(width / 2.0, height * 0.35, depth / 2.0)
        camera.ortho_size = max(width, depth, height * 1.1) * 0.95

    def current_material(self) -> VoxelMaterial:
        return VoxelMaterial(self.colour, self.texture)

    def _push_undo(self) -> None:
        self.undo_stack.append(self.map.copy())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            self.status = "Nada para desfazer."
            return False
        self.redo_stack.append(self.map.copy())
        before = self.map.size
        self.map = self.undo_stack.pop()
        self._after_change("Desfeito.")
        if self.camera is not None and self.map.size != before:
            self.bind_camera(self.camera)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            self.status = "Nada para refazer."
            return False
        self.undo_stack.append(self.map.copy())
        before = self.map.size
        self.map = self.redo_stack.pop()
        self._after_change("Refeito.")
        if self.camera is not None and self.map.size != before:
            self.bind_camera(self.camera)
        return True

    def _after_change(self, message: str) -> None:
        self.status = message
        self._mesh_dirty = True
        self._preview_dirty = True
        self._update_hud()

    # ------------------------------------------------------------------
    # Construção de malhas
    # ------------------------------------------------------------------
    def _rebuild_mesh(self) -> None:
        self.mesh_data = build_mesh_data(self.map, self.atlas)
        if not self.create_gl:
            self._mesh_dirty = False
            return
        if self.mesh is not None:
            self.mesh.delete()
            self.mesh = None
        if self.mesh_data.vertex_count:
            self.mesh = TexturedMesh(self.mesh_data.vertices.flatten(), self.mesh_data.indices)
        self._mesh_dirty = False

    def _rebuild_preview(self) -> None:
        if not self.create_gl:
            self._preview_dirty = False
            return
        if self.preview_mesh is not None:
            self.preview_mesh.delete()
            self.preview_mesh = None
        if self.stamp is None:
            self.preview_data = ObjectMeshData(np.empty((0, 11), np.float32), np.empty(0, np.uint32), 0)
            self._preview_dirty = False
            return
        rotated = self.stamp.rotated_y(self.stamp_rotation)
        self.preview_data = build_mesh_data(rotated, self.atlas)
        if self.preview_data.vertex_count:
            self.preview_mesh = TexturedMesh(self.preview_data.vertices.flatten(), self.preview_data.indices)
        self._preview_dirty = False

    def update(self, dt: float = 0.0) -> None:
        del dt
        if self._mesh_dirty:
            self._rebuild_mesh()
        if self._preview_dirty:
            self._rebuild_preview()
        self._update_hud()

    # ------------------------------------------------------------------
    # Picking
    # ------------------------------------------------------------------
    def update_cursor(self, mouse_x: float, mouse_y: float, width: int, height: int,
                      view: np.ndarray, projection: np.ndarray, model: np.ndarray) -> None:
        ray = screen_to_world_ray(mouse_x, mouse_y, width, height, view, projection, model)
        hit = raycast_voxels(ray, _ObjectProvider(self.map), max_distance=512.0)
        target: tuple[int, int, int] | None = None
        if hit is not None:
            self.cursor_normal = hit.normal
            if self.tool in ("erase", "paint"):
                target = hit.block
            else:
                target = (
                    hit.block[0] + hit.normal[0],
                    hit.block[1] + hit.normal[1],
                    hit.block[2] + hit.normal[2],
                )
        else:
            self.cursor_normal = (0, 1, 0)
            if abs(float(ray.direction[1])) > 1e-6:
                distance = -float(ray.origin[1]) / float(ray.direction[1])
                if distance >= 0.0:
                    point = ray.origin + ray.direction * distance
                    x = math.floor(float(point[0]))
                    z = math.floor(float(point[2]))
                    if 0 <= x < self.map.size[0] and 0 <= z < self.map.size[2]:
                        target = (x, 0, z)
        if target is not None and not self.map.in_bounds(*target):
            target = None
        self.cursor = target

    # ------------------------------------------------------------------
    # Edição
    # ------------------------------------------------------------------
    def apply_current_tool(self) -> bool:
        if self.cursor is None:
            self.status = "Nenhuma célula sob o cursor."
            return False
        x, y, z = self.cursor
        material = self.current_material()
        if self.tool == "build":
            if not self.map.in_bounds(x, y, z) or self.map.get(x, y, z) >= 0:
                self.status = "A célula já está ocupada."
                return False
            self._push_undo()
            self.map.set(x, y, z, self.map.add_material(material))
            self._after_change(f"Voxel criado em ({x}, {y}, {z}).")
            return True
        if self.tool == "erase":
            if not self.map.in_bounds(x, y, z) or self.map.get(x, y, z) < 0:
                self.status = "Não há voxel para apagar."
                return False
            self._push_undo()
            self.map.clear(x, y, z)
            self._after_change(f"Voxel removido de ({x}, {y}, {z}).")
            return True
        if self.tool == "paint":
            if not self.map.in_bounds(x, y, z) or self.map.get(x, y, z) < 0:
                self.status = "Não há voxel para pintar."
                return False
            self._push_undo()
            self.map.set(x, y, z, self.map.add_material(material))
            self._after_change(f"Voxel pintado em ({x}, {y}, {z}).")
            return True
        if self.tool == "stamp":
            if self.stamp is None:
                self._load_next_library()
            if self.stamp is None:
                self.status = "Nenhum objeto na biblioteca. Use F2 para exportar um."
                return False
            if not self.map.in_bounds(x, y, z):
                self.status = "O objeto começa fora da grade."
                return False
            self._push_undo()
            placed = self.map.blit(self.stamp, (x, y, z), self.stamp_rotation)
            if placed == 0:
                self.undo_stack.pop()
                self.status = "O objeto não cabe nessa posição."
                return False
            self._after_change(f"{placed} voxels de {self.stamp_name} colocados.")
            return True
        return False

    def handle_mouse_button(self, button: int, action: int, shift: bool = False) -> bool:
        if button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS and not shift:
            self.click_pending = True
            return True
        return False

    def process_click(self) -> bool:
        if not self.click_pending:
            return False
        self.click_pending = False
        return self.apply_current_tool()

    # ------------------------------------------------------------------
    # Teclado
    # ------------------------------------------------------------------
    def handle_key(self, key: int, action: int, mods: int) -> bool:
        if action not in (glfw.PRESS, glfw.REPEAT):
            return False
        control = bool(mods & (glfw.MOD_CONTROL | getattr(glfw, "MOD_SUPER", 0)))
        shift = bool(mods & glfw.MOD_SHIFT)
        if control and key == glfw.KEY_Z:
            self.undo()
            return True
        if control and key == glfw.KEY_Y:
            self.redo()
            return True
        if key == glfw.KEY_TAB:
            step = -1 if shift else 1
            self.tool = TOOLS[(TOOLS.index(self.tool) + step) % len(TOOLS)]
            if self.tool == "stamp" and self.stamp is None:
                self._load_next_library()
            self.status = f"Ferramenta: {TOOL_LABELS[self.tool]}."
            return True
        if key == glfw.KEY_C and not control:
            self.colour_index = (self.colour_index + (-1 if shift else 1)) % len(PALETTE)
            self.status = f"Cor: {PALETTE[self.colour_index][0]}."
            return True
        if key == glfw.KEY_X and not control:
            self.texture_index = (self.texture_index + (-1 if shift else 1)) % len(self.atlas.tile_names)
            self.status = f"Textura: {self.texture}."
            return True
        if key == glfw.KEY_R and not control:
            self.stamp_rotation = (self.stamp_rotation + 1) % 4
            self._preview_dirty = True
            self.status = f"Rotação do objeto: {self.stamp_rotation * 90}°."
            return True
        if key == glfw.KEY_G and not control:
            self.show_grid = not self.show_grid
            self.status = f"Grade: {'ligada' if self.show_grid else 'desligada'}."
            return True
        if key == glfw.KEY_F2 and not control:
            self.export_object()
            return True
        if key == glfw.KEY_F3 and not control:
            self._load_next_library()
            return True
        if key == glfw.KEY_F5 and not control:
            self.save_map()
            return True
        if key == glfw.KEY_F9 and not control:
            self.load_map()
            return True
        if key == glfw.KEY_F6 and not control:
            self.resize_grid(-2)
            return True
        if key == glfw.KEY_F7 and not control:
            self.resize_grid(2)
            return True
        return False

    # ------------------------------------------------------------------
    # Arquivos
    # ------------------------------------------------------------------
    def export_object(self) -> str | None:
        try:
            obj = self.map.copy()
            obj.kind = "object"
            obj.name = "objeto"
            path = obj.save(self.export_path)
            self.status = f"Objeto exportado: {os.path.basename(path)} (F3 para carimbar)."
            return path
        except Exception as exc:
            self.status = f"Falha ao exportar: {exc}"
            return None

    def save_map(self) -> str | None:
        try:
            self.map.kind = "map"
            path = self.map.save(self.save_path)
            self.status = f"Mapa salvo: {os.path.basename(path)}."
            return path
        except Exception as exc:
            self.status = f"Falha ao salvar: {exc}"
            return None

    def load_map(self) -> bool:
        try:
            loaded = VoxelObject.load(self.save_path)
            loaded.kind = "map"
            self.map = loaded
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._after_change(f"Mapa carregado: {os.path.basename(self.save_path)}.")
            if self.camera is not None:
                self.bind_camera(self.camera)
            return True
        except Exception as exc:
            self.status = f"Falha ao carregar mapa: {exc}"
            return False

    def _library_paths(self) -> list[str]:
        paths = sorted(str(path) for path in Path(self.library_dir).glob("*.json"))
        if os.path.exists(self.export_path) and self.export_path not in paths:
            paths.append(self.export_path)
        return paths

    def _load_next_library(self) -> bool:
        paths = self._library_paths()
        if not paths:
            self.status = "Biblioteca vazia: exporte um objeto com F2."
            return False
        self.library_index = (self.library_index + 1) % len(paths)
        path = paths[self.library_index]
        try:
            self.stamp = VoxelObject.load(path)
            self.stamp_name = os.path.basename(path)
            self.tool = "stamp"
            self.stamp_rotation = 0
            self._preview_dirty = True
            self._update_hud()
            self.status = f"Objeto carregado: {self.stamp_name} (clique para carimbar)."
            return True
        except Exception as exc:
            self.status = f"Falha ao carregar objeto: {exc}"
            return False

    def resize_grid(self, delta: int) -> bool:
        old = self.map.size
        new = tuple(max(1, min(MAX_DIM, value + int(delta))) for value in old)
        if new == old:
            self.status = "A grade não mudou."
            return False
        self._push_undo()
        self.map.resize(new)
        self._after_change(f"Grade: {new[0]}x{new[1]}x{new[2]}.")
        if self.camera is not None:
            self.bind_camera(self.camera)
        return True

    # ------------------------------------------------------------------
    # HUD e render
    # ------------------------------------------------------------------
    def _update_hud(self) -> None:
        if self.hud is None:
            return
        colour_name = PALETTE[self.colour_index][0]
        cursor = "—" if self.cursor is None else f"({self.cursor[0]}, {self.cursor[1]}, {self.cursor[2]})"
        stamp = self.stamp_name or "nenhum"
        lines = [
            (f"Ferramenta: {TOOL_LABELS[self.tool]}   [Tab]", (225, 230, 238)),
            (f"Cor: {colour_name}   [C]   Textura: {self.texture}   [X]", (200, 210, 220)),
            (f"Grid: {self.grid_size[0]}x{self.grid_size[1]}x{self.grid_size[2]}   [F6/F7]", (200, 210, 220)),
            (f"Objeto: {stamp}   rotação {self.stamp_rotation * 90}°   [F3/R]", (200, 210, 220)),
            (f"Cursor: {cursor}   Voxels: {self.map.voxel_count}", (200, 210, 220)),
            (f"{self.status}", (245, 210, 120)),
        ]
        self.hud.set_state("EDITOR DE MAPA — ISOMETRICON", lines, swatch=self.colour)

    def _common_shader(self, shader, projection: np.ndarray, view: np.ndarray, model: np.ndarray) -> None:
        shader.use()
        shader.set_mat4("u_Projection", projection)
        shader.set_mat4("u_View", view)
        shader.set_mat4("u_Model", model)
        shader.set_bool("u_Skinned", False)
        shader.set_bool("u_UndergroundMode", False)
        shader.set_bool("u_WaterMode", False)
        shader.set_int("u_CutawayPass", 0)
        shader.set_float("u_Vitiligo", 0.0)
        shader.set_int("u_Underwear", 0)
        shader.set_float("u_Alpha", 1.0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.atlas.texture_id)
        shader.set_int("u_TextureAtlas", 0)

    def render(self, shader, projection: np.ndarray, view: np.ndarray, model: np.ndarray,
               time: float, window_width: int, window_height: int) -> None:
        if not self.create_gl:
            return
        self.update()
        if self.platform is not None:
            self.platform.render(projection, view, model, (self.map.size[0], self.map.size[2]),
                                 None if self.cursor is None else (self.cursor[0], self.cursor[2]),
                                 time, self.show_grid)
        self._common_shader(shader, projection, view, model)
        if self.mesh is not None and self.mesh_data.vertex_count:
            shader.set_mat4("u_Model", model)
            self.mesh.draw()

        if self.tool == "stamp" and self.preview_mesh is not None and self.cursor is not None:
            shader.use()
            shader.set_mat4("u_Projection", projection)
            shader.set_mat4("u_View", view)
            shader.set_mat4("u_Model", model @ mat4_translate(*self.cursor))
            shader.set_float("u_Alpha", 0.45)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
            self.preview_mesh.draw()
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisable(gl.GL_BLEND)
            shader.set_float("u_Alpha", 1.0)

        if self.cursor is not None and self.highlight is not None:
            x, y, z = self.cursor
            colour = (1.0, 0.85, 0.30) if self.tool != "erase" else (1.0, 0.35, 0.30)
            self.highlight.render(view, projection, model, x, y, z, time=time, base_color=colour)

        if self.hud is not None:
            self._update_hud()
            self.hud.render(window_width, window_height)

    def delete(self) -> None:
        for mesh in (self.mesh, self.preview_mesh):
            if mesh is not None:
                mesh.delete()
        self.mesh = None
        self.preview_mesh = None
        if self.platform is not None:
            self.platform.delete()
            self.platform = None
        if self.highlight is not None:
            self.highlight.delete()
            self.highlight = None
        if self.hud is not None:
            self.hud.delete()
            self.hud = None
        self.atlas.delete()
