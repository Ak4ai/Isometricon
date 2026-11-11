"""Escreve modelos glTF 2.0 (.glb) simples, para os testes do leitor e para gerar um modelo de amostra.

Não é um exportador completo: só malhas de triângulos com normais, UV, cor de vértice, materiais com cor ou textura
(PNG embutido) e nós com transformação.
"""

from __future__ import annotations

import io
import json
import struct
from typing import List, Optional, Sequence, Tuple

import numpy as np

_FLOAT, _UINT, _USHORT = 5126, 5125, 5123
_ARRAY_BUFFER, _ELEMENT_ARRAY_BUFFER = 34962, 34963


class GlbBuilder:
    """Monta o documento e o buffer; ``build`` devolve os bytes do .glb."""

    def __init__(self) -> None:
        self.nodes: List[dict] = []
        self.meshes: List[dict] = []
        self.materials: List[dict] = []
        self.images: List[dict] = []
        self.textures: List[dict] = []
        self.accessors: List[dict] = []
        self.views: List[dict] = []
        self.skins: List[dict] = []
        self.animations: List[dict] = []
        self._blob = bytearray()

    # ---- dados
    def _view(self, data: bytes, target: Optional[int] = None) -> int:
        while len(self._blob) % 4:
            self._blob.append(0)
        view = {"buffer": 0, "byteOffset": len(self._blob), "byteLength": len(data)}
        if target:
            view["target"] = target
        self._blob += data
        self.views.append(view)
        return len(self.views) - 1

    def _accessor(self, array: np.ndarray, component: int, kind: str, target: Optional[int] = None,
                  bounds: bool = False) -> int:
        dtype = {_FLOAT: np.float32, _UINT: np.uint32, _USHORT: np.uint16}[component]
        array = np.ascontiguousarray(array, dtype=dtype)
        entry = {"bufferView": self._view(array.tobytes(), target), "componentType": component,
                 "count": int(len(array)), "type": kind}
        if bounds:
            entry["min"] = [float(v) for v in array.min(axis=0)]
            entry["max"] = [float(v) for v in array.max(axis=0)]
        self.accessors.append(entry)
        return len(self.accessors) - 1

    # ---- elementos
    def add_material(self, color: Sequence[float] = (1, 1, 1, 1), png: Optional[bytes] = None,
                     double_sided: bool = False, alpha_mode: str = "OPAQUE") -> int:
        pbr = {"baseColorFactor": [float(c) for c in color], "metallicFactor": 0.0, "roughnessFactor": 1.0}
        if png is not None:
            self.images.append({"bufferView": self._view(png), "mimeType": "image/png"})
            self.textures.append({"source": len(self.images) - 1})
            pbr["baseColorTexture"] = {"index": len(self.textures) - 1}
        material = {"pbrMetallicRoughness": pbr, "doubleSided": double_sided}
        if alpha_mode != "OPAQUE":
            material["alphaMode"] = alpha_mode
        self.materials.append(material)
        return len(self.materials) - 1

    def add_mesh(self, positions, indices, normals=None, uvs=None, colors=None, material: Optional[int] = None,
                 name: str = "malha", index_type: int = _USHORT, joints=None, weights=None) -> int:
        attributes = {"POSITION": self._accessor(positions, _FLOAT, "VEC3", _ARRAY_BUFFER, bounds=True)}
        if normals is not None:
            attributes["NORMAL"] = self._accessor(normals, _FLOAT, "VEC3", _ARRAY_BUFFER)
        if uvs is not None:
            attributes["TEXCOORD_0"] = self._accessor(uvs, _FLOAT, "VEC2", _ARRAY_BUFFER)
        if colors is not None:
            attributes["COLOR_0"] = self._accessor(colors, _FLOAT, "VEC3", _ARRAY_BUFFER)
        if joints is not None and weights is not None:
            attributes["JOINTS_0"] = self._accessor(joints, _USHORT, "VEC4", _ARRAY_BUFFER)
            attributes["WEIGHTS_0"] = self._accessor(weights, _FLOAT, "VEC4", _ARRAY_BUFFER)
        primitive = {"attributes": attributes}
        if indices is not None:
            primitive["indices"] = self._accessor(np.asarray(indices).reshape(-1), index_type, "SCALAR",
                                                  _ELEMENT_ARRAY_BUFFER)
        if material is not None:
            primitive["material"] = material
        self.meshes.append({"name": name, "primitives": [primitive]})
        return len(self.meshes) - 1

    def add_node(self, mesh: Optional[int] = None, name: str = "nó", translation=None, rotation=None, scale=None,
                 matrix=None, children: Sequence[int] = (), skin: Optional[int] = None) -> int:
        node: dict = {"name": name}
        if mesh is not None:
            node["mesh"] = mesh
        if skin is not None:
            node["skin"] = skin
        if matrix is not None:
            node["matrix"] = [float(v) for v in np.asarray(matrix, dtype=np.float64).T.reshape(-1)]  # por colunas
        if translation is not None:
            node["translation"] = [float(v) for v in translation]
        if rotation is not None:
            node["rotation"] = [float(v) for v in rotation]
        if scale is not None:
            node["scale"] = [float(v) for v in scale]
        if children:
            node["children"] = [int(c) for c in children]
        self.nodes.append(node)
        return len(self.nodes) - 1

    def add_skin(self, joint_nodes: Sequence[int], inverse_bind=None) -> int:
        """Um esqueleto com os nós ``joint_nodes``; ``inverse_bind`` (J, 4, 4) em linhas, como no numpy."""
        skin = {"joints": [int(j) for j in joint_nodes]}
        if inverse_bind is not None:
            columns = np.asarray(inverse_bind, dtype=np.float32).transpose(0, 2, 1).reshape(len(joint_nodes), 16)
            skin["inverseBindMatrices"] = self._accessor(columns, _FLOAT, "MAT4")
        self.skins.append(skin)
        return len(self.skins) - 1

    def add_animation(self, name: str, tracks: Sequence[tuple], interpolation: str = "LINEAR") -> int:
        """Um clipe. ``tracks``: (nó, "translation"|"rotation"|"scale", tempos, valores)."""
        channels, samplers = [], []
        for node, path, times, values in tracks:
            samplers.append({"input": self._accessor(np.asarray(times), _FLOAT, "SCALAR", bounds=False),
                             "output": self._accessor(np.asarray(values), _FLOAT, "VEC4" if path == "rotation" else "VEC3"),
                             "interpolation": interpolation})
            channels.append({"sampler": len(samplers) - 1, "target": {"node": int(node), "path": path}})
        self.animations.append({"name": name, "channels": channels, "samplers": samplers})
        return len(self.animations) - 1

    # ---- arquivo
    def document(self, scene_nodes: Sequence[int]) -> dict:
        doc = {"asset": {"version": "2.0", "generator": "isometricon"}, "scene": 0,
               "scenes": [{"nodes": [int(n) for n in scene_nodes]}], "nodes": self.nodes, "meshes": self.meshes,
               "accessors": self.accessors, "bufferViews": self.views,
               "buffers": [{"byteLength": len(self._blob)}]}
        for key, value in (("materials", self.materials), ("images", self.images), ("textures", self.textures),
                           ("skins", self.skins), ("animations", self.animations)):
            if value:
                doc[key] = value
        return doc

    def build(self, scene_nodes: Sequence[int]) -> bytes:
        text = json.dumps(self.document(scene_nodes), separators=(",", ":")).encode("utf-8")
        text += b" " * (-len(text) % 4)
        blob = bytes(self._blob) + b"\0" * (-len(self._blob) % 4)
        total = 12 + 8 + len(text) + 8 + len(blob)
        return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(text), 0x4E4F534A) + text
                + struct.pack("<II", len(blob), 0x004E4942) + blob)


# ---------------------------------------------------------------------------------------------- formas
def box(lo: Sequence[float], hi: Sequence[float]):
    """Uma caixa: (posições, normais, uvs, índices), 24 vértices e 12 triângulos, voltados para fora."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    faces = [  # normal, e os 4 cantos em sentido anti-horário visto de fora
        ((0, 1, 0), [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)]),
        ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),
        ((0, 0, 1), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
        ((1, 0, 0), [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)]),
        ((0, 0, -1), [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)]),
        ((-1, 0, 0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]),
    ]
    positions, normals, uvs, indices = [], [], [], []
    for number, (normal, corners) in enumerate(faces):
        positions += corners
        normals += [normal] * 4
        uvs += [(0, 1), (1, 1), (1, 0), (0, 0)]
        base = number * 4
        indices += [base, base + 1, base + 2, base + 2, base + 3, base]
    return (np.array(positions, dtype=np.float32), np.array(normals, dtype=np.float32),
            np.array(uvs, dtype=np.float32), np.array(indices, dtype=np.uint16))


def checker_png(size: int = 16, a=(235, 235, 235), b=(90, 130, 220)) -> bytes:
    """Uma textura xadrez de ``size`` pixels, em PNG."""
    from PIL import Image

    image = Image.new("RGBA", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = (*(a if (x // 2 + y // 2) % 2 == 0 else b), 255)
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def sample_humanoid() -> bytes:
    """Um boneco de caixas (cabeça, tronco, braços e pernas), 1,7 de altura, de frente para +z. Para teste e amostra."""
    builder = GlbBuilder()
    skin = builder.add_material((1.0, 0.82, 0.68, 1.0))
    shirt = builder.add_material((1, 1, 1, 1), png=checker_png())
    trousers = builder.add_material((0.2, 0.25, 0.5, 1.0))
    parts = [  # nome, material, canto mínimo, canto máximo
        ("cabeça", skin, (-0.12, 1.45, -0.12), (0.12, 1.70, 0.12)),
        ("tronco", shirt, (-0.20, 0.85, -0.10), (0.20, 1.45, 0.10)),
        ("braço E", skin, (0.20, 0.85, -0.07), (0.30, 1.45, 0.07)),
        ("braço D", skin, (-0.30, 0.85, -0.07), (-0.20, 1.45, 0.07)),
        ("perna E", trousers, (0.01, 0.0, -0.08), (0.20, 0.85, 0.08)),
        ("perna D", trousers, (-0.20, 0.0, -0.08), (-0.01, 0.85, 0.08)),
        ("nariz", skin, (-0.03, 1.55, 0.12), (0.03, 1.59, 0.17)),   # mostra para onde ele olha: +z
    ]
    children = []
    for name, material, lo, hi in parts:
        positions, normals, uvs, indices = box(lo, hi)
        mesh = builder.add_mesh(positions, indices, normals, uvs, material=material, name=name)
        children.append(builder.add_node(mesh=mesh, name=name))
    root = builder.add_node(name="boneco", children=children)
    return builder.build([root])
