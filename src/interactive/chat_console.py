"""Console de comando e chat interativo estilo Minecraft para o Isometricon.

Permite abrir a barra de chat com [T] ou [/], digitar comandos de personalização
em tempo real (ex: '/skin olhos vermelho', '/skin top sweater', '/skin vestir <id>')
e visualizar o feedback colorido na interface gráfica. Os comandos ficam em skin_commands.
"""

from dataclasses import dataclass
import os
import sys
import time
from typing import Any, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.math import mat4_ortho
from src.rendering import Shader


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ChatMessage:
    """Mensagem de texto com cor e timestamp no chat."""
    text: str
    color: Tuple[int, int, int] = (255, 255, 255)
    timestamp: float = 0.0


# Os comandos (execução, autocompletar e ajuda) vêm de um quadro único em skin_commands.
from src.interactive.skin_commands import COMMAND_TREE, SkinCommandHandler, expects_args  # noqa: E402,F401


class ChatConsole:
    """Console de Chat estilo Minecraft com entrada de comandos, histórico, autocompletar e HUD 2D."""

    def __init__(
        self,
        command_handler: Optional[SkinCommandHandler] = None,
        create_gl: bool = True,
        max_messages: int = 10,
        glfw_window: Optional[Any] = None,
    ) -> None:
        self.command_handler = command_handler
        if self.command_handler is not None:
            self.command_handler.chat_console = self
        self.create_gl = create_gl
        self.max_messages = max_messages
        self.glfw_window = glfw_window

        self.loading_frame: int = 0
        self.loading_timer: float = 0.0
        self.SPINNER_FRAMES = ["|", "/", "-", "\\"]

        self.is_open: bool = False
        self.input_text: str = ""
        self.cursor_pos: int = 0
        self.cursor_visible: bool = True
        self.cursor_timer: float = 0.0

        self.messages: List[ChatMessage] = [
            ChatMessage("[Isometricon] Pressione [T] para abrir o chat ou [/] para comandos", (200, 200, 200), time.time()),
            ChatMessage("[Dica] Digite /skin e use [TAB] para autocompletar; /ajuda lista os comandos.", (255, 215, 0), time.time()),
        ]
        self.history: List[str] = []
        self.history_index: int = -1

        # Estado do Autocompletar / Sugestões inteligentes estilo Minecraft
        self.suggestions: List[str] = []
        self.suggestion_index: int = 0
        self.suggestion_prefix: str = ""
        self.suggestion_base: str = ""
        self.ghost_text: str = ""
        self.suggestion_chips: List[Tuple[str, int, int, int, int]] = []
        self._tab_cycle_active: bool = False
        self._tab_base_text: str = ""
        self._ignore_chars: set = set()

        self.hud_dirty: bool = True
        self.hud_tex_id: Optional[int] = None
        self.hud_shader: Optional[Shader] = None
        self.vao: int = 0
        self.vbo: int = 0
        self.ebo: int = 0

        # Carrega fontes
        self.font = self._load_font(15)
        self.font_small = self._load_font(12)

        if self.create_gl:
            self._init_gl()

    def _get_clipboard_string(self) -> str:
        """Obtém o conteúdo de texto da área de transferência (clipboard) como string garantida."""
        # 1. No Windows, prioriza a API Win32 nativa (CF_UNICODETEXT) - 100% confiável e direta
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.OpenClipboard.argtypes = [ctypes.c_void_p]
                user32.OpenClipboard.restype = ctypes.c_int
                user32.CloseClipboard.argtypes = []
                user32.CloseClipboard.restype = ctypes.c_int
                user32.GetClipboardData.restype = ctypes.c_void_p
                user32.GetClipboardData.argtypes = [ctypes.c_uint]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.restype = ctypes.c_int

                opened = False
                for _ in range(5):
                    if user32.OpenClipboard(None):
                        opened = True
                        break
                    time.sleep(0.005)

                if opened:
                    try:
                        h = user32.GetClipboardData(13)  # CF_UNICODETEXT
                        if h:
                            p = kernel32.GlobalLock(h)
                            if p:
                                try:
                                    val = ctypes.c_wchar_p(p).value
                                    if val:
                                        return str(val)
                                finally:
                                    kernel32.GlobalUnlock(h)
                    finally:
                        user32.CloseClipboard()
            except Exception:
                pass

        # 2. Fallback via GLFW (decodificando bytes se pyglfw retornar tipo binário)
        try:
            import glfw
            win = self.glfw_window or glfw.get_current_context()
            if win:
                t = glfw.get_clipboard_string(win)
                if t is not None:
                    if isinstance(t, bytes):
                        t = t.decode("utf-8", errors="replace")
                    if isinstance(t, str) and t:
                        return t
        except Exception:
            pass

        # 3. Fallback via tkinter se disponível
        try:
            import tkinter
            tk = tkinter.Tk()
            tk.withdraw()
            try:
                res = tk.clipboard_get()
                if res:
                    return str(res)
            finally:
                tk.destroy()
        except Exception:
            pass

        return ""

    def _set_clipboard_string(self, text: str) -> None:
        """Define o conteúdo de texto da área de transferência."""
        if not text:
            return

        text = str(text)

        # 1. No Windows, usa a API Win32 nativa (CF_UNICODETEXT)
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.OpenClipboard.argtypes = [ctypes.c_void_p]
                user32.OpenClipboard.restype = ctypes.c_int
                user32.CloseClipboard.argtypes = []
                user32.CloseClipboard.restype = ctypes.c_int
                user32.EmptyClipboard.argtypes = []
                user32.EmptyClipboard.restype = ctypes.c_int
                user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
                user32.SetClipboardData.restype = ctypes.c_void_p
                kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
                kernel32.GlobalAlloc.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.restype = ctypes.c_int

                opened = False
                for _ in range(5):
                    if user32.OpenClipboard(None):
                        opened = True
                        break
                    time.sleep(0.005)

                if opened:
                    try:
                        user32.EmptyClipboard()
                        encoded = text.encode("utf-16-le") + b"\x00\x00"
                        h = kernel32.GlobalAlloc(0x0002, len(encoded))  # GMEM_MOVEABLE
                        if h:
                            p = kernel32.GlobalLock(h)
                            if p:
                                ctypes.memmove(p, encoded, len(encoded))
                                kernel32.GlobalUnlock(h)
                                user32.SetClipboardData(13, h)
                    finally:
                        user32.CloseClipboard()
                return
            except Exception:
                pass

        # 2. Fallback via GLFW
        try:
            import glfw
            win = self.glfw_window or glfw.get_current_context()
            if win:
                glfw.set_clipboard_string(win, text)
                return
        except Exception:
            pass

    def _load_font(self, size: int = 15) -> Any:
        """Carrega fonte Consolas ou TrueType equivalente do sistema."""
        font_candidates = [
            "consola.ttf",
            "consolas.ttf",
            "C:/Windows/Fonts/consola.ttf",
            "segoeui.ttf",
            "arial.ttf",
        ]
        for f in font_candidates:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _init_gl(self) -> None:
        """Inicializa shaders e buffers OpenGL para o quad 2D do HUD."""
        import OpenGL.GL as gl

        v_shader = os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.vert")
        f_shader = os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.frag")
        self.hud_shader = Shader(v_shader, f_shader)

        # Quad unitário 2D (Pos2, UV2)
        quad_verts = np.array([
            0.0, 0.0,   0.0, 0.0,
            1.0, 0.0,   1.0, 0.0,
            1.0, 1.0,   1.0, 1.0,
            0.0, 1.0,   0.0, 1.0,
        ], dtype=np.float32)

        quad_indices = np.array([
            0, 1, 2,
            2, 3, 0,
        ], dtype=np.uint32)

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        self.ebo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self.vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, quad_verts.nbytes, quad_verts, gl.GL_STATIC_DRAW)

        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, gl.GL_STATIC_DRAW)

        stride = 4 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, None)

        gl.glEnableVertexAttribArray(1)
        import ctypes
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(2 * 4))

        gl.glBindVertexArray(0)

        # Textura do HUD
        self.hud_tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.hud_tex_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

    def add_message(self, text: str, color: Tuple[int, int, int] = (255, 255, 255)) -> None:
        """Adiciona uma nova mensagem ao histórico do chat."""
        msg = ChatMessage(text=text, color=color, timestamp=time.time())
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
        self.hud_dirty = True
        print(f"[Chat] {text}")

    def open(self, initial_text: str = "", ignore_char: Optional[str] = None) -> None:
        """Abre a barra de digitação do chat."""
        self.is_open = True
        self.input_text = initial_text
        self.cursor_pos = len(initial_text)
        self.cursor_visible = True
        self.cursor_timer = 0.0
        self.history_index = -1
        self._tab_cycle_active = False
        self._ignore_chars = {ignore_char.lower(), ignore_char.upper()} if ignore_char else set()
        self._update_autocomplete()
        self.hud_dirty = True

    def close(self) -> None:
        """Fecha a barra de digitação do chat sem executar."""
        self.is_open = False
        self.input_text = ""
        self.cursor_pos = 0
        self.history_index = -1
        self._tab_cycle_active = False
        self._ignore_chars.clear()
        self.suggestions = []
        self.ghost_text = ""
        self.hud_dirty = True

    def toggle(self, initial_text: str = "") -> None:
        """Alterna a abertura da barra de chat."""
        if self.is_open:
            self.close()
        else:
            self.open(initial_text)

    def handle_char(self, codepoint: int) -> bool:
        """Recebe entrada de caractere Unicode do GLFW."""
        if not self.is_open:
            return False

        # Ignora caracteres de controle ASCII (< 32, ex: Ctrl+V emitindo codepoint 22, ou DEL 127)
        if codepoint < 32 or codepoint == 127:
            return True

        try:
            char = chr(codepoint)
        except (ValueError, OverflowError):
            return False

        try:
            if self._ignore_chars:
                if char in self._ignore_chars:
                    self._ignore_chars.clear()
                    return True
                self._ignore_chars.clear()

            # Insere caractere na posição do cursor
            self.input_text = self.input_text[:self.cursor_pos] + char + self.input_text[self.cursor_pos:]
            self.cursor_pos += 1
            self.cursor_visible = True
            self.cursor_timer = 0.0
            self._tab_cycle_active = False
            self._update_autocomplete()
            self.hud_dirty = True
            return True
        except Exception as e:
            print(f"[Chat] Erro ao inserir caractere: {e}")
            return True

    def handle_key(self, key: int, action: int, mods: int) -> bool:
        """Processa eventos de teclas. Retorna True se o evento foi consumido."""
        import glfw

        # Abrir com 'T' ou '/' quando fechado
        if not self.is_open:
            if action == glfw.PRESS:
                if key == glfw.KEY_T:
                    self.open(ignore_char="t")
                    return True
                elif key == glfw.KEY_SLASH:
                    self.open("/", ignore_char="/")
                    return True
            return False

        # Quando aberto, teclas especiais
        if action in (glfw.PRESS, glfw.REPEAT):
            # Atalhos de Clipboard e Edição com Ctrl ou Cmd (Super)
            ctrl_or_cmd = bool(mods & (glfw.MOD_CONTROL | glfw.MOD_SUPER))
            if ctrl_or_cmd and key == glfw.KEY_V:
                try:
                    clip = self._get_clipboard_string()
                    if clip:
                        if isinstance(clip, bytes):
                            clip = clip.decode("utf-8", errors="replace")
                        clip = str(clip).replace("\r", "").replace("\n", " ").strip()
                        if clip:
                            self.input_text = self.input_text[:self.cursor_pos] + clip + self.input_text[self.cursor_pos:]
                            self.cursor_pos += len(clip)
                            self.cursor_visible = True
                            self.cursor_timer = 0.0
                            self._tab_cycle_active = False
                            self._update_autocomplete()
                            self.hud_dirty = True
                except Exception as e:
                    print(f"[Chat] Erro ao colar texto: {e}")
                return True

            if ctrl_or_cmd and key == glfw.KEY_C:
                try:
                    if self.input_text:
                        self._set_clipboard_string(str(self.input_text))
                except Exception as e:
                    print(f"[Chat] Erro ao copiar para área de transferência: {e}")
                return True

            if ctrl_or_cmd and key == glfw.KEY_A:
                self.cursor_pos = len(self.input_text)
                self.cursor_visible = True
                self.hud_dirty = True
                return True

            if key == glfw.KEY_ESCAPE:
                self.close()
                return True

            elif key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER):
                self._submit_input()
                return True

            elif key == glfw.KEY_TAB:
                self._apply_autocomplete(shift_held=bool(mods & glfw.MOD_SHIFT))
                return True

            elif key == glfw.KEY_BACKSPACE:
                if self.cursor_pos > 0:
                    self.input_text = self.input_text[:self.cursor_pos - 1] + self.input_text[self.cursor_pos:]
                    self.cursor_pos -= 1
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_DELETE:
                if self.cursor_pos < len(self.input_text):
                    self.input_text = self.input_text[:self.cursor_pos] + self.input_text[self.cursor_pos + 1:]
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_LEFT:
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_RIGHT:
                if self.cursor_pos < len(self.input_text):
                    self.cursor_pos += 1
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_HOME:
                self.cursor_pos = 0
                self.cursor_visible = True
                self._tab_cycle_active = False
                self._update_autocomplete()
                self.hud_dirty = True
                return True

            elif key == glfw.KEY_END:
                self.cursor_pos = len(self.input_text)
                self.cursor_visible = True
                self._tab_cycle_active = False
                self._update_autocomplete()
                self.hud_dirty = True
                return True

            elif key == glfw.KEY_UP:
                self._navigate_history(-1)
                return True

            elif key == glfw.KEY_DOWN:
                self._navigate_history(1)
                return True

        # Consome todas as outras teclas quando o chat está aberto para não movimentar o jogo
        return True

    def _sugg_expects_args(self, chosen: str) -> bool:
        """Verifica se uma opção de comando ainda aceita argumentos posteriores."""
        return expects_args(chosen)

    def _get_suggestions_for_prefix(self, text: str) -> Tuple[List[str], str, str]:
        """Extrai as sugestões contextuais com base na árvore de comandos."""
        if not text.startswith("/"):
            return [], "", text

        clean = text[1:]

        # Caso 1: Ainda digitando o comando raiz (sem espaço)
        if " " not in clean:
            prefix = clean.lower()
            root_cmds = sorted(list(COMMAND_TREE.keys()))
            matches = [f"/{c}" for c in root_cmds if c.startswith(prefix)]
            return matches, text, ""

        # Caso 2: Já digitou o comando raiz e argumentos
        parts = clean.split(" ")
        root_cmd = parts[0].lower()
        args = parts[1:]

        node = COMMAND_TREE.get(root_cmd)
        if node is None:
            return [], "", text

        curr = node
        base_parts = ["/" + parts[0]]

        for part in args[:-1]:
            base_parts.append(part)
            if isinstance(curr, dict):
                curr = curr.get(part.lower())
                if curr is None:
                    return [], "", text
            elif isinstance(curr, list):
                return [], "", text

        curr_token = args[-1].lower()
        base_text = " ".join(base_parts) + " "
        if callable(curr):
            curr = curr()  # options computed on demand (the items downloaded so far)
        if isinstance(curr, (dict, list)):
            matches = [opt for opt in curr if opt.lower().startswith(curr_token)]
            return matches, args[-1], base_text

        return [], "", text

    def _update_autocomplete(self, preserve_cycle: bool = False) -> None:
        """Calcula a lista de comandos e argumentos válidos para sugestão em tempo real."""
        if self._tab_cycle_active and preserve_cycle:
            self.ghost_text = ""
            return

        text = self.input_text[:self.cursor_pos]
        if not text.startswith("/"):
            self.suggestions = []
            self.suggestion_index = 0
            self.suggestion_prefix = ""
            self.suggestion_base = ""
            self.ghost_text = ""
            return

        suggestions, prefix, base_text = self._get_suggestions_for_prefix(text)
        self.suggestions = suggestions
        self.suggestion_prefix = prefix
        self.suggestion_base = base_text

        if self.suggestion_index >= len(self.suggestions):
            self.suggestion_index = 0

        if self.suggestions:
            chosen = self.suggestions[self.suggestion_index]
            if chosen.lower().startswith(prefix.lower()):
                suffix = chosen[len(prefix):]
            else:
                suffix = chosen

            needs_space = self._sugg_expects_args(chosen)
            self.ghost_text = suffix + (" " if needs_space and not suffix.endswith(" ") else "")
        else:
            self.ghost_text = ""

    def _apply_autocomplete(self, shift_held: bool = False) -> None:
        """Aplica a sugestão ativa do autocomplete ou avança para a próxima com TAB."""
        if not self.suggestions:
            return

        if self._tab_cycle_active:
            if shift_held:
                self.suggestion_index = (self.suggestion_index - 1) % len(self.suggestions)
            else:
                self.suggestion_index = (self.suggestion_index + 1) % len(self.suggestions)
        else:
            self._tab_cycle_active = True
            self._tab_base_text = self.suggestion_base

        chosen = self.suggestions[self.suggestion_index]
        needs_space = self._sugg_expects_args(chosen)
        new_word = chosen + (" " if needs_space else "")

        if chosen.startswith("/"):
            self.input_text = new_word
        else:
            self.input_text = self._tab_base_text + new_word

        self.cursor_pos = len(self.input_text)
        self.cursor_visible = True
        self.cursor_timer = 0.0

        if needs_space:
            self._tab_cycle_active = False
            self._update_autocomplete()
        else:
            self._update_autocomplete(preserve_cycle=True)

        self.hud_dirty = True

    def handle_mouse_click(self, x: float, y: float) -> bool:
        """Processa clique do mouse sobre os chips de sugestão do autocomplete."""
        if not self.is_open or not self.suggestion_chips:
            return False

        for sugg, x0, y0, x1, y1 in self.suggestion_chips:
            if x0 <= x <= x1 and y0 <= y <= y1:
                if sugg in self.suggestions:
                    self.suggestion_index = self.suggestions.index(sugg)
                else:
                    self.suggestions = [sugg]
                    self.suggestion_index = 0

                self._tab_cycle_active = False
                self._apply_autocomplete()
                return True
        return False

    def _navigate_history(self, direction: int) -> None:
        """Navega para comandos anteriores ou posteriores no histórico."""
        if not self.history:
            return

        if self.history_index == -1:
            if direction < 0:
                self.history_index = len(self.history) - 1
        else:
            self.history_index += direction

        if self.history_index < 0:
            self.history_index = 0
        elif self.history_index >= len(self.history):
            self.history_index = -1
            self.input_text = ""
            self.cursor_pos = 0
            self._tab_cycle_active = False
            self._update_autocomplete()
            self.hud_dirty = True
            return

        self.input_text = self.history[self.history_index]
        self.cursor_pos = len(self.input_text)
        self.cursor_visible = True
        self._tab_cycle_active = False
        self._update_autocomplete()
        self.hud_dirty = True

    def _submit_input(self) -> None:
        """Executa a linha digitada e fecha a barra de chat."""
        cmd = self.input_text.strip()
        self.close()

        if not cmd:
            return

        # Registra no histórico
        if not self.history or self.history[-1] != cmd:
            self.history.append(cmd)

        # Executa no CommandHandler
        if self.command_handler:
            success, feedback, color = self.command_handler.execute(cmd)
            if feedback:
                self.add_message(feedback, color)
        else:
            self.add_message(f"> {cmd}", (255, 255, 255))

    def update(self, dt: float) -> None:
        """Atualiza temporizador do cursor, processa callbacks na thread principal e anima spinner."""
        if self.command_handler is not None:
            self.command_handler.process_pending_callbacks()

        # Atualiza animação do loading spinner se estiver importando roupa em background
        is_importing = bool(self.command_handler and self.command_handler.busy_status)
        if is_importing:
            self.loading_timer += dt
            if self.loading_timer >= 0.12:
                self.loading_timer = 0.0
                self.loading_frame = (self.loading_frame + 1) % len(self.SPINNER_FRAMES)
                self.hud_dirty = True

        if self.is_open:
            self.cursor_timer += dt
            if self.cursor_timer >= 0.45:
                self.cursor_timer = 0.0
                self.cursor_visible = not self.cursor_visible
                self.hud_dirty = True

    def render(self, window_width: int, window_height: int) -> None:
        """Renderiza a caixa de chat e mensagens na tela usando OpenGL 3.3 Core."""
        if not self.create_gl or self.hud_shader is None:
            return

        now = time.time()
        # Filtra mensagens recentes (exibe mensagens nos últimos 8 segundos quando chat fechado)
        visible_messages = [
            m for m in self.messages
            if self.is_open or (now - m.timestamp < 8.0)
        ]

        is_importing = bool(self.command_handler and self.command_handler.busy_status)
        if not self.is_open and not visible_messages and not is_importing:
            return

        import OpenGL.GL as gl

        # 1. Desenha a textura do HUD se modificada
        if self.hud_dirty:
            hud_img = self._generate_hud_image(window_width, window_height, visible_messages)
            img_data = np.array(hud_img, dtype=np.uint8)

            gl.glBindTexture(gl.GL_TEXTURE_2D, self.hud_tex_id)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                hud_img.width, hud_img.height, 0,
                gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data
            )
            self.hud_dirty = False

        # 2. Configura pipeline 2D ortográfico
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDepthMask(gl.GL_FALSE)

        self.hud_shader.use()
        proj = mat4_ortho(0.0, float(window_width), float(window_height), 0.0, -1.0, 1.0)
        self.hud_shader.set_mat4("u_Projection", proj)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.hud_tex_id)
        self.hud_shader.set_int("u_Texture", 0)

        # Ajusta vértices para as dimensões exatas da janela
        w = float(window_width)
        h = float(window_height)
        quad_verts = np.array([
            0.0, 0.0,   0.0, 0.0,
            w,   0.0,   1.0, 0.0,
            w,   h,     1.0, 1.0,
            0.0, h,     0.0, 1.0,
        ], dtype=np.float32)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, quad_verts.nbytes, quad_verts)

        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_BLEND)

    def _generate_hud_image(
        self,
        width: int,
        height: int,
        visible_messages: List[ChatMessage],
    ) -> Image.Image:
        """Desenha a imagem RGBA contendo as mensagens, sugestões de autocompletar e campo de texto estilo Minecraft."""
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Dimensões da caixa de chat (canto inferior esquerdo)
        box_x = 16
        box_w = min(740, width - 32)
        line_height = 20
        max_lines = 8
        messages_to_show = visible_messages[-max_lines:]

        # Altura calculada da caixa
        hist_h = len(messages_to_show) * line_height + 10
        has_suggestions = self.is_open and bool(self.suggestions)
        sugg_h = 34 if has_suggestions else 0
        input_h = 28 if self.is_open else 0
        total_h = hist_h + sugg_h + input_h + (8 if has_suggestions else 6)
        box_y = height - total_h - 16

        # Fundo semitransparente escuro estilo Minecraft Chat
        if self.is_open or messages_to_show:
            draw.rectangle(
                [box_x - 6, box_y - 4, box_x + box_w + 6, box_y + total_h + 2],
                fill=(0, 0, 0, 165 if self.is_open else 115),
                outline=(50, 50, 60, 180) if self.is_open else None,
                width=1,
            )

        # Desenha mensagens do histórico
        curr_y = box_y + 4
        for msg in messages_to_show:
            r, g, b = msg.color
            draw.text((box_x + 1, curr_y + 1), msg.text, font=self.font, fill=(20, 20, 20, 220))
            draw.text((box_x, curr_y), msg.text, font=self.font, fill=(r, g, b, 255))
            curr_y += line_height

        # Painel de sugestões e autocomplete (quando aberto e com sugestões)
        self.suggestion_chips = []
        if has_suggestions:
            sugg_y = box_y + hist_h + 2
            draw.rectangle(
                [box_x - 4, sugg_y, box_x + box_w + 4, sugg_y + sugg_h],
                fill=(12, 16, 24, 235),
                outline=(45, 65, 95, 210),
                width=1,
            )

            # Badge indicadora de tecla TAB
            tab_badge_w = 48
            draw.rounded_rectangle(
                [box_x + 4, sugg_y + 6, box_x + 4 + tab_badge_w, sugg_y + 28],
                radius=3,
                fill=(210, 165, 25, 240),
            )
            draw.text((box_x + 8, sugg_y + 9), "TAB ⇥", font=self.font_small, fill=(15, 15, 15, 255))

            # Chips horizontais de sugestões
            cx = box_x + 4 + tab_badge_w + 8
            cy = sugg_y + 6
            for i, sugg in enumerate(self.suggestions):
                try:
                    sugg_text_w = int(draw.textlength(sugg, font=self.font))
                except AttributeError:
                    sugg_text_w = len(sugg) * 9
                chip_w = sugg_text_w + 12

                # Se estourar a largura do painel, exibe contagem restante
                if cx + chip_w > box_x + box_w - 45:
                    remaining = len(self.suggestions) - i
                    draw.text((cx + 2, cy + 4), f"+{remaining}", font=self.font_small, fill=(160, 175, 195, 220))
                    break

                if i == self.suggestion_index:
                    # Chip ativo em destaque
                    draw.rounded_rectangle(
                        [cx, cy, cx + chip_w, cy + 22],
                        radius=4,
                        fill=(28, 92, 185, 250),
                        outline=(120, 215, 255, 255),
                        width=1,
                    )
                    draw.text((cx + 6, cy + 3), sugg, font=self.font, fill=(255, 255, 255, 255))
                else:
                    # Chip inativo
                    draw.rounded_rectangle(
                        [cx, cy, cx + chip_w, cy + 22],
                        radius=4,
                        fill=(22, 28, 38, 215),
                        outline=(52, 64, 82, 180),
                        width=1,
                    )
                    draw.text((cx + 6, cy + 3), sugg, font=self.font, fill=(180, 195, 215, 225))

                self.suggestion_chips.append((sugg, cx, cy, cx + chip_w, cy + 22))
                cx += chip_w + 6

        # Campo de entrada de comando (quando aberto)
        if self.is_open:
            input_y = box_y + hist_h + (sugg_h + 4 if has_suggestions else 0)
            draw.rectangle(
                [box_x - 4, input_y, box_x + box_w + 4, input_y + input_h],
                fill=(10, 12, 16, 235),
                outline=(80, 135, 215, 230),
                width=1,
            )

            prompt_symbol = "> "
            draw.text((box_x + 6, input_y + 6), prompt_symbol, font=self.font, fill=(255, 215, 0, 255))

            try:
                prompt_w = draw.textlength(prompt_symbol, font=self.font)
            except AttributeError:
                prompt_w = 18

            text_x = box_x + 6 + prompt_w
            draw.text((text_x, input_y + 6), self.input_text, font=self.font, fill=(255, 255, 255, 255))

            # Texto fantasma (ghost text) da sugestão atual
            if self.ghost_text:
                try:
                    user_w = draw.textlength(self.input_text, font=self.font)
                except AttributeError:
                    user_w = len(self.input_text) * 9
                draw.text((text_x + user_w, input_y + 6), self.ghost_text, font=self.font, fill=(140, 150, 175, 180))

            # Cursor piscante
            if self.cursor_visible:
                text_before_cursor = self.input_text[:self.cursor_pos]
                try:
                    cursor_offset = draw.textlength(text_before_cursor, font=self.font)
                except AttributeError:
                    cursor_offset = len(text_before_cursor) * 9
                cursor_x = text_x + cursor_offset
                draw.text((cursor_x, input_y + 6), "_", font=self.font, fill=(255, 255, 255, 255))
        else:
            hint_text = "[T] Abrir Chat / Comandos | [/] Digitar Comando"
            draw.text((box_x, height - 22), hint_text, font=self.font, fill=(160, 160, 170, 160))

        # Badge animada de Loading / Importando em segundo plano (canto superior direito)
        if self.command_handler and self.command_handler.busy_status:
            spinner = self.SPINNER_FRAMES[self.loading_frame % len(self.SPINNER_FRAMES)]
            status_text = self.command_handler.busy_status
            badge_text = f"[ {spinner} ] {status_text}"

            try:
                badge_w = int(draw.textlength(badge_text, font=self.font)) + 24
            except AttributeError:
                badge_w = len(badge_text) * 10 + 24
            badge_h = 32
            badge_x = width - badge_w - 20
            badge_y = 20

            # Fundo translúcido estilizado com borda neon ciano
            draw.rounded_rectangle(
                [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
                radius=6,
                fill=(12, 22, 34, 230),
                outline=(85, 255, 255, 240),
                width=2,
            )
            # Texto e spinner em ciano neon brilhante
            draw.text(
                (badge_x + 12, badge_y + 7),
                badge_text,
                font=self.font,
                fill=(85, 255, 255, 255),
            )

        return img

    def delete(self) -> None:
        """Libera os recursos OpenGL do HUD."""
        if not self.create_gl:
            return
        import OpenGL.GL as gl

        if self.hud_tex_id:
            try:
                gl.glDeleteTextures(1, [self.hud_tex_id])
            except Exception:
                pass
            self.hud_tex_id = None

        if self.vao:
            try:
                gl.glDeleteVertexArrays(1, [self.vao])
            except Exception:
                pass
            self.vao = 0

        if self.vbo:
            try:
                gl.glDeleteBuffers(1, [self.vbo])
            except Exception:
                pass
            self.vbo = 0

        if self.ebo:
            try:
                gl.glDeleteBuffers(1, [self.ebo])
            except Exception:
                pass
            self.ebo = 0

        if self.hud_shader:
            try:
                self.hud_shader.delete()
            except Exception:
                pass
            self.hud_shader = None
