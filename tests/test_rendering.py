"""Testes unitários para o módulo de renderização (Shader e Mesh)."""

import os
import glfw
import pytest
import numpy as np

from src.rendering import Shader, Mesh


@pytest.fixture(scope="module")
def gl_context():
    """Inicializa um contexto OpenGL headless/invisível para testes de GPU."""
    if not glfw.init():
        pytest.skip("GLFW não pôde ser inicializado no ambiente de teste")

    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)

    window = glfw.create_window(64, 64, "Test", None, None)
    if not window:
        glfw.terminate()
        pytest.skip("Contexto OpenGL 3.3 Core não suportado ou sem display neste ambiente")

    glfw.make_context_current(window)
    yield window

    glfw.destroy_window(window)
    glfw.terminate()


def test_shader_file_not_found():
    """Verifica se FileNotFound é lançado para arquivos inexistentes."""
    with pytest.raises(FileNotFoundError):
        Shader("assets/shaders/inexistente.vert", "assets/shaders/world.frag")


def test_shader_compilation(gl_context):
    """Verifica a compilação e linkagem dos shaders padrão do mundo."""
    shader = Shader("assets/shaders/world.vert", "assets/shaders/world.frag")
    assert shader.program_id > 0

    shader.use()
    # Testar upload de uniforms
    shader.set_mat4("u_Model", np.identity(4, dtype=np.float32))
    shader.set_vec3("u_LightDir", 0.5, 1.0, 0.3)
    shader.set_vec3("u_LightColor", 1.0, 1.0, 1.0)
    shader.set_vec3("u_AmbientColor", 0.2, 0.2, 0.2)
    shader.set_bool("u_UseInstancing", False)

    shader.delete()
    assert shader.program_id == 0


def test_mesh_creation_and_draw(gl_context):
    """Verifica a criação de buffers VAO/VBO/EBO e chamada de desenho."""
    # Vértice simples: [pos(3), norm(3), col(3)]
    vertices = np.array([
        -0.5, -0.5, 0.0,  0.0, 0.0, 1.0,  1.0, 0.0, 0.0,
         0.5, -0.5, 0.0,  0.0, 0.0, 1.0,  0.0, 1.0, 0.0,
         0.0,  0.5, 0.0,  0.0, 0.0, 1.0,  0.0, 0.0, 1.0,
    ], dtype=np.float32)

    indices = np.array([0, 1, 2], dtype=np.uint32)

    mesh = Mesh(vertices, indices)
    assert mesh.vao > 0
    assert mesh.vbo > 0
    assert mesh.ebo is not None
    assert mesh.index_count == 3

    # Desenho sem erros
    mesh.draw()

    mesh.delete()
    assert mesh.vao == 0


def test_chunk_mesh_textured_upload_and_draw(gl_context):
    """Contrato real CPU → TexturedMesh → shader texturizado → GPU."""
    import OpenGL.GL as gl
    from src.rendering import TexturedMesh
    from src.world import BlockType, Chunk3D, ChunkMesher

    chunk = Chunk3D()
    chunk.blocks[:2, :2, :2] = BlockType.STONE
    data = ChunkMesher().build(chunk)
    shader = Shader('assets/shaders/world_textured.vert', 'assets/shaders/world_textured.frag')
    mesh = None
    texture = gl.glGenTextures(1)
    try:
        mesh = TexturedMesh(data.vertices, data.indices)
        assert mesh.vertex_count == 96
        assert mesh.index_count == 144
        gl.glBindVertexArray(mesh.vao)
        for attribute, size in enumerate((3, 3, 2, 3)):
            assert gl.glGetVertexAttribiv(attribute, gl.GL_VERTEX_ATTRIB_ARRAY_SIZE)[0] == size
            assert gl.glGetVertexAttribiv(attribute, gl.GL_VERTEX_ATTRIB_ARRAY_STRIDE)[0] == 44
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, mesh.vbo)
        uploaded = gl.glGetBufferSubData(gl.GL_ARRAY_BUFFER, 0, data.vertices.nbytes)
        assert uploaded.tobytes() == data.vertices.tobytes()
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, mesh.ebo)
        uploaded = gl.glGetBufferSubData(gl.GL_ELEMENT_ARRAY_BUFFER, 0, data.indices.nbytes)
        assert uploaded.tobytes() == data.indices.tobytes()
        shader.use()
        for uniform in ('u_Model', 'u_View', 'u_Projection'):
            shader.set_mat4(uniform, np.identity(4, dtype=np.float32))
        shader.set_vec3('u_LightDir', 0.5, 1.0, 0.3)
        shader.set_vec3('u_LightColor', 1.0, 1.0, 1.0)
        shader.set_vec3('u_AmbientColor', 0.3, 0.3, 0.3)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 1, 1, 0,
                        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, np.full(4, 255, dtype=np.uint8))
        shader.set_int('u_TextureAtlas', 0)
        mesh.draw()
        assert gl.glGetError() == gl.GL_NO_ERROR
        empty = ChunkMesher().build(Chunk3D())
        mesh.update_buffers(empty.vertices, empty.indices)
        assert mesh.vertex_count == mesh.index_count == 0
        mesh.draw()
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        gl.glBindVertexArray(0)
        shader.unbind()
        if mesh is not None:
            mesh.delete()
        shader.delete()
        gl.glDeleteTextures(1, [texture])
