"""
Câmera isométrica para Isometricon.
- Projeção ortográfica sem perspectiva.
- Orientação isométrica padrão:
    Yaw   = 45°
    Pitch = asin(tan(30°)) ≈ 35.264°
- Zoom através de ortho_size.
- Pan do ponto focal no plano XZ.
- Rotação ortogonal do tabuleiro em passos de 90°.
"""

from __future__ import annotations
import math
from typing import Tuple
import numpy as np
from src.math import mat4_look_at, mat4_ortho, mat4_rotate_y, vec3

class IsometricCamera:
    DEFAULT_YAW_DEGREES = 45.0
    DEFAULT_PITCH_DEGREES = math.degrees(
        math.asin(math.tan(math.radians(30.0)))
    )
    DEFAULT_ORTHO_SIZE = 2.0
    DEFAULT_DISTANCE = 10.0
    DEFAULT_NEAR = 0.1
    DEFAULT_FAR = 100.0
    MIN_ORTHO_SIZE = 0.25
    MAX_ORTHO_SIZE = 100.0
    # Fator de zoom por unidade de scroll.
    ZOOM_FACTOR = 0.15
    def __init__(
        self,
        target: np.ndarray | None = None,
        ortho_size: float = DEFAULT_ORTHO_SIZE,
        near: float = DEFAULT_NEAR,
        far: float = DEFAULT_FAR,
    ) -> None:
        """Inicializa a câmera isométrica.
        Args:
            target:
                Ponto do mundo que a câmera observa.
            ortho_size:
                Extensão vertical da projeção ortográfica.
            near:
                Plano de recorte próximo.
            far:
                Plano de recorte distante.
        """
        if ortho_size <= 0.0:
            raise ValueError("ortho_size deve ser maior que zero.")
        if near <= 0.0:
            raise ValueError("near deve ser maior que zero.")
        if far <= near:
            raise ValueError("far deve ser maior que near.")
        self.target = (
            np.asarray(target, dtype=np.float32).copy()
            if target is not None
            else vec3(0.0, 0.0, 0.0)
        )
        if self.target.shape != (3,):
            raise ValueError("target deve ser um vetor 3D.")
        self.yaw = math.radians(self.DEFAULT_YAW_DEGREES)
        self.pitch = math.radians(self.DEFAULT_PITCH_DEGREES)
        self.ortho_size = float(
            np.clip(
                ortho_size,
                self.MIN_ORTHO_SIZE,
                self.MAX_ORTHO_SIZE,
            )
        )
        self.near = float(near)
        self.far = float(far)
        # Rotação lógica do tabuleiro.
        # Valores possíveis: 0, 90, 180, 270.
        self.board_rotation = 0
    # ------------------------------------------------------------------
    # Propriedades da câmera
    # ------------------------------------------------------------------
    @property
    def yaw_degrees(self) -> float:
        #Retorna o yaw em graus
        return math.degrees(self.yaw)
    @property
    def pitch_degrees(self) -> float:
        #Retorna o pitch em graus
        return math.degrees(self.pitch)
    @property
    def board_rotation_degrees(self) -> int:
        #Retorna a rotação atual do tabuleiro em graus.
        return self.board_rotation
    # ------------------------------------------------------------------
    # Vetores da câmera
    # ------------------------------------------------------------------
    def _horizontal_view_direction(self) -> np.ndarray:
        #Retorna a direção horizontal para a qual a câmera olha.
        #O vetor aponta da câmera em direção ao target, ignorando Y.
        sin_yaw = math.sin(self.yaw)
        cos_yaw = math.cos(self.yaw)
        direction = np.array(
            [-sin_yaw, 0.0, -cos_yaw],
            dtype=np.float32,
        )
        length = np.linalg.norm(direction)
        if length == 0.0:
            return vec3(0.0, 0.0, -1.0)
        return direction / length
    def _right_direction(self) -> np.ndarray:
        #Retorna o vetor correspondente ao lado direito da câmera.
	#O vetor está restrito ao plano XZ.
        forward = self._horizontal_view_direction()
        up = vec3(0.0, 1.0, 0.0)
        right = np.cross(forward, up)
        length = np.linalg.norm(right)
        if length == 0.0:
            return vec3(1.0, 0.0, 0.0)
        return (right / length).astype(np.float32)
    def _forward_direction(self) -> np.ndarray:
        #Retorna o vetor frontal projetado no plano XZ.
        forward = self._horizontal_view_direction()
        return np.array(
            [forward[0], 0.0, forward[2]],
            dtype=np.float32,
        )
    def _camera_position(self) -> np.ndarray:
        #Calcula a posição da câmera a partir do target e dos ângulos.
        cos_pitch = math.cos(self.pitch)
        sin_pitch = math.sin(self.pitch)
        sin_yaw = math.sin(self.yaw)
        cos_yaw = math.cos(self.yaw)
        offset = np.array(
            [
                cos_pitch * sin_yaw,
                sin_pitch,
                cos_pitch * cos_yaw,
            ],
            dtype=np.float32,
        )
        return self.target + offset * self.DEFAULT_DISTANCE
    # ------------------------------------------------------------------
    # Matrizes
    # ------------------------------------------------------------------
    def get_view_matrix(self) -> np.ndarray:
        #Calcula e retorna a View Matrix
        eye = self._camera_position()
        return mat4_look_at(
            eye=eye,
            target=self.target,
            up=vec3(0.0, 1.0, 0.0),
        )
    def get_projection_matrix(
        self,
        width: int,
        height: int,
    ) -> np.ndarray:
        #Calcula e retorna a Projection Matrix ortográfica.
        #O aspect ratio é aplicado apenas horizontalmente, preservando
        #a proporção dos objetos.
        if width <= 0 or height <= 0:
            raise ValueError(
                "width e height devem ser maiores que zero."
            )
        aspect = float(width) / float(height)
        vertical_size = self.ortho_size
        horizontal_size = vertical_size * aspect
        return mat4_ortho(
            -horizontal_size,
            horizontal_size,
            -vertical_size,
            vertical_size,
            self.near,
            self.far,
        )
    def get_model_matrix(self) -> np.ndarray:
        #Retorna a matriz de rotação do tabuleiro.
        #A rotação ocorre exclusivamente no eixo Y e em passos exatos
        #de 90 graus
        angle = math.radians(self.board_rotation)
        return mat4_rotate_y(angle)
    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------
    def zoom(self, amount: float) -> None:
        """
        Aplica zoom ortográfico.
        Args:
            amount:
                Valor positivo aproxima.
                Valor negativo afasta.
        """
        amount = float(amount)
        if amount == 0.0:
            return
        # Scroll positivo -> aproxima -> diminui ortho_size.
        scale = 1.0 - amount * self.ZOOM_FACTOR
        # Evita escala zero/negativa em entradas muito grandes.
        scale = max(scale, 0.05)
        self.ortho_size *= scale
        self.ortho_size = float(
            np.clip(
                self.ortho_size,
                self.MIN_ORTHO_SIZE,
                self.MAX_ORTHO_SIZE,
            )
        )
    def zoom_in(self, amount: float = 1.0) -> None:
        self.zoom(abs(float(amount)))
    def zoom_out(self, amount: float = 1.0) -> None:
        self.zoom(-abs(float(amount)))
    # ------------------------------------------------------------------
    # Pan
    # ------------------------------------------------------------------
    def pan(self, dx: float, dz: float) -> None:
        #Move diretamente o ponto focal no plano XZ.
        #Este método é útil para controles de teclado ou chamadas programáticas (dx e dy são deslocamentos)
        self.target[0] += float(dx)
        self.target[2] += float(dz)
    def pan_screen(
        self,
        dx: float,
        dy: float,
        sensitivity: float = 0.005,
    ) -> None:
        #Move o target de acordo com o movimento da tela.
        #O movimento é convertido para o plano XZ respeitando aorientação atual da câmera (dx e dy são deslocamentos)
        dx = float(dx)
        dy = float(dy)
        sensitivity = float(sensitivity)
        right = self._right_direction()
        forward = self._forward_direction()
        # Arrastar para a direita move o mundo para a direita,
        # portanto o target é deslocado para a esquerda.
        movement = (
            -right * dx
            + forward * dy
        ) * sensitivity * self.ortho_size
        self.target += movement
        # O pan da câmera ocorre somente no plano XZ.
        self.target[1] = 0.0
    # ------------------------------------------------------------------
    # Rotação do tabuleiro
    # ------------------------------------------------------------------
    def rotate_left(self) -> None:
        #Rotaciona o tabuleiro 90° para a esquerda
        self.board_rotation = (
            self.board_rotation - 90
        ) % 360
    def rotate_right(self) -> None:
        #Rotaciona o tabuleiro 90° para a direita
        self.board_rotation = (
            self.board_rotation + 90
        ) % 360
    def reset_rotation(self) -> None:
        #Retorna a rotação do tabuleiro para 0°
        self.board_rotation = 0
    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_scroll(
        self,
        x_offset: float,
        y_offset: float,
    ) -> None:
        #Processa evento da roda do mouse
        del x_offset

        if y_offset > 0.0:
            self.zoom_in(abs(y_offset))
        elif y_offset < 0.0:
            self.zoom_out(abs(y_offset))
    def handle_key(
        self,
        key: int,
        action: int,
    ) -> bool:
        #Processa Q/E. Returns: True se o evento foi consumido pela câmera.
        # GLFW usa 1 para PRESS e 2 para REPEAT.
        if action not in (1, 2):
            return False
        # GLFW_KEY_Q = 81
        if key == 81:
            self.rotate_left()
            return True
        # GLFW_KEY_E = 69
        if key == 69:
            self.rotate_right()
            return True
        return False
    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def get_target(self) -> np.ndarray:
        #Retorna uma cópia do ponto focal
        return self.target.copy()
    def set_target(
        self,
        x: float,
        y: float,
        z: float,
    ) -> None:
        #Define o ponto focal da câmera
        self.target[:] = (
            float(x),
            float(y),
            float(z),
        )
    def set_ortho_size(self, value: float) -> None:
        #Define diretamente o tamanho ortográfico
        if value <= 0.0:
            raise ValueError(
                "ortho_size deve ser maior que zero."
            )
        self.ortho_size = float(
            np.clip(
                value,
                self.MIN_ORTHO_SIZE,
                self.MAX_ORTHO_SIZE,
            )
        )
    def get_camera_state(self) -> Tuple[float, float, float, int]:
        #Retorna estado útil para debug/UI. Returns: (yaw_degrees, pitch_degrees, ortho_size, board_rotation)
        return (
            self.yaw_degrees,
            self.pitch_degrees,
            self.ortho_size,
            self.board_rotation,
        )
