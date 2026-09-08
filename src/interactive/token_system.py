"""Sistema de tokens e miniaturas para RPG de mesa no Isometricon."""

import math
from typing import Callable, Optional, Tuple

import numpy as np

from src.math import mat4_rotate_y, mat4_scale, mat4_translate, vec3
from src.rendering.mesh import TexturedMesh


def _build_cylinder(
    r_bottom: float,
    r_top: float,
    y_bottom: float,
    y_top: float,
    slices: int,
    color: Tuple[float, float, float],
    vertices_list: list,
    indices_list: list,
) -> None:
    """Helper para adicionar um cilindro/cone facetado na lista de vértices e índices."""
    start_index = len(vertices_list)
    r, g, b = color

    # Gera vértices superior e inferior para cada fatia
    for i in range(slices + 1):
        angle = (2.0 * math.pi * i) / slices
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        nx = cos_a
        nz = sin_a
        ny = 0.0

        # Vértice inferior
        vertices_list.append([
            r_bottom * cos_a, y_bottom, r_bottom * sin_a,
            nx, ny, nz,
            0.5, 0.5,
            r, g, b,
        ])
        # Vértice superior
        vertices_list.append([
            r_top * cos_a, y_top, r_top * sin_a,
            nx, ny, nz,
            0.5, 0.5,
            r, g, b,
        ])

    for i in range(slices):
        i0 = start_index + i * 2
        i1 = start_index + i * 2 + 1
        i2 = start_index + (i + 1) * 2
        i3 = start_index + (i + 1) * 2 + 1

        indices_list.extend([i0, i2, i1, i1, i2, i3])


def _build_disc(
    radius: float,
    y: float,
    slices: int,
    normal_y: float,
    color: Tuple[float, float, float],
    vertices_list: list,
    indices_list: list,
) -> None:
    """Helper para fechar tampa circular superior ou inferior."""
    center_idx = len(vertices_list)
    r, g, b = color
    ny = 1.0 if normal_y > 0 else -1.0

    vertices_list.append([
        0.0, y, 0.0,
        0.0, ny, 0.0,
        0.5, 0.5,
        r, g, b,
    ])

    start_perimeter = len(vertices_list)
    for i in range(slices + 1):
        angle = (2.0 * math.pi * i) / slices
        vertices_list.append([
            radius * math.cos(angle), y, radius * math.sin(angle),
            0.0, ny, 0.0,
            0.5, 0.5,
            r, g, b,
        ])

    for i in range(slices):
        p0 = start_perimeter + i
        p1 = start_perimeter + i + 1
        if ny > 0:
            indices_list.extend([center_idx, p0, p1])
        else:
            indices_list.extend([center_idx, p1, p0])


def create_token_mesh() -> TexturedMesh:
    """Cria a malha procedural de uma miniatura 3D de RPG (pawn de herói).

    Estrutura:
    - Base sólida de ardósia escura (pedestal de mesa)
    - Anel ornamental dourado de realce
    - Tronco/Capa heroica escarlate
    - Capacete metálico prateado
    - Viseira frontal ciano luminoso (indica direção do olhar)
    """
    v_data: list[list[float]] = []
    i_data: list[int] = []
    slices = 16

    # 1. Base / Pedestal (r=0.36, y de 0.0 a 0.12) - Ardósia
    slate_color = (0.22, 0.24, 0.28)
    _build_disc(0.36, 0.0, slices, -1.0, slate_color, v_data, i_data)
    _build_cylinder(0.36, 0.36, 0.0, 0.12, slices, slate_color, v_data, i_data)

    # 2. Anel de destaque dourado (r=0.34, y de 0.12 a 0.16) - Ouro
    gold_color = (0.95, 0.78, 0.18)
    _build_cylinder(0.34, 0.34, 0.12, 0.16, slices, gold_color, v_data, i_data)
    _build_disc(0.34, 0.16, slices, 1.0, gold_color, v_data, i_data)

    # 3. Corpo / Capa (r_bottom=0.24, r_top=0.14, y de 0.16 a 0.68) - Vermelho Heróico
    tunic_color = (0.85, 0.18, 0.20)
    _build_cylinder(0.24, 0.14, 0.16, 0.68, slices, tunic_color, v_data, i_data)

    # 4. Cabeça / Capacete (r=0.16, y de 0.68 a 0.98) - Prata Metálica
    steel_color = (0.75, 0.78, 0.86)
    _build_cylinder(0.14, 0.16, 0.68, 0.84, slices, steel_color, v_data, i_data)
    _build_cylinder(0.16, 0.10, 0.84, 0.98, slices, steel_color, v_data, i_data)
    _build_disc(0.10, 0.98, slices, 1.0, steel_color, v_data, i_data)

    # 5. Viseira frontal indicando o olhar (+Z) - Ciano Brilhante
    visor_color = (0.15, 0.90, 0.95)
    visor_idx = len(v_data)
    v_data.extend([
        # Face frontal retangular (+Z)
        [-0.08, 0.82, 0.17,  0.0, 0.0, 1.0,  0.5, 0.5,  *visor_color],
        [ 0.08, 0.82, 0.17,  0.0, 0.0, 1.0,  0.5, 0.5,  *visor_color],
        [ 0.08, 0.90, 0.17,  0.0, 0.0, 1.0,  0.5, 0.5,  *visor_color],
        [-0.08, 0.90, 0.17,  0.0, 0.0, 1.0,  0.5, 0.5,  *visor_color],
    ])
    i_data.extend([
        visor_idx, visor_idx + 1, visor_idx + 2,
        visor_idx + 2, visor_idx + 3, visor_idx,
    ])

    vertices_arr = np.array(v_data, dtype=np.float32)
    indices_arr = np.array(i_data, dtype=np.uint32)

    return TexturedMesh(vertices_arr, indices_arr)


class PlayerToken:
    """Controlador de miniatura 3D com movimentação contínua estilo RPG e aderência ao relevo."""

    def __init__(
        self,
        start_x: float = 0.5,
        start_z: float = 0.5,
        speed: float = 5.0,
        create_mesh: bool = True,
    ) -> None:
        self.position = np.array([start_x, 10.0, start_z], dtype=np.float32)
        self.yaw: float = 0.0
        self.speed: float = speed
        self.is_moving: bool = False
        self.mesh: Optional[TexturedMesh] = create_token_mesh() if create_mesh else None


    def update(
        self,
        dt: float,
        keys_pressed: dict[int, bool],
        forward_dir: np.ndarray,
        right_dir: np.ndarray,
        terrain_height_func: Callable[[float, float], int],
    ) -> None:
        """Atualiza a posição do token com WASD, rotação suave e altura do terreno."""
        import glfw

        move_vec = np.zeros(3, dtype=np.float32)
        if keys_pressed.get(glfw.KEY_W, False):
            move_vec += forward_dir
        if keys_pressed.get(glfw.KEY_S, False):
            move_vec -= forward_dir
        if keys_pressed.get(glfw.KEY_D, False):
            move_vec += right_dir
        if keys_pressed.get(glfw.KEY_A, False):
            move_vec -= right_dir

        # Ignora componente vertical para o vetor de deslocamento
        move_vec[1] = 0.0
        length = float(np.linalg.norm(move_vec))

        if length > 1e-4:
            self.is_moving = True
            norm_move = move_vec / length
            self.position[0] += norm_move[0] * self.speed * dt
            self.position[2] += norm_move[2] * self.speed * dt

            # Alinha o olhar da miniatura na direção em que ela caminha
            target_yaw = math.atan2(norm_move[0], norm_move[2])
            angle_diff = (target_yaw - self.yaw + math.pi) % (2.0 * math.pi) - math.pi
            self.yaw += angle_diff * min(dt * 14.0, 1.0)
        else:
            self.is_moving = False

        # Consulta altura da superfície sólida abaixo da miniatura
        surface_y = terrain_height_func(self.position[0], self.position[2])
        # A base do token deve descansar no topo do bloco (surface_y + 1.0)
        target_y = float(surface_y) + 1.0

        # Interpolação suave para subir/descer colinas e degraus
        self.position[1] += (target_y - self.position[1]) * min(dt * 18.0, 1.0)

    def get_current_block(self) -> Tuple[int, int, int]:
        """Retorna a coordenada inteira (X, Y, Z) do bloco sobre o qual o token está pisando."""
        bx = int(math.floor(self.position[0]))
        bz = int(math.floor(self.position[2]))
        by = int(round(self.position[1] - 1.0))
        return bx, by, bz

    def get_model_matrix(self) -> np.ndarray:
        """Gera a matriz Model (Transformação) para renderizar a miniatura."""
        return mat4_translate(self.position[0], self.position[1], self.position[2]) @ mat4_rotate_y(self.yaw)

    def draw(self) -> None:
        """Desenha a malha da miniatura."""
        if self.mesh is not None:
            self.mesh.draw()

    def delete(self) -> None:
        """Libera os buffers OpenGL."""
        if self.mesh is not None:
            self.mesh.delete()
            self.mesh = None
