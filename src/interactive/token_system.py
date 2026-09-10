"""Sistema de tokens e miniaturas para RPG de mesa no Isometricon."""

import json
import math
import os
from typing import Any, Callable, Optional, Tuple

import numpy as np

from src.math import (
    mat4_identity,
    mat4_rotate_x,
    mat4_rotate_y,
    mat4_rotate_z,
    mat4_scale,
    mat4_translate,
    vec3,
)
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

        # Enrolamento CCW voltado para fora do cilindro (Front Face)
        indices_list.extend([i0, i1, i2, i1, i3, i2])


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
        # Enrolamento CCW correto: visto de cima para ny>0, visto de baixo para ny<0
        if ny > 0:
            indices_list.extend([center_idx, p1, p0])
        else:
            indices_list.extend([center_idx, p0, p1])


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

    # 1. Base / Pedestal (r=0.36, y de 0.005 a 0.12) - Ardósia sólida e fechada
    slate_color = (0.22, 0.24, 0.28)
    _build_disc(0.36, 0.005, slices, -1.0, slate_color, v_data, i_data)
    _build_cylinder(0.36, 0.36, 0.005, 0.12, slices, slate_color, v_data, i_data)
    _build_disc(0.36, 0.12, slices, 1.0, slate_color, v_data, i_data)

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


class CharacterPart:
    """Representa uma peça anatômica individual com pivot e matriz hierárquica Forward Kinematics."""

    def __init__(
        self,
        name: str,
        parent_name: Optional[str],
        pivot: np.ndarray,
        mesh: Optional[TexturedMesh],
    ) -> None:
        self.name = name
        self.parent_name = parent_name
        self.pivot = np.ascontiguousarray(pivot, dtype=np.float32)
        self.mesh = mesh
        # [pitch (X), yaw (Y), roll (Z)] em radianos
        self.local_rot = np.zeros(3, dtype=np.float32)
        # [dx, dy, dz] deslocamento local em relação ao pivot
        self.local_offset = np.zeros(3, dtype=np.float32)
        self.world_matrix = np.eye(4, dtype=np.float32)

    def delete(self) -> None:
        if self.mesh is not None:
            self.mesh.delete()
            self.mesh = None


class ModularCharacter:
    """Gerencia a hierarquia Forward Kinematics (FK) e animação procedural de caminhada."""

    def __init__(self, json_path: str, create_mesh: bool = True) -> None:
        self.parts: dict[str, CharacterPart] = {}
        self.topological_order: list[str] = []
        self.idle_time: float = 0.0

        if not os.path.exists(json_path):
            return

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        parent_map = {k: data[k]["parent"] for k in data}

        # Ordenação topológica (garante que os nós-pai sejam processados antes dos filhos)
        visited: set[str] = set()
        ordered: list[str] = []

        def visit(node: Optional[str]) -> None:
            if node is None or node in visited or node not in parent_map:
                return
            p = parent_map.get(node)
            if p and p not in visited:
                visit(p)
            visited.add(node)
            ordered.append(node)

        for name in data:
            visit(name)

        self.topological_order = ordered

        # Calibra o offset vertical para a sola dos sapatos tocar exatamente Y=0.0
        min_foot_y = 0.0
        for name in ["pe esquerdo", "pe direito"]:
            if name in data:
                p_y = data[name]["pivot"][1]
                v_ys = [v[1] + p_y for v in data[name]["vertices"]]
                if v_ys:
                    min_foot_y = min(min_foot_y, min(v_ys))
        base_y_shift = -min_foot_y if min_foot_y < 0 else 0.0

        for name in self.topological_order:
            part_info = data[name]
            pivot = np.array(part_info["pivot"], dtype=np.float32)
            pivot[1] += base_y_shift

            mesh = None
            if create_mesh:
                v_arr = np.array(part_info["vertices"], dtype=np.float32)
                i_arr = np.array(part_info["indices"], dtype=np.uint32)
                mesh = TexturedMesh(v_arr, i_arr)

            self.parts[name] = CharacterPart(
                name=name,
                parent_name=part_info["parent"],
                pivot=pivot,
                mesh=mesh,
            )

        self.evaluate_fk()

    def evaluate_fk(self) -> None:
        """Avalia a árvore de transformações hierárquicas."""
        for name in self.topological_order:
            part = self.parts[name]
            rot_mat = (
                mat4_rotate_y(part.local_rot[1])
                @ mat4_rotate_x(part.local_rot[0])
                @ mat4_rotate_z(part.local_rot[2])
            )
            if part.parent_name is None or part.parent_name not in self.parts:
                # Raiz (pelve)
                trans = mat4_translate(
                    part.pivot[0] + part.local_offset[0],
                    part.pivot[1] + part.local_offset[1],
                    part.pivot[2] + part.local_offset[2],
                )
                part.world_matrix = trans @ rot_mat
            else:
                parent = self.parts[part.parent_name]
                rel_pivot = part.pivot - parent.pivot
                trans = mat4_translate(
                    rel_pivot[0] + part.local_offset[0],
                    rel_pivot[1] + part.local_offset[1],
                    rel_pivot[2] + part.local_offset[2],
                )
                part.world_matrix = parent.world_matrix @ trans @ rot_mat

    def _blend_rot(self, name: str, axis: int, target: float, factor: float) -> None:
        if name in self.parts:
            curr = self.parts[name].local_rot[axis]
            self.parts[name].local_rot[axis] += (target - curr) * factor

    def _compute_leg_angles(self, phase: float) -> Tuple[float, float, float]:
        """Calcula (hip_pitch, knee_pitch, foot_pitch) em radianos para o ciclo de passada completo.

        Convenção OpenGL Isometricon (mat4_rotate_x):
        - Ângulo negativo: gira para frente (+Z)
        - Ângulo positivo: gira para trás (-Z)
        """
        phi = phase % (2.0 * math.pi)
        # Avanço do quadril: no início do ciclo (phi=0), a perna está estendida à frente (-26 graus -> +Z)
        hip = -math.cos(phi) * math.radians(26.0)

        if phi < math.pi:
            # Fase de apoio (Stance): pé no solo empurrando o corpo para trás (+Z para -Z)
            # Leve amortecimento do joelho para trás (ângulo positivo)
            cushion = math.sin(phi) * math.radians(8.0)
            knee = cushion
            foot = -math.sin(phi - math.pi / 4.0) * math.radians(8.0)
        else:
            # Fase de oscilação (Swing): pé no ar avançando de trás para frente (-Z para +Z)
            s = (phi - math.pi) / math.pi
            # Flexão profunda do joelho para trás (ângulo positivo de até 48 graus)
            knee = math.sin(s * math.pi) * math.radians(48.0)
            # Tornozelo aponta levemente para cima para não arrastar no chão
            foot = -math.sin(s * math.pi) * math.radians(10.0)

        return hip, knee, foot

    def update_animation(self, dt: float, is_moving: bool, walk_time: float) -> None:
        """Atualiza a rotação dos membros para a caminhada natural ou postura em repouso."""
        if is_moving:
            # Perna esquerda e perna direita em oposição de fase (defasadas por PI)
            hip_L, knee_L, foot_L = self._compute_leg_angles(walk_time)
            hip_R, knee_R, foot_R = self._compute_leg_angles(walk_time + math.pi)

            # Braços balançam em oposição às pernas
            arm_amp = math.radians(24.0)
            forearm_amp = math.radians(26.0)
            base_elbow = math.radians(6.0)

            # Perna esquerda avança (hip_L < 0) -> Braço esquerdo recua (target_arm_L > 0)
            target_arm_L = math.cos(walk_time) * arm_amp
            target_arm_R = -math.cos(walk_time) * arm_amp

            # Cotovelos flexionam para frente (ângulo negativo) quando o braço avança
            target_forearm_L = -max(0.0, -target_arm_L) * (forearm_amp / arm_amp) - base_elbow
            target_forearm_R = -max(0.0, -target_arm_R) * (forearm_amp / arm_amp) - base_elbow

            # Pelvis bounce vertical (passada saltitante em cada passo)
            target_bounce = abs(math.sin(walk_time)) * 0.04
            # Torso: leve rotação em yaw acompanhando o balanço dos ombros
            target_torso_yaw = -math.cos(walk_time) * math.radians(4.0)
            target_head_pitch = math.sin(walk_time * 2.0) * math.radians(1.5)
        else:
            hip_L, knee_L, foot_L = 0.0, 0.0, 0.0
            hip_R, knee_R, foot_R = 0.0, 0.0, 0.0
            target_arm_L, target_arm_R = 0.0, 0.0
            target_forearm_L = -math.radians(5.0)
            target_forearm_R = -math.radians(5.0)

            self.idle_time += dt * 2.5
            target_bounce = math.sin(self.idle_time) * 0.005
            target_torso_yaw = 0.0
            target_head_pitch = math.sin(self.idle_time) * math.radians(1.0)

        blend_speed = min(dt * 16.0, 1.0)
        self._blend_rot("coxa esquerda", 0, hip_L, blend_speed)
        self._blend_rot("canela esquerda", 0, knee_L, blend_speed)
        self._blend_rot("pe esquerdo", 0, foot_L, blend_speed)

        self._blend_rot("coxa direita", 0, hip_R, blend_speed)
        self._blend_rot("canela direita", 0, knee_R, blend_speed)
        self._blend_rot("pe direito", 0, foot_R, blend_speed)

        self._blend_rot("braco superior esquerdo", 0, target_arm_L, blend_speed)
        self._blend_rot("braco superior direito", 0, target_arm_R, blend_speed)
        self._blend_rot("antebraco esquerdo", 0, target_forearm_L, blend_speed)
        self._blend_rot("antebraco direito", 0, target_forearm_R, blend_speed)

        self._blend_rot("torso", 1, target_torso_yaw, blend_speed)
        self._blend_rot("cabeca", 0, target_head_pitch, blend_speed)

        if "pelve" in self.parts:
            curr_y = self.parts["pelve"].local_offset[1]
            self.parts["pelve"].local_offset[1] += (target_bounce - curr_y) * blend_speed

        self.evaluate_fk()

    def draw(self, shader: Any, base_matrix: np.ndarray) -> None:
        """Renderiza cada peça com sua matriz hierárquica correspondente."""
        for name in self.topological_order:
            part = self.parts[name]
            if part.mesh is not None:
                part_model = base_matrix @ part.world_matrix
                shader.set_mat4("u_Model", part_model)
                part.mesh.draw()

    def delete(self) -> None:
        for part in self.parts.values():
            part.delete()
        self.parts.clear()


class PlayerToken:
    """Controlador de miniatura 3D com movimentação contínua estilo RPG e animação modular procedural."""

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
        self.walk_time: float = 0.0

        json_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets", "models", "character_modular.json"
        )
        if create_mesh and os.path.exists(json_path):
            self.modular_character: Optional[ModularCharacter] = ModularCharacter(json_path, create_mesh=True)
            self.mesh: Optional[TexturedMesh] = None
        else:
            self.modular_character = None
            self.mesh: Optional[TexturedMesh] = create_token_mesh() if create_mesh else None

    def update(
        self,
        dt: float,
        keys_pressed: dict[int, bool],
        forward_dir: np.ndarray,
        right_dir: np.ndarray,
        terrain_height_func: Callable[[float, float], int],
    ) -> None:
        """Atualiza a posição do token com WASD, rotação suave, altura do terreno e animação."""
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

            # Avança o acumulador do ciclo de passos proporcional à velocidade
            self.walk_time += dt * (self.speed * 2.2)
        else:
            self.is_moving = False

        # Consulta altura da superfície sólida abaixo da miniatura
        surface_y = terrain_height_func(self.position[0], self.position[2])
        self.current_surface_y = int(surface_y)
        # A base do token deve descansar no topo do bloco (surface_y + 1.0)
        target_y = float(surface_y) + 1.0

        # Interpolação suave para subir/descer colinas e degraus
        self.position[1] += (target_y - self.position[1]) * min(dt * 18.0, 1.0)

        # Atualiza a animação procedural modular
        if self.modular_character is not None:
            self.modular_character.update_animation(dt, self.is_moving, self.walk_time)

    def get_current_block(self) -> Tuple[int, int, int]:
        """Retorna a coordenada inteira (X, Y, Z) do bloco sobre o qual o token está pisando."""
        bx = int(math.floor(self.position[0]))
        bz = int(math.floor(self.position[2]))
        by = getattr(self, "current_surface_y", int(round(self.position[1] - 1.0)))
        return bx, by, bz

    def get_model_matrix(self) -> np.ndarray:
        """Gera a matriz Model (Transformação) para renderizar a miniatura."""
        return mat4_translate(self.position[0], self.position[1], self.position[2]) @ mat4_rotate_y(self.yaw)

    def draw(self, shader: Any = None, base_model: Optional[np.ndarray] = None) -> None:
        """Desenha a miniatura (modular se disponível, ou malha única)."""
        import OpenGL.GL as gl
        gl.glDisable(gl.GL_CULL_FACE)
        if self.modular_character is not None and shader is not None:
            mat = base_model if base_model is not None else self.get_model_matrix()
            self.modular_character.draw(shader, mat)
        elif self.mesh is not None:
            self.mesh.draw()
        gl.glEnable(gl.GL_CULL_FACE)

    def delete(self) -> None:
        """Libera os buffers OpenGL."""
        if self.modular_character is not None:
            self.modular_character.delete()
            self.modular_character = None
        if self.mesh is not None:
            self.mesh.delete()
            self.mesh = None
