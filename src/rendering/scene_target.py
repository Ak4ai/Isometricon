"""O framebuffer do mundo: a cena 3D do jogo é desenhada aqui e depois copiada para a tela.

Assim as opções gráficas valem na hora, sem recriar a janela:
- MSAA: as amostras do framebuffer (0 = sem antisserrilhado, até o máximo da placa);
- escala: a cena é desenhada numa resolução menor e ampliada na cópia (a interface, desenhada depois, fica nítida);
- FXAA: a cópia passa pelo antisserrilhado rápido, que suaviza as bordas pela imagem pronta.

Uso no quadro: ``begin`` antes da cena, ``finish`` antes da interface (o chat, o cursor e os menus vão direto para a
tela). Sem ``begin`` no quadro, ``finish`` não faz nada.
"""

from typing import Optional, Tuple

import OpenGL.GL as gl

_VERTEX = """#version 330 core
out vec2 v_Uv;
void main()
{
    // um triângulo que cobre a tela inteira, sem buffer de vértices
    vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    v_Uv = corner;
    gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
"""

# FXAA na forma enxuta (o algoritmo de Timothy Lottes, NVIDIA): acha a direção da borda pela luminância dos
# vizinhos e mistura ao longo dela; se a mistura larga sai do intervalo de luminância local, fica a estreita.
_FRAGMENT = """#version 330 core
in vec2 v_Uv;
out vec4 FragColor;
uniform sampler2D u_Scene;
uniform vec2 u_Texel;     // 1 / tamanho da cena, em uv
uniform bool u_Fxaa;

const vec3 LUMA = vec3(0.299, 0.587, 0.114);
const float SPAN_MAX = 8.0;
const float REDUCE_MUL = 1.0 / 8.0;
const float REDUCE_MIN = 1.0 / 128.0;

vec3 fxaa(vec2 uv)
{
    vec3 nw = texture(u_Scene, uv + vec2(-1.0, -1.0) * u_Texel).rgb;
    vec3 ne = texture(u_Scene, uv + vec2( 1.0, -1.0) * u_Texel).rgb;
    vec3 sw = texture(u_Scene, uv + vec2(-1.0,  1.0) * u_Texel).rgb;
    vec3 se = texture(u_Scene, uv + vec2( 1.0,  1.0) * u_Texel).rgb;
    vec3 m  = texture(u_Scene, uv).rgb;
    float lNw = dot(nw, LUMA), lNe = dot(ne, LUMA), lSw = dot(sw, LUMA), lSe = dot(se, LUMA), lM = dot(m, LUMA);
    float lMin = min(lM, min(min(lNw, lNe), min(lSw, lSe)));
    float lMax = max(lM, max(max(lNw, lNe), max(lSw, lSe)));
    vec2 dir = vec2(-((lNw + lNe) - (lSw + lSe)), (lNw + lSw) - (lNe + lSe));
    float reduce = max((lNw + lNe + lSw + lSe) * 0.25 * REDUCE_MUL, REDUCE_MIN);
    float scale = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
    dir = clamp(dir * scale, vec2(-SPAN_MAX), vec2(SPAN_MAX)) * u_Texel;
    vec3 a = 0.5 * (texture(u_Scene, uv + dir * (1.0 / 3.0 - 0.5)).rgb
                  + texture(u_Scene, uv + dir * (2.0 / 3.0 - 0.5)).rgb);
    vec3 b = a * 0.5 + 0.25 * (texture(u_Scene, uv - dir * 0.5).rgb + texture(u_Scene, uv + dir * 0.5).rgb);
    float lB = dot(b, LUMA);
    return (lB < lMin || lB > lMax) ? a : b;
}

void main()
{
    FragColor = vec4(u_Fxaa ? fxaa(v_Uv) : texture(u_Scene, v_Uv).rgb, 1.0);
}
"""


def scaled_size(width: int, height: int, scale: float) -> Tuple[int, int]:
    """O tamanho da cena para a janela e a escala (pelo menos 1x1)."""
    return max(1, round(width * scale)), max(1, round(height * scale))


class SceneTarget:
    """Framebuffer da cena com MSAA, escala de resolução e FXAA configuráveis a cada quadro."""

    def __init__(self) -> None:
        self._allocated: Optional[Tuple[int, int, int]] = None  # (largura, altura, amostras)
        self._msaa_fbo = self._msaa_color = self._msaa_depth = 0
        self._fbo = self._color = self._depth = 0
        self._program = self._vao = 0
        self._max_samples = None
        self.active = False
        self.scale = 1.0
        self.size = (1, 1)          # tamanho da cena em pixels
        self._window = (1, 1)
        self._fxaa = False

    # ------------------------------------------------------------------ quadro
    def begin(self, width: int, height: int, *, samples: int = 4, scale: float = 1.0, fxaa: bool = False) -> None:
        """Passa a desenhar no framebuffer da cena (limpo) e ajusta a área de desenho ao tamanho dele."""
        if self._max_samples is None:
            self._max_samples = int(gl.glGetIntegerv(gl.GL_MAX_SAMPLES))
        samples = min(int(samples), self._max_samples) if samples > 1 else 0
        self.scale = float(scale)
        self.size = scaled_size(width, height, scale)
        self._window = (max(1, int(width)), max(1, int(height)))
        self._fxaa = bool(fxaa)
        if self._allocated != (*self.size, samples):
            self._allocate(*self.size, samples)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._msaa_fbo or self._fbo)
        gl.glViewport(0, 0, *self.size)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self.active = True

    def finish(self) -> None:
        """Copia a cena para a tela (resolvendo o MSAA e, se ligado, com FXAA) e volta a desenhar na tela."""
        if not self.active:
            return
        self.active = False
        width, height = self.size
        if self._msaa_fbo:
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._msaa_fbo)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
            gl.glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glViewport(0, 0, *self._window)
        if self._program == 0:
            self._create_program()
        program = gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)
        vao = gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING)
        unit = gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)
        depth_test = gl.glIsEnabled(gl.GL_DEPTH_TEST)
        blend = gl.glIsEnabled(gl.GL_BLEND)
        cull = gl.glIsEnabled(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glUseProgram(self._program)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        texture = gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._color)
        gl.glUniform1i(gl.glGetUniformLocation(self._program, "u_Scene"), 0)
        gl.glUniform2f(gl.glGetUniformLocation(self._program, "u_Texel"), 1.0 / width, 1.0 / height)
        gl.glUniform1i(gl.glGetUniformLocation(self._program, "u_Fxaa"), int(self._fxaa))
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        # devolve o estado
        gl.glBindTexture(gl.GL_TEXTURE_2D, int(texture))
        gl.glActiveTexture(int(unit))
        gl.glBindVertexArray(int(vao))
        gl.glUseProgram(int(program))
        for capability, enabled in ((gl.GL_DEPTH_TEST, depth_test), (gl.GL_BLEND, blend), (gl.GL_CULL_FACE, cull)):
            (gl.glEnable if enabled else gl.glDisable)(capability)

    # ------------------------------------------------------------------ recursos
    def _allocate(self, width: int, height: int, samples: int) -> None:
        self._release_buffers()
        # a cópia final (e a cena inteira, sem MSAA): cor em textura, para a passada da tela ler com filtro
        self._color = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._color)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self._fbo = int(gl.glGenFramebuffers(1))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self._color, 0)
        if not samples:
            # a profundidade no formato da janela (24 + 8): o DepthProbe copia dela sem conversão
            self._depth = int(gl.glGenRenderbuffers(1))
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH24_STENCIL8, width, height)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_STENCIL_ATTACHMENT, gl.GL_RENDERBUFFER,
                                         self._depth)
        self._check("cena")
        if samples:
            self._msaa_fbo = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._msaa_fbo)
            self._msaa_color = int(gl.glGenRenderbuffers(1))
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._msaa_color)
            gl.glRenderbufferStorageMultisample(gl.GL_RENDERBUFFER, samples, gl.GL_RGBA8, width, height)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER,
                                         self._msaa_color)
            self._msaa_depth = int(gl.glGenRenderbuffers(1))
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._msaa_depth)
            gl.glRenderbufferStorageMultisample(gl.GL_RENDERBUFFER, samples, gl.GL_DEPTH24_STENCIL8, width, height)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_STENCIL_ATTACHMENT, gl.GL_RENDERBUFFER,
                                         self._msaa_depth)
            self._check("cena com MSAA")
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        self._allocated = (width, height, samples)

    @staticmethod
    def _check(name: str) -> None:
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            raise RuntimeError(f"Framebuffer da {name} incompleto (0x{int(status):x})")

    def _create_program(self) -> None:
        from OpenGL.GL import shaders
        self._program = int(shaders.compileProgram(shaders.compileShader(_VERTEX, gl.GL_VERTEX_SHADER),
                                                   shaders.compileShader(_FRAGMENT, gl.GL_FRAGMENT_SHADER),
                                                   validate=False))
        self._vao = int(gl.glGenVertexArrays(1))

    def _release_buffers(self) -> None:
        if self._msaa_fbo or self._fbo:
            gl.glDeleteFramebuffers(2, [self._msaa_fbo, self._fbo])
        renderbuffers = [r for r in (self._msaa_color, self._msaa_depth, self._depth) if r]
        if renderbuffers:
            gl.glDeleteRenderbuffers(len(renderbuffers), renderbuffers)
        if self._color:
            gl.glDeleteTextures(1, [self._color])
        self._msaa_fbo = self._msaa_color = self._msaa_depth = self._fbo = self._color = self._depth = 0
        self._allocated = None

    def delete(self) -> None:
        self._release_buffers()
        if self._program:
            gl.glDeleteProgram(self._program)
            gl.glDeleteVertexArrays(1, [self._vao])
            self._program = self._vao = 0
