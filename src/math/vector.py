"""Modulo de operações com vetores 3D usando NumPy."""
import numpy as np

def vec3(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> np.ndarray:
    """Cria um vetor 3D a partir de coordenadas x, y e z."""
    return np.array([x, y, z], dtype=np.float32)

def normalize(v: np.ndarray) -> np.ndarray:
    """Normaliza um vetor 3D."""
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return (v / norm).astype(np.float32)

def dot(u: np.ndarray, v: np.ndarray) -> float:
    """Calcula o produto escalar entre dois vetores 3D."""
    return float(np.dot(u, v))
                 
def cross(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Calcula o produto vetorial entre dois vetores 3D."""
    return np.cross(u, v).astype(np.float32)