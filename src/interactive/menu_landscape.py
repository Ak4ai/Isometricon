"""Paisagem voxel de apresentação, isolada dos mundos e saves do jogador."""
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
import time
import numpy as np
import OpenGL.GL as gl
from src.camera import IsometricCamera
from src.math import mat4_identity, vec3
from src.rendering import Shader, TexturedMesh, TextureAtlas
from src.world import BlockType, ChunkMesher, TerrainGenerator
from src.world.mesher import ChunkMeshData

ROOT = Path(__file__).resolve().parents[2]


def build_landscape(atlas, seed=8817):
    generator = TerrainGenerator(seed=seed, base_height=7, amplitude=7, sea_level=7)
    chunks = generator.generate_region((x, 0, z) for x in range(-4, 4) for z in range(-4, 4))

    def lookup(x, y, z):
        chunk = chunks.get((x//16, y//16, z//16))
        return chunk.get_block(x%16, y%16, z%16) if chunk else BlockType.AIR

    def put(x, y, z, block):
        chunk = chunks.get((x//16, y//16, z//16))
        if chunk:
            chunk.set_block(x%16, y%16, z%16, block)

    # Pequenos bosques compostos pelos mesmos blocos do motor.
    rng = np.random.default_rng(seed)
    for x, z in rng.integers(-58, 58, size=(145, 2)):
        x, z = int(x), int(z)
        ground = generator.get_height(x, z)
        if ground < generator.sea_level or ground > 10:
            continue
        for y in range(ground+1, ground+4):
            put(x, y, z, BlockType.WOOD)
        for dy in range(3, 6):
            radius = 2 if dy < 5 else 1
            for dx in range(-radius, radius+1):
                for dz in range(-radius, radius+1):
                    if abs(dx)+abs(dz) <= radius+1:
                        put(x+dx, ground+dy, z+dz, BlockType.LEAVES)
    mesher = ChunkMesher(atlas=atlas)
    vertices,indices=[],[]
    offset=0
    for chunk in chunks.values():
        data=mesher.build(chunk,lookup)
        data.vertices[:,:3]+=np.asarray(chunk.local_to_world(0,0,0),dtype=np.float32)
        vertices.append(data.vertices)
        indices.append(data.indices+np.uint32(offset))
        offset+=len(data.vertices)
    # A paisagem estática compartilha atlas/material: uma única chamada de desenho.
    return [(ChunkMeshData(np.concatenate(vertices),np.concatenate(indices)),mat4_identity())]


class MenuLandscape:
    def __init__(self):
        self.atlas = TextureAtlas(create_gl=True)
        self.shader = Shader(str(ROOT/'assets/shaders/world_textured.vert'),
                             str(ROOT/'assets/shaders/world_textured.frag'))
        self.camera = IsometricCamera(target=vec3(0, 6, 0), ortho_size=23, far=300)
        self.camera.DEFAULT_DISTANCE = 110
        self.meshes = []
        self.started = time.monotonic()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='MenuLandscape')
        from src.interactive.menu_style import warm_menu_surfaces
        self.executor.submit(warm_menu_surfaces)
        self.future = self.executor.submit(build_landscape, self.atlas)
        self.error = None

    def prepare(self, wait=False):
        if self.future is None or (not wait and not self.future.done()):
            return
        try:
            for data, model in self.future.result():
                self.meshes.append((TexturedMesh(data.vertices, data.indices), model))
        except Exception as error:
            self.error = str(error)
            print('[Menu] Paisagem indisponível:', error)
        finally:
            self.future = None
            self.executor.shutdown(wait=False)

    def draw(self, width, height, reduce_motion=False):
        self.prepare()
        if not self.meshes:
            return
        elapsed = 0 if reduce_motion else time.monotonic()-self.started
        self.camera.yaw = math.radians(45 + 4*math.sin(elapsed*.035))
        self.camera.target[0] = 0 if reduce_motion else 1.5*math.sin(elapsed*.025)
        shader = self.shader
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_BLEND)
        shader.use()
        shader.set_mat4('u_Projection', self.camera.get_projection_matrix(width,height))
        shader.set_mat4('u_View', self.camera.get_view_matrix())
        shader.set_bool('u_Skinned', False)
        shader.set_bool('u_UndergroundMode', False)
        shader.set_int('u_CutawayPass', 0)
        shader.set_float('u_Alpha', 1.)
        shader.set_vec3('u_LightDir', .6, 1.2, .4)
        shader.set_vec3('u_LightColor', .85, .76, .58)
        shader.set_vec3('u_AmbientColor', .38, .43, .39)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.atlas.texture_id)
        shader.set_int('u_TextureAtlas', 0)
        for mesh, model in self.meshes:
            shader.set_mat4('u_Model', model)
            mesh.draw()

    def delete(self):
        if self.future:
            self.future.cancel()
        self.executor.shutdown(wait=False, cancel_futures=True)
        for mesh, _ in self.meshes:
            mesh.delete()
        self.atlas.delete()
        self.shader.delete()
