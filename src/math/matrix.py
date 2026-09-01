"""Módulo de álgebra linear e matrizes 4x4 em NumPy para OpenGL 3.3 Core."""

from typing import Sequence
import numpy as np

from src.math.vector import cross, dot, normalize, vec3


def mat4_identity() -> np.ndarray:
    """Retorna uma matriz identidade 4x4 do tipo float32 contígua."""
    return np.identity(4, dtype=np.float32)


def mat4_translate(tx: float, ty: float, tz: float) -> np.ndarray:
    """Cria uma matriz de translação 4x4.

    Args:
        tx: Deslocamento no eixo X.
        ty: Deslocamento no eixo Y.
        tz: Deslocamento no eixo Z.

    Returns:
        Matriz 4x4 np.float32 com a translação aplicada.
    """
    m = np.identity(4, dtype=np.float32)
    m[0, 3] = float(tx)
    m[1, 3] = float(ty)
    m[2, 3] = float(tz)
    return np.ascontiguousarray(m, dtype=np.float32)


def mat4_scale(sx: float, sy: float, sz: float) -> np.ndarray:
    """Cria uma matriz de escala 4x4.

    Args:
        sx: Fator de escala no eixo X.
        sy: Fator de escala no eixo Y.
        sz: Fator de escala no eixo Z.

    Returns:
        Matriz 4x4 np.float32 com a escala aplicada.
    """
    m = np.identity(4, dtype=np.float32)
    m[0, 0] = float(sx)
    m[1, 1] = float(sy)
    m[2, 2] = float(sz)
    return np.ascontiguousarray(m, dtype=np.float32)


def mat4_rotate_x(angle_rad: float) -> np.ndarray:
    """Cria uma matriz de rotação 4x4 em torno do eixo X.

    Args:
        angle_rad: Ângulo de rotação em radianos.

    Returns:
        Matriz 4x4 np.float32 com a rotação aplicada.
    """
    c = float(np.cos(angle_rad))
    s = float(np.sin(angle_rad))
    return np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, c, -s, 0.0],
            [0.0, s, c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def mat4_rotate_y(angle_rad: float) -> np.ndarray:
    """Cria uma matriz de rotação 4x4 em torno do eixo Y.

    Args:
        angle_rad: Ângulo de rotação em radianos.

    Returns:
        Matriz 4x4 np.float32 com a rotação aplicada.
    """
    c = float(np.cos(angle_rad))
    s = float(np.sin(angle_rad))
    return np.array(
        [
            [c, 0.0, s, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [-s, 0.0, c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def mat4_rotate_z(angle_rad: float) -> np.ndarray:
    """Cria uma matriz de rotação 4x4 em torno do eixo Z.

    Args:
        angle_rad: Ângulo de rotação em radianos.

    Returns:
        Matriz 4x4 np.float32 com a rotação aplicada.
    """
    c = float(np.cos(angle_rad))
    s = float(np.sin(angle_rad))
    return np.array(
        [
            [c, -s, 0.0, 0.0],
            [s, c, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def mat4_rotate(angle_rad: float, axis: np.ndarray) -> np.ndarray:
    """Cria uma matriz de rotação 4x4 em torno de um eixo 3D arbitrário (Fórmula de Rodrigues).

    Args:
        angle_rad: Ângulo de rotação em radianos.
        axis: Vetor de 3 elementos representando o eixo de rotação.

    Returns:
        Matriz 4x4 np.float32.
    """
    norm_axis = normalize(np.asarray(axis, dtype=np.float32))
    x, y, z = norm_axis[0], norm_axis[1], norm_axis[2]
    c = float(np.cos(angle_rad))
    s = float(np.sin(angle_rad))
    t = 1.0 - c

    return np.array(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0.0],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0.0],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def mat4_look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Cria a matriz de visão (View Matrix) padrão do OpenGL (Right-Handed).

    Args:
        eye: Posição da câmera no espaço de mundo (vec3).
        target: Ponto para onde a câmera está olhando (vec3).
        up: Vetor que indica a direção para cima (vec3).

    Returns:
        Matriz 4x4 np.float32 de Visão.
    """
    eye_vec = np.asarray(eye, dtype=np.float32)
    target_vec = np.asarray(target, dtype=np.float32)
    up_vec = np.asarray(up, dtype=np.float32)

    # Vetor de direção da visão (forward)
    forward = normalize(target_vec - eye_vec)
    # Vetor perpendicular à direita (side)
    side = normalize(cross(forward, up_vec))
    # Vetor recalculado para cima (verdadeiro up)
    true_up = cross(side, forward)

    m = np.identity(4, dtype=np.float32)
    m[0, 0:3] = side
    m[1, 0:3] = true_up
    m[2, 0:3] = -forward

    m[0, 3] = -dot(side, eye_vec)
    m[1, 3] = -dot(true_up, eye_vec)
    m[2, 3] = dot(forward, eye_vec)

    return np.ascontiguousarray(m, dtype=np.float32)


def mat4_ortho(
    left: float,
    right: float,
    bottom: float,
    top: float,
    near: float,
    far: float,
) -> np.ndarray:
    """Cria a matriz de Projeção Ortográfica (Orthographic Projection) para OpenGL.

    Mapeia a caixa delimitadora [left, right] x [bottom, top] x [-near, -far]
    no cubo canônico NDC [-1, 1]^3.

    Args:
        left: Limite esquerdo do frustum.
        right: Limite direito do frustum.
        bottom: Limite inferior do frustum.
        top: Limite superior do frustum.
        near: Distância do plano de corte próximo (near plane).
        far: Distância do plano de corte distante (far plane).

    Returns:
        Matriz 4x4 np.float32 de Projeção Ortográfica.
    """
    rl = float(right - left)
    tb = float(top - bottom)
    fn = float(far - near)

    if rl == 0.0 or tb == 0.0 or fn == 0.0:
        raise ValueError("Dimensões do frustum ortográfico não podem ser zero.")

    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 2.0 / rl
    m[1, 1] = 2.0 / tb
    m[2, 2] = -2.0 / fn
    m[3, 3] = 1.0

    m[0, 3] = -(right + left) / rl
    m[1, 3] = -(top + bottom) / tb
    m[2, 3] = -(far + near) / fn

    return np.ascontiguousarray(m, dtype=np.float32)


def mat4_perspective(
    fovy_rad: float,
    aspect: float,
    near: float,
    far: float,
) -> np.ndarray:
    """Cria a matriz de Projeção em Perspectiva (Perspective Projection) para OpenGL.

    Args:
        fovy_rad: Campo de visão vertical em radianos.
        aspect: Razão de aspecto da viewport (largura / altura).
        near: Distância do plano de corte próximo (> 0).
        far: Distância do plano de corte distante (> near).

    Returns:
        Matriz 4x4 np.float32 de Projeção em Perspectiva.
    """
    if near <= 0.0 or far <= near or aspect <= 0.0:
        raise ValueError("Parâmetros de projeção em perspectiva inválidos.")

    tan_half_fovy = float(np.tan(fovy_rad / 2.0))
    if tan_half_fovy == 0.0:
        raise ValueError("Campo de visão (fovy) não pode ser zero.")

    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 1.0 / (aspect * tan_half_fovy)
    m[1, 1] = 1.0 / tan_half_fovy
    m[2, 2] = -(far + near) / (far - near)
    m[2, 3] = -(2.0 * far * near) / (far - near)
    m[3, 2] = -1.0

    return np.ascontiguousarray(m, dtype=np.float32)


def mat4_inverse(matrix: np.ndarray) -> np.ndarray:
    """Calcula a inversa de uma matriz 4x4.

    Args:
        matrix: Matriz 4x4.

    Returns:
        Matriz 4x4 inversa em np.float32.
    """
    inv = np.linalg.inv(matrix)
    return np.ascontiguousarray(inv, dtype=np.float32)


def mat4_multiply(*matrices: np.ndarray) -> np.ndarray:
    """Multiplica sequencialmente uma lista de matrizes 4x4 (M1 @ M2 @ ... @ Mn).

    Args:
        matrices: Duas ou mais matrizes 4x4.

    Returns:
        Resultado da multiplicação matricial em np.float32 contíguo.
    """
    if not matrices:
        return mat4_identity()

    res = np.asarray(matrices[0], dtype=np.float32)
    for m in matrices[1:]:
        res = res @ np.asarray(m, dtype=np.float32)

    return np.ascontiguousarray(res, dtype=np.float32)


def transform_point(matrix: np.ndarray, point: np.ndarray) -> np.ndarray:
    """Aplica transformação linear e translação a um ponto 3D com divisão de perspectiva.

    Args:
        matrix: Matriz 4x4 de transformação.
        point: Vetor 3D [x, y, z].

    Returns:
        Vetor 3D resultante [x', y', z'] em np.float32.
    """
    p4 = np.array([point[0], point[1], point[2], 1.0], dtype=np.float32)
    res4 = matrix @ p4
    w = res4[3]
    if w != 0.0 and w != 1.0:
        return (res4[:3] / w).astype(np.float32)
    return res4[:3].astype(np.float32)


def transform_vector(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    """Aplica transformação linear a um vetor 3D de direção (sem translação).

    Args:
        matrix: Matriz 4x4 de transformação.
        vector: Vetor 3D [x, y, z].

    Returns:
        Vetor 3D resultante [x', y', z'] em np.float32.
    """
    v4 = np.array([vector[0], vector[1], vector[2], 0.0], dtype=np.float32)
    res4 = matrix @ v4
    return res4[:3].astype(np.float32)
