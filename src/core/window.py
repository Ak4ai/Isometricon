"""Gerenciamento de Janela e Contexto OpenGL 3.3 Core Profile via GLFW."""

from typing import Callable, List, Optional, Tuple
import OpenGL.GL as gl
import glfw


class Window:
    """Encapsula a inicialização do GLFW e o ciclo de vida da janela OpenGL."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        title: str = "Isometricon - 3D VTT Engine (OpenGL 3.3 Core)",
        vsync: bool = True,
        resizable: bool = True,
    ) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.vsync = vsync
        self.resizable = resizable

        self._window = None
        self._last_frame_time = 0.0
        self._delta_time = 0.0
        self._frame_count = 0
        self._fps_timer = 0.0
        self._current_fps = 0.0

        # Callbacks registrados externamente
        self._resize_callbacks: List[Callable[[int, int], None]] = []
        self._scroll_callbacks: List[Callable[[float, float], None]] = []
        self._cursor_pos_callbacks: List[Callable[[float, float], None]] = []
        self._mouse_button_callbacks: List[Callable[[int, int, int], None]] = []
        self._key_callbacks: List[Callable[[int, int, int, int], None]] = []

        self._init_glfw()

    def _init_glfw(self) -> None:
        """Inicializa GLFW e cria janela com contexto OpenGL 3.3 Core Profile."""
        if not glfw.init():
            raise RuntimeError("Falha crítica ao inicializar GLFW.")

        # Configuração estrita do Contexto OpenGL 3.3 Core Profile
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE if self.resizable else glfw.FALSE)
        glfw.window_hint(glfw.SAMPLES, 4)  # 4x MSAA para bordas suaves de blocos

        self._window = glfw.create_window(self.width, self.height, self.title, None, None)
        if not self._window:
            glfw.terminate()
            raise RuntimeError("Falha ao criar a janela GLFW (OpenGL 3.3 Core Profile).")

        glfw.make_context_current(self._window)
        glfw.swap_interval(1 if self.vsync else 0)

        # Configurar Viewport inicial baseado no framebuffer real
        fb_w, fb_h = glfw.get_framebuffer_size(self._window)
        gl.glViewport(0, 0, fb_w, fb_h)

        # Registrar callbacks internos do GLFW
        glfw.set_framebuffer_size_callback(self._window, self._on_framebuffer_resize)
        glfw.set_scroll_callback(self._window, self._on_scroll)
        glfw.set_cursor_pos_callback(self._window, self._on_cursor_pos)
        glfw.set_mouse_button_callback(self._window, self._on_mouse_button)
        glfw.set_key_callback(self._window, self._on_key)

        self._last_frame_time = glfw.get_time()

    def _on_framebuffer_resize(self, window, width: int, height: int) -> None:
        """Callback acionado ao redimensionar a janela."""
        if width > 0 and height > 0:
            self.width = width
            self.height = height
            gl.glViewport(0, 0, width, height)
            for cb in self._resize_callbacks:
                cb(width, height)

    def _on_scroll(self, window, x_offset: float, y_offset: float) -> None:
        """Callback acionado pela roda do mouse."""
        for cb in self._scroll_callbacks:
            cb(x_offset, y_offset)

    def _on_cursor_pos(self, window, x_pos: float, y_pos: float) -> None:
        """Callback acionado pelo movimento do mouse."""
        for cb in self._cursor_pos_callbacks:
            cb(x_pos, y_pos)

    def _on_mouse_button(self, window, button: int, action: int, mods: int) -> None:
        """Callback acionado por botões do mouse."""
        for cb in self._mouse_button_callbacks:
            cb(button, action, mods)

    def _on_key(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        """Callback de teclado. Fecha a janela ao pressionar ESC por padrão."""
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.set_window_should_close(self._window, True)
        for cb in self._key_callbacks:
            cb(key, scancode, action, mods)

    def add_resize_callback(self, callback: Callable[[int, int], None]) -> None:
        """Adiciona um observador para eventos de redimensionamento."""
        self._resize_callbacks.append(callback)

    def add_scroll_callback(self, callback: Callable[[float, float], None]) -> None:
        """Adiciona um observador para eventos de scroll do mouse (Zoom)."""
        self._scroll_callbacks.append(callback)

    def add_cursor_pos_callback(self, callback: Callable[[float, float], None]) -> None:
        """Adiciona um observador para movimento do cursor (Pan / Raycasting)."""
        self._cursor_pos_callbacks.append(callback)

    def add_mouse_button_callback(self, callback: Callable[[int, int, int], None]) -> None:
        """Adiciona um observador para cliques de mouse."""
        self._mouse_button_callbacks.append(callback)

    def add_key_callback(self, callback: Callable[[int, int, int, int], None]) -> None:
        """Adiciona um observador para eventos de teclado."""
        self._key_callbacks.append(callback)

    def is_key_pressed(self, key: int) -> bool:
        """Verifica se uma tecla específica está atualmente pressionada."""
        return glfw.get_key(self._window, key) == glfw.PRESS

    def is_mouse_button_pressed(self, button: int) -> bool:
        """Verifica se um botão do mouse está pressionado."""
        return glfw.get_mouse_button(self._window, button) == glfw.PRESS

    def get_cursor_pos(self) -> Tuple[float, float]:
        """Retorna a posição atual do cursor (x, y)."""
        return glfw.get_cursor_pos(self._window)

    def get_aspect_ratio(self) -> float:
        """Retorna o aspect ratio atual da janela (largura / altura)."""
        return float(self.width) / float(self.height) if self.height > 0 else 1.0

    def update_delta_time(self) -> float:
        """Calcula o delta time entre frames e atualiza a média de FPS."""
        current_time = glfw.get_time()
        self._delta_time = current_time - self._last_frame_time
        self._last_frame_time = current_time

        # Contagem de FPS
        self._frame_count += 1
        if current_time - self._fps_timer >= 1.0:
            self._current_fps = self._frame_count / (current_time - self._fps_timer)
            self._frame_count = 0
            self._fps_timer = current_time

        return self._delta_time

    @property
    def delta_time(self) -> float:
        """Tempo decorrido (em segundos) desde o último frame."""
        return self._delta_time

    @property
    def fps(self) -> float:
        """Taxa atual de quadros por segundo (FPS)."""
        return self._current_fps

    def should_close(self) -> bool:
        """Informa se o usuário solicitou o fechamento da janela."""
        return glfw.window_should_close(self._window)

    def poll_events(self) -> None:
        """Processa eventos da fila do sistema operacional."""
        glfw.poll_events()

    def swap_buffers(self) -> None:
        """Troca os buffers frontal e traseiro (Double Buffering)."""
        glfw.swap_buffers(self._window)

    def set_title(self, title: str) -> None:
        """Atualiza o título da janela dinamicamente."""
        self.title = title
        glfw.set_window_title(self._window, title)

    def close(self) -> None:
        """Fecha a janela e finaliza o GLFW de forma segura."""
        if self._window:
            glfw.destroy_window(self._window)
            self._window = None
        glfw.terminate()
