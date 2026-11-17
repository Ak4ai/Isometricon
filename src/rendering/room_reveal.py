"""Envia a máscara do espaço do jogador (ver ``src/world/room_reveal.py``) ao shader do mundo.

A máscara vai como textura 3D de 1 canal (255 = espaço do jogador, 128 = casca, 0 = fora). O shader:
- escurece o que está fora do espaço (brilho exterior ``exterior``);
- descarta o que fica entre a câmera e o espaço (teto, andar de cima, terra por cima), com dither.

``level`` (0 a 1) suaviza a entrada e a saída do efeito; ao sair de um espaço a máscara antiga
continua na GPU até o efeito apagar, para o mundo voltar ao normal sem pular.
"""

from typing import Optional

import numpy as np
import OpenGL.GL as gl

from src.rendering.mesh import TexturedMesh
from src.world.room_caps import build_caps
from src.world.room_reveal import WINDOW, RoomMask, RoomRevealTracker

MASK_UNIT = 2          # unidade de textura da máscara (a 0 é o atlas)
FADE_HALF_LIFE = 0.12  # segundos para o efeito andar metade do caminho


class RoomRevealRenderer:
    """Mantém a textura da máscara na GPU e os uniforms do efeito."""

    def __init__(self, exterior: float = 0.12, terrain_atlas=None, structure_atlas=None,
                 background: bool = False) -> None:
        """
        Args:
            exterior: brilho do que fica fora do espaço (0 preto, 1 normal).
            terrain_atlas: TextureAtlas do terreno, de onde saem as UVs das tampas.
            structure_atlas: função que devolve o SchematicAtlas (ou None), para as tampas das construções.
            background: monta as tampas numa thread à parte; a máscara nova só vai à GPU junto com as tampas
                dela (sem quadros de parede aberta sem tampa).
        """
        self.terrain_atlas = terrain_atlas
        self.structure_atlas = structure_atlas or (lambda: None)
        self._caps_key = None
        self._terrain_caps: Optional[TexturedMesh] = None
        self._structure_caps: Optional[TexturedMesh] = None
        self.enabled = True
        self.exterior = float(exterior)  # brilho do que está fora do espaço: 0 preto, 1 normal
        self.ceiling = 1.0               # brilho do teto do espaço que sobra do corte do andar: 0 preto, 1 normal
        self.level = 0.0                 # intensidade suavizada, 0 a 1
        self.texture_id = 0
        self._shown: Optional[RoomMask] = None  # a máscara que está na GPU
        # os outros cortes do shader, para as tampas os seguirem (definidos pelo laço principal a cada quadro)
        self.story = None   # room_caps.StoryCut ou None
        self.sight = None   # room_caps.SightCut ou None
        self.center = None  # (x, z) do centro do cômodo (u_StoryCenter), referência de frente e fundo
        self.caps_ms = 0.0  # quanto levou a última reconstrução das tampas
        self._uploaded = None
        self._wanted: Optional[RoomMask] = None  # a máscara mais nova do rastreador (vai para _shown com as tampas)
        self._executor = None
        self._job = None
        if background:
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="room-caps")

    # ------------------------------------------------------------------ estado
    def update(self, dt: float, tracker: RoomRevealTracker) -> None:
        """Avança a suavização e, se há espaço novo, manda a máscara para a GPU."""
        mask = tracker.mask
        wants = self.enabled and mask is not None and mask.active
        if wants:
            self._wanted = mask
            if self._shown is None or self.terrain_atlas is None:
                self._shown = mask  # entrando (o efeito começa apagado) ou sem tampas: vai já
        target = 1.0 if wants else 0.0
        self.level += (target - self.level) * (1.0 - 0.5 ** (max(dt, 0.0) / FADE_HALF_LIFE))
        if abs(target - self.level) < 0.002:
            self.level = target
        if self.level == 0.0 and not wants:
            self._shown = self._wanted = None
        if self._shown is not None and self._uploaded is not self._shown:
            self._upload(self._shown)

    def _ensure_texture(self) -> None:
        if self.texture_id:
            return
        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_3D, name, value)
        sx, sy, sz = WINDOW
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage3D(gl.GL_TEXTURE_3D, 0, gl.GL_R8, sx, sy, sz, 0, gl.GL_RED, gl.GL_UNSIGNED_BYTE,
                        np.zeros((sz, sy, sx), dtype=np.uint8))

    def _upload(self, mask: RoomMask) -> None:
        self._ensure_texture()
        sx, sy, sz = WINDOW
        # a máscara é [x, y, z]; a textura 3D quer (profundidade z, altura y, largura x)
        data = np.ascontiguousarray(mask.data.transpose(2, 1, 0))
        gl.glActiveTexture(gl.GL_TEXTURE0 + MASK_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexSubImage3D(gl.GL_TEXTURE_3D, 0, 0, 0, 0, sx, sy, sz, gl.GL_RED, gl.GL_UNSIGNED_BYTE, data)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self._uploaded = mask

    # ------------------------------------------------------------------ desenho
    @property
    def visible(self) -> bool:
        return self.level > 0.0 and self._shown is not None

    def apply(self, shader, base_model: np.ndarray, view: np.ndarray) -> None:
        """Liga o efeito no shader do mundo (chamar antes de desenhar o terreno e as construções)."""
        if not self.visible:
            shader.set_float("u_RoomActive", 0.0)
            return
        inverse_model = np.linalg.inv(np.asarray(base_model, dtype=np.float64))
        # o shader trabalha no espaço girado pelo modelo; a máscara está no espaço do mundo
        forward_render = -np.asarray(view, dtype=np.float64)[2, :3]  # para onde a câmera olha
        view_dir = inverse_model[:3, :3] @ forward_render
        view_dir /= max(float(np.linalg.norm(view_dir)), 1e-9)
        self._update_caps(view_dir)  # pode trocar a máscara mostrada (junto com as tampas dela)
        ox, oy, oz = self._shown.origin
        gl.glActiveTexture(gl.GL_TEXTURE0 + MASK_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        shader.set_int("u_RoomMask", MASK_UNIT)
        shader.set_mat4("u_RoomInvModel", inverse_model.astype(np.float32))
        shader.set_vec3("u_RoomOrigin", float(ox), float(oy), float(oz))
        shader.set_vec3("u_RoomSize", float(WINDOW[0]), float(WINDOW[1]), float(WINDOW[2]))
        shader.set_vec3("u_ViewDir", float(view_dir[0]), float(view_dir[1]), float(view_dir[2]))
        shader.set_float("u_RoomExterior", self.exterior)
        shader.set_float("u_RoomCeiling", self.ceiling)
        shader.set_float("u_RoomActive", float(self.level))

    # ------------------------------------------------------------------ tampas
    def _update_caps(self, view_dir: np.ndarray) -> None:
        """Refaz as tampas quando a máscara, a direção da câmera ou os cortes mudaram.

        Em segundo plano, um cálculo por vez: ao terminar, as tampas (e a máscara para a qual foram feitas) entram
        no quadro; se algo mudou nesse meio-tempo, o próximo quadro pede outro."""
        if self.terrain_atlas is None:
            return
        if self._job is not None:
            if not self._job.done():
                return
            job, self._job = self._job, None
            self._adopt_caps(*job.result())
        target = self._wanted if self._wanted is not None else self._shown
        story = self.story
        sight = self.sight
        key = (id(target), tuple(np.round(view_dir, 3)),
               None if story is None else (story.cut_y, story.feet_y, tuple(np.round(story.center, 1))),
               None if sight is None else sight.feet_y,
               None if self.center is None else tuple(np.round(self.center, 1)))
        if key == self._caps_key:
            return
        if sight is not None:
            # as tampas cobrem o corredor em qualquer ponto do cômodo: não se refazem a cada passo do jogador (o
            # shader descarta as que caem em blocos que o corredor não cortou, e as outras ficam dentro do vizinho)
            sight = type(sight)(None, None, sight.radius, sight.feet_y)
        args = (key, target, np.array(view_dir), story, sight, self.center)
        if self._executor is not None:
            self._job = self._executor.submit(self._build_caps, *args)
            return
        self._adopt_caps(*self._build_caps(*args))

    def _build_caps(self, key, mask: RoomMask, view_dir, story, sight, center):
        """Monta as tampas (só numpy; pode rodar fora da thread do GL)."""
        import time
        started = time.perf_counter()

        def structure_uv(block: str, face: str):
            atlas = self.structure_atlas()
            return atlas.get_uv(block, face) if atlas is not None else (0.0, 0.0, 1.0, 1.0)

        caps = build_caps(mask, view_dir, self.terrain_atlas, structure_uv, story, sight, center)
        return key, mask, caps, (time.perf_counter() - started) * 1000.0

    def _adopt_caps(self, key, mask: RoomMask, caps, elapsed_ms: float) -> None:
        if mask is not self._shown:
            if self._shown is None:
                return  # o efeito já apagou: as tampas são de um cômodo que saiu de cena
            self._shown = mask
            self._upload(mask)
        self._terrain_caps = self._store(self._terrain_caps, caps.terrain)
        self._structure_caps = self._store(self._structure_caps, caps.structures)
        self._caps_key = key
        self.caps_ms = elapsed_ms

    @staticmethod
    def _store(mesh: Optional[TexturedMesh], data) -> Optional[TexturedMesh]:
        vertices, indices = data
        if len(indices) == 0:
            if mesh is not None:
                mesh.delete()
            return None
        if mesh is None:
            return TexturedMesh(vertices, indices)
        mesh.update_buffers(vertices, indices)
        return mesh

    def draw_terrain_caps(self, shader, base_model: np.ndarray) -> None:
        """Desenha as tampas do terreno (com o atlas do terreno já ligado)."""
        if self.visible and self._terrain_caps is not None:
            shader.set_mat4("u_Model", np.asarray(base_model, dtype=np.float32))
            self._terrain_caps.draw()

    def draw_structure_caps(self, shader, base_model: np.ndarray) -> None:
        """Desenha as tampas das construções, ligando o atlas delas."""
        atlas = self.structure_atlas()
        if self.visible and self._structure_caps is not None and atlas is not None:
            atlas.bind(0)
            shader.set_int("u_TextureAtlas", 0)
            shader.set_mat4("u_Model", np.asarray(base_model, dtype=np.float32))
            self._structure_caps.draw()

    @staticmethod
    def disable(shader) -> None:
        """Desliga o efeito (o personagem e o resto não devem ser escurecidos nem descartados)."""
        shader.set_float("u_RoomActive", 0.0)

    def delete(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self._job = None
        for mesh in (self._terrain_caps, self._structure_caps):
            if mesh is not None:
                mesh.delete()
        self._terrain_caps = self._structure_caps = self._caps_key = None
        if self.texture_id:
            gl.glDeleteTextures(1, [self.texture_id])
            self.texture_id = 0
        self._shown = self._uploaded = self._wanted = None
