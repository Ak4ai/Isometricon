"""Módulo de operações com vetores usando NumPy."""

import numpy as np


def vec2(x: float = 0.0, y: float = 0.0) -> np.ndarray:
    """Cria um vetor 2D a partir de coordenadas x e y."""
    return np.array([x, y], dtype=np.float32)


def vec3(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> np.ndarray:
    """Cria um vetor 3D a partir de coordenadas x, y e z."""
    return np.array([x, y, z], dtype=np.float32)


def vec4(x: float = 0.0, y: float = 0.0, z: float = 0.0, w: float = 1.0) -> np.ndarray:
    """Cria um vetor 4D homogêneo a partir de coordenadas x, y, z e w."""
    return np.array([x, y, z, w], dtype=np.float32)


def length(v: np.ndarray) -> float:
    """Calcula o comprimento (magnitude euclidiana) de um vetor."""
    return float(np.linalg.norm(v))


def distance(u: np.ndarray, v: np.ndarray) -> float:
    """Calcula a distância euclidiana entre dois pontos."""
    return float(np.linalg.norm(u - v))


def normalize(v: np.ndarray) -> np.ndarray:
    """Normaliza um vetor para comprimento unitário."""
    norm = float(np.linalg.norm(v))
    if norm == 0.0:
        return np.asarray(v, dtype=np.float32)
    return (v / norm).astype(np.float32)


def dot(u: np.ndarray, v: np.ndarray) -> float:
    """Calcula o produto escalar entre dois vetores."""
    return float(np.dot(u, v))


def cross(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Calcula o produto vetorial entre dois vetores 3D."""
    return np.cross(u, v).astype(np.float32)