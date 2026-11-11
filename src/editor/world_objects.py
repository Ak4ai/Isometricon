"""Objetos voxel colocados no mundo procedural infinito.

O objeto é uma entidade independente (não é gravado nos chunks): o terreno
continua sendo gerado normalmente, e colisão/raycast combinam terreno + objetos.
A persistência é por seed, em ``saves/mundos/mundo_<seed>.json``.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw, ImageFont

from src.editor.map_project import PlacedObject
from src.editor.material_atlas import MaterialAtlas
from src.editor.object_mesher import ObjectMeshData, build_mesh_data
from src.editor.selection import SelectionBoxRenderer
from src.editor.voxel_object import VoxelObject
from src.interaction import raycast_voxels, screen_to_world_ray
from src.math import mat4_translate
from src.rendering.hud_quad import HudQuad
from src.rendering.mesh import TexturedMesh
from src.world import BlockType

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORLD_FORMAT = "isometricon-world-objects"
WORLD_VERSION = 1
CLICK_COOLDOWN = 0.25
PANEL_WIDTH = 440
PANEL_HEIGHT = 202
_FONT_CANDIDATES = (
    "consola.ttf", "consolas.ttf", "C:/Windows/Fonts/consola.ttf",
    "segoeui.ttf", "arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Menlo.ttf",
)


class WorldObjectStore:
    """Lista persistida de objetos de uma seed."""

    def __init__(self, seed: int, objects: Iterable[PlacedObject] | None = None,
                 path: str | None = None) -> None:
        self.seed = int(seed)
        self.objects: list[PlacedObject] = [item.copy() for item in (objects or [])]
        self.path = os.path.abspath(path or os.path.join(
            PROJECT_ROOT, "saves", "mundos", f"mundo_{self.seed}.json"))

    @classmethod
    def load(cls, path: str | os.PathLike) -> "WorldObjectStore":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("format") != WORLD_FORMAT or int(data.get("version", -1)) != WORLD_VERSION:
            raise ValueError("Formato de objetos de mundo não suportado.")
        seed = int(data.get("seed", 0))
        objects = [PlacedObject.from_dict(item) for item in data.get("objects", [])]
        return cls(seed, objects, os.fspath(path))

    @classmethod
    def load_seed(cls, seed: int) -> "WorldObjectStore":
        store = cls(seed)
        if not os.path.exists(store.path):
            return store
        loaded = cls.load(store.path)
        loaded.seed = int(seed)
        return loaded

    def occupied(self, x: int, y: int, z: int) -> bool:
        return any(item.occupies(int(x), int(y), int(z)) for item in self.objects)

    def object_at(self, x: int, y: int, z: int) -> int | None:
        for index in range(len(self.objects) - 1, -1, -1):
            if self.objects[index].occupies(int(x), int(y), int(z)):
                return index
        return None

    def add(self, obj: VoxelObject, position: tuple[int, int, int], rotation: int,
            name: str, source: str = "") -> PlacedObject:
        placed = PlacedObject(obj.copy(), position, rotation, name, source)
        self.objects.append(placed)
        return placed

    def remove(self, index: int) -> PlacedObject:
        return self.objects.pop(index)

    def to_dict(self) -> dict:
        return {
            "format": WORLD_FORMAT,
            "version": WORLD_VERSION,
            "seed": self.seed,
            "objects": [item.to_dict() for item in self.objects],
        }

    def save(self) -> str:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=1)
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        return self.path


class WorldObjectProvider:
    """Combina terreno + objetos e implementa o contrato VoxelGridProvider."""

    def __init__(self, store: WorldObjectStore, terrain_lookup: Callable[[int, int, int], BlockType],
                 terrain_height: Callable[[float, float], int] | None = None) -> None:
        self.store = store
        self.terrain_lookup = terrain_lookup
        self.terrain_height = terrain_height

    def get_block_at(self, x: int, y: int, z: int) -> BlockType:
        if self.store.occupied(x, y, z):
            return BlockType.STONE
        return BlockType(self.terrain_lookup(int(x), int(y), int(z)))

    def get_top_solid_block(self, x: int, z: int) -> int:
        top = int(self.terrain_height(float(x), float(z))) if self.terrain_height is not None else 0
        for item in self.store.objects:
            bounds = item.bounds()
            if bounds is None:
                continue
            low, high = bounds
            if low[0] <= x <= high[0] and low[2] <= z <= high[2]:
                top = max(top, high[1])
        for y in range(top, -1, -1):
            if self.get_block_at(x, y, z) != BlockType.AIR:
                return y
        return -1

    def is_solid(self, x: int, y: int, z: int) -> bool:
        return self.get_block_at(x, y, z) != BlockType.AIR


class WorldTokenProvider:
    """Colisão do token: terreno como coluna até a altura + objetos colocados.

    Mantém o comportamento de altura do modo terreno (o token não cai em
    cavernas) e adiciona as células dos objetos.
    """

    def __init__(self, store: WorldObjectStore, terrain_height: Callable[[float, float], int]) -> None:
        self.store = store
        self.terrain_height = terrain_height

    def get_block_at(self, x: int, y: int, z: int) -> BlockType:
        if self.store.occupied(int(x), int(y), int(z)):
            return BlockType.STONE
        return BlockType.STONE if int(y) <= int(self.terrain_height(float(x), float(z))) else BlockType.AIR

    def get_top_solid_block(self, x: int, z: int) -> int:
        top = int(self.terrain_height(float(x), float(z)))
        for item in self.store.objects:
            bounds = item.bounds()
            if bounds is None:
                continue
            low, high = bounds
            if low[0] <= x <= high[0] and low[2] <= z <= high[2]:
                top = max(top, high[1])
        return top


class WorldObjectRenderer:
    def __init__(self, store: WorldObjectStore, create_gl: bool = True) -> None:
        self.store = store
        self.create_gl = create_gl
        self.atlas = MaterialAtlas(create_gl=create_gl)
        self.meshes: list[tuple[PlacedObject, TexturedMesh | None]] = []
        if create_gl:
            self.rebuild()

    def rebuild(self) -> None:
        for _, mesh in self.meshes:
            if mesh is not None:
                mesh.delete()
        self.meshes = []
        if not self.create_gl:
            return
        for placed in self.store.objects:
            data = build_mesh_data(placed.rendered_object(), self.atlas)
            mesh = TexturedMesh(data.vertices.flatten(), data.indices) if data.vertex_count else None
            self.meshes.append((placed, mesh))

    def render(self, shader, model: np.ndarray, cutaway: bool = False,
               player_y: float = 0.0) -> None:
        if not self.create_gl:
            return
        shader.use()
        shader.set_bool("u_Skinned", False)
        shader.set_bool("u_UndergroundMode", cutaway)
        shader.set_bool("u_WaterMode", False)
        shader.set_float("u_PlayerY", float(player_y))
        shader.set_float("u_CutawayAlpha", 0.38)
        shader.set_float("u_CutawayFade", 0.45)
        shader.set_int("u_CutawayPass", 0)
        shader.set_float("u_Vitiligo", 0.0)
        shader.set_int("u_Underwear", 0)
        shader.set_float("u_Alpha", 1.0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.atlas.texture_id)
        shader.set_int("u_TextureAtlas", 0)
        for placed, mesh in self.meshes:
            if mesh is not None:
                shader.set_mat4("u_Model", model @ mat4_translate(*placed.position))
                mesh.draw()
        if cutaway:
            gl.glEnable(gl.GL_BLEND)
            gl.glDepthFunc(gl.GL_ALWAYS)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
            shader.set_int("u_CutawayPass", 1)
            for placed, mesh in self.meshes:
                if mesh is not None:
                    shader.set_mat4("u_Model", model @ mat4_translate(*placed.position))
                    mesh.draw()
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDisable(gl.GL_BLEND)
            shader.set_int("u_CutawayPass", 0)
            shader.set_bool("u_UndergroundMode", False)

    def delete(self) -> None:
        for _, mesh in self.meshes:
            if mesh is not None:
                mesh.delete()
        self.meshes = []
        self.atlas.delete()


class WorldObjectHud:
    ACTIONS = (
        ("place", "Colocar"),
        ("select", "Selecionar"),
        ("object", "Objeto"),
        ("rotate", "Girar"),
        ("remove", "Remover"),
        ("cancel", "Sair"),
    )

    def __init__(self) -> None:
        self.quad: HudQuad | None = HudQuad()
        self._key: tuple | None = None
        self._image: Image.Image | None = None
        self._dirty = False
        self._buttons: dict[str, tuple[int, int, int, int]] = {}

    def _font(self, size: int) -> Any:
        for candidate in _FONT_CANDIDATES:
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def set_state(self, title: str, lines: Iterable[tuple[str, tuple[int, int, int]]],
                  active_mode: str = "off") -> None:
        rows = tuple(lines)
        key = (title, rows, active_mode)
        if key == self._key:
            return
        self._key = key
        image = Image.new("RGBA", (PANEL_WIDTH, PANEL_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, PANEL_WIDTH - 1, PANEL_HEIGHT - 1), radius=10,
                               fill=(13, 18, 26, 238), outline=(232, 186, 76, 255), width=2)
        draw.text((14, 10), title, font=self._font(16), fill=(240, 208, 120, 255))
        y = 36
        for text, colour in rows:
            draw.text((14, y), text, font=self._font(13), fill=(*colour, 255))
            y += 18
        self._buttons = {}
        for index, (action, label) in enumerate(self.ACTIONS):
            box = (12 + index * 70, 158, 12 + index * 70 + 66, 188)
            self._buttons[action] = box
            active = action == active_mode
            draw.rounded_rectangle(box, radius=5,
                                   fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                                   outline=(240, 205, 120, 255) if active else (80, 95, 115, 255),
                                   width=1)
            colour = (20, 24, 30, 255) if active else (210, 218, 228, 255)
            try:
                width = draw.textbbox((0, 0), label, font=self._font(10))[2]
            except Exception:
                width = len(label) * 6
            draw.text((box[0] + (box[2] - box[0] - width) / 2, box[1] + 6),
                      label, font=self._font(10), fill=colour)
        self._image = image
        self._dirty = True

    def hit(self, x: float, y: float) -> str | None:
        for action, (x0, y0, x1, y1) in self._buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return action
        return None

    def render(self, window_width: int, window_height: int) -> None:
        if self._image is None or self.quad is None:
            return
        if self._dirty:
            self.quad.set_image(self._image)
            self._dirty = False
        self.quad.draw(float(window_width - PANEL_WIDTH - 16), 16.0, window_width, window_height)

    def contains(self, x: float, y: float, window_width: int) -> bool:
        x0 = window_width - PANEL_WIDTH - 16
        return x0 <= x <= x0 + PANEL_WIDTH and 16 <= y <= 16 + PANEL_HEIGHT

    def hit_window(self, x: float, y: float, window_width: int) -> str | None:
        x0 = window_width - PANEL_WIDTH - 16
        if not self.contains(x, y, window_width):
            return None
        return self.hit(x - x0, y - 16)

    def delete(self) -> None:
        if self.quad is not None:
            self.quad.delete()
            self.quad = None


class WorldObjectEditor:
    """Modo de colocação/seleção de objetos no ``--terrain`` procedural."""

    OFF = "off"
    PLACE = "place"
    SELECT = "select"

    def __init__(self, seed: int, terrain_lookup: Callable[[int, int, int], BlockType],
                 terrain_height: Callable[[float, float], int] | None = None,
                 create_gl: bool = True, store_path: str | None = None) -> None:
        self.seed = int(seed)
        try:
            if store_path is not None:
                self.store = (WorldObjectStore.load(store_path) if os.path.exists(store_path)
                              else WorldObjectStore(seed, path=store_path))
            else:
                self.store = WorldObjectStore.load_seed(seed)
        except Exception as exc:
            self.store = WorldObjectStore(seed, path=store_path) if store_path is not None else WorldObjectStore(seed)
            self._load_error = str(exc)
        else:
            self._load_error = ""
        self.provider = WorldObjectProvider(self.store, terrain_lookup, terrain_height)
        self.token_provider = WorldTokenProvider(self.store, terrain_height) if terrain_height is not None else None
        self.create_gl = create_gl
        self.renderer = WorldObjectRenderer(self.store, create_gl=create_gl) if create_gl else None
        self.selection_box = SelectionBoxRenderer() if create_gl else None
        self.hud = WorldObjectHud() if create_gl else None
        self.library_dir = os.path.join(PROJECT_ROOT, "assets", "objects")
        self.export_path = os.path.join(PROJECT_ROOT, "saves", "objeto.json")
        self.stamp: VoxelObject | None = None
        self.stamp_name = ""
        self.source = ""
        self.rotation = 0
        self.mode = self.OFF
        self.cursor: tuple[int, int, int] | None = None
        self.valid = False
        self.preview_mesh: TexturedMesh | None = None
        self.preview_data: ObjectMeshData | None = None
        self.selected_index: int | None = None
        self.status = (f"Objetos da seed não carregados: {self._load_error}" if self._load_error
                       else "P: colocar objeto  V: selecionar  F3: biblioteca")
        self._preview_dirty = True
        self._meshes_dirty = True
        self.last_mouse_window: tuple[float, float] | None = None
        self._last_click_time = 0.0
        self.token_position: tuple[float, float, float] | None = None
        self._window_width = 1280
        if create_gl:
            self._rebuild_meshes()
            self._rebuild_preview()
        self._update_hud()

    @property
    def selected(self) -> PlacedObject | None:
        if self.selected_index is None or not 0 <= self.selected_index < len(self.store.objects):
            return None
        return self.store.objects[self.selected_index]

    @property
    def mode_label(self) -> str:
        return {self.OFF: "desligado", self.PLACE: "colocar", self.SELECT: "selecionar"}[self.mode]

    # ------------------------------------------------------------------
    # Seeds e arquivos
    # ------------------------------------------------------------------
    def switch_seed(self, seed: int) -> None:
        self.seed = int(seed)
        try:
            self.store = WorldObjectStore.load_seed(seed)
        except Exception as exc:
            self.store = WorldObjectStore(seed)
            self.status = f"Objetos da seed não carregados: {exc}"
        self.provider.store = self.store
        if self.token_provider is not None:
            self.token_provider.store = self.store
        if self.renderer is not None:
            self.renderer.store = self.store
        self.selected_index = None
        self.mode = self.OFF
        self._meshes_dirty = True
        self._update_hud()

    def save(self) -> str | None:
        try:
            path = self.store.save()
            self.status = f"Objetos salvos: {os.path.basename(path)}."
            return path
        except Exception as exc:
            self.status = f"Falha ao salvar objetos: {exc}"
            return None

    # ------------------------------------------------------------------
    # Malhas
    # ------------------------------------------------------------------
    def _rebuild_meshes(self) -> None:
        if self.renderer is not None:
            self.renderer.rebuild()
        self._meshes_dirty = False

    def _rebuild_preview(self) -> None:
        if self.preview_mesh is not None:
            self.preview_mesh.delete()
            self.preview_mesh = None
        if self.stamp is None or not self.create_gl:
            self._preview_dirty = False
            return
        rotated = self.stamp.rotated_y(self.rotation)
        data = build_mesh_data(rotated, self.renderer.atlas)  # type: ignore[union-attr]
        self.preview_data = data
        if data.vertex_count:
            self.preview_mesh = TexturedMesh(data.vertices.flatten(), data.indices)
        self._preview_dirty = False

    def update(self) -> None:
        if self._meshes_dirty:
            self._rebuild_meshes()
        if self._preview_dirty:
            self._rebuild_preview()
        self._update_hud()

    # ------------------------------------------------------------------
    # Biblioteca
    # ------------------------------------------------------------------
    def _library_paths(self) -> list[str]:
        paths = sorted(str(path) for path in Path(self.library_dir).glob("*.json"))
        if os.path.exists(self.export_path) and self.export_path not in paths:
            paths.append(self.export_path)
        return paths

    def load_object(self, path: str) -> bool:
        try:
            self.stamp = VoxelObject.load(path)
            self.stamp_name = os.path.basename(path)
            self.source = os.path.abspath(path)
            self.rotation = 0
            self.mode = self.PLACE
            self._preview_dirty = True
            self.status = f"Objeto: {self.stamp_name}. Clique no topo do terreno."
            self._update_hud()
            return True
        except Exception as exc:
            self.status = f"Falha ao carregar objeto: {exc}"
            return False

    def _load_next_library(self) -> bool:
        paths = self._library_paths()
        if not paths:
            self.status = "Biblioteca vazia."
            return False
        index = getattr(self, "_library_index", -1) + 1
        index %= len(paths)
        self._library_index = index
        path = paths[index]
        try:
            self.stamp = VoxelObject.load(path)
            self.stamp_name = os.path.basename(path)
            self.source = path
            self.rotation = 0
            self.mode = self.PLACE
            self._preview_dirty = True
            self.status = f"Objeto: {self.stamp_name}. Clique no topo do terreno."
            self._update_hud()
            return True
        except Exception as exc:
            self.status = f"Falha ao carregar objeto: {exc}"
            return False

    # ------------------------------------------------------------------
    # Colocação / seleção
    # ------------------------------------------------------------------
    def _object_grid_cells(self, obj: VoxelObject, position: tuple[int, int, int],
                           rotation: int) -> list[tuple[int, int, int]]:
        rotated = obj.rotated_y(rotation)
        return [(position[0] + int(x), position[1] + int(y), position[2] + int(z))
                for x, y, z in np.argwhere(rotated.blocks != -1)]

    def _overlaps_token(self, cells: list[tuple[int, int, int]], token_position) -> bool:
        if token_position is None:
            return False
        tx, ty, tz = (float(token_position[0]), float(token_position[1]), float(token_position[2]))
        for x, y, z in cells:
            if not (x + 1 <= tx - 0.35 or x >= tx + 0.35 or
                    z + 1 <= tz - 0.35 or z >= tz + 0.35 or
                    y + 1 <= ty or y >= ty + 1.8):
                return True
        return False

    def update_cursor(self, mouse_x: float, mouse_y: float, width: int, height: int,
                      view: np.ndarray, projection: np.ndarray, model: np.ndarray,
                      token_position=None, mouse_window: tuple[float, float] | None = None) -> None:
        self._window_width = int(width)
        self.last_mouse_window = mouse_window
        if token_position is not None:
            self.token_position = (float(token_position[0]), float(token_position[1]), float(token_position[2]))
        if self.mode == self.OFF:
            self.cursor = None
            self.valid = False
            return
        ray = screen_to_world_ray(mouse_x, mouse_y, width, height, view, projection, model)
        hit = raycast_voxels(ray, self.provider, max_distance=512.0)
        if self.mode == self.SELECT:
            self.cursor = hit.block if hit is not None else None
            self.valid = self.cursor is not None
            return
        self.valid = False
        if hit is None or self.stamp is None:
            self.cursor = None
            return
        if hit.normal != (0, 1, 0):
            self.cursor = hit.block
            return
        target = (hit.block[0], hit.block[1] + 1, hit.block[2])
        self.cursor = target
        if hit.block_type == BlockType.WATER:
            return
        cells = self._object_grid_cells(self.stamp, target, self.rotation)
        if not cells:
            return
        if any(self.store.occupied(*cell) for cell in cells):
            return
        if any(self.provider.get_block_at(*cell) == BlockType.WATER for cell in cells):
            return
        if self._overlaps_token(cells, token_position):
            return
        self.valid = True

    def place_current(self) -> bool:
        if self.mode != self.PLACE or self.stamp is None or self.cursor is None:
            return False
        if not self.valid:
            self.status = "Posição inválida: aponte para o topo de um bloco."
            return False
        name = Path(self.stamp_name).stem or self.stamp.name
        self.store.add(self.stamp, self.cursor, self.rotation, name, self.source)
        self.selected_index = len(self.store.objects) - 1
        self.save()
        self._meshes_dirty = True
        self.status = f"{name} colocado em {self.cursor}."
        self._update_hud()
        return True

    def select_at_cursor(self) -> bool:
        if self.cursor is None:
            return False
        self.selected_index = self.store.object_at(*self.cursor)
        self.status = "Objeto selecionado." if self.selected_index is not None else "Nenhum objeto aqui."
        return self.selected_index is not None

    def remove_selected(self) -> bool:
        if self.selected is None:
            return False
        self.store.remove(self.selected_index)  # type: ignore[arg-type]
        self.selected_index = None
        self.save()
        self._meshes_dirty = True
        self.status = "Objeto removido."
        self._update_hud()
        return True

    def rotate_selected(self) -> bool:
        if self.selected is None:
            return False
        self.selected.rotation = (self.selected.rotation + 1) % 4
        self.save()
        self._meshes_dirty = True
        self.status = "Objeto rotacionado."
        return True

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def toggle_place(self) -> bool:
        if self.mode == self.PLACE:
            self.mode = self.OFF
            self.status = "Modo de colocação desligado."
        else:
            if self.stamp is None:
                return self._load_next_library()
            self.mode = self.PLACE
            self.status = f"Colocando {self.stamp_name}."
        self.valid = False
        self._update_hud()
        return True

    def _hud_action(self, action: str | None) -> None:
        if action is None:
            return
        if action == "place":
            self.toggle_place()
        elif action == "select":
            self.mode = self.SELECT
            self.selected_index = None
            self.status = "Clique em um objeto para selecionar."
        elif action == "object":
            self._load_next_library()
        elif action == "rotate":
            if self.mode == self.PLACE:
                self.rotation = (self.rotation + 1) % 4
                self._preview_dirty = True
                self.status = f"Rotação: {self.rotation * 90}°."
            else:
                self.rotate_selected()
        elif action == "remove":
            self.remove_selected()
        elif action == "cancel":
            self.mode = self.OFF
            self.selected_index = None
            self.valid = False
            self.status = "Objetos: modo desligado."
        self._update_hud()

    def handle_key(self, key: int, action: int, mods: int) -> bool:
        if action not in (glfw.PRESS, glfw.REPEAT):
            return False
        if key == glfw.KEY_P:
            return self.toggle_place()
        if key == glfw.KEY_V:
            self.mode = self.SELECT
            self.selected_index = None
            self.status = "Clique em um objeto para selecionar."
            self._update_hud()
            return True
        if key == glfw.KEY_ESCAPE and self.mode != self.OFF:
            self.mode = self.OFF
            self.selected_index = None
            self.valid = False
            self.status = "Objetos: modo desligado."
            self._update_hud()
            return True
        if self.mode == self.OFF:
            return False
        if key == glfw.KEY_F3:
            return self._load_next_library()
        if key == glfw.KEY_R:
            if self.mode == self.SELECT and self.selected is not None:
                return self.rotate_selected()
            if self.mode == self.PLACE:
                self.rotation = (self.rotation + 1) % 4
                self._preview_dirty = True
                self.status = f"Rotação: {self.rotation * 90}°."
            return True
        if key in (glfw.KEY_DELETE, glfw.KEY_BACKSPACE):
            return self.remove_selected()
        if key == glfw.KEY_F5:
            self.save()
            return True
        return False

    def handle_mouse_button(self, button: int, action: int, shift: bool = False) -> bool:
        if button != glfw.MOUSE_BUTTON_LEFT or action != glfw.PRESS or shift:
            return False
        if self.mode == self.OFF:
            return False
        if self.last_mouse_window is not None and self.hud is not None:
            action = self.hud.hit_window(self.last_mouse_window[0], self.last_mouse_window[1], self._window_width)
            if action is not None:
                self._hud_action(action)
                return True
            if self.hud.contains(self.last_mouse_window[0], self.last_mouse_window[1], self._window_width):
                return True
        now = time.monotonic()
        if now - self._last_click_time < CLICK_COOLDOWN:
            return True
        self._last_click_time = now
        if self.mode == self.PLACE:
            self.place_current()
            return True
        if self.mode == self.SELECT:
            self.select_at_cursor()
            return True
        return False

    # ------------------------------------------------------------------
    # HUD / render
    # ------------------------------------------------------------------
    def _update_hud(self) -> None:
        if self.hud is None:
            return
        selected = self.selected.name if self.selected is not None else "nenhum"
        cursor = "—" if self.cursor is None else f"({self.cursor[0]}, {self.cursor[1]}, {self.cursor[2]})"
        validity = "—" if self.mode == self.OFF else ("válida" if self.valid else "inválida")
        lines = [
            (f"Modo: {self.mode_label}   Objeto: {self.stamp_name or 'nenhum'}", (220, 226, 235)),
            (f"Objetos: {len(self.store.objects)}   Selecionado: {selected}", (200, 210, 220)),
            (f"Cursor: {cursor}   Posição: {validity}", (200, 210, 220)),
            (f"Seed: {self.seed}", (170, 180, 195)),
            (self.status, (245, 210, 120)),
            ("P colocar  V selecionar  F3 objeto  R girar  Esc sair  Del remover", (150, 160, 175)),
        ]
        self.hud.set_state("OBJETOS NO MUNDO — ISOMETRICON", lines, active_mode=self.mode)

    def _token_inside_object(self) -> bool:
        if self.token_position is None:
            return False
        tx, ty, tz = self.token_position
        for placed in self.store.objects:
            bounds = placed.bounds()
            if bounds is None:
                continue
            low, high = bounds
            if (low[0] <= tx < high[0] + 1.0 and low[1] <= ty < high[1] + 1.0
                    and low[2] <= tz < high[2] + 1.0):
                return True
        return False

    def _draw_alpha(self, shader, projection: np.ndarray, view: np.ndarray, model: np.ndarray,
                    mesh: TexturedMesh, origin, alpha: float) -> None:
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

    def render(self, shader, projection: np.ndarray, view: np.ndarray, model: np.ndarray) -> None:
        if not self.create_gl:
            return
        self.update()
        inside = self._token_inside_object()
        if self.renderer is not None:
            self.renderer.render(shader, model, cutaway=inside,
                                 player_y=float(self.token_position[1]) if self.token_position else 0.0)
        if self.mode == self.PLACE and self.valid and self.cursor is not None and self.preview_mesh is not None:
            self._draw_alpha(shader, projection, view, model, self.preview_mesh, self.cursor, 0.30)
        selected = self.selected
        if selected is not None and self.selection_box is not None:
            bounds = selected.bounds()
            if bounds is not None:
                self.selection_box.render(projection, view, model, bounds[0], bounds[1],
                                          (1.0, 0.85, 0.25))
        if self.mode == self.PLACE and self.cursor is not None and self.stamp is not None and self.selection_box is not None:
            preview = PlacedObject(self.stamp, self.cursor, self.rotation)
            bounds = preview.bounds()
            if bounds is not None:
                colour = (0.45, 1.0, 0.55) if self.valid else (1.0, 0.35, 0.30)
                self.selection_box.render(projection, view, model, bounds[0], bounds[1], colour)

    def render_hud(self, window_width: int, window_height: int) -> None:
        if self.hud is not None:
            self._update_hud()
            self.hud.render(window_width, window_height)

    def delete(self) -> None:
        if self.preview_mesh is not None:
            self.preview_mesh.delete()
            self.preview_mesh = None
        if self.renderer is not None:
            self.renderer.delete()
            self.renderer = None
        if self.selection_box is not None:
            self.selection_box.delete()
            self.selection_box = None
        if self.hud is not None:
            self.hud.delete()
            self.hud = None
