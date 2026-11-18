"""O cursor de contexto do modo terreno (no lugar da seta do sistema) e a mira do personagem.

É o desenho do Isocraft (``IsoContextCursor``): uma cruz pequena com contorno preto na ponta do mouse e, em
volta, uma forma que diz o que o clique faria:

- ``WALK`` (nada sob o cursor): só a cruz, branca;
- ``MINE`` (um bloco qualquer): colchetes dos lados, cinza claro;
- ``INTERACT`` (algo de usar, como uma porta): quatro pontos em losango, dourados, pulsando; o bloco ganha
  contorno e, ao alcance, o rótulo da ação em cima dele (``[E] Abrir``);
- ``ATTACK`` e ``BUILD``: cantos (vermelhos, pulsando; verdes), para quando houver entidades e construir.

Junto vem a mira (``PlayerFacingPolicy`` do Isocraft, com "virar para onde anda" desligado, o padrão dele): o
personagem gira sempre para o ponto sob o cursor, andando ou parado, suave (meia-vida de 0,06 s). O ponto é o
do bloco atingido; sem bloco, onde o raio do cursor corta o plano da altura dos pés.

As formas são feitas em "pixels de interface" (``SCALE`` pixels de tela cada), como a GUI do jogo base.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCALE = 2              # pixels de tela por pixel de interface
PULSE_SPEED = 5.0      # rad/s do pulso das formas de interagir e atacar
AIM_HALF_LIFE = 0.06   # segundos para o giro até o cursor andar metade do caminho
AIM_DEAD_ZONE = 0.25   # blocos: com o cursor em cima do próprio personagem, não gira
PROMPT_RISE = 22       # pixels de interface entre o ponto do bloco e o rótulo
PROMPT_HEIGHT = 1.15   # acima da base do bloco, onde o rótulo se prende
INTERACT_REACH = 3.0   # blocos (no plano) até onde a porta sob o cursor abre
INTERACT_VERTICAL = 2  # blocos acima ou abaixo dos pés
CURSOR_IDLE = 3.0      # segundos sem mexer o mouse (ou o touchpad) até o cursor sumir: joga-se só no teclado
CURSOR_FADE = 0.3      # segundos do fim desse tempo em que ele vai apagando


def cursor_opacity(idle: float) -> float:
    """O quanto o cursor aparece ``idle`` segundos depois do último movimento do mouse (1 a 0)."""
    if idle >= CURSOR_IDLE:
        return 0.0
    return min(1.0, (CURSOR_IDLE - idle) / CURSOR_FADE)


class CursorMode(Enum):
    WALK = (255, 255, 255, 255)
    MINE = (232, 232, 232, 255)
    INTERACT = (255, 215, 90, 255)
    ATTACK = (255, 85, 85, 255)
    BUILD = (123, 232, 123, 255)

    @property
    def color(self) -> Tuple[int, int, int, int]:
        return self.value


BLACK = (0, 0, 0, 255)
CHEVRON = (102, 224, 255, 255)


def classify(hit, door=None) -> CursorMode:
    """O modo do cursor: ``hit`` é o bloco sob ele (ou None), ``door`` a porta desse bloco (ou None)."""
    if hit is None:
        return CursorMode.WALK
    if door is not None:
        return CursorMode.INTERACT
    return CursorMode.MINE


def pulse(time: float) -> int:
    """0 ou 1: quanto as formas que pulsam crescem agora."""
    return int(round(0.5 + 0.5 * math.sin(time * PULSE_SPEED)))


# --------------------------------------------------------------------------------------------- desenho
class _Canvas:
    """Retângulos em pixels de interface, ao redor de um centro, numa imagem RGBA ampliada ``SCALE`` vezes."""

    HALF = 16  # pixels de interface do centro até a borda

    def __init__(self) -> None:
        side = (2 * self.HALF + 1) * SCALE
        self.image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

    def fill(self, x0: int, y0: int, x1: int, y1: int, color) -> None:
        """Pinta [x0, x1) x [y0, y1), com (0, 0) no centro (como o ``fill`` da GUI)."""
        if x1 <= x0 or y1 <= y0:
            return
        h = self.HALF
        self.draw.rectangle(((x0 + h) * SCALE, (y0 + h) * SCALE, (x1 + h) * SCALE - 1, (y1 + h) * SCALE - 1),
                            fill=color)

    def line(self, x0: float, y0: float, x1: float, y1: float, color) -> None:
        """Linha fina de um pixel de interface, pisada ponto a ponto."""
        steps = max(int(math.ceil(max(abs(x1 - x0), abs(y1 - y0)))), 1)
        for i in range(steps + 1):
            t = i / steps
            x, y = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
            self.fill(x, y, x + 1, y + 1, color)


def _base(canvas: _Canvas, color) -> None:
    """A cruz: contorno preto e o miolo na cor do modo."""
    canvas.fill(-4, -1, 5, 2, BLACK)
    canvas.fill(-1, -4, 2, 5, BLACK)
    canvas.fill(-3, 0, 4, 1, color)
    canvas.fill(0, -3, 1, 4, color)


def _corners(canvas: _Canvas, radius: int, length: int, color) -> None:
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = sx * radius, sy * radius
            canvas.fill(min(px, px - sx * length), py, max(px, px - sx * length) + 1, py + 1, color)
            canvas.fill(px, min(py, py - sy * length), px + 1, max(py, py - sy * length) + 1, color)


def _diamond(canvas: _Canvas, radius: int, color) -> None:
    for x, y in ((0, -radius), (0, radius), (-radius, 0), (radius, 0)):
        canvas.fill(x - 1, y - 1, x + 2, y + 2, color)


def _side_brackets(canvas: _Canvas, radius: int, color) -> None:
    for s in (-1, 1):
        px = s * radius
        canvas.fill(px, -4, px + 1, 5, color)
        canvas.fill(min(px, px - 2 * s), -4, max(px, px - 2 * s) + 1, -3, color)
        canvas.fill(min(px, px - 2 * s), 4, max(px, px - 2 * s) + 1, 5, color)


def _chevron(canvas: _Canvas, direction: int) -> None:
    """A seta de alcance vertical: para cima (-1) ou para baixo (1)."""
    near, far = direction * 8, direction * 12
    canvas.line(-4, near, 0, far, CHEVRON)
    canvas.line(0, far, 4, near, CHEVRON)


def cursor_image(mode: CursorMode, grow: int = 0, vertical: int = 0) -> Image.Image:
    """A imagem do cursor (o centro da imagem é a ponta do mouse). ``grow``: o pulso (0 ou 1); ``vertical``:
    -1 ou 1 para a seta de alcance acima ou abaixo, 0 sem ela."""
    canvas = _Canvas()
    _base(canvas, mode.color)
    if vertical:
        _chevron(canvas, vertical)
    if mode is CursorMode.MINE:
        _side_brackets(canvas, 6, mode.color)
    elif mode is CursorMode.INTERACT:
        _diamond(canvas, 6 + grow, mode.color)
    elif mode is CursorMode.ATTACK:
        _corners(canvas, 7 + grow, 3, mode.color)
    elif mode is CursorMode.BUILD:
        _corners(canvas, 6, 2, mode.color)
    return canvas.image


def _font(size: int):
    for name in ("consolab.ttf", "C:/Windows/Fonts/consolab.ttf", "arialbd.ttf", "consola.ttf", "arial.ttf",
                 "DejaVuSansMono-Bold.ttf", "DejaVuSans-Bold.ttf"):   # as do Linux, sem as do Windows
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)   # sem tamanho, a padrão é miúda e o contorno some com o verbo
    except TypeError:                         # Pillow antigo (antes do 10.1)
        return ImageFont.load_default()


def prompt_image(key: str, verb: str) -> Image.Image:
    """O rótulo da ação: a tecla em branco numa caixa de borda clara, o verbo em dourado ao lado."""
    font = _font(8 * SCALE)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    key_w = probe.textlength(key, font=font) / SCALE
    verb_w = probe.textlength(verb, font=font) / SCALE
    box = int(math.ceil(key_w)) + 6                  # a caixa da tecla
    width = box + 4 + int(math.ceil(verb_w)) + 1
    image = Image.new("RGBA", ((width + 2) * SCALE, 14 * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def fill(x0, y0, x1, y1, color):  # em pixels de interface, com a caixa começando em (1, 1)
        draw.rectangle(((x0 + 1) * SCALE, (y0 + 1) * SCALE, (x1 + 1) * SCALE - 1, (y1 + 1) * SCALE - 1), fill=color)

    fill(-1, 0, box + 1, 13, (0, 0, 0, 102))          # sombra
    fill(0, 1, box, 12, (26, 26, 26, 204))            # fundo da tecla
    border = (181, 181, 181, 255)
    fill(0, 1, box, 2, border)
    fill(0, 11, box, 12, border)
    fill(0, 1, 1, 12, border)
    fill(box - 1, 1, box, 12, border)
    top = 3 * SCALE
    draw.text((4 * SCALE, top), key, font=font, fill=(255, 255, 255, 255))
    draw.text(((box + 5) * SCALE, top), verb, font=font, fill=CursorMode.INTERACT.color,
              stroke_width=1, stroke_fill=(20, 22, 28, 220))
    return image


# --------------------------------------------------------------------------------------------- o que se vê
SKY = "sky"          # o pixel sob o mouse não tem terreno nem construção (céu, fundo)
SURFACE_INSIDE = 0.02  # blocos além da superfície vista onde o raio recomeça (já dentro do bloco visto)


class DepthProbe:
    """O ponto do mundo que aparece sob o mouse, lido da profundidade do quadro.

    Dentro de um cômodo o shader corta o teto, as paredes da frente e o andar de cima: esses blocos continuam no
    mundo, mas não aparecem. O cursor não deve parar neles (é o ``raycastSkippingDissolved`` do Isocraft): o raio
    do mouse recomeça na superfície que de fato está na tela. Lê-se a profundidade depois do terreno e das
    construções (antes da água, do personagem e dos realces), e ela vale para o quadro seguinte."""

    RING = 6  # leituras em voo (a GPU chega a ficar uns quadros atrás da CPU)
    UNIT = 7  # a unidade de textura da cópia (salva e restaurada)

    _VERTEX = """#version 330 core
uniform sampler2D depth_pixel;
out float depth_value;
void main() { depth_value = texelFetch(depth_pixel, ivec2(0, 0), 0).r; gl_Position = vec4(0.0, 0.0, 0.0, 1.0); }
"""

    def __init__(self) -> None:
        self.surface = None  # ponto do mundo, SKY, ou None (sem leitura)
        self._pending = [None] * self.RING  # (mouse, mvp, largura, altura) de cada leitura em voo
        self._fences = [None] * self.RING   # a cerca de cada leitura: passou, o buffer já pode ser lido
        self._frame = 0
        self._ready = None  # o caminho rápido foi montado (None: ainda não tentado; False: lê direto, mais lento)
        self._buffers = []  # um buffer da GPU por vaga, onde cai a profundidade
        self._mapped = []   # o endereço de cada buffer mapeado de vez (lido sem chamar o GL), se der
        self._depth_texture = self._depth_fbo = self._program = self._vao = 0

    def _create(self) -> bool:
        import ctypes
        import OpenGL.GL as gl
        from OpenGL.GL import shaders
        ring = self.RING
        self._buffers = [int(b) for b in np.atleast_1d(gl.glGenBuffers(ring))]
        # Qualquer leitura de volta pelo GL (glGetBufferSubData, glReadPixels) faz o driver da NVIDIA esperar
        # a própria fila (~16 ms), mesmo com o dado pronto: com o buffer mapeado de vez (ARB_buffer_storage),
        # ler é só ler a memória, depois da cerca.
        persistent = self._persistent_flags()
        for buffer in self._buffers:
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, buffer)
            if persistent:
                from OpenGL.GL.ARB.buffer_storage import glBufferStorage
                from OpenGL.raw.GL.VERSION.GL_3_0 import glMapBufferRange
                glBufferStorage(gl.GL_ARRAY_BUFFER, 4, None, persistent)
                self._mapped.append(int(glMapBufferRange(gl.GL_ARRAY_BUFFER, 0, 4, persistent) or 0))
            else:
                gl.glBufferData(gl.GL_ARRAY_BUFFER, 4, None, gl.GL_STREAM_READ)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        if not all(self._mapped):
            self._mapped = []
        try:
            while gl.glGetError() != gl.GL_NO_ERROR:
                pass
            program = int(gl.glCreateProgram())
            vertex = shaders.compileShader(self._VERTEX, gl.GL_VERTEX_SHADER)
            gl.glAttachShader(program, vertex)
            names = (ctypes.c_char_p * 1)(b"depth_value")
            gl.glTransformFeedbackVaryings(program, 1, ctypes.cast(names, ctypes.POINTER(ctypes.POINTER(ctypes.c_char))),
                                           gl.GL_INTERLEAVED_ATTRIBS)
            gl.glLinkProgram(program)
            gl.glDeleteShader(vertex)
            if gl.glGetProgramiv(program, gl.GL_LINK_STATUS) != gl.GL_TRUE:
                gl.glDeleteProgram(program)
                return False
            self._program = program
            self._vao = int(gl.glGenVertexArrays(1))
            # o pixel de profundidade no formato da janela (24 + 8), para o blit copiar sem conversão
            self._depth_texture = int(gl.glGenTextures(1))
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._depth_texture)
            from OpenGL.raw.GL.VERSION.GL_1_0 import glTexImage2D  # o PyOpenGL não conhece o tipo 24_8
            glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH24_STENCIL8, 1, 1, 0, gl.GL_DEPTH_STENCIL,
                         gl.GL_UNSIGNED_INT_24_8, None)
            for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_NEAREST)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            self._depth_fbo = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._depth_fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_STENCIL_ATTACHMENT, gl.GL_TEXTURE_2D,
                                      self._depth_texture, 0)
            complete = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            return complete and gl.glGetError() == gl.GL_NO_ERROR
        except Exception:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            return False

    @staticmethod
    def _persistent_flags() -> int:
        """As flags do mapeamento persistente, ou 0 sem a extensão."""
        import OpenGL.GL as gl
        try:
            count = int(gl.glGetIntegerv(gl.GL_NUM_EXTENSIONS))
            if "GL_ARB_buffer_storage" not in {gl.glGetStringi(gl.GL_EXTENSIONS, i).decode() for i in range(count)}:
                return 0
            from OpenGL.GL.ARB.buffer_storage import GL_MAP_COHERENT_BIT, GL_MAP_PERSISTENT_BIT
            return gl.GL_MAP_READ_BIT | GL_MAP_PERSISTENT_BIT | GL_MAP_COHERENT_BIT
        except Exception:
            return 0

    def _copy(self, x: int, y: int, slot: int) -> None:
        """Só na GPU: o pixel de profundidade do quadro vai para a textura de 1x1, e um vértice (sem desenhar
        nada) o lê dela e o escreve no buffer da vaga (transform feedback). Nenhum ``glReadPixels``: no driver
        da NVIDIA ele espera a GPU mesmo para um PBO."""
        import OpenGL.GL as gl
        program = gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)
        vao = gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING)
        unit = gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)
        # lê do framebuffer em que a cena está sendo desenhada (a tela, ou o da cena: ver SceneTarget)
        source = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, source)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._depth_fbo)
        gl.glBlitFramebuffer(x, y, x + 1, y + 1, 0, 0, 1, 1, gl.GL_DEPTH_BUFFER_BIT, gl.GL_NEAREST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, source)
        gl.glActiveTexture(gl.GL_TEXTURE0 + self.UNIT)
        texture = gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._depth_texture)
        gl.glUseProgram(self._program)
        gl.glUniform1i(gl.glGetUniformLocation(self._program, "depth_pixel"), self.UNIT)
        gl.glBindVertexArray(self._vao)
        gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        gl.glBindBufferBase(gl.GL_TRANSFORM_FEEDBACK_BUFFER, 0, self._buffers[slot])
        gl.glBeginTransformFeedback(gl.GL_POINTS)
        gl.glDrawArrays(gl.GL_POINTS, 0, 1)
        gl.glEndTransformFeedback()
        gl.glBindBufferBase(gl.GL_TRANSFORM_FEEDBACK_BUFFER, 0, 0)
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        # devolve o estado
        gl.glBindTexture(gl.GL_TEXTURE_2D, int(texture))
        gl.glActiveTexture(int(unit))
        gl.glBindVertexArray(int(vao))
        gl.glUseProgram(int(program))

    def read(self, mouse, width: int, height: int, mvp: np.ndarray, scale: float = 1.0) -> None:
        """Pede a profundidade sob o mouse e recolhe a leitura mais nova que a GPU já terminou.

        Ler o pixel na hora faria a CPU esperar a GPU acabar o quadro: o pixel vai, só na GPU, para um buffer
        da GPU, com uma cerca (``glFenceSync``) logo atrás; o buffer só é lido depois que a cerca passou, e até
        lá vale a leitura anterior. O ponto é do quadro em que foi pedido (com as matrizes dele). ``scale`` é a
        escala da cena desenhada fora da tela (o pixel lido é o do mouse nessa resolução)."""
        import ctypes
        import OpenGL.GL as gl
        from OpenGL.raw.GL.VERSION.GL_1_0 import glReadPixels as read_pixels
        if self._ready is None:
            self._ready = self._create()
        ring = self.RING
        # recolhe: da mais nova para a mais antiga, a primeira já pronta (as mais antigas que ela não valem mais)
        for age in range(1, ring):
            slot = (self._frame - age) % ring
            if self._pending[slot] is None:
                continue
            fence = self._fences[slot]
            if fence is not None and int(gl.glGetSynciv(fence, gl.GL_SYNC_STATUS, 1)[1]) != gl.GL_SIGNALED:
                continue
            if self._mapped and fence is not None:
                depth = ctypes.c_float.from_address(self._mapped[slot]).value
            else:
                gl.glBindBuffer(gl.GL_COPY_READ_BUFFER, self._buffers[slot])
                data = bytes(gl.glGetBufferSubData(gl.GL_COPY_READ_BUFFER, 0, 4))
                gl.glBindBuffer(gl.GL_COPY_READ_BUFFER, 0)
                depth = float(np.frombuffer(data, dtype=np.float32)[0])
            at, matrix, w, h = self._pending[slot]
            self.surface = unproject(at, depth, w, h, matrix)
            for older in range(age, ring):
                self._drop((self._frame - older) % ring)
            break
        # pede
        slot = self._frame % ring
        self._drop(slot)
        target_w, target_h = max(1, round(width * scale)), max(1, round(height * scale))
        x, y = int(mouse[0] * scale), int(target_h - 1 - int(mouse[1] * scale))
        if 0 <= x < target_w and 0 <= y < target_h:
            if self._ready:
                self._copy(x, y, slot)
                self._fences[slot] = gl.glFenceSync(gl.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
            else:
                gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, self._buffers[slot])
                read_pixels(x, y, 1, 1, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, ctypes.c_void_p(0))
                gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, 0)
            self._pending[slot] = (tuple(mouse), np.array(mvp, dtype=np.float64), width, height)
        self._frame += 1

    def _drop(self, slot: int) -> None:
        if self._fences[slot] is not None:
            import OpenGL.GL as gl
            gl.glDeleteSync(self._fences[slot])
        self._fences[slot] = self._pending[slot] = None

    def clear(self) -> None:
        self.surface = None
        for slot in range(self.RING):
            self._drop(slot)

    def delete(self) -> None:
        import OpenGL.GL as gl
        if self._buffers:
            if self._mapped:
                for buffer in self._buffers:
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, buffer)
                    gl.glUnmapBuffer(gl.GL_ARRAY_BUFFER)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glDeleteBuffers(len(self._buffers), self._buffers)
        if self._depth_fbo:
            gl.glDeleteFramebuffers(1, [self._depth_fbo])
            gl.glDeleteTextures(1, [self._depth_texture])
        if self._vao:
            gl.glDeleteVertexArrays(1, [self._vao])
        if self._program:
            gl.glDeleteProgram(self._program)
        for slot in range(self.RING):
            self._drop(slot)
        self.__init__()
        self._ready = False


def unproject(mouse, depth: float, width: int, height: int, mvp: np.ndarray):
    """O ponto do mundo no pixel ``mouse`` (de cima para baixo) com a profundidade ``depth`` (0 a 1), ou SKY."""
    if depth >= 1.0 - 1e-7:
        return SKY
    ndc = np.array([2.0 * (float(mouse[0]) + 0.5) / width - 1.0, 1.0 - 2.0 * (float(mouse[1]) + 0.5) / height,
                    2.0 * depth - 1.0, 1.0])
    world = np.linalg.inv(np.asarray(mvp, dtype=np.float64)) @ ndc
    if abs(world[3]) < 1e-12:
        return None
    return world[:3] / world[3]


def raycast_visible(ray, provider, surface, raycast):
    """O primeiro bloco que o mouse vê: o raio recomeça na superfície visível ``surface`` (de ``DepthProbe``),
    pulando o que o corte do cômodo escondeu. Sem leitura, é o raio inteiro; no céu, nada."""
    if surface is None:
        return raycast(ray, provider)
    if isinstance(surface, str):
        return None
    from src.interaction.raycast import Ray, RayHit
    origin = np.asarray(ray.origin, dtype=np.float64)
    direction = np.asarray(ray.direction, dtype=np.float64)
    along = float(np.dot(np.asarray(surface, dtype=np.float64) - origin, direction))
    if along <= 0.0:
        return raycast(ray, provider)
    start = along + SURFACE_INSIDE
    hit = raycast(Ray(origin + direction * start, direction), provider)
    if hit is None:
        return None
    if hit.distance == 0.0:
        # o bloco visto: o ponto e a face são os da superfície (a face mais perto do ponto, voltada para a câmera)
        point = origin + direction * along
        offsets = [abs(point[a] - round(point[a])) for a in range(3)]
        axis = int(np.argmin(offsets))
        normal = [0, 0, 0]
        normal[axis] = -1 if direction[axis] > 0 else 1
        return RayHit(hit.block, point.astype(np.float32), along, tuple(normal), hit.block_type)
    return RayHit(hit.block, hit.point, hit.distance + start, hit.normal, hit.block_type)


# --------------------------------------------------------------------------------------------- mira
def aim_point(hit, ray, feet_y: float) -> Optional[np.ndarray]:
    """O ponto para onde o personagem olha: o do bloco sob o cursor; sem bloco, onde o raio do cursor corta o
    plano da altura dos pés (como ``cursorAimPoint`` do Isocraft)."""
    if hit is not None:
        return np.asarray(hit.point, dtype=np.float64)
    if ray is None:
        return None
    origin = np.asarray(ray.origin, dtype=np.float64)
    direction = np.asarray(ray.direction, dtype=np.float64)
    if abs(direction[1]) <= 1e-4:
        return None
    t = (feet_y - origin[1]) / direction[1]
    if t <= 0.0:
        return None
    return origin + direction * t


def face_toward(yaw: float, position, target, dt: float) -> float:
    """O ``yaw`` (rad, 0 olhando para +z) girado, suave, para ``target`` visto de ``position``; no plano."""
    if target is None:
        return yaw
    dx = float(target[0]) - float(position[0])
    dz = float(target[2]) - float(position[2])
    if dx * dx + dz * dz < AIM_DEAD_ZONE ** 2:
        return yaw
    goal = math.atan2(dx, dz)
    diff = (goal - yaw + math.pi) % (2.0 * math.pi) - math.pi
    return yaw + diff * (1.0 - 0.5 ** (max(dt, 0.0) / AIM_HALF_LIFE))


def block_name_at(structures, provider, cell) -> Optional[str]:
    """O nome (do Minecraft) do bloco na célula: o da construção que a ocupa, senão o do terreno com forma."""
    x, y, z = (int(v) for v in cell)
    for placed in structures:
        schematic = placed.schematic
        ox, oy, oz = placed.origin
        lx, ly, lz = x - ox, y - oy, z - oz
        if 0 <= lx < schematic.width and 0 <= ly < schematic.height and 0 <= lz < schematic.length:
            name = str(schematic.grid[ly, lz, lx])
            if name != "minecraft:air":
                return name
    if provider is not None:
        from src.world.block import SHAPED_BLOCK_NAMES
        return SHAPED_BLOCK_NAMES.get(provider.get_block_at(x, y, z))
    return None


def highlight_box(name: Optional[str]):
    """A caixa que envolve a forma do bloco, em blocos dentro da célula ((x0, y0, z0), (x1, y1, z1)); ``None``
    para um cubo inteiro. O contorno do cursor segue a forma (um alçapão fino não ganha um cubo vazio em cima)."""
    if not name:
        return None
    from src.world.block_shapes import Quad, shape_for
    parts = shape_for(name)
    if not parts:
        return None
    points = []
    for part in parts:
        points.extend(part.corners if isinstance(part, Quad) else (part.lo, part.hi))
    corners = np.asarray(points, dtype=np.float64) / 16.0
    lo, hi = np.clip(corners.min(axis=0), 0.0, 1.0), np.clip(corners.max(axis=0), 0.0, 1.0)
    hi = np.maximum(hi, lo + 1.0 / 16.0)  # um plano (escada de mão, trilho) ganha a espessura de um pixel
    return tuple(float(v) for v in lo), tuple(float(v) for v in hi)


def door_in_reach(door, feet) -> bool:
    """A porta sob o cursor está perto o bastante de quem está em ``feet`` para abrir com a mão."""
    if door is None:
        return False
    wx, wy, wz = door.world
    dx, dz = wx + 0.5 - float(feet[0]), wz + 0.5 - float(feet[2])
    return dx * dx + dz * dz <= INTERACT_REACH ** 2 and abs(wy - int(math.floor(float(feet[1])))) <= INTERACT_VERTICAL


# --------------------------------------------------------------------------------------------- na tela
class ContextCursor:
    """Desenha o cursor na posição do mouse e o rótulo da ação preso ao bloco."""

    def __init__(self, create_gl: bool = True) -> None:
        self.time = 0.0
        self.mode = CursorMode.WALK
        self._cursor = None
        self._prompt = None
        self._cursor_key = None
        self._prompt_key = None
        if create_gl:
            import OpenGL.GL as gl
            from src.rendering.hud_quad import HudQuad
            self._cursor, self._prompt = HudQuad(), HudQuad()
            for quad in (self._cursor, self._prompt):  # pixel art: sem filtro
                gl.glBindTexture(gl.GL_TEXTURE_2D, quad.texture)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

    def update(self, dt: float, mode: CursorMode) -> None:
        self.time += max(dt, 0.0)
        self.mode = mode

    def render(self, mouse, width: int, height: int, prompt_at=None, key: str = "", verb: str = "",
               opacity: float = 1.0) -> None:
        """``mouse``: (x, y) em pixels da janela; ``prompt_at``: (x, y) na tela do ponto do bloco, ou None."""
        if self._cursor is None or opacity <= 0.0:
            return
        grow = pulse(self.time) if self.mode in (CursorMode.INTERACT, CursorMode.ATTACK) else 0
        state = (self.mode, grow)
        if state != self._cursor_key:
            self._cursor.set_image(cursor_image(self.mode, grow))
            self._cursor_key = state
        w, h = self._cursor.size
        self._cursor.draw(round(mouse[0] - w / 2), round(mouse[1] - h / 2), width, height, opacity=opacity)
        if prompt_at is None or not verb:
            return
        if (key, verb) != self._prompt_key:
            self._prompt.set_image(prompt_image(key, verb))
            self._prompt_key = (key, verb)
        w, h = self._prompt.size
        self._prompt.draw(round(prompt_at[0] - w / 2), round(prompt_at[1] - PROMPT_RISE * SCALE), width, height,
                          opacity=opacity)

    def delete(self) -> None:
        for quad in (self._cursor, self._prompt):
            if quad is not None:
                quad.delete()
        self._cursor = self._prompt = None
