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
