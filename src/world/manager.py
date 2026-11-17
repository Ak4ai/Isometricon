"""Gerenciador dinâmico de mundo (WorldManager) para carregamento contínuo/infinito de chunks."""

import math
import queue
import threading
from collections import deque
from typing import Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

import numpy as np

from src.math import mat4_scale, mat4_translate
from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.mesher import ChunkMeshData, ChunkMesher, blocks_around
from src.world.terrain import TerrainGenerator
from src.world.water import TICK as WATER_TICK, WaterSimulation

WATER_CELLS_PER_FRAME = 64  # células de água avaliadas por quadro (até ~8 ms nas encostas): a onda leva alguns quadros

if TYPE_CHECKING:
    from src.rendering.mesh import TexturedMesh

_CORNERS_16 = np.array([
    [0.0, 0.0, 0.0, 1.0],
    [16.0, 0.0, 0.0, 1.0],
    [0.0, 16.0, 0.0, 1.0],
    [16.0, 16.0, 0.0, 1.0],
    [0.0, 0.0, 16.0, 1.0],
    [16.0, 0.0, 16.0, 1.0],
    [0.0, 16.0, 16.0, 1.0],
    [16.0, 16.0, 16.0, 1.0],
], dtype=np.float32)


class WorldManager:
    """Gerencia o ciclo de vida, streaming contínuo e renderização assíncrona de chunks."""

    def __init__(
        self,
        generator: TerrainGenerator,
        render_distance: int = 2,
        create_gl_meshes: bool = True,
        atlas: object = None,
        async_loading: bool = True,
    ) -> None:
        self.generator = generator
        self.render_distance = render_distance
        self.create_gl_meshes = create_gl_meshes
        self.atlas = atlas
        self.async_loading = bool(async_loading and create_gl_meshes)

        # Chunks carregados na memória lógica: (cx, cy, cz) -> Chunk3D
        self.chunks: Dict[Tuple[int, int, int], Chunk3D] = {}
        self._chunks_lock = threading.Lock()

        # Malhas OpenGL ativas na GPU: (cx, cy, cz) -> (TexturedMesh, transform_matrix)
        self.meshes: Dict[Tuple[int, int, int], Tuple[TexturedMesh, np.ndarray]] = {}
        self._pending_mesh_deletions: List[object] = []

        self.mesher = ChunkMesher(atlas=atlas, ambient_occlusion=True)
        self._last_center: Tuple[int, int] | None = None
        # Revisão barata para consumidores que precisam reagir a streaming sem
        # observar o dicionário interno enquanto a worker o modifica.
        self._chunk_revision = 0

        # Estruturas para geração assíncrona em background thread
        self._request_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_busy = threading.Event()
        self._in_progress: Set[Tuple[int, int, int]] = set()
        self._worker_thread: Optional[threading.Thread] = None
        # Água com as regras do Minecraft (src/world/water.py). ``_water_levels`` é a altura da superfície de cada
        # célula de água corrente, que a malha usa; a fonte fica de fora (cheia).
        self.water = WaterSimulation(_ManagerFluidWorld(self))
        self._water_levels = self.water.heights
        self._water_seeded_chunks: set[tuple[int, int, int]] = set()
        self._water_tick = 0.0
        self.water_step_interval = WATER_TICK
        # A água que se espalha sozinha junta as mudanças e refaz malhas/revisão no máximo a cada
        # ``water_remesh_interval`` s: cada refazer custa a malha na worker e, no quadro, o cômodo e a grade.
        self.water_remesh_interval = 0.5
        self._water_pending: set[tuple[int, int, int]] = set()
        self._water_since_flush = 0.0
        self.water_radius = 48.0
        # Caixas (mín, máx, inclusive) onde o terreno vira ar: o espaço das construções fixadas. Aplicadas também
        # aos chunks gerados depois (um chunk descarregado volta da semente e perderia o corte).
        self.cleared_boxes: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = []

        if self.async_loading:
            self._start_worker()

    def _start_worker(self) -> None:
        """Inicia a thread worker em segundo plano para geração e meshing."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="WorldManagerWorker", daemon=True
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        """Loop de execução da worker thread que gera chunks e calcula malhas na CPU."""
        import time

        while not self._stop_event.is_set():
            try:
                positions = self._request_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if positions is None or self._stop_event.is_set():
                break

            self._worker_busy.set()
            try:
                if isinstance(positions, tuple) and positions[0] == "remesh":
                    # a água mudou: refaz as malhas aqui, fora do quadro (era um travamento de ~15 ms por chunk)
                    for key in positions[1]:
                        if self._stop_event.is_set():
                            break
                        with self._chunks_lock:
                            chunk = self.chunks.get(key)
                        if chunk is None:
                            continue
                        mesh_data = self.mesher.build(chunk, self.neighbor_at, self._water_levels, around=self.blocks_around(key))
                        if not self._stop_event.is_set():
                            self._result_queue.put((key, chunk, mesh_data))
                        time.sleep(0.0005)
                    continue
                # Descarta requisições obsoletas se o jogador já se afastou muito
                if self._last_center is not None:
                    ccx, ccz = self._last_center
                    if all(
                        abs(pos[0] - ccx) > self.render_distance + 1
                        or abs(pos[2] - ccz) > self.render_distance + 1
                        for pos in positions
                    ):
                        continue

                # 1. Gera o relevo procedural e as cavernas 3D
                new_chunks = self.generator.generate_region(positions)

                with self._chunks_lock:
                    self._apply_clearings(new_chunks)  # sob a trava: não perde um corte feito agora
                    self.chunks.update(new_chunks)
                    self._chunk_revision += 1

                # 2. Constrói a malha e envia cada chunk concluído individualmente
                for key, chunk in new_chunks.items():
                    if self._stop_event.is_set():
                        break
                    mesh_data = self.mesher.build(chunk, self.neighbor_at, self._water_levels, around=self.blocks_around(key))
                    if not self._stop_event.is_set():
                        self._result_queue.put((key, chunk, mesh_data))
                    time.sleep(0.0005)  # Cede cooperativamente o GIL para a thread de renderização
            except Exception:
                pass
            finally:
                self._worker_busy.clear()
                self._request_queue.task_done()

    def blocks_around(self, key: Tuple[int, int, int]) -> np.ndarray:
        """O cubo 18³ de IDs em volta do chunk (ele e a borda dos vizinhos), para a malha (ver mesher.blocks_around)."""
        with self._chunks_lock:
            return blocks_around(self.chunks.get, key)

    def neighbor_at(self, x: int, y: int, z: int) -> BlockType:
        """Consulta rápida de blocos para cálculo de Face Culling entre chunks vizinhos."""
        size = Chunk3D.SIZE
        cx = x // size
        cy = y // size
        cz = z // size
        with self._chunks_lock:
            chunk = self.chunks.get((cx, cy, cz))
        if chunk is None:
            return BlockType.AIR
        return chunk.get_block(*chunk.world_to_local(x, y, z))

    def load_initial_region(self, focus_x: float, focus_z: float) -> None:
        """Carrega a área inicial sincronicamente no spawn para abrir a cena sem atraso visual."""
        size = Chunk3D.SIZE
        center_cx = int(math.floor(focus_x / size))
        center_cz = int(math.floor(focus_z / size))
        self._last_center = (center_cx, center_cz)

        target_columns = [
            (cx, 0, cz)
            for cx in range(center_cx - self.render_distance, center_cx + self.render_distance + 1)
            for cz in range(center_cz - self.render_distance, center_cz + self.render_distance + 1)
        ]

        new_chunks = self.generator.generate_region(target_columns)
        self._apply_clearings(new_chunks)
        with self._chunks_lock:
            self.chunks.update(new_chunks)
            self._chunk_revision += 1

        if self.create_gl_meshes:
            from src.rendering.mesh import TexturedMesh

            for key, chunk in new_chunks.items():
                data = self.mesher.build(chunk, self.neighbor_at, self._water_levels, around=self.blocks_around(key))
                if data.face_count > 0:
                    mesh = TexturedMesh(data.vertices, data.indices)
                    transform = mat4_translate(*chunk.local_to_world(0, 0, 0))
                    self.meshes[key] = (mesh, transform)

    def update(self, focus_x: float, focus_z: float) -> None:
        """Atualiza a grade de chunks de forma fluida sem bloquear a thread gráfica."""
        # 1. Processa malhas prontas geradas em segundo plano (upload amortizado para GPU)
        if self.async_loading:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._start_worker()

        if not self._result_queue.empty():
            uploads = 0
            max_uploads_per_frame = 1  # Amortiza em 1 chunk/frame: elimina micro-travamentos (<0.5ms)
            while not self._result_queue.empty() and uploads < max_uploads_per_frame:
                try:
                    item = self._result_queue.get_nowait()
                except queue.Empty:
                    break

                key, chunk, data = item
                self._in_progress.discard((key[0], 0, key[2]))
                if key not in self.chunks:
                    self._result_queue.task_done()
                    continue  # descarregado enquanto a malha era feita
                if self.create_gl_meshes and data.face_count == 0 and key in self.meshes:
                    self._pending_mesh_deletions.append(self.meshes.pop(key)[0])  # a malha refeita ficou vazia

                if self.create_gl_meshes and data.face_count > 0:
                    from src.rendering.mesh import TexturedMesh

                    mesh = TexturedMesh(data.vertices, data.indices)
                    transform = mat4_translate(*chunk.local_to_world(0, 0, 0))
                    if key in self.meshes:
                        old_mesh, _ = self.meshes[key]
                        self._pending_mesh_deletions.append(old_mesh)
                    self.meshes[key] = (mesh, transform)

                uploads += 1
                self._result_queue.task_done()

        # Amortiza a liberação de malhas da GPU (1 por frame) para evitar stalls de sincronização no driver
        if self._pending_mesh_deletions:
            old_mesh = self._pending_mesh_deletions.pop(0)
            try:
                old_mesh.delete()
            except Exception:
                pass

        if not self.has_pending_streaming_work():
            self._simulate_water(focus_x, focus_z)

        size = Chunk3D.SIZE
        center_cx = int(math.floor(focus_x / size))
        center_cz = int(math.floor(focus_z / size))

        if self._last_center == (center_cx, center_cz):
            return

        self._last_center = (center_cx, center_cz)

        # 2. Determina colunas ativas dentro do raio de visão
        target_columns: Set[Tuple[int, int]] = {
            (cx, cz)
            for cx in range(center_cx - self.render_distance, center_cx + self.render_distance + 1)
            for cz in range(center_cz - self.render_distance, center_cz + self.render_distance + 1)
        }

        # 3. Descarrega chunks fora do raio de visão
        with self._chunks_lock:
            to_unload = [
                key for key in list(self.chunks.keys())
                if (key[0], key[2]) not in target_columns
            ]
            for key in to_unload:
                if key in self.meshes:
                    mesh, _ = self.meshes.pop(key)
                    self._pending_mesh_deletions.append(mesh)
                self.chunks.pop(key, None)
                self._in_progress.discard((key[0], 0, key[2]))
                origin_x = key[0] * Chunk3D.SIZE
                origin_y = key[1] * Chunk3D.SIZE
                origin_z = key[2] * Chunk3D.SIZE
                self._water_seeded_chunks.discard(key)
                self.water.forget(lambda cell, ox=origin_x, oy=origin_y, oz=origin_z: (
                    ox <= cell[0] < ox + Chunk3D.SIZE
                    and oy <= cell[1] < oy + Chunk3D.SIZE
                    and oz <= cell[2] < oz + Chunk3D.SIZE
                ))
            if to_unload:
                self._chunk_revision += 1

        # 4. Enfileira novos chunks que precisam ser gerados
        new_positions = []
        for cx, cz in target_columns:
            pos = (cx, 0, cz)
            with self._chunks_lock:
                already_loaded = pos in self.chunks
            if not already_loaded and pos not in self._in_progress:
                new_positions.append(pos)
                self._in_progress.add(pos)

        if new_positions:
            # Ordena por proximidade do jogador (chunks mais próximos chegam primeiro)
            new_positions.sort(key=lambda p: (p[0] - center_cx) ** 2 + (p[2] - center_cz) ** 2)

            if self.async_loading:
                # Envia colunas individualmente para streaming fluido e contínuo
                for pos in new_positions:
                    self._request_queue.put([pos])
            else:
                # Modo síncrono para testes ou execução local
                new_chunks = self.generator.generate_region(new_positions)
                with self._chunks_lock:
                    self.chunks.update(new_chunks)
                    self._chunk_revision += 1

                if self.create_gl_meshes:
                    from src.rendering.mesh import TexturedMesh

                    for key, chunk in new_chunks.items():
                        data = self.mesher.build(chunk, self.neighbor_at, around=self.blocks_around(key))
                        if data.face_count > 0:
                            mesh = TexturedMesh(data.vertices, data.indices)
                            transform = mat4_translate(*chunk.local_to_world(0, 0, 0))
                            self.meshes[key] = (mesh, transform)

    def _simulate_water(self, focus_x: float, focus_z: float) -> None:
        """Avança a água (uma onda de blocos a cada ``water_step_interval``) e refaz as malhas que mudaram.

        A onda é avaliada aos poucos, ``WATER_CELLS_PER_FRAME`` células por quadro, e aplicada quando termina."""
        self._water_tick += 1.0 / 60.0
        self._water_since_flush += 1.0 / 60.0
        self._flush_water(force=False)
        if not self.water.stepping:
            if self._water_tick < self.water_step_interval:
                return
            self._water_tick = 0.0
            self._seed_water(focus_x, focus_z)
            if not self.water.busy:
                return
            self.water.begin_step()
        changed_cells = self.water.advance(WATER_CELLS_PER_FRAME)
        if not changed_cells:
            return

        size = Chunk3D.SIZE
        for x, y, z in changed_cells:
            # o chunk da célula e, se ela está na borda, o vizinho (a face entre os dois muda)
            for dx, dy, dz in ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                self._water_pending.add(((x + dx) // size, (y + dy) // size, (z + dz) // size))
        self._flush_water(force=False)

    def _flush_water(self, *, force: bool) -> None:
        """Refaz os chunks juntados pela água corrente, se já passou o intervalo (ou ``force``)."""
        if not self._water_pending or not (force or self._water_since_flush >= self.water_remesh_interval):
            return
        changed, self._water_pending = self._water_pending, set()
        self._water_since_flush = 0.0
        self._rebuild_after_water(changed, merge_pending=False)

    def place_water(self, x: int, y: int, z: int) -> bool:
        """Põe uma fonte de água numa célula de ar carregada (para testar a água); ``False`` se não dá."""
        if self.water.world.block(x, y, z) is not BlockType.AIR:
            return False
        self.water.world.set_block(x, y, z, BlockType.WATER)
        self.water.wake([(x, y, z)])
        size = Chunk3D.SIZE
        self._rebuild_after_water({(x // size, y // size, z // size)})
        return True

    def place_block(self, x: int, y: int, z: int, block: BlockType) -> Optional[BlockType]:
        """Põe um bloco numa célula de ar (ou de enfeite) carregada; devolve o bloco posto ou ``None``.

        A escada de mão escolhe sozinha a direção: fica presa no primeiro bloco sólido ao lado (norte, sul, leste,
        oeste); sem parede ao lado não há onde prendê-la.
        """
        from src.world.block import LADDER_BY_FACING, is_ladder, is_shaped, is_solid

        current = self.water.world.block(x, y, z)
        if current is None or not (current is BlockType.AIR or is_shaped(current)):
            return None
        if is_ladder(block):
            # (dx, dz) até a parede -> a escada olha para o lado oposto
            for (dx, dz), facing in (((0, 1), "north"), ((0, -1), "south"), ((-1, 0), "east"), ((1, 0), "west")):
                wall = self.water.world.block(x + dx, y, z + dz)
                if wall is not None and is_solid(wall):
                    block = LADDER_BY_FACING[facing]
                    break
            else:
                return None
        self.water.world.set_block(x, y, z, block)
        size = Chunk3D.SIZE
        self._rebuild_after_water({(x // size, y // size, z // size)})
        return block

    # ------------------------------------------------------------------ terreno sob as construções
    @staticmethod
    def _box_slices(chunk_key, lo, hi):
        """Fatias locais [x, y, z] da caixa dentro do chunk, ou ``None`` se não se encostam."""
        size = Chunk3D.SIZE
        origin = [k * size for k in chunk_key]
        slices = []
        for axis in range(3):
            a = max(lo[axis], origin[axis]) - origin[axis]
            b = min(hi[axis] + 1, origin[axis] + size) - origin[axis]
            if b <= a:
                return None
            slices.append(slice(a, b))
        return tuple(slices)

    def _apply_clearings(self, chunks: Dict[Tuple[int, int, int], Chunk3D]) -> None:
        for key, chunk in chunks.items():
            for lo, hi in self.cleared_boxes:
                cut = self._box_slices(key, lo, hi)
                if cut is not None:
                    chunk.blocks[cut] = int(BlockType.AIR)

    def _keys_touching(self, lo, hi) -> set:
        """Chunks da caixa e os vizinhos de borda (a face entre os dois muda)."""
        size = Chunk3D.SIZE
        return {(cx, cy, cz)
                for cx in range((lo[0] - 1) // size, (hi[0] + 1) // size + 1)
                for cy in range((lo[1] - 1) // size, (hi[1] + 1) // size + 1)
                for cz in range((lo[2] - 1) // size, (hi[2] + 1) // size + 1)}

    def clear_box(self, lo: Tuple[int, int, int], hi: Tuple[int, int, int]) -> None:
        """O terreno da caixa (inclusive) vira ar, agora e nos chunks gerados depois (o espaço de uma construção)."""
        lo, hi = tuple(int(v) for v in lo), tuple(int(v) for v in hi)
        with self._chunks_lock:
            self.cleared_boxes.append((lo, hi))
            self._apply_clearings({k: c for k, c in self.chunks.items() if self._box_slices(k, lo, hi) is not None})
        self.water.forget(lambda cell: all(lo[i] <= cell[i] <= hi[i] for i in range(3)))
        self._rebuild_after_water(self._keys_touching(lo, hi))

    def restore_box(self, lo: Tuple[int, int, int], hi: Tuple[int, int, int]) -> None:
        """Devolve o terreno da caixa (a construção saiu): gera de novo pela semente, mantendo os outros cortes."""
        lo, hi = tuple(int(v) for v in lo), tuple(int(v) for v in hi)
        if (lo, hi) not in self.cleared_boxes:
            return  # não foi cortada aqui (outro mundo, ou o mundo já foi refeito)
        self.cleared_boxes.remove((lo, hi))
        with self._chunks_lock:
            keys = [k for k in self.chunks if self._box_slices(k, lo, hi) is not None]
        fresh = self.generator.generate_region(keys) if keys else {}
        self._apply_clearings(fresh)
        with self._chunks_lock:
            for key, chunk in fresh.items():
                current = self.chunks.get(key)
                if current is not None:
                    cut = self._box_slices(key, lo, hi)
                    current.blocks[cut] = chunk.blocks[cut]
        self._rebuild_after_water(self._keys_touching(lo, hi))

    def _rebuild_after_water(self, changed: set, *, merge_pending: bool = True) -> None:
        """Refaz as malhas dos chunks em que a água mudou e avisa quem segue a revisão."""
        if merge_pending and self._water_pending:   # uma ação do jogador leva junto a água que esperava
            changed = set(changed) | self._water_pending
            self._water_pending = set()
            self._water_since_flush = 0.0
        with self._chunks_lock:
            changed &= set(self.chunks)
            self._chunk_revision += 1          # a máscara das sombras e o contorno veem a água nova

        if not self.create_gl_meshes:
            return
        if self.async_loading and self._worker_thread is not None and self._worker_thread.is_alive():
            self._request_queue.put(("remesh", sorted(changed)))   # a worker refaz; o quadro só envia à GPU
            return
        from src.rendering.mesh import TexturedMesh
        for key in changed:
            chunk = self.chunks.get(key)
            if chunk is None:
                continue
            data = self.mesher.build(chunk, self.neighbor_at, self._water_levels, around=self.blocks_around(key))
            old_mesh = self.meshes.pop(key, None)
            if old_mesh is not None:
                self._pending_mesh_deletions.append(old_mesh[0])
            if data.face_count > 0:
                self.meshes[key] = (
                    TexturedMesh(data.vertices, data.indices),
                    mat4_translate(*chunk.local_to_world(0, 0, 0)),
                )

    def _seed_water(self, focus_x: float, focus_z: float) -> None:
        """Acorda a água dos chunks novos perto do foco: só a que encosta em ar (o resto já está parado)."""
        size = Chunk3D.SIZE
        with self._chunks_lock:
            candidates = [
                (key, chunk) for key, chunk in self.chunks.items()
                if key not in self._water_seeded_chunks
            ]
        radius = self.water_radius + size
        for key, chunk in candidates:
            center_x = key[0] * size + size / 2
            center_z = key[2] * size + size / 2
            if (center_x - focus_x) ** 2 + (center_z - focus_z) ** 2 > radius * radius:
                continue
            self._water_seeded_chunks.add(key)
            water = chunk.blocks == int(BlockType.WATER)
            if not water.any():
                continue
            air = chunk.blocks == int(BlockType.AIR)
            # água com ar embaixo ou do lado, dentro do chunk; na borda, olha-se o mundo
            touches = np.zeros_like(water)
            touches[:, 1:, :] |= air[:, :-1, :]
            touches[1:, :, :] |= air[:-1, :, :]
            touches[:-1, :, :] |= air[1:, :, :]
            touches[:, :, 1:] |= air[:, :, :-1]
            touches[:, :, :-1] |= air[:, :, 1:]
            border = np.zeros_like(water)
            border[[0, -1], :, :] = True
            border[:, [0, -1], :] = True
            border[:, :, [0, -1]] = True
            origin = chunk.local_to_world(0, 0, 0)
            for lx, ly, lz in np.argwhere(water & (touches | border)):
                self.water.wake([(origin[0] + int(lx), origin[1] + int(ly), origin[2] + int(lz))])

    def get_height(self, world_x: float, world_z: float) -> int:
        """Retorna a altura do terreno sólido na coordenada informada."""
        return self.generator.get_height(int(math.floor(world_x)), int(math.floor(world_z)))

    def get_loaded_chunks_snapshot(self) -> tuple[int, Dict[Tuple[int, int, int], Chunk3D]]:
        """Retorna ``(revisão, cópia rasa)`` coerente dos chunks carregados.

        O snapshot evita que renderizadores de overlay iterem o dicionário que
        a worker de streaming pode alterar. Os chunks permanecem imutáveis para
        o fluxo atual de geração; portanto uma cópia rasa é suficiente.
        """
        with self._chunks_lock:
            return self._chunk_revision, dict(self.chunks)

    def get_loaded_chunk_revision(self) -> int:
        """Retorna a revisão atual sem alocar um snapshot dos chunks."""
        with self._chunks_lock:
            return self._chunk_revision

    def has_pending_streaming_work(self) -> bool:
        """Indica se a sequência atual ainda pode alterar os chunks carregados."""
        return bool(
            self._in_progress
            or self._worker_busy.is_set()
            or not self._request_queue.empty()
            or not self._result_queue.empty()
        )

    def render(
        self,
        shader,
        base_model: np.ndarray,
        view_projection: Optional[np.ndarray] = None,
    ) -> int:
        """Renderiza malhas de chunks ativas na GPU com Frustum Culling opcional.

        Retorna a quantidade de chunks efetivamente desenhados no frame.
        """
        drawn_count = 0
        if view_projection is not None:
            for mesh, transform in list(self.meshes.values()):
                model = base_model @ transform
                mvp = view_projection @ model
                clip = _CORNERS_16 @ mvp.T
                w = clip[:, 3]
                # Se todos os 8 cantos estiverem fora de qualquer um dos 6 planos do frustum, descarta
                if (
                    (clip[:, 0] < -w).all()
                    or (clip[:, 0] > w).all()
                    or (clip[:, 1] < -w).all()
                    or (clip[:, 1] > w).all()
                    or (clip[:, 2] < -w).all()
                    or (clip[:, 2] > w).all()
                ):
                    continue

                shader.set_mat4("u_Model", model)
                mesh.draw()
                drawn_count += 1
        else:
            for mesh, transform in list(self.meshes.values()):
                shader.set_mat4("u_Model", base_model @ transform)
                mesh.draw()
                drawn_count += 1

        return drawn_count

    def delete(self) -> None:
        """Libera todas as malhas de chunks da GPU e encerra threads ativas."""
        self.cleared_boxes = []  # as construções vão junto com o mundo
        if self.async_loading and self._worker_thread is not None and self._worker_thread.is_alive():
            self._stop_event.set()
            try:
                self._request_queue.put_nowait(None)
            except Exception:
                pass
            self._worker_thread.join(timeout=0.5)
            self._worker_thread = None

        while not self._request_queue.empty():
            try:
                self._request_queue.get_nowait()
                self._request_queue.task_done()
            except Exception:
                break

        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
                self._result_queue.task_done()
            except Exception:
                break

        self._in_progress.clear()

        # Libera malhas pendentes de exclusão
        for mesh in self._pending_mesh_deletions:
            try:
                mesh.delete()
            except Exception:
                pass
        self._pending_mesh_deletions.clear()

        for mesh, _ in self.meshes.values():
            try:
                mesh.delete()
            except Exception:
                pass
        self.meshes.clear()

        with self._chunks_lock:
            had_chunks = bool(self.chunks)
            self.chunks.clear()
            if had_chunks:
                self._chunk_revision += 1

        self._last_center = None


class _ManagerFluidWorld:
    """O mundo carregado visto pela água: ``None`` onde não há chunk (a água não entra no desconhecido) e sólido
    abaixo de y = 0."""

    def __init__(self, manager: "WorldManager") -> None:
        self.manager = manager

    def block(self, x: int, y: int, z: int) -> Optional[BlockType]:
        if y < 0:
            return BlockType.STONE  # abaixo de y = 0 é o chão do mundo (como em room_reveal): a água não vaza
        size = Chunk3D.SIZE
        with self.manager._chunks_lock:
            chunk = self.manager.chunks.get((x // size, y // size, z // size))
        if chunk is None:
            return None
        return chunk.get_block(*chunk.world_to_local(x, y, z))

    def set_block(self, x: int, y: int, z: int, block: BlockType) -> None:
        size = Chunk3D.SIZE
        with self.manager._chunks_lock:
            chunk = self.manager.chunks.get((x // size, y // size, z // size))
        if chunk is not None:
            chunk.set_block(*chunk.world_to_local(x, y, z), block)
