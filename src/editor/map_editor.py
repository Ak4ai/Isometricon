"""Controlador do editor de mapa/objetos voxel (modo ``--map-editor``).

O editor é aditivo ao motor: usa a mesma câmera, o mesmo shader iluminado e o
mesmo ``TexturedMesh``. A plataforma tem shader próprio; o mapa tem um volume
base editável e uma lista de construções independentes (mover/rotacionar/
duplicar/excluir).
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
from src.editor.editor_hud import PANEL_HEIGHT, PANEL_WIDTH, EditorHud
from src.editor.map_project import MapProject, PlacedObject
from src.editor.material_atlas import MaterialAtlas
from src.editor.object_mesher import ObjectMeshData, build_mesh_data
from src.editor.platform import PlatformRenderer
from src.editor.selection import SelectionBoxRenderer
from src.editor.voxel_object import MAX_DIM, VoxelMaterial, VoxelObject
from src.interaction import raycast_voxels, screen_to_world_ray
from src.interactive.highlight import BlockHighlightRenderer
from src.math import mat4_translate, vec3
from src.rendering.mesh import TexturedMesh
from src.world import BlockType

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = ("build", "erase", "paint", "stamp", "select")
TOOL_LABELS = {"build": "Construir", "erase": "Apagar", "paint": "Pintar",
               "stamp": "Carimbar", "select": "Selecionar"}
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
MAX_BRUSH = 8
MAX_GRID_SPACING = 8


class _ObjectProvider:
    """VoxelLookup do projeto inteiro (base + objetos colocados)."""

    def __init__(self, project: MapProject) -> None:
        self.project = project

    def get_block_at(self, x: int, y: int, z: int) -> BlockType:
        return BlockType.STONE if self.project.occupied(x, y, z) else BlockType.AIR


class MapEditor:
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
        self.project = MapProject(VoxelObject((16, 16, 16), "mapa", "map"), name="mapa")
        self._sync_aliases()
        self.atlas = MaterialAtlas(create_gl=self.create_gl)
        self.platform = PlatformRenderer() if self.create_gl else None
        self.highlight = BlockHighlightRenderer() if self.create_gl else None
        self.selection_box = SelectionBoxRenderer() if self.create_gl else None
        self.hud = EditorHud() if self.create_gl else None
        self.mesh: TexturedMesh | None = None
        self.object_meshes: list[tuple[PlacedObject, TexturedMesh | None, ObjectMeshData]] = []
        self.mesh_data: ObjectMeshData = ObjectMeshData(np.empty((0, 11), np.float32), np.empty(0, np.uint32), 0)
        self.preview_mesh: TexturedMesh | None = None
        self.preview_data: ObjectMeshData = self.mesh_data
        self.cursor_preview_mesh: TexturedMesh | None = None
        self.cursor_preview_data: ObjectMeshData = self.mesh_data
        self.tool = "build"
        self.colour_index = 0
        self.custom_colour: tuple[int, int, int] | None = None
        self.texture_index = 0
        self.brush_size = 1
        self.grid_spacing = 1
        self.cursor: tuple[int, int, int] | None = None
        self.cursor_normal: tuple[int, int, int] = (0, 1, 0)
        self.stamp: VoxelObject | None = None
        self.stamp_name = ""
        self.stamp_rotation = 0
        self.selected_index: int | None = None
        self.stamp_valid: bool | None = None
        self.library_index = -1
        self.library_open = False
        self.library_cursor = 0
        self.library_pending_delete: str | None = None
        self.status = "Clique na plataforma para construir. Tab troca a ferramenta."
        self.show_grid = True
        self.click_pending = False
        self.dragging = False
        self._last_drag_cell: tuple[int, int, int] | None = None
        self.last_mouse: tuple[float, float] | None = None
        self.last_mouse_window: tuple[float, float] | None = None
        self.hex_mode = False
        self.hex_buffer = ""
        self.pending_shrink: tuple[tuple[int, int, int], int] | None = None
        self.undo_stack: list[MapProject] = []
        self.redo_stack: list[MapProject] = []
        self._mesh_dirty = True
        self._preview_dirty = True
        self._cursor_preview_dirty = True
        if map_path and os.path.exists(map_path):
            try:
                self.project = MapProject.load(map_path)
                self._sync_aliases()
                self.status = f"Mapa carregado: {os.path.basename(map_path)}"
            except Exception as exc:
                self.status = f"Falha ao carregar mapa: {exc}"
        if camera is not None:
            self.bind_camera(camera)
        self._rebuild_meshes()
        self._rebuild_preview()
        self._rebuild_cursor_preview()
        self._update_hud()

    # ------------------------------------------------------------------
    # Aliases e estado
    # ------------------------------------------------------------------
    def _sync_aliases(self) -> None:
        self.map = self.project.base
        self.objects = self.project.objects

    @property
    def grid_size(self) -> tuple[int, int, int]:
        return self.project.size

    @property
    def selected(self) -> PlacedObject | None:
        if self.selected_index is None or not 0 <= self.selected_index < len(self.objects):
            return None
        return self.objects[self.selected_index]

    @property
    def colour(self) -> tuple[int, int, int]:
        return self.custom_colour if self.custom_colour is not None else PALETTE[self.colour_index][1]

    @property
    def colour_name(self) -> str:
        return "Personalizada" if self.custom_colour is not None else PALETTE[self.colour_index][0]

    @property
    def texture(self) -> str:
        return self.atlas.tile_names[self.texture_index]

    def bind_camera(self, camera: IsometricCamera) -> None:
        self.camera = camera
        width, height, depth = self.project.size
        camera.target = vec3(width / 2.0, height * 0.35, depth / 2.0)
        camera.ortho_size = max(width, depth, height * 1.1) * 0.95

    def current_material(self) -> VoxelMaterial:
        return VoxelMaterial(self.colour, self.texture)

    # ------------------------------------------------------------------
    # Histórico
    # ------------------------------------------------------------------
    def _push_undo(self) -> None:
        self.undo_stack.append(self.project.copy())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _restore(self, project: MapProject) -> None:
        before = self.project.size
        self.project = project
        self._sync_aliases()
        self.selected_index = min(self.selected_index, len(self.objects) - 1) if self.selected_index is not None and self.objects else None
        self._after_change("")
        if self.camera is not None and self.project.size != before:
            self.bind_camera(self.camera)
        self._mesh_dirty = True

    def undo(self) -> bool:
        if not self.undo_stack:
            self.status = "Nada para desfazer."
            return False
        self.redo_stack.append(self.project.copy())
        self._restore(self.undo_stack.pop())
        self.status = "Desfeito."
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            self.status = "Nada para refazer."
            return False
        self.undo_stack.append(self.project.copy())
        self._restore(self.redo_stack.pop())
        self.status = "Refeito."
        return True

    def _after_change(self, message: str) -> None:
        if message:
            self.status = message
        self._mesh_dirty = True
        self._cursor_preview_dirty = True
        self._update_hud()

    # ------------------------------------------------------------------
    # Malhas
    # ------------------------------------------------------------------
    def _make_mesh(self, data: ObjectMeshData) -> TexturedMesh | None:
        if not self.create_gl or not data.vertex_count:
            return None
        return TexturedMesh(data.vertices.flatten(), data.indices)

    def _rebuild_meshes(self) -> None:
        self.mesh_data = build_mesh_data(self.map, self.atlas)
        if self.mesh is not None:
            self.mesh.delete()
        self.mesh = self._make_mesh(self.mesh_data)
        for _, mesh, _ in self.object_meshes:
            if mesh is not None:
                mesh.delete()
        self.object_meshes = []
        for placed in self.objects:
            data = build_mesh_data(placed.rendered_object(), self.atlas)
            self.object_meshes.append((placed, self._make_mesh(data), data))
        self._mesh_dirty = False

    def _rebuild_preview(self) -> None:
        if self.preview_mesh is not None:
            self.preview_mesh.delete()
            self.preview_mesh = None
        if self.stamp is None:
            self.preview_data = ObjectMeshData(np.empty((0, 11), np.float32), np.empty(0, np.uint32), 0)
            self._preview_dirty = False
            return
        rotated = self.stamp.rotated_y(self.stamp_rotation)
        self.preview_data = build_mesh_data(rotated, self.atlas)
        self.preview_mesh = self._make_mesh(self.preview_data)
        self._preview_dirty = False

    def _rebuild_cursor_preview(self) -> None:
        if self.cursor_preview_mesh is not None:
            self.cursor_preview_mesh.delete()
            self.cursor_preview_mesh = None
        tiny = VoxelObject((1, 1, 1), "preview", "object")
        tiny.set(0, 0, 0, tiny.add_material(self.current_material()))
        self.cursor_preview_data = build_mesh_data(tiny, self.atlas)
        self.cursor_preview_mesh = self._make_mesh(self.cursor_preview_data)
        self._cursor_preview_dirty = False

    def update(self, dt: float = 0.0) -> None:
        del dt
        if self._mesh_dirty:
            self._rebuild_meshes()
        if self._preview_dirty:
            self._rebuild_preview()
        if self._cursor_preview_dirty:
            self._rebuild_cursor_preview()
        self._update_hud()

    # ------------------------------------------------------------------
    # Picking
    # ------------------------------------------------------------------
    def update_cursor(self, mouse_x: float, mouse_y: float, width: int, height: int,
                      view: np.ndarray, projection: np.ndarray, model: np.ndarray,
                      mouse_window: tuple[float, float] | None = None) -> None:
        self.last_mouse = (float(mouse_x), float(mouse_y))
        if mouse_window is not None:
            self.last_mouse_window = (float(mouse_window[0]), float(mouse_window[1]))
        else:
            try:
                context = glfw.get_current_context()
                self.last_mouse_window = glfw.get_cursor_pos(context) if context is not None else None
            except Exception:
                self.last_mouse_window = None
        ray = screen_to_world_ray(mouse_x, mouse_y, width, height, view, projection, model)
        hit = raycast_voxels(ray, _ObjectProvider(self.project), max_distance=512.0)
        if self.tool == "select":
            self.cursor = hit.block if hit is not None else None
            self.cursor_normal = hit.normal if hit is not None else (0, 1, 0)
            return
        target: tuple[int, int, int] | None = None
        if hit is not None:
            self.cursor_normal = hit.normal
            if self.tool in ("erase", "paint"):
                target = hit.block
            else:
                target = (hit.block[0] + hit.normal[0], hit.block[1] + hit.normal[1],
                          hit.block[2] + hit.normal[2])
        else:
            self.cursor_normal = (0, 1, 0)
            if abs(float(ray.direction[1])) > 1e-6:
                distance = -float(ray.origin[1]) / float(ray.direction[1])
                if distance >= 0.0:
                    point = ray.origin + ray.direction * distance
                    x, z = math.floor(float(point[0])), math.floor(float(point[2]))
                    if 0 <= x < self.project.size[0] and 0 <= z < self.project.size[2]:
                        target = (x, 0, z)
        if target is not None and not self.map.in_bounds(*target):
            target = None
        self.cursor = target
        self.stamp_valid = None
        if self.tool == "stamp" and self.stamp is not None and target is not None:
            bounds = PlacedObject(self.stamp, target, self.stamp_rotation).bounds()
            if bounds is None:
                self.stamp_valid = False
            else:
                low, high = bounds
                self.stamp_valid = not (
                    high[0] < 0 or high[1] < 0 or high[2] < 0
                    or low[0] >= self.project.size[0]
                    or low[1] >= self.project.size[1]
                    or low[2] >= self.project.size[2]
                )

    # ------------------------------------------------------------------
    # Células / edição
    # ------------------------------------------------------------------
    def _brush_cells(self) -> list[tuple[int, int, int]]:
        if self.cursor is None:
            return []
        half = self.brush_size // 2
        start = -half
        end = start + self.brush_size
        cells = []
        for dx in range(start, end):
            for dy in range(start, end):
                for dz in range(start, end):
                    cell = (self.cursor[0] + dx, self.cursor[1] + dy, self.cursor[2] + dz)
                    if self.map.in_bounds(*cell):
                        cells.append(cell)
        return cells

    def apply_current_tool(self) -> bool:
        if self.cursor is None:
            self.status = "Nenhuma célula sob o cursor."
            return False
        if self.tool == "select":
            index = self.project.object_at(*self.cursor)
            self.selected_index = index
            self.status = "Objeto selecionado." if index is not None else "Nenhum objeto aqui."
            return index is not None
        if self.tool == "build":
            cells = [cell for cell in self._brush_cells() if not self.project.occupied(*cell)]
            if not cells:
                self.status = "As células já estão ocupadas."
                return False
            self._push_undo()
            material = self.map.add_material(self.current_material())
            for cell in cells:
                self.map.set(*cell, material)
            self._after_change(f"{len(cells)} voxel(is) criado(s).")
            return True
        if self.tool == "erase":
            cells = [cell for cell in self._brush_cells()
                     if self.map.in_bounds(*cell) and self.map.get(*cell) >= 0]
            if not cells:
                self.status = "Não há voxel da base para apagar."
                return False
            self._push_undo()
            for cell in cells:
                self.map.clear(*cell)
            self._after_change(f"{len(cells)} voxel(is) removido(s).")
            return True
        if self.tool == "paint":
            cells = [cell for cell in self._brush_cells()
                     if self.map.in_bounds(*cell) and self.map.get(*cell) >= 0]
            if not cells:
                self.status = "Não há voxel da base para pintar."
                return False
            self._push_undo()
            material = self.map.add_material(self.current_material())
            for cell in cells:
                self.map.set(*cell, material)
            self._after_change(f"{len(cells)} voxel(is) pintado(s).")
            return True
        if self.tool == "stamp":
            if self.stamp is None:
                self._load_next_library()
            if self.stamp is None:
                self.status = "Nenhum objeto na biblioteca. Use F2 para exportar um."
                return False
            bounds = PlacedObject(self.stamp, self.cursor, self.stamp_rotation).bounds()
            if bounds is None:
                self.status = "Objeto vazio."
                return False
            (low, high) = bounds
            if high[0] < 0 or high[1] < 0 or high[2] < 0 or low[0] >= self.project.size[0] or low[1] >= self.project.size[1] or low[2] >= self.project.size[2]:
                self.status = "O objeto começa fora da grade."
                return False
            self._push_undo()
            placed = self.project.add_object(self.stamp, self.cursor, self.stamp_rotation, Path(self.stamp_name).stem)
            self.selected_index = len(self.objects) - 1
            self._after_change(f"{placed.object.voxel_count} voxels de {placed.name} colocados.")
            return True
        return False

    # ------------------------------------------------------------------
    # Objeto selecionado
    # ------------------------------------------------------------------
    def _move_selected(self, dx: int, dy: int, dz: int) -> bool:
        placed = self.selected
        if placed is None:
            self.status = "Selecione um objeto primeiro."
            return False
        self._push_undo()
        placed.position = (placed.position[0] + dx, placed.position[1] + dy, placed.position[2] + dz)
        self._after_change("Objeto movido.")
        return True

    def _rotate_selected(self) -> bool:
        placed = self.selected
        if placed is None:
            return False
        self._push_undo()
        placed.rotation = (placed.rotation + 1) % 4
        self._after_change("Objeto rotacionado.")
        return True

    def _duplicate_selected(self) -> bool:
        placed = self.selected
        if placed is None:
            return False
        self._push_undo()
        copy = placed.copy()
        copy.position = (copy.position[0] + 1, copy.position[1], copy.position[2] + 1)
        self.objects.append(copy)
        self.selected_index = len(self.objects) - 1
        self._after_change("Objeto duplicado.")
        return True

    def _delete_selected(self) -> bool:
        if self.selected is None:
            return False
        self._push_undo()
        self.project.remove_object(self.selected_index)  # type: ignore[arg-type]
        self.selected_index = None
        self._after_change("Objeto excluído.")
        return True

    # ------------------------------------------------------------------
    # Mouse / teclado
    # ------------------------------------------------------------------
    def fill_base(self) -> bool:
        """Cria um piso base no nível y=0 para o mapa atual."""
        cells = [(x, z) for x in range(self.project.size[0]) for z in range(self.project.size[2])
                 if self.map.get(x, 0, z) < 0]
        if not cells:
            self.status = "A base já está preenchida."
            return False
        self._push_undo()
        material = self.map.add_material(self.current_material())
        for x, z in cells:
            self.map.set(x, 0, z, material)
        self._after_change(f"Base plana criada com {len(cells)} voxels.")
        return True

    def handle_mouse_button(self, button: int, action: int, shift: bool = False) -> bool:
        if button != glfw.MOUSE_BUTTON_LEFT:
            return False
        if action == glfw.PRESS and not shift:
            if self.last_mouse_window is not None:
                x, y = self.last_mouse_window
                if 12 <= x <= 12 + PANEL_WIDTH and 12 <= y <= 12 + PANEL_HEIGHT:
                    self._hud_action(self.hud.hit(x - 12, y - 12) if self.hud is not None else None)
                    return True
            self.dragging = True
            self.click_pending = True
            return True
        if action == glfw.RELEASE:
            self.dragging = False
        return False

    def process_click(self) -> bool:
        if not self.click_pending:
            return False
        self.click_pending = False
        result = self.apply_current_tool()
        self._last_drag_cell = self.cursor
        return result

    def update_drag(self) -> None:
        if not self.dragging or self.click_pending or self.cursor is None:
            return
        if self.tool in ("select",):
            return
        if self.cursor != self._last_drag_cell:
            self._last_drag_cell = self.cursor
            self.apply_current_tool()

    def _hud_action(self, action: str | None) -> None:
        if action is None:
            return
        if action in TOOLS:
            self.tool = action
            if action == "stamp" and self.stamp is None:
                self._load_next_library()
            self.status = f"Ferramenta: {TOOL_LABELS[action]}."
        elif action == "save":
            self.save_map()
        elif action == "load":
            self.load_map()
        elif action == "export":
            self.export_object()
        elif action == "library":
            self.open_library()
        elif action == "undo":
            self.undo()
        elif action == "redo":
            self.redo()
        elif action == "grid":
            self.show_grid = not self.show_grid
            self.status = f"Grade: {'ligada' if self.show_grid else 'desligada'}."
        elif action == "base":
            self.fill_base()
        self._update_hud()

    def handle_char(self, codepoint: int) -> bool:
        if not self.hex_mode:
            return False
        character = chr(codepoint)
        if character in "0123456789abcdefABCDEF" and len(self.hex_buffer) < 6:
            self.hex_buffer += character
            self.status = f"Hexadecimal: #{self.hex_buffer}"
            return True
        return False

    def _apply_hex(self) -> bool:
        if len(self.hex_buffer) != 6:
            self.status = "Digite exatamente 6 dígitos hexadecimais."
            return False
        try:
            value = int(self.hex_buffer, 16)
        except ValueError:
            self.status = "Cor hexadecimal inválida."
            return False
        self.custom_colour = ((value >> 16) & 255, (value >> 8) & 255, value & 255)
        self.hex_mode = False
        self.hex_buffer = ""
        self._cursor_preview_dirty = True
        self.status = f"Cor personalizada: #{value:06x}"
        return True

    def handle_key(self, key: int, action: int, mods: int) -> bool:
        if action not in (glfw.PRESS, glfw.REPEAT):
            return False
        control = bool(mods & (glfw.MOD_CONTROL | getattr(glfw, "MOD_SUPER", 0)))
        shift = bool(mods & glfw.MOD_SHIFT)
        if self.hex_mode:
            if key == glfw.KEY_ENTER or key == glfw.KEY_KP_ENTER:
                self._apply_hex()
                return True
            if key == glfw.KEY_ESCAPE:
                self.hex_mode = False
                self.hex_buffer = ""
                self.status = "Cor hexadecimal cancelada."
                return True
            if key == glfw.KEY_BACKSPACE and self.hex_buffer:
                self.hex_buffer = self.hex_buffer[:-1]
                self.status = f"Hexadecimal: #{self.hex_buffer}"
                return True
            return False
        if self.library_open:
            paths = self._library_paths()
            if key == glfw.KEY_F4 or key == glfw.KEY_ESCAPE:
                self.library_open = False
                self.library_pending_delete = None
                self.status = "Biblioteca fechada."
                return True
            if key == glfw.KEY_UP and paths:
                self.library_cursor = (self.library_cursor - 1) % len(paths)
                self.library_pending_delete = None
                return True
            if key == glfw.KEY_DOWN and paths:
                self.library_cursor = (self.library_cursor + 1) % len(paths)
                self.library_pending_delete = None
                return True
            if key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER) and paths:
                return self._load_library_path(paths[self.library_cursor % len(paths)])
            if key == glfw.KEY_D and not control:
                return self._library_duplicate()
            if key in (glfw.KEY_DELETE, glfw.KEY_BACKSPACE):
                self._library_delete()
                return True
        if control and key == glfw.KEY_Z:
            self.undo()
            return True
        if control and key == glfw.KEY_Y:
            self.redo()
            return True
        if control and key == glfw.KEY_D:
            return self._duplicate_selected()
        if key == glfw.KEY_H and not control:
            self.hex_mode = True
            self.hex_buffer = ""
            self.status = "Digite 6 dígitos hexadecimais e Enter."
            return True
        if key == glfw.KEY_F4 and not control:
            self.open_library()
            return True
        if key == glfw.KEY_TAB:
            self.tool = TOOLS[(TOOLS.index(self.tool) + (-1 if shift else 1)) % len(TOOLS)]
            if self.tool == "stamp" and self.stamp is None:
                self._load_next_library()
            self.status = f"Ferramenta: {TOOL_LABELS[self.tool]}."
            return True
        if key in (glfw.KEY_DELETE, glfw.KEY_BACKSPACE) and self.selected is not None:
            return self._delete_selected()
        if key == glfw.KEY_LEFT and self.selected is not None:
            return self._move_selected(-1, 0, 0)
        if key == glfw.KEY_RIGHT and self.selected is not None:
            return self._move_selected(1, 0, 0)
        if key == glfw.KEY_UP and self.selected is not None:
            return self._move_selected(0, 0, -1)
        if key == glfw.KEY_DOWN and self.selected is not None:
            return self._move_selected(0, 0, 1)
        if key == glfw.KEY_PAGE_UP and self.selected is not None:
            return self._move_selected(0, 1, 0)
        if key == glfw.KEY_PAGE_DOWN and self.selected is not None:
            return self._move_selected(0, -1, 0)
        if key == glfw.KEY_C and not control:
            self.custom_colour = None
            self.colour_index = (self.colour_index + (-1 if shift else 1)) % len(PALETTE)
            self._cursor_preview_dirty = True
            self.status = f"Cor: {PALETTE[self.colour_index][0]}."
            return True
        if key == glfw.KEY_X and not control:
            self.texture_index = (self.texture_index + (-1 if shift else 1)) % len(self.atlas.tile_names)
            self._cursor_preview_dirty = True
            self.status = f"Textura: {self.texture}."
            return True
        if key == glfw.KEY_R and not control:
            if self.selected is not None:
                return self._rotate_selected()
            self.stamp_rotation = (self.stamp_rotation + 1) % 4
            self._preview_dirty = True
            self.status = f"Rotação do carimbo: {self.stamp_rotation * 90}°."
            return True
        if key == glfw.KEY_G and not control:
            self.show_grid = not self.show_grid
            self.status = f"Grade: {'ligada' if self.show_grid else 'desligada'}."
            return True
        if key == glfw.KEY_LEFT_BRACKET and not control:
            self.grid_spacing = max(1, self.grid_spacing - 1)
            self.status = f"Espaçamento da grade: {self.grid_spacing}."
            return True
        if key == glfw.KEY_RIGHT_BRACKET and not control:
            self.grid_spacing = min(MAX_GRID_SPACING, self.grid_spacing + 1)
            self.status = f"Espaçamento da grade: {self.grid_spacing}."
            return True
        if key == glfw.KEY_MINUS and not control:
            self.brush_size = max(1, self.brush_size - 1)
            self.status = f"Pincel: {self.brush_size}."
            return True
        if key == glfw.KEY_EQUAL and not control:
            self.brush_size = min(MAX_BRUSH, self.brush_size + 1)
            self.status = f"Pincel: {self.brush_size}."
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
        if key == glfw.KEY_F8 and not control:
            self.fill_base()
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
            if self.selected is not None:
                obj = self.selected.object.copy()
                obj.name = self.selected.name
            else:
                obj = self.map.copy()
                obj.name = "objeto"
            obj.kind = "object"
            path = obj.save(self.export_path)
            self.status = f"Objeto exportado: {os.path.basename(path)}."
            return path
        except Exception as exc:
            self.status = f"Falha ao exportar: {exc}"
            return None

    def save_map(self) -> str | None:
        try:
            path = self.project.save(self.save_path)
            self.status = f"Mapa salvo: {os.path.basename(path)} ({len(self.objects)} objetos)."
            return path
        except Exception as exc:
            self.status = f"Falha ao salvar: {exc}"
            return None

    def load_map(self) -> bool:
        try:
            self.project = MapProject.load(self.save_path)
            self._sync_aliases()
            self.selected_index = None
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._mesh_dirty = True
            self._after_change(f"Mapa carregado: {os.path.basename(self.save_path)}.")
            if self.camera is not None:
                self.bind_camera(self.camera)
            return True
        except Exception as exc:
            self.status = f"Falha ao carregar mapa: {exc}"
            return False

    def open_library(self) -> bool:
        paths = self._library_paths()
        if not paths:
            self.status = "Biblioteca vazia: exporte um objeto com F2."
            return False
        self.library_open = True
        self.library_cursor = 0
        self.library_pending_delete = None
        self.status = "Biblioteca: ↑/↓ escolhe, Enter carimba, D duplica, Delete exclui."
        self._update_hud()
        return True

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
            self.library_open = False
            self._preview_dirty = True
            self._update_hud()
            self.status = f"Objeto carregado: {self.stamp_name} (clique para carimbar)."
            return True
        except Exception as exc:
            self.status = f"Falha ao carregar objeto: {exc}"
            return False

    def _load_library_path(self, path: str) -> bool:
        try:
            self.stamp = VoxelObject.load(path)
            self.stamp_name = os.path.basename(path)
            self.tool = "stamp"
            self.stamp_rotation = 0
            self._preview_dirty = True
            self.library_open = False
            self.status = f"Objeto carregado: {self.stamp_name} (clique para carimbar)."
            self._update_hud()
            return True
        except Exception as exc:
            self.status = f"Falha ao carregar objeto: {exc}"
            return False

    def _library_duplicate(self) -> bool:
        paths = self._library_paths()
        if not paths:
            return False
        source = paths[self.library_cursor % len(paths)]
        stem, suffix = os.path.splitext(source)
        target = f"{stem}_copia{suffix}"
        index = 2
        while os.path.exists(target):
            target = f"{stem}_copia{index}{suffix}"
            index += 1
        try:
            import shutil
            shutil.copyfile(source, target)
            self.status = f"Objeto duplicado: {os.path.basename(target)}."
            return True
        except Exception as exc:
            self.status = f"Falha ao duplicar: {exc}"
            return False

    def _library_delete(self) -> bool:
        paths = self._library_paths()
        if not paths:
            return False
        target = paths[self.library_cursor % len(paths)]
        if self.library_pending_delete != target:
            self.library_pending_delete = target
            self.status = f"Delete novamente para excluir {os.path.basename(target)}."
            return False
        try:
            os.remove(target)
            self.library_pending_delete = None
            self.library_cursor = min(self.library_cursor, max(0, len(self._library_paths()) - 1))
            self.status = f"Objeto excluído: {os.path.basename(target)}."
            return True
        except Exception as exc:
            self.status = f"Falha ao excluir: {exc}"
            return False

    def _dropped_by_shrink(self, new_size: tuple[int, int, int]) -> int:
        blocks = self.map.blocks
        inside = np.zeros(blocks.shape, dtype=bool)
        common = tuple(min(old, new) for old, new in zip(blocks.shape, new_size))
        inside[: common[0], : common[1], : common[2]] = True
        return int(np.count_nonzero((blocks != -1) & ~inside))

    def resize_grid(self, delta: int) -> bool:
        old = self.project.size
        new = tuple(max(1, min(MAX_DIM, value + int(delta))) for value in old)
        if new == old:
            self.status = "A grade não mudou."
            return False
        dropped = self._dropped_by_shrink(new) if any(n < o for n, o in zip(new, old)) else 0
        if dropped and self.pending_shrink != (new, dropped):
            self.pending_shrink = (new, dropped)
            self.status = f"{dropped} voxel(is) ficarão fora. Pressione F6 novamente para confirmar."
            return False
        self.pending_shrink = None
        self._push_undo()
        self.project.resize(new)
        self._after_change(f"Grade: {new[0]}x{new[1]}x{new[2]}.")
        if self.camera is not None:
            self.bind_camera(self.camera)
        return True

    # ------------------------------------------------------------------
    # HUD / render
    # ------------------------------------------------------------------
    def _update_hud(self) -> None:
        if self.hud is None:
            return
        cursor = "—" if self.cursor is None else f"({self.cursor[0]}, {self.cursor[1]}, {self.cursor[2]})"
        selected = self.selected.name if self.selected is not None else "nenhum"
        if self.library_open:
            paths = self._library_paths()
            entries = []
            for index, path in enumerate(paths[:5]):
                marker = ">" if index == self.library_cursor % max(1, len(paths)) else " "
                entries.append((f"{marker} {index + 1}. {os.path.basename(path)}", (200, 210, 220)))
            if not entries:
                entries = [("(biblioteca vazia)", (200, 210, 220))]
            entries.append(("↑/↓ escolhe  Enter carimba  D duplica  Del exclui  F4 fecha", (245, 210, 120)))
            self.hud.set_state("BIBLIOTECA DE OBJETOS", entries, swatch=self.colour, active_tool=self.tool)
            return
        lines = [
            (f"Ferramenta: {TOOL_LABELS[self.tool]} [Tab]  Pincel: {self.brush_size} [-/+]", (225, 230, 238)),
            (f"Cor: {self.colour_name} [C]  Textura: {self.texture} [X]", (200, 210, 220)),
            (f"Grid: {self.grid_size[0]}x{self.grid_size[1]}x{self.grid_size[2]} [F6/F7] passo {self.grid_spacing} [/] max 64", (200, 210, 220)),
            (f"Objetos: {len(self.objects)}  Selecionado: {selected}", (200, 210, 220)),
            (f"Cursor: {cursor}  Voxels: {self.project.voxel_count}", (200, 210, 220)),
            (self.status, (245, 210, 120)),
        ]
        if self.tool == "stamp" and self.stamp is not None and self.stamp_valid is False:
            lines[-1] = ("Carimbo fora da grade — escolha outra célula.", (245, 120, 100))
        if self.hex_mode:
            lines[-1] = (f"Hexadecimal: #{self.hex_buffer}_  (Enter aplica, Esc cancela)", (245, 210, 120))
        self.hud.set_state("EDITOR DE MAPA — ISOMETRICON", lines, swatch=self.colour, active_tool=self.tool)

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

    def _draw_alpha_mesh(self, shader, projection, view, model, mesh, origin, alpha: float) -> None:
        if mesh is None:
            return
        shader.use()
        shader.set_mat4("u_Projection", projection)
        shader.set_mat4("u_View", view)
        shader.set_mat4("u_Model", model @ mat4_translate(*origin))
        shader.set_float("u_Alpha", alpha)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthMask(gl.GL_FALSE)
        mesh.draw()
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_BLEND)
        shader.set_float("u_Alpha", 1.0)

    def render(self, shader, projection: np.ndarray, view: np.ndarray, model: np.ndarray,
               time: float, window_width: int, window_height: int) -> None:
        if not self.create_gl:
            return
        self.update()
        if self.platform is not None:
            self.platform.render(projection, view, model, (self.project.size[0], self.project.size[2]),
                                 None if self.cursor is None else (self.cursor[0], self.cursor[2]),
                                 time, self.show_grid, self.grid_spacing)
        self._common_shader(shader, projection, view, model)
        if self.mesh is not None and self.mesh_data.vertex_count:
            shader.set_mat4("u_Model", model)
            self.mesh.draw()
        for placed, mesh, _ in self.object_meshes:
            if mesh is not None:
                shader.set_mat4("u_Model", model @ mat4_translate(*placed.position))
                mesh.draw()

        if self.tool == "stamp" and self.preview_mesh is not None and self.cursor is not None:
            self._draw_alpha_mesh(shader, projection, view, model, self.preview_mesh, self.cursor, 0.42)
        elif self.tool in ("build", "paint") and self.cursor_preview_mesh is not None and self.cursor is not None:
            self._draw_alpha_mesh(shader, projection, view, model, self.cursor_preview_mesh, self.cursor, 0.55)

        if self.selected is not None and self.selection_box is not None:
            bounds = self.selected.bounds()
            if bounds is not None:
                self.selection_box.render(projection, view, model, bounds[0], bounds[1])

        if self.cursor is not None and self.highlight is not None:
            x, y, z = self.cursor
            if self.tool == "erase" or (self.tool == "stamp" and self.stamp_valid is False):
                colour = (1.0, 0.35, 0.30)
            elif self.tool == "stamp" and self.stamp_valid:
                colour = (0.45, 1.0, 0.55)
            else:
                colour = (1.0, 0.85, 0.30)
            self.highlight.render(view, projection, model, x, y, z, time=time, base_color=colour)

        if self.hud is not None:
            self._update_hud()
            self.hud.render(window_width, window_height)

    def delete(self) -> None:
        for mesh in [self.mesh, self.preview_mesh, self.cursor_preview_mesh] + [item[1] for item in self.object_meshes]:
            if mesh is not None:
                mesh.delete()
        self.mesh = None
        self.preview_mesh = None
        self.cursor_preview_mesh = None
        self.object_meshes = []
        if self.platform is not None:
            self.platform.delete()
            self.platform = None
        if self.selection_box is not None:
            self.selection_box.delete()
            self.selection_box = None
        if self.highlight is not None:
            self.highlight.delete()
            self.highlight = None
        if self.hud is not None:
            self.hud.delete()
            self.hud = None
        self.atlas.delete()
