"""Gerenciador dinâmico de mundo (WorldManager) para carregamento contínuo/infinito de chunks."""

import math
import queue
import threading
from typing import Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

import numpy as np

from src.math import mat4_scale, mat4_translate
from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.mesher import ChunkMeshData, ChunkMesher
from src.world.terrain import TerrainGenerator

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

        self.mesher = ChunkMesher(atlas=atlas)
        self._last_center: Tuple[int, int] | None = None

        # Estruturas para geração assíncrona em background thread
        self._request_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._in_progress: Set[Tuple[int, int, int]] = set()
        self._worker_thread: Optional[threading.Thread] = None

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

            try:
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
                    self.chunks.update(new_chunks)

                # 2. Constrói a malha e envia cada chunk concluído individualmente
                for key, chunk in new_chunks.items():
                    if self._stop_event.is_set():
                        break
                    mesh_data = self.mesher.build(chunk, self.neighbor_at)
                    if not self._stop_event.is_set():
                        self._result_queue.put((key, chunk, mesh_data))
                    time.sleep(0.0005)  # Cede cooperativamente o GIL para a thread de renderização
            except Exception:
                pass
            finally:
                self._request_queue.task_done()

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
        with self._chunks_lock:
            self.chunks.update(new_chunks)

        if self.create_gl_meshes:
            from src.rendering.mesh import TexturedMesh

            for key, chunk in new_chunks.items():
                data = self.mesher.build(chunk, self.neighbor_at)
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

                if self.create_gl_meshes:
                    from src.rendering.mesh import TexturedMesh

                    for key, chunk in new_chunks.items():
                        data = self.mesher.build(chunk, self.neighbor_at)
                        if data.face_count > 0:
                            mesh = TexturedMesh(data.vertices, data.indices)
                            transform = mat4_translate(*chunk.local_to_world(0, 0, 0))
                            self.meshes[key] = (mesh, transform)

    def get_height(self, world_x: float, world_z: float) -> int:
        """Retorna a altura do terreno sólido na coordenada informada."""
        return self.generator.get_height(int(math.floor(world_x)), int(math.floor(world_z)))

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
            self.chunks.clear()

        self._last_center = None

