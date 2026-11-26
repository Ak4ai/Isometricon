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

from .clips import Channel, Clip, RestPose, decompose
from .rig import MAX_BONES, Rig

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_JSON_STRUCTURE = 400_000
MAX_TRIANGLES = 300_000
MAX_VERTICES = MAX_TRIANGLES * 3
MAX_ACCESSOR_VALUES = MAX_VERTICES * 4
MAX_MESH_PARTS = 4096
MAX_NODES = 16_384
MAX_NODE_DEPTH = 128
MAX_TEXTURE_SIDE = 4096
MAX_TEXTURE_PIXELS = 32 * 1024 * 1024  # total das imagens decodificadas
MAX_CLIPS = 64
MAX_KEYFRAMES = 100_000   # por canal
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
    joints: Optional[np.ndarray] = None   # (N, 4) osso de cada influência, no índice do ``Rig`` (só com esqueleto)
    weights: Optional[np.ndarray] = None  # (N, 4) peso de cada influência, somando 1

    @property
    def triangles(self) -> int:
        return len(self.indices) // 3


@dataclass
class GlbModel:
    """O modelo lido: as partes e quem mais o arquivo trouxe (para as fases seguintes)."""

    submeshes: List[Submesh] = field(default_factory=list)
    skins: int = 0              # quantos esqueletos o arquivo tem
    animations: List[str] = field(default_factory=list)   # nomes dos clipes do arquivo
    clips: List[Clip] = field(default_factory=list)       # os clipes que mexem nos ossos do esqueleto
    rest_pose: Optional[RestPose] = None                   # pose de montagem em TRS, para tocar os clipes
    warnings: List[str] = field(default_factory=list)
    rig: Optional[Rig] = None   # o esqueleto da malha (o primeiro do arquivo que tem pesos), na mesma posição da malha
    transform: np.ndarray = field(default_factory=lambda: np.identity(4))   # o que ``normalize`` fez com o modelo

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
        total = np.identity(4)
        for _ in range(yaw_turns % 4):
            for s in self.submeshes:
                v = s.vertices
                v[:, [0, 2]] = np.stack([v[:, 2], -v[:, 0]], axis=1)        # gira 90° em y
                v[:, [3, 5]] = np.stack([v[:, 5], -v[:, 3]], axis=1)
            turn = np.identity(4)
            turn[:3, :3] = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
            total = turn @ total
        low, high = (corner.astype(np.float64) for corner in self.bounds())
        size = float(high[1] - low[1])
        if size <= 1e-9:
            raise ModelError("O modelo não tem altura.")
        scale = height / size
        centre = np.array([(low[0] + high[0]) / 2.0, low[1], (low[2] + high[2]) / 2.0])
        with np.errstate(over="raise", invalid="raise"):
            try:
                for s in self.submeshes:
                    s.vertices[:, :3] = (s.vertices[:, :3] - centre) * scale
            except FloatingPointError as error:
                raise ModelError("As dimensões do modelo normalizado excedem o limite.") from error
        move = np.identity(4)
        move[:3, :3] *= scale
        move[:3, 3] = -centre * scale
        total = move @ total
        self.transform = total @ self.transform
        if self.rig is not None:       # o esqueleto acompanha o modelo
            self.rig = self.rig.transformed(total)
        return self


# ------------------------------------------------------------------------------------------------ arquivo
def read_model_bytes(path: str) -> bytes:
    """Lê só a quantidade de bytes que o importador suporta."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except OSError as error:
        raise ModelError(f"Não consegui abrir o arquivo: {error}") from error
    if len(data) > MAX_FILE_BYTES:
        raise ModelError(f"O arquivo passa de {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    return data


def load_model(path: str) -> GlbModel:
    """Lê um .glb ou .gltf com dados embutidos."""
    return parse_model(read_model_bytes(path))


def parse_model(data: bytes) -> GlbModel:
    """Lê o conteúdo de um ``.glb`` ou de um ``.gltf`` (texto JSON com os dados embutidos)."""
    if len(data) > MAX_FILE_BYTES:
        raise ModelError(f"O arquivo passa de {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    try:
        if data[:4] == b"glTF":
            document, blob = _split_glb(data)
        else:
            try:
                document, blob = _read_json(data), None
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ModelError("Não é um arquivo glTF (.glb ou .gltf).") from error
        asset = document.get("asset") if isinstance(document, dict) else None
        if not isinstance(asset, dict) or str(asset.get("version", "")).split(".")[0] != "2":
            raise ModelError("Só o glTF 2.0 é aceito.")
        with np.errstate(over="raise", invalid="raise"):
            return _Reader(document, blob).read()
    except ModelError:
        raise
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, OverflowError, RecursionError,
            FloatingPointError, np.linalg.LinAlgError) as error:
        raise ModelError("Estrutura ou dados do modelo inválidos.") from error


def _read_json(data: bytes) -> dict:
    # Limita o crescimento dos objetos Python antes de carregar o JSON.
    # Uma URI base64 pode ser grande, mas não contém esses separadores.
    if data.count(b",") + data.count(b"{") + data.count(b"[") > MAX_JSON_STRUCTURE:
        raise ModelError("A descrição JSON do modelo excede o limite de elementos.")
    return json.loads(data)


def _split_glb(data: bytes):
    if len(data) < 20:
        raise ModelError("O arquivo .glb está incompleto.")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC or version != 2:
        raise ModelError("Não é um .glb da versão 2.")
    document, blob, offset = None, None, 12
    if length != len(data):
        raise ModelError("Comprimento inválido no .glb.")
    while offset < length:
        if offset + 8 > length:
            raise ModelError("O cabeçalho de um bloco do .glb está cortado.")
        size, kind = struct.unpack_from("<II", data, offset)
        if offset + 8 + size > length or size % 4:
            raise ModelError("O arquivo .glb está cortado.")
        if kind == _CHUNK_JSON and document is None:
            try:
                document = _read_json(data[offset + 8: offset + 8 + size])
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ModelError("O JSON do .glb é inválido.") from error
        elif kind == _CHUNK_BIN and blob is None:
            blob = memoryview(data)[offset + 8: offset + 8 + size]
        offset += 8 + size
    if document is None:
        raise ModelError("O .glb não tem o bloco de descrição.")
    return document, blob


# ------------------------------------------------------------------------------------------------ leitor
class _Reader:
    def __init__(self, document: dict, blob: Optional[memoryview]) -> None:
        self.doc = document
        self.blob = blob
        self.model = GlbModel()
        self._buffers: Dict[int, memoryview] = {}
        self._images: Dict[int, object] = {}
        self._parent_node: Dict[int, int] = {}
        self._world_cache: Dict[int, np.ndarray] = {}
        self._triangles = self._vertices = self._image_pixels = 0
        self._primitives = 0
        self._rig_skin: Optional[int] = None     # o skin cujo esqueleto vai para o modelo

    # ---- dados
    def _buffer(self, index: int) -> memoryview:
        if index in self._buffers:
            return self._buffers[index]
        try:
            if index < 0:
                raise IndexError(index)
            entry = self.doc["buffers"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("O modelo aponta para um buffer que não existe.") from error
        uri = entry.get("uri")
        if uri is None:
            if index != 0 or self.blob is None:
                raise ModelError("O .glb não traz os dados do buffer.")
            raw = self.blob
        else:
            raw = memoryview(_data_uri(uri))
        size = int(entry["byteLength"])
        if not 0 <= size <= len(raw):
            raise ModelError("Os dados do buffer estão cortados.")
        self._buffers[index] = raw[:size]
        return self._buffers[index]

    def _view(self, index: int) -> Tuple[memoryview, Optional[int]]:
        try:
            if index < 0:
                raise IndexError(index)
            view = self.doc["bufferViews"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("O modelo aponta para uma bufferView que não existe.") from error
        buffer = self._buffer(int(view.get("buffer", 0)))
        start = int(view.get("byteOffset", 0))
        end = start + int(view["byteLength"])
        if not 0 <= start <= end <= len(buffer):
            raise ModelError("Uma bufferView passa do fim do buffer.")
        return buffer[start:end], view.get("byteStride")

    def _accessor_layout(self, index: int):
        try:
            if index < 0:
                raise IndexError(index)
            entry = self.doc["accessors"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("O modelo aponta para um accessor que não existe.") from error
        dtype = _COMPONENT.get(int(entry["componentType"]))
        width = _WIDTH.get(entry["type"])
        if dtype is None or width is None:
            raise ModelError("Tipo de dado do modelo desconhecido.")
        count = int(entry["count"])
        if not 0 <= count <= MAX_VERTICES or count * width > MAX_ACCESSOR_VALUES:
            raise ModelError("Um accessor excede o limite de valores do modelo.")
        return entry, dtype, width, count

    def accessor(self, index: int) -> np.ndarray:
        """Os valores do accessor como array (count, componentes)."""
        entry, kind, width, count = self._accessor_layout(index)
        if "sparse" in entry:
            self.model.warnings.append("Accessor 'sparse' não é suportado; ignorado.")
        if "bufferView" not in entry:
            return np.zeros((count, width), dtype=np.float32)
        chunk, stride = self._view(int(entry["bufferView"]))
        dtype = np.dtype(kind).newbyteorder("<")
        element = dtype.itemsize * width
        stride = element if stride is None else int(stride)
        offset = int(entry.get("byteOffset", 0))
        if (not 0 <= offset <= len(chunk) or not element <= stride <= 252
                or stride % dtype.itemsize or offset % dtype.itemsize
                or (count and offset + stride * (count - 1) + element > len(chunk))):
            raise ModelError("Um accessor tem deslocamento ou stride inválido.")
        # A view estridada lê os atributos intercalados sem criar uma matriz
        # auxiliar de índices com um inteiro para cada byte do accessor.
        values = np.ndarray((count, width), dtype=dtype, buffer=chunk, offset=offset,
                            strides=(stride, dtype.itemsize))
        if entry.get("normalized") and kind in _NORMALIZER:
            return np.maximum(values.astype(np.float32) / _NORMALIZER[kind], -1.0)
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
            with Image.open(io.BytesIO(raw)) as source:
                if max(source.size) > MAX_TEXTURE_SIDE:
                    raise ModelError(f"A textura passa de {MAX_TEXTURE_SIDE} pixels de lado.")
                self._image_pixels += source.width * source.height
                if self._image_pixels > MAX_TEXTURE_PIXELS:
                    raise ModelError("As texturas excedem o limite total de pixels.")
                picture = source.convert("RGBA")
        except ModelError:
            raise
        except Image.DecompressionBombError as error:
            raise ModelError("A textura excede o limite de pixels.") from error
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
        nodes = doc.get("nodes", [])
        if len(nodes) > MAX_NODES:
            raise ModelError("A cena excede o limite de nós.")
        for index, node in enumerate(nodes):
            for child in node.get("children", []):
                child = int(child)
                if not 0 <= child < len(nodes) or child in self._parent_node:
                    raise ModelError("A hierarquia contém um filho inválido ou com mais de um pai.")
                self._parent_node[child] = index
        depths: Dict[int, int] = {}
        for index in range(len(nodes)):
            chain = []
            cursor = index
            while cursor is not None and cursor not in depths:
                if cursor in chain or len(chain) >= MAX_NODE_DEPTH:
                    raise ModelError("A hierarquia de nós contém um ciclo ou é profunda demais.")
                chain.append(cursor)
                cursor = self._parent_node.get(cursor)
            depth = depths.get(cursor, 0)
            for cursor in reversed(chain):
                depth += 1
                if depth > MAX_NODE_DEPTH:
                    raise ModelError("A hierarquia de nós é profunda demais.")
                depths[cursor] = depth
        scenes = doc.get("scenes", [])
        roots = scenes[int(doc.get("scene", 0))].get("nodes", []) if scenes else []
        if not roots:
            roots = [i for i in range(len(nodes)) if i not in self._parent_node]
        seen: set = set()
        for root in roots:
            self._node(int(root), np.identity(4), seen)
        if not self.model.submeshes:
            raise ModelError("O modelo não tem nenhuma malha de triângulos.")
        if self._rig_skin is not None:
            self.model.rig = self._build_rig(self._rig_skin)
            self._build_clips()
        if self.model.triangles > MAX_TRIANGLES:
            raise ModelError(f"O modelo tem {self.model.triangles} triângulos; o limite é {MAX_TRIANGLES}.")
        return self.model

    def _node(self, index: int, parent: np.ndarray, seen: set) -> None:
        if index in seen:
            return
        seen.add(index)
        try:
            if index < 0:
                raise IndexError(index)
            node = self.doc["nodes"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("A cena aponta para um nó que não existe.") from error
        world = parent @ _local_matrix(node)
        if "mesh" in node:
            # um nó com esqueleto ignora a própria transformação: os vértices já estão no espaço dos ossos
            matrix = np.identity(4) if "skin" in node else world
            self._mesh(int(node["mesh"]), matrix, node.get("name") or f"malha {node['mesh']}",
                       int(node["skin"]) if "skin" in node else None)
        for child in node.get("children", []):
            self._node(int(child), world, seen)

    def _mesh(self, index: int, matrix: np.ndarray, name: str, skin: Optional[int] = None) -> None:
        try:
            if index < 0:
                raise IndexError(index)
            mesh = self.doc["meshes"][index]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("Um nó aponta para uma malha que não existe.") from error
        normal_matrix = np.linalg.inv(matrix[:3, :3]).T if abs(np.linalg.det(matrix[:3, :3])) > 1e-12 else np.identity(3)
        flip = np.linalg.det(matrix[:3, :3]) < 0  # espelhado: inverte o sentido dos triângulos
        primitives = mesh.get("primitives", [])
        self._primitives += len(primitives)
        if self._primitives > MAX_MESH_PARTS:
            raise ModelError("O modelo excede o limite de partes de malha.")
        for number, primitive in enumerate(primitives):
            mode = int(primitive.get("mode", 4))
            if mode != 4:
                self.model.warnings.append("Só triângulos soltos (modo 4) são lidos; uma parte foi ignorada.")
                continue
            attributes = primitive.get("attributes", {})
            if "POSITION" not in attributes:
                continue
            position_id = int(attributes["POSITION"])
            _, _, width, count = self._accessor_layout(position_id)
            if width != 3:
                raise ModelError("O atributo POSITION deve ter três componentes.")
            index_id = int(primitive["indices"]) if "indices" in primitive else None
            index_count = count
            if index_id is not None:
                index_info, kind, width, index_count = self._accessor_layout(index_id)
                if width != 1 or kind not in (np.uint8, np.uint16, np.uint32) or index_info.get("normalized"):
                    raise ModelError("Tipo de índice de triângulo inválido.")
            if count == 0 or index_count < 3:
                continue
            self._triangles += index_count // 3
            self._vertices += count
            if self._triangles > MAX_TRIANGLES:
                raise ModelError(f"O modelo excede o limite de {MAX_TRIANGLES} triângulos.")
            if self._vertices > MAX_VERTICES:
                raise ModelError("O modelo excede o limite de vértices.")
            positions = self._vertex_attribute(attributes, "POSITION", count, (3,)).astype(np.float64)
            indices = (self.accessor(index_id).reshape(-1).astype(np.int64) if index_id is not None
                       else np.arange(count, dtype=np.int64))
            indices = indices[:index_count // 3 * 3]
            if len(indices) and (indices.max() >= count or indices.min() < 0):
                raise ModelError("Um índice aponta para um vértice que não existe.")
            if flip:
                indices = indices.reshape(-1, 3)[:, ::-1].reshape(-1)
            if "NORMAL" in attributes:
                normals = self._vertex_attribute(attributes, "NORMAL", count, (3,)).astype(np.float64)
            else:
                normals = _smooth_normals(positions, indices)
            uv = self._vertex_attribute(attributes, "TEXCOORD_0", count, (2,)).astype(np.float64) if "TEXCOORD_0" in attributes \
                else np.zeros((count, 2))
            colour = np.ones((count, 3))
            if "COLOR_0" in attributes:
                colour = np.clip(self._vertex_attribute(attributes, "COLOR_0", count, (3, 4))[:, :3].astype(np.float64), 0.0, 1.0)

            joints = weights = None
            if skin is not None and "JOINTS_0" in attributes and "WEIGHTS_0" in attributes:
                if self._rig_skin is None:
                    self._rig_skin = skin
                if skin == self._rig_skin:
                    joints = self._vertex_attribute(attributes, "JOINTS_0", count, (4,)).astype(np.int64)
                    weights = np.maximum(self._vertex_attribute(attributes, "WEIGHTS_0", count, (4,)).astype(np.float64), 0.0)
                    total = weights.sum(axis=1, keepdims=True)
                    weights = np.where(total > 1e-9, weights / np.maximum(total, 1e-9), np.array([1.0, 0.0, 0.0, 0.0]))
                else:
                    self.model.warnings.append("O modelo tem mais de um esqueleto; só o primeiro é usado.")

            if joints is not None and (joints.min(initial=0) < 0 or joints.max(initial=0) > np.iinfo(np.uint16).max):
                raise ModelError("Um vértice usa um osso que não está no esqueleto.")
            material = self._material(primitive.get("material"))
            vertices = np.empty((count, FLOATS_PER_VERTEX), dtype=np.float32)
            vertices[:, :3] = positions @ matrix[:3, :3].T + matrix[:3, 3]
            rotated = normals @ normal_matrix.T
            vertices[:, 3:6] = rotated / np.maximum(np.linalg.norm(rotated, axis=1, keepdims=True), 1e-12)
            vertices[:, 6:8] = uv[:, :2]
            vertices[:, 8:11] = colour
            if not np.isfinite(vertices).all():
                raise ModelError("A malha transformada contém valores não finitos.")
            self.model.submeshes.append(Submesh(
                name=f"{name}.{number}", vertices=vertices, indices=indices.astype(np.uint32),
                joints=None if joints is None else joints.astype(np.uint16),
                weights=None if weights is None else weights.astype(np.float32), **material))

    def _vertex_attribute(self, attributes, name: str, count: int, widths: tuple) -> np.ndarray:
        index = int(attributes[name])
        _, _, width, rows = self._accessor_layout(index)
        if rows != count or width not in widths:
            raise ModelError(f"As dimensões do atributo {name} não batem com POSITION.")
        values = self.accessor(index)
        if not np.isfinite(values).all():
            raise ModelError(f"O atributo {name} contém valores não finitos.")
        return values

    def _world_of(self, node: int) -> np.ndarray:
        """A matriz de mundo de um nó (também dos que não estão na cena)."""
        if node not in self._world_cache:
            parent = self._parent_node.get(node)
            local = _local_matrix(self.doc["nodes"][node])
            self._world_cache[node] = local if parent is None else self._world_of(parent) @ local
        return self._world_cache[node]

    def _build_rig(self, skin_index: int) -> Rig:
        try:
            if skin_index < 0:
                raise IndexError(skin_index)
            skin = self.doc["skins"][skin_index]
            joint_nodes = skin["joints"]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("O esqueleto do modelo está incompleto.") from error
        count = len(joint_nodes)
        if count == 0:
            raise ModelError("O esqueleto do modelo não tem ossos.")
        if count > MAX_BONES:
            raise ModelError(f"O esqueleto tem {count} ossos; o limite é {MAX_BONES}.")
        joint_nodes = [int(j) for j in joint_nodes]
        if len(set(joint_nodes)) != count or any(not 0 <= j < len(self.doc["nodes"]) for j in joint_nodes):
            raise ModelError("O esqueleto aponta para nós inválidos.")
        for submesh in self.model.submeshes:
            if submesh.joints is not None and int(submesh.joints.max(initial=0)) >= count:
                raise ModelError("Um vértice usa um osso que não está no esqueleto.")
        index_of = {node: i for i, node in enumerate(joint_nodes)}
        parents = np.full(count, -1, dtype=np.int64)
        for i, node in enumerate(joint_nodes):
            ancestor = self._parent_node.get(node)
            while ancestor is not None and ancestor not in index_of:
                ancestor = self._parent_node.get(ancestor)
            if ancestor is not None:
                parents[i] = index_of[ancestor]
        world = np.array([self._world_of(node) for node in joint_nodes])
        local = np.array([world[i] if parents[i] < 0 else np.linalg.inv(world[parents[i]]) @ world[i]
                          for i in range(count)])
        if "inverseBindMatrices" in skin:
            matrix_id = int(skin["inverseBindMatrices"])
            _, _, width, rows = self._accessor_layout(matrix_id)
            if width != 16 or rows != count:
                raise ModelError("O número de matrizes de montagem difere do número de ossos.")
            matrices = self.accessor(matrix_id).astype(np.float64)
            inverse_bind = np.array([m.reshape(4, 4).T for m in matrices[:count]])   # o glTF guarda por colunas
        else:
            inverse_bind = np.array([np.linalg.inv(w) for w in world])
        names = [self.doc["nodes"][node].get("name") or f"osso {i}" for i, node in enumerate(joint_nodes)]
        try:
            return Rig(names, parents, local, inverse_bind)
        except ValueError as error:
            raise ModelError(str(error)) from error

    def _build_clips(self) -> None:
        """Lê os clipes de ``animations`` que mexem nos ossos do esqueleto (os demais canais são ignorados)."""
        nodes = self.doc.get("nodes", [])
        joint_nodes = [int(j) for j in self.doc["skins"][self._rig_skin]["joints"]]
        index_of = {node: i for i, node in enumerate(joint_nodes)}
        count = len(joint_nodes)
        translation, rotation, scale = np.zeros((count, 3)), np.zeros((count, 4)), np.ones((count, 3))
        prefix = np.tile(np.identity(4), (count, 1, 1))
        for i, node in enumerate(joint_nodes):
            translation[i], rotation[i], scale[i] = decompose(_local_matrix(nodes[node]))
            ancestor = self._parent_node.get(node)
            between = np.identity(4)
            while ancestor is not None and ancestor not in index_of:
                between = _local_matrix(nodes[ancestor]) @ between   # nós soltos entre o osso e o pai dele
                ancestor = self._parent_node.get(ancestor)
            if ancestor is None:   # raiz do esqueleto: o que está acima dela, até a cena
                parent = self._parent_node.get(node)
                between = np.identity(4) if parent is None else self._world_of(parent)
            prefix[i] = between
        self.model.rest_pose = RestPose(translation, rotation, scale, prefix)
        total = 0
        for number, animation in enumerate(self.doc.get("animations", [])[:MAX_CLIPS]):
            clip = Clip(animation.get("name") or f"animação {number}", 0.0)
            samplers = animation.get("samplers", [])
            for channel in animation.get("channels", []):
                target = channel.get("target", {})
                path = target.get("path")
                joint = index_of.get(target.get("node"))
                if joint is None or path not in ("translation", "rotation", "scale"):
                    continue
                try:
                    sampler = samplers[int(channel["sampler"])]
                    time_id = int(sampler["input"])
                    value_id = int(sampler["output"])
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                mode = sampler.get("interpolation", "LINEAR")
                _, _, time_width, frames = self._accessor_layout(time_id)
                _, _, value_width, samples = self._accessor_layout(value_id)
                expected = frames * (3 if mode == "CUBICSPLINE" else 1)
                if frames > MAX_KEYFRAMES or total + frames > MAX_KEYFRAMES * 4:
                    raise ModelError("As animações excedem o limite de quadros-chave.")
                if (not frames or time_width != 1 or samples != expected
                        or value_width != (4 if path == "rotation" else 3)):
                    continue
                times = self.accessor(time_id).reshape(-1).astype(np.float64)
                values = self.accessor(value_id).astype(np.float64)
                if mode == "CUBICSPLINE":
                    values = values[1::3]   # as tangentes ficam de fora (interpolação linear)
                total += frames
                if not np.isfinite(times).all() or not np.isfinite(values).all() or np.any(np.diff(times) < 0):
                    continue
                clip.channels.append(Channel(joint, path, times, values, step=(mode == "STEP")))
                clip.duration = max(clip.duration, float(times[-1]))
            if clip.channels:
                self.model.clips.append(clip)

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
