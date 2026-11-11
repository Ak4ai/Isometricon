"""Leitor de modelos glTF 2.0 (.glb, e .gltf com tudo embutido), sem OpenGL e sem biblioteca de fora.

Devolve a malha pronta para o jogo: por material, vértices de 11 floats (posição, normal, UV, cor) como a
``TexturedMesh``, os índices e a imagem da textura. Sem esqueleto ainda: o modelo sai na pose de montagem, com a
transformação dos nós já aplicada (ver ``skins`` em ``GlbModel`` para a fase seguinte).

Como o arquivo vem de fora, o leitor tem limites (tamanho, triângulos, textura) e recusa ``uri`` que aponte para
outro arquivo: só lê o que está dentro do próprio arquivo.
"""

from __future__ import annotations

import base64
import io
import json
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TRIANGLES = 300_000
MAX_TEXTURE_SIDE = 4096
FLOATS_PER_VERTEX = 11  # posição(3), normal(3), uv(2), cor(3)

_GLB_MAGIC = 0x46546C67  # "glTF"
_CHUNK_JSON = 0x4E4F534A
_CHUNK_BIN = 0x004E4942
_COMPONENT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NORMALIZER = {np.int8: 127.0, np.uint8: 255.0, np.int16: 32767.0, np.uint16: 65535.0}
_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


class ModelError(ValueError):
    """O arquivo não pôde ser lido como um modelo (formato, limite ou dado inválido)."""


@dataclass
class Submesh:
    """Uma parte do modelo com um só material."""

    name: str
    vertices: np.ndarray                  # (N, 11) float32
    indices: np.ndarray                   # (M,) uint32
    image: Optional[object] = None        # PIL.Image RGBA da textura de cor, se há
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)   # fator de cor do material
    double_sided: bool = False
    alpha_mode: str = "OPAQUE"

    @property
    def triangles(self) -> int:
        return len(self.indices) // 3


@dataclass
class GlbModel:
    """O modelo lido: as partes e quem mais o arquivo trouxe (para as fases seguintes)."""

    submeshes: List[Submesh] = field(default_factory=list)
    skins: int = 0              # quantos esqueletos o arquivo tem (ainda não usados)
    animations: List[str] = field(default_factory=list)   # nomes dos clipes (ainda não usados)
    warnings: List[str] = field(default_factory=list)

    @property
    def triangles(self) -> int:
        return sum(s.triangles for s in self.submeshes)

    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Os cantos mínimo e máximo da caixa que envolve o modelo."""
        points = np.concatenate([s.vertices[:, :3] for s in self.submeshes]) if self.submeshes else np.zeros((1, 3))
        return points.min(axis=0), points.max(axis=0)

    def normalize(self, height: float = 1.8, yaw_turns: int = 0) -> "GlbModel":
        """Põe os pés em y = 0, centra em x e z e escala para ``height`` de altura (o jogo usa metros).

        ``yaw_turns``: quartos de volta em y, para modelos que olham para outro lado que +z.
        """
        if not self.submeshes:
            return self
        for _ in range(yaw_turns % 4):
            for s in self.submeshes:
                v = s.vertices
                v[:, [0, 2]] = np.stack([v[:, 2], -v[:, 0]], axis=1)        # gira 90° em y
                v[:, [3, 5]] = np.stack([v[:, 5], -v[:, 3]], axis=1)
        low, high = self.bounds()
        size = float(high[1] - low[1])
        if size <= 1e-9:
            raise ModelError("O modelo não tem altura.")
        scale = height / size
        centre = np.array([(low[0] + high[0]) / 2.0, low[1], (low[2] + high[2]) / 2.0])
        for s in self.submeshes:
            s.vertices[:, :3] = (s.vertices[:, :3] - centre) * scale
        return self


# ------------------------------------------------------------------------------------------------ arquivo
def load_model(path: str) -> GlbModel:
    """Lê um ``.glb`` (ou um ``.gltf`` sem arquivos externos) do disco."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except OSError as error:
        raise ModelError(f"Não consegui abrir o arquivo: {error}") from error
    if len(data) > MAX_FILE_BYTES:
        raise ModelError(f"O arquivo passa de {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    return parse_model(data)


def parse_model(data: bytes) -> GlbModel:
    """Lê o conteúdo de um ``.glb`` ou de um ``.gltf`` (texto JSON com os dados embutidos)."""
    if data[:4] == b"glTF":
        document, blob = _split_glb(data)
    else:
        try:
            document, blob = json.loads(data.decode("utf-8")), None
        except (UnicodeDecodeError, ValueError) as error:
            raise ModelError("Não é um arquivo glTF (.glb ou .gltf).") from error
    if not isinstance(document, dict) or str(document.get("asset", {}).get("version", "")).split(".")[0] != "2":
        raise ModelError("Só o glTF 2.0 é aceito.")
    return _Reader(document, blob).read()


def _split_glb(data: bytes):
    if len(data) < 20:
        raise ModelError("O arquivo .glb está incompleto.")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC or version != 2:
        raise ModelError("Não é um .glb da versão 2.")
    document, blob, offset = None, None, 12
    while offset + 8 <= min(length, len(data)):
        size, kind = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8: offset + 8 + size]
        if len(chunk) < size:
            raise ModelError("O arquivo .glb está cortado.")
        if kind == _CHUNK_JSON and document is None:
            try:
                document = json.loads(chunk.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as error:
                raise ModelError("O JSON do .glb é inválido.") from error
        elif kind == _CHUNK_BIN and blob is None:
            blob = chunk
        offset += 8 + size + (-size) % 4
    if document is None:
        raise ModelError("O .glb não tem o bloco de descrição.")
    return document, blob


# ------------------------------------------------------------------------------------------------ leitor
class _Reader:
    def __init__(self, document: dict, blob: Optional[bytes]) -> None:
        self.doc = document
        self.blob = blob
        self.model = GlbModel()
        self._buffers: Dict[int, bytes] = {}
        self._images: Dict[int, object] = {}

    # ---- dados
    def _buffer(self, index: int) -> bytes:
        if index in self._buffers:
            return self._buffers[index]
        try:
            entry = self.doc["buffers"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("O modelo aponta para um buffer que não existe.") from error
        uri = entry.get("uri")
        if uri is None:
            if index != 0 or self.blob is None:
                raise ModelError("O .glb não traz os dados do buffer.")
            raw = self.blob
        else:
            raw = _data_uri(uri)
        if len(raw) < int(entry.get("byteLength", 0)):
            raise ModelError("Os dados do buffer estão cortados.")
        self._buffers[index] = raw
        return raw

    def _view(self, index: int) -> Tuple[bytes, int, Optional[int]]:
        try:
            view = self.doc["bufferViews"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("O modelo aponta para uma bufferView que não existe.") from error
        buffer = self._buffer(int(view.get("buffer", 0)))
        start = int(view.get("byteOffset", 0))
        end = start + int(view["byteLength"])
        if end > len(buffer):
            raise ModelError("Uma bufferView passa do fim do buffer.")
        return buffer[start:end], start, view.get("byteStride")

    def accessor(self, index: int) -> np.ndarray:
        """Os valores do accessor como array (count, componentes), com os inteiros normalizados em float."""
        try:
            entry = self.doc["accessors"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("O modelo aponta para um accessor que não existe.") from error
        if "sparse" in entry:
            self.model.warnings.append("Accessor 'sparse' não é suportado; ignorado.")
        dtype = _COMPONENT.get(int(entry["componentType"]))
        width = _WIDTH.get(entry["type"])
        if dtype is None or width is None:
            raise ModelError("Tipo de dado do modelo desconhecido.")
        count = int(entry["count"])
        if "bufferView" not in entry:
            return np.zeros((count, width), dtype=np.float32)
        chunk, _, stride = self._view(int(entry["bufferView"]))
        itemsize = np.dtype(dtype).itemsize
        element = itemsize * width
        stride = int(stride) if stride else element
        offset = int(entry.get("byteOffset", 0))
        if count and offset + stride * (count - 1) + element > len(chunk):
            raise ModelError("Um accessor passa do fim dos dados.")
        if stride == element:
            values = np.frombuffer(chunk, dtype=dtype, count=count * width, offset=offset).reshape(count, width)
        else:  # dados intercalados com outros: lê elemento por elemento
            raw = np.frombuffer(chunk, dtype=np.uint8)
            rows = np.arange(count)[:, None] * stride + offset + np.arange(element)[None, :]
            values = raw[rows].copy().view(dtype).reshape(count, width)
        if entry.get("normalized") and dtype in _NORMALIZER:
            return np.maximum(values.astype(np.float32) / _NORMALIZER[dtype], -1.0)
        return values

    def image(self, index: int):
        if index in self._images:
            return self._images[index]
        from PIL import Image

        try:
            entry = self.doc["images"][index]
            if "bufferView" in entry:
                raw = bytes(self._view(int(entry["bufferView"]))[0])
            else:
                raw = _data_uri(entry["uri"])
            picture = Image.open(io.BytesIO(raw))
            if max(picture.size) > MAX_TEXTURE_SIDE:
                raise ModelError(f"A textura passa de {MAX_TEXTURE_SIDE} pixels de lado.")
            picture = picture.convert("RGBA")
        except ModelError:
            raise
        except Exception as error:  # imagem corrompida ou formato que o Pillow não lê
            self.model.warnings.append(f"Não consegui ler uma textura: {error}")
            picture = None
        self._images[index] = picture
        return picture

    # ---- cena
    def read(self) -> GlbModel:
        doc = self.doc
        self.model.skins = len(doc.get("skins", []))
        self.model.animations = [a.get("name", f"animação {i}") for i, a in enumerate(doc.get("animations", []))]
        scenes = doc.get("scenes", [])
        roots = scenes[int(doc.get("scene", 0))].get("nodes", []) if scenes else []
        if not roots:
            roots = [i for i in range(len(doc.get("nodes", [])))]  # sem cena: todos os nós, cada um na sua raiz
        seen: set = set()
        for root in roots:
            self._node(int(root), np.identity(4), seen)
        if not self.model.submeshes:
            raise ModelError("O modelo não tem nenhuma malha de triângulos.")
        if self.model.triangles > MAX_TRIANGLES:
            raise ModelError(f"O modelo tem {self.model.triangles} triângulos; o limite é {MAX_TRIANGLES}.")
        return self.model

    def _node(self, index: int, parent: np.ndarray, seen: set) -> None:
        if index in seen:
            return
        seen.add(index)
        try:
            node = self.doc["nodes"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("A cena aponta para um nó que não existe.") from error
        world = parent @ _local_matrix(node)
        if "mesh" in node:
            # um nó com esqueleto ignora a própria transformação: os vértices já estão no espaço dos ossos
            matrix = np.identity(4) if "skin" in node else world
            self._mesh(int(node["mesh"]), matrix, node.get("name") or f"malha {node['mesh']}")
        for child in node.get("children", []):
            self._node(int(child), world, seen)

    def _mesh(self, index: int, matrix: np.ndarray, name: str) -> None:
        try:
            mesh = self.doc["meshes"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("Um nó aponta para uma malha que não existe.") from error
        normal_matrix = np.linalg.inv(matrix[:3, :3]).T if abs(np.linalg.det(matrix[:3, :3])) > 1e-12 else np.identity(3)
        flip = np.linalg.det(matrix[:3, :3]) < 0  # espelhado: inverte o sentido dos triângulos
        for number, primitive in enumerate(mesh.get("primitives", [])):
            mode = int(primitive.get("mode", 4))
            if mode != 4:
                self.model.warnings.append("Só triângulos soltos (modo 4) são lidos; uma parte foi ignorada.")
                continue
            attributes = primitive.get("attributes", {})
            if "POSITION" not in attributes:
                continue
            positions = self.accessor(int(attributes["POSITION"])).astype(np.float64)
            count = len(positions)
            if "indices" in primitive:
                indices = self.accessor(int(primitive["indices"])).reshape(-1).astype(np.int64)
            else:
                indices = np.arange(count, dtype=np.int64)
            indices = indices[: len(indices) // 3 * 3]
            if len(indices) and (indices.max() >= count or indices.min() < 0):
                raise ModelError("Um índice aponta para um vértice que não existe.")
            if flip:
                indices = indices.reshape(-1, 3)[:, ::-1].reshape(-1)
            if "NORMAL" in attributes:
                normals = self.accessor(int(attributes["NORMAL"])).astype(np.float64)
            else:
                normals = _smooth_normals(positions, indices)
            uv = self.accessor(int(attributes["TEXCOORD_0"])).astype(np.float64) if "TEXCOORD_0" in attributes \
                else np.zeros((count, 2))
            colour = np.ones((count, 3))
            if "COLOR_0" in attributes:
                colour = np.clip(self.accessor(int(attributes["COLOR_0"]))[:, :3].astype(np.float64), 0.0, 1.0)

            material = self._material(primitive.get("material"))
            vertices = np.empty((count, FLOATS_PER_VERTEX), dtype=np.float32)
            vertices[:, :3] = positions @ matrix[:3, :3].T + matrix[:3, 3]
            rotated = normals @ normal_matrix.T
            vertices[:, 3:6] = rotated / np.maximum(np.linalg.norm(rotated, axis=1, keepdims=True), 1e-12)
            vertices[:, 6:8] = uv[:, :2]
            vertices[:, 8:11] = colour
            self.model.submeshes.append(Submesh(
                name=f"{name}.{number}", vertices=vertices, indices=indices.astype(np.uint32), **material))

    def _material(self, index) -> dict:
        info = {"image": None, "color": (1.0, 1.0, 1.0, 1.0), "double_sided": False, "alpha_mode": "OPAQUE"}
        if index is None:
            return info
        try:
            material = self.doc["materials"][int(index)]
        except (KeyError, IndexError, TypeError):
            return info
        pbr = material.get("pbrMetallicRoughness", {})
        info["color"] = tuple(float(v) for v in pbr.get("baseColorFactor", (1.0, 1.0, 1.0, 1.0)))
        info["double_sided"] = bool(material.get("doubleSided", False))
        info["alpha_mode"] = material.get("alphaMode", "OPAQUE")
        texture = pbr.get("baseColorTexture")
        if texture is not None:
            if int(texture.get("texCoord", 0)) != 0:
                self.model.warnings.append("Textura com TEXCOORD diferente de 0 não é suportada.")
            try:
                source = self.doc["textures"][int(texture["index"])].get("source")
            except (KeyError, IndexError, TypeError):
                source = None
            if source is not None:
                info["image"] = self.image(int(source))
        return info


# ------------------------------------------------------------------------------------------------ apoio
def _data_uri(uri: str) -> bytes:
    """Só ``data:`` (dados embutidos); qualquer outro caminho é recusado, para não ler fora do arquivo."""
    if not isinstance(uri, str) or not uri.startswith("data:"):
        raise ModelError("O modelo usa um arquivo externo (uri). Exporte um .glb com tudo dentro.")
    head, _, payload = uri.partition(",")
    try:
        return base64.b64decode(payload) if head.endswith(";base64") else payload.encode("latin-1")
    except Exception as error:
        raise ModelError("Dados embutidos inválidos.") from error


def _local_matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.asarray(node["matrix"], dtype=np.float64).reshape(4, 4).T   # o glTF guarda por colunas
    matrix = np.identity(4)
    x, y, z, w = (float(v) for v in node.get("rotation", (0.0, 0.0, 0.0, 1.0)))
    norm = (x * x + y * y + z * z + w * w) ** 0.5 or 1.0
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    rotation = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    scale = np.asarray(node.get("scale", (1.0, 1.0, 1.0)), dtype=np.float64)
    matrix[:3, :3] = rotation * scale[None, :]
    matrix[:3, 3] = np.asarray(node.get("translation", (0.0, 0.0, 0.0)), dtype=np.float64)
    return matrix


def _smooth_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Normais por vértice, da média das normais das faces (para modelos que não trazem)."""
    normals = np.zeros_like(positions)
    triangles = indices.reshape(-1, 3)
    if len(triangles):
        a, b, c = (positions[triangles[:, k]] for k in range(3))
        face = np.cross(b - a, c - a)
        for k in range(3):
            np.add.at(normals, triangles[:, k], face)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.where(length > 1e-12, normals / np.maximum(length, 1e-12), np.array([0.0, 1.0, 0.0]))
    return normals
