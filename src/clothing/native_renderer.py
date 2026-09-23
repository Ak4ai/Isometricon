"""Renderizador 100% Python Nativo (Independente do Blender).

Renderiza o avatar completo com rosto anime, cabelo, roupas Roblox,
iluminação direcional dupla calibrada, gamma correction e Z-Buffer HSR (Hardware Hidden Surface Removal)
via OpenGL 3.3 Core Profile em contexto headless (invisível) via GLFW.
"""

import os
import sys
import math
import ctypes
import json
import numpy as np
import OpenGL.GL as gl
import glfw
from PIL import Image

VERTEX_SHADER_SRC = """#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;
layout (location = 2) in vec2 aTexCoord;
layout (location = 3) in vec3 aColor;

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 u_Projection;

out vec3 v_FragPos;
out vec3 v_Normal;
out vec2 v_TexCoord;
out vec3 v_Color;

void main()
{
    vec4 worldPos = u_Model * vec4(aPos, 1.0);
    v_FragPos = worldPos.xyz;
    v_Normal = mat3(transpose(inverse(u_Model))) * aNormal;
    v_TexCoord = aTexCoord;
    v_Color = aColor;
    gl_Position = u_Projection * u_View * worldPos;
}
"""

FRAGMENT_SHADER_SRC = """#version 330 core
in vec3 v_FragPos;
in vec3 v_Normal;
in vec2 v_TexCoord;
in vec3 v_Color;

out vec4 FragColor;

uniform sampler2D u_Texture;
uniform bool u_HasTexture;
uniform vec3 u_LightDir1;
uniform vec3 u_LightDir2;
uniform vec3 u_LightColor1;
uniform vec3 u_LightColor2;
uniform vec3 u_AmbientColor;
uniform vec3 u_CamPos;

void main()
{
    vec4 texColor = u_HasTexture ? texture(u_Texture, v_TexCoord) : vec4(1.0);
    if (texColor.a < 0.1) {
        discard;
    }

    vec3 norm = normalize(v_Normal);
    vec3 viewDir = normalize(u_CamPos - v_FragPos);

    // Key Light
    vec3 l1 = normalize(u_LightDir1);
    float diff1 = max(dot(norm, l1), 0.0);
    vec3 diffuse1 = diff1 * u_LightColor1;

    // Fill Light
    vec3 l2 = normalize(u_LightDir2);
    float diff2 = max(dot(norm, l2), 0.0);
    vec3 diffuse2 = diff2 * u_LightColor2;

    // Specular Blinn-Phong sutil
    vec3 halfDir = normalize(l1 + viewDir);
    float spec = pow(max(dot(norm, halfDir), 0.0), 24.0);
    vec3 specular = 0.06 * spec * u_LightColor1;

    vec3 baseColor = texColor.rgb * v_Color;
    vec3 linearRgb = (u_AmbientColor + diffuse1 + diffuse2) * baseColor + specular;

    // Gamma correction sRGB
    vec3 sRgb = pow(max(linearRgb, vec3(0.0)), vec3(1.0 / 2.2));

    FragColor = vec4(sRgb, texColor.a);
}
"""

def perspective(fovy, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m

def look_at(eye, center, up):
    eye = np.array(eye, dtype=np.float32)
    center = np.array(center, dtype=np.float32)
    up = np.array(up, dtype=np.float32)
    f = center - eye
    f /= np.linalg.norm(f)
    u = up / np.linalg.norm(up)
    s = np.cross(f, u)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    t = np.identity(4, dtype=np.float32)
    t[:3, 3] = -eye
    return m @ t

class NativeRenderer:
    """Renderizador OpenGL Core 3.3 headless para geração de imagens sem o Blender."""

    def __init__(self, width=1024, height=1024):
        self.width = width
        self.height = height
        self._init_context()
        self._init_shaders()
        self._init_white_texture()

    def _init_context(self):
        if not glfw.init():
            raise RuntimeError("Falha ao inicializar GLFW.")
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.SAMPLES, 4)
        self.window = glfw.create_window(self.width, self.height, "HeadlessRenderer", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Falha ao criar janela offscreen GLFW.")
        glfw.make_context_current(self.window)

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glEnable(gl.GL_MULTISAMPLE)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glViewport(0, 0, self.width, self.height)

    def _init_shaders(self):
        vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vs, VERTEX_SHADER_SRC)
        gl.glCompileShader(vs)
        if not gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS):
            raise RuntimeError(f"Erro no Vertex Shader: {gl.glGetShaderInfoLog(vs).decode()}")

        fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(fs, FRAGMENT_SHADER_SRC)
        gl.glCompileShader(fs)
        if not gl.glGetShaderiv(fs, gl.GL_COMPILE_STATUS):
            raise RuntimeError(f"Erro no Fragment Shader: {gl.glGetShaderInfoLog(fs).decode()}")

        self.program = gl.glCreateProgram()
        gl.glAttachShader(self.program, vs)
        gl.glAttachShader(self.program, fs)
        gl.glLinkProgram(self.program)
        if not gl.glGetProgramiv(self.program, gl.GL_LINK_STATUS):
            raise RuntimeError(f"Erro no Link do Shader: {gl.glGetProgramInfoLog(self.program).decode()}")

        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

        self.u_Model = gl.glGetUniformLocation(self.program, "u_Model")
        self.u_View = gl.glGetUniformLocation(self.program, "u_View")
        self.u_Projection = gl.glGetUniformLocation(self.program, "u_Projection")
        self.u_Texture = gl.glGetUniformLocation(self.program, "u_Texture")
        self.u_HasTexture = gl.glGetUniformLocation(self.program, "u_HasTexture")
        self.u_LightDir1 = gl.glGetUniformLocation(self.program, "u_LightDir1")
        self.u_LightDir2 = gl.glGetUniformLocation(self.program, "u_LightDir2")
        self.u_LightColor1 = gl.glGetUniformLocation(self.program, "u_LightColor1")
        self.u_LightColor2 = gl.glGetUniformLocation(self.program, "u_LightColor2")
        self.u_AmbientColor = gl.glGetUniformLocation(self.program, "u_AmbientColor")
        self.u_CamPos = gl.glGetUniformLocation(self.program, "u_CamPos")

    def _init_white_texture(self):
        white_pixel = np.array([255, 255, 255, 255], dtype=np.uint8)
        self.white_tex = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.white_tex)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 1, 1, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, white_pixel)

    def load_texture(self, png_path):
        if not png_path or not os.path.exists(png_path):
            return self.white_tex
        img = Image.open(png_path).convert("RGBA")
        img_data = np.array(img, dtype=np.uint8)
        tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, img.width, img.height, 0,
            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data
        )
        return tex_id

    def load_texture_from_image(self, img):
        """Carrega uma textura OpenGL diretamente de uma instância PIL.Image sem salvar em disco."""
        if img is None:
            return self.white_tex
        img = img.convert("RGBA")
        img_data = np.array(img, dtype=np.uint8)
        tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, img.width, img.height, 0,
            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data
        )
        return tex_id

    def load_clean_obj_groups(self, obj_path, allowed_prefixes, default_color=(1.0, 1.0, 1.0)):
        """Carrega apenas os grupos permitidos de character_clean.obj com coordenadas OpenGL."""
        if not os.path.exists(obj_path):
            return None
        raw_v = []
        raw_vt = []
        raw_vn = []
        faces = []

        current_o = None
        include_face = False

        with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0] == "o" or parts[0] == "g":
                    current_o = parts[1]
                    include_face = any(current_o.startswith(p) for p in allowed_prefixes)
                elif parts[0] == "v":
                    raw_v.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif parts[0] == "vt":
                    raw_vt.append([float(parts[1]), float(parts[2])])
                elif parts[0] == "vn":
                    raw_vn.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif parts[0] == "f" and include_face:
                    faces.append(parts[1:])

        if not raw_v or not faces:
            return None

        v_data = []
        indices = []
        vert_cache = {}

        for face in faces:
            face_indices = []
            for token in face:
                if token in vert_cache:
                    face_indices.append(vert_cache[token])
                    continue
                sub = token.split("/")
                v_idx = int(sub[0]) - 1
                vt_idx = int(sub[1]) - 1 if len(sub) > 1 and sub[1] else -1
                vn_idx = int(sub[2]) - 1 if len(sub) > 2 and sub[2] else -1

                bx, by, bz = raw_v[v_idx]
                pos = [bx, by, bz]

                if vn_idx >= 0 and vn_idx < len(raw_vn):
                    nx, ny, nz = raw_vn[vn_idx]
                    norm = [nx, ny, nz]
                else:
                    norm = [0.0, 1.0, 0.0]

                if vt_idx >= 0 and vt_idx < len(raw_vt):
                    uv = [raw_vt[vt_idx][0], 1.0 - raw_vt[vt_idx][1]]
                else:
                    uv = [0.5, 0.5]

                idx = len(v_data) // 11
                v_data.extend(pos)
                v_data.extend(norm)
                v_data.extend(uv)
                v_data.extend(default_color)
                vert_cache[token] = idx
                face_indices.append(idx)

            for i in range(1, len(face_indices) - 1):
                indices.extend([face_indices[0], face_indices[i], face_indices[i + 1]])

        v_arr = np.array(v_data, dtype=np.float32)
        i_arr = np.array(indices, dtype=np.uint32)

        vao = gl.glGenVertexArrays(1)
        vbo = gl.glGenBuffers(1)
        ebo = gl.glGenBuffers(1)

        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, v_arr.nbytes, v_arr, gl.GL_STATIC_DRAW)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, i_arr.nbytes, i_arr, gl.GL_STATIC_DRAW)

        stride = 11 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(12))
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(24))
        gl.glEnableVertexAttribArray(3)
        gl.glVertexAttribPointer(3, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(32))
        gl.glBindVertexArray(0)

        return {"vao": vao, "vbo": vbo, "ebo": ebo, "count": len(i_arr)}

    def load_obj_as_mesh(self, obj_path, default_color=(1.0, 1.0, 1.0)):
        """Carrega OBJ e calcula normais por triângulo caso não existam."""
        if not os.path.exists(obj_path):
            return None
        raw_v = []
        raw_vt = []
        raw_vn = []
        faces = []

        with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("# Arm hidden") or line.startswith("# Forearm hidden"):
                    return None
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0] == "v":
                    raw_v.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif parts[0] == "vt":
                    raw_vt.append([float(parts[1]), float(parts[2])])
                elif parts[0] == "vn":
                    raw_vn.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif parts[0] == "f":
                    faces.append(parts[1:])

        if not raw_v or not faces:
            return None

        v_data = []
        indices = []

        # Para garantir normais corretas com shading sem normais no OBJ, calcula por face
        for face in faces:
            face_tokens = face
            tri_sub_indices = []
            for token in face_tokens:
                sub = token.split("/")
                v_idx = int(sub[0]) - 1
                vt_idx = int(sub[1]) - 1 if len(sub) > 1 and sub[1] else -1
                vn_idx = int(sub[2]) - 1 if len(sub) > 2 and sub[2] else -1

                bx, by, bz = raw_v[v_idx]
                pos = [bx, bz, -by]

                if vn_idx >= 0 and vn_idx < len(raw_vn):
                    nx, ny, nz = raw_vn[vn_idx]
                    norm = [nx, nz, -ny]
                else:
                    norm = None

                if vt_idx >= 0 and vt_idx < len(raw_vt):
                    uv = [raw_vt[vt_idx][0], 1.0 - raw_vt[vt_idx][1]]
                else:
                    uv = [0.5, 0.5]

                tri_sub_indices.append((pos, norm, uv))

            # Triangularizar e computar normal geométrica se faltar
            for i in range(1, len(tri_sub_indices) - 1):
                p0, n0, uv0 = tri_sub_indices[0]
                p1, n1, uv1 = tri_sub_indices[i]
                p2, n2, uv2 = tri_sub_indices[i + 1]

                if n0 is None:
                    # Calcula normal do triângulo
                    v10 = np.array(p1) - np.array(p0)
                    v20 = np.array(p2) - np.array(p0)
                    fn = np.cross(v10, v20)
                    norm_len = np.linalg.norm(fn)
                    fn = list(fn / norm_len) if norm_len > 1e-7 else [0.0, 1.0, 0.0]
                    n0, n1, n2 = fn, fn, fn

                for p, n, u in [(p0, n0, uv0), (p1, n1, uv1), (p2, n2, uv2)]:
                    curr_idx = len(v_data) // 11
                    v_data.extend(p)
                    v_data.extend(n)
                    v_data.extend(u)
                    v_data.extend(default_color)
                    indices.append(curr_idx)

        v_arr = np.array(v_data, dtype=np.float32)
        i_arr = np.array(indices, dtype=np.uint32)

        vao = gl.glGenVertexArrays(1)
        vbo = gl.glGenBuffers(1)
        ebo = gl.glGenBuffers(1)

        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, v_arr.nbytes, v_arr, gl.GL_STATIC_DRAW)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, i_arr.nbytes, i_arr, gl.GL_STATIC_DRAW)

        stride = 11 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(12))
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(24))
        gl.glEnableVertexAttribArray(3)
        gl.glVertexAttribPointer(3, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(32))
        gl.glBindVertexArray(0)

        return {"vao": vao, "vbo": vbo, "ebo": ebo, "count": len(i_arr)}

    def render_scene(self, meshes_list, cam_pos=(0.0, 1.05, 2.75), cam_target=(0.0, 0.95, 0.0), fovy=40.0):
        """Renderiza a cena na GPU offscreen com Z-Buffer HSR ativo."""
        gl.glClearColor(0.18, 0.18, 0.20, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        gl.glUseProgram(self.program)

        proj = perspective(fovy, float(self.width) / float(self.height), 0.1, 50.0)
        view = look_at(cam_pos, cam_target, [0.0, 1.0, 0.0])
        model = np.identity(4, dtype=np.float32)

        gl.glUniformMatrix4fv(self.u_Projection, 1, gl.GL_FALSE, proj.T)
        gl.glUniformMatrix4fv(self.u_View, 1, gl.GL_FALSE, view.T)
        gl.glUniformMatrix4fv(self.u_Model, 1, gl.GL_FALSE, model.T)

        gl.glUniform3f(self.u_CamPos, cam_pos[0], cam_pos[1], cam_pos[2])
        # Iluminação equilibrada
        gl.glUniform3f(self.u_LightDir1, -0.5, 1.1, 0.9)
        gl.glUniform3f(self.u_LightColor1, 0.75, 0.75, 0.78)
        gl.glUniform3f(self.u_LightDir2, 0.6, -0.2, -0.6)
        gl.glUniform3f(self.u_LightColor2, 0.22, 0.24, 0.28)
        gl.glUniform3f(self.u_AmbientColor, 0.35, 0.35, 0.38)

        for item in meshes_list:
            mesh = item["mesh"]
            tex_id = item.get("tex_id", self.white_tex)
            has_tex = (tex_id != self.white_tex)

            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
            gl.glUniform1i(self.u_Texture, 0)
            gl.glUniform1i(self.u_HasTexture, 1 if has_tex else 0)

            gl.glBindVertexArray(mesh["vao"])
            gl.glDrawElements(gl.GL_TRIANGLES, mesh["count"], gl.GL_UNSIGNED_INT, None)
            gl.glBindVertexArray(0)

        gl.glFinish()

        pixels = gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        img = Image.frombytes("RGBA", (self.width, self.height), pixels).transpose(Image.FLIP_TOP_BOTTOM)
        return img

    def destroy(self):
        if hasattr(self, "window") and self.window:
            glfw.destroy_window(self.window)
            glfw.terminate()
            self.window = None

def render_native_outfit(
    top_id,
    bottom_id,
    label,
    output_front,
    output_back,
    output_iso,
    customization=None,
    tool_id=None
):
    """Executa a renderização 100% nativa em Python de um outfit com customização modular e HSR rigoroso."""
    from src.clothing.customization import AvatarCustomization, HeadAtlasBuilder
    if customization is None:
        customization = AvatarCustomization()

    base_dir = r"C:/Users/Henrique/Documents/GitHub/Isometricon"
    models_dir = os.path.join(base_dir, "assets", "models")
    clean_obj = os.path.join(models_dir, "character_clean.obj")
    skin_color = list(customization.skin_color_rgb)

    from src.clothing.wear_engine import RobloxWearEngine
    engine = RobloxWearEngine()
    wear_data = engine.wear(top_id)

    is_long = wear_data.get("is_long_sleeves", False)
    is_short = wear_data.get("is_short_sleeves", False)
    is_sleeveless = wear_data.get("is_sleeveless", False)

    renderer = NativeRenderer(width=1024, height=1024)

    # 1. Gera textura atlas dinâmica para a cabeça (Rosto e Cabelo opcionais e customizáveis)
    atlas_builder = HeadAtlasBuilder()
    head_img = atlas_builder.build_atlas(customization)
    head_tex_id = renderer.load_texture_from_image(head_img)

    draw_list = []

    # Suporte modular para Cabeça Arredondada (compatível com Roblox) ou Quadrada (Blocky)
    if customization.is_rounded_head:
        rounded_head_obj = os.path.join(models_dir, "character_head_rounded.obj")
        head_mesh = renderer.load_clean_obj_groups(rounded_head_obj, [""])
        if head_mesh:
            draw_list.append({"mesh": head_mesh, "tex_id": head_tex_id})
        if customization.should_render_3d_nose:
            nose_mesh = renderer.load_clean_obj_groups(clean_obj, ["Export_nariz"])
            if nose_mesh:
                draw_list.append({"mesh": nose_mesh, "tex_id": head_tex_id})
        if customization.should_render_3d_hair and not customization.custom_hair_obj:
            hair_mesh = renderer.load_clean_obj_groups(clean_obj, ["Export_cabelo"])
            if hair_mesh:
                draw_list.append({"mesh": hair_mesh, "tex_id": head_tex_id})
    else:
        allowed_groups = ["Export_cabeca"]
        if customization.should_render_3d_hair and not customization.custom_hair_obj:
            allowed_groups.append("Export_cabelo")
        if customization.should_render_3d_nose:
            allowed_groups.append("Export_nariz")
        head_mesh = renderer.load_clean_obj_groups(clean_obj, allowed_groups)
        if head_mesh:
            draw_list.append({"mesh": head_mesh, "tex_id": head_tex_id})

    # Cabelo 3D customizado (ex: cabelo Roblox Mesh/OBJ ajustado)
    if customization.custom_hair_obj and os.path.exists(customization.custom_hair_obj):
        custom_hair_mesh = renderer.load_clean_obj_groups(customization.custom_hair_obj, [""])
        hair_tex = getattr(customization, "custom_hair_tex", None)
        if hair_tex and os.path.exists(hair_tex):
            hair_tex_id = renderer.load_texture(hair_tex)
        else:
            # Sincroniza a malha 3D com a cor exata do cabelo escolhida (hair_rgb_255)
            hair_rgb = getattr(customization, "hair_rgb_255", (92, 62, 54))
            solid_hair = Image.new("RGBA", (16, 16), hair_rgb + (255,))
            hair_tex_id = renderer.load_texture_from_image(solid_hair)
        if custom_hair_mesh:
            draw_list.append({"mesh": custom_hair_mesh, "tex_id": hair_tex_id})

    neck_mesh = renderer.load_clean_obj_groups(clean_obj, ["Export_pecoco"], default_color=skin_color)
    if neck_mesh:
        draw_list.append({"mesh": neck_mesh, "tex_id": renderer.white_tex})

    # 2. HSR dos Membros (Braços e Antebraços):
    # - Manga Longa: Braços e Antebraços cobertos pelo tecido (ocultos)
    # - Manga Curta: Braço superior fatiado estanque, Antebraço visível
    # - Regata: Braço superior completo visível, Antebraço visível
    for side in ["left", "right"]:
        arm_path = os.path.join(models_dir, f"character_native_arm_{side}.obj")
        arm_mesh = renderer.load_obj_as_mesh(arm_path, default_color=skin_color)
        if arm_mesh:
            draw_list.append({"mesh": arm_mesh, "tex_id": renderer.white_tex})

        forearm_path = os.path.join(models_dir, f"character_native_forearm_{side}.obj")
        forearm_mesh = renderer.load_obj_as_mesh(forearm_path, default_color=skin_color)
        if forearm_mesh:
            draw_list.append({"mesh": forearm_mesh, "tex_id": renderer.white_tex})

    # 3. Top (Camisa/Regata/Suéter)
    top_obj_path = os.path.join(models_dir, f"character_native_{top_id}.obj")
    top_mesh = renderer.load_obj_as_mesh(top_obj_path)
    top_tex_id = renderer.load_texture(wear_data["tex_path"])
    if top_mesh:
        draw_list.append({"mesh": top_mesh, "tex_id": top_tex_id})

    # 4. Bottom (Calça Jeans + Botas)
    bottom_obj_path = os.path.join(models_dir, f"character_native_{bottom_id}.obj")
    bottom_mesh = renderer.load_obj_as_mesh(bottom_obj_path)
    bottom_tex_path = os.path.join(base_dir, "assets", "models", "clothing", "Black_Distressed_Designer_Jeans_w__Boots_109837605892174.png")
    bottom_tex_id = renderer.load_texture(bottom_tex_path)
    if bottom_mesh:
        draw_list.append({"mesh": bottom_mesh, "tex_id": bottom_tex_id})

    # 4.5 Tool / Arma / Katana (opcional)
    if tool_id is not None:
        tool_data = engine.equip_tool(tool_id)
        tool_mesh = renderer.load_obj_as_mesh(tool_data["output_obj"])
        tool_tex_id = renderer.load_texture(tool_data["tex_path"])
        if tool_mesh:
            draw_list.append({"mesh": tool_mesh, "tex_id": tool_tex_id})

    # 5. Render Frente
    img_front = renderer.render_scene(
        draw_list,
        cam_pos=(0.0, 1.05, 2.75),
        cam_target=(0.0, 0.95, 0.0),
        fovy=40.0
    )
    img_front.save(output_front)
    print(f"[OK] Render Frente salvo: {output_front}")

    # 6. Render Costas
    img_back = renderer.render_scene(
        draw_list,
        cam_pos=(0.0, 1.05, -2.75),
        cam_target=(0.0, 0.95, 0.0),
        fovy=40.0
    )
    img_back.save(output_back)
    print(f"[OK] Render Costas salvo: {output_back}")

    # 7. Render Isométrica 3/4
    img_iso = renderer.render_scene(
        draw_list,
        cam_pos=(-1.9, 1.55, 2.3),
        cam_target=(0.0, 0.95, 0.0),
        fovy=38.0
    )
    img_iso.save(output_iso)
    print(f"[OK] Render Isométrica 3/4 salvo: {output_iso}")

    renderer.destroy()
    return img_front, img_back, img_iso

def render_all_three_outfits():
    """Gera todas as imagens de teste para as 3 categorias (Regata, Manga Curta, Manga Longa) 100% em Python."""
    out_dir = r"C:/Users/Henrique/Documents/GitHub/Isometricon/assets/renders"
    os.makedirs(out_dir, exist_ok=True)
    bottom_id = 109837605892174

    outfits = [
        {"id": 97346273111638, "label": "jersey"},
        {"id": 89475537632859, "label": "boxy"},
        {"id": 9240757332, "label": "sweater"},
    ]

    for item in outfits:
        aid = item["id"]
        lbl = item["label"]
        print(f"\n==================================================")
        print(f"  RENDERIZANDO 100% PYTHON: {lbl.upper()} ({aid})")
        print(f"==================================================")
        render_native_outfit(
            top_id=aid,
            bottom_id=bottom_id,
            label=lbl,
            output_front=os.path.join(out_dir, f"native_python_{lbl}_front.png"),
            output_back=os.path.join(out_dir, f"native_python_{lbl}_back.png"),
            output_iso=os.path.join(out_dir, f"native_python_{lbl}_iso.png")
        )

def render_customization_showcase():
    """Gera um showcase abrangente demonstrando a opcionalidade total e a variedade de rostos e cabelos."""
    from src.clothing.customization import AvatarCustomization, FaceOption, HairStyle, HairColor

    out_dir = r"C:/Users/Henrique/Documents/GitHub/Isometricon/assets/renders"
    os.makedirs(out_dir, exist_ok=True)
    bottom_id = 109837605892174 # Jeans

    showcases = [
        # 1. Totalmente Opcional: Careca + Sem Rosto (Manequim / Voxel liso)
        {
            "top_id": 97346273111638,
            "name": "custom_bald_faceless",
            "desc": "Careca + Sem Rosto (Opcionalidade Total)",
            "cust": AvatarCustomization(face=FaceOption.BLANK, hair_style=HairStyle.BALD),
        },
        # 2. Loiro Dourado + Olhos Verdes Esmeralda
        {
            "top_id": 89475537632859,
            "name": "custom_blonde_green_eyes",
            "desc": "Loiro Dourado + Olhos Verdes",
            "cust": AvatarCustomization(face=FaceOption.ANIME_GREEN, hair_style=HairStyle.ANIME_LONG, hair_color=HairColor.BLONDE),
        },
        # 3. Rosa Pastel + Piscadela Animada
        {
            "top_id": 9240757332,
            "name": "custom_pink_wink",
            "desc": "Rosa Pastel + Piscadela Animada",
            "cust": AvatarCustomization(face=FaceOption.ANIME_WINK, hair_style=HairStyle.ANIME_LONG, hair_color=HairColor.PINK),
        },
        # 4. Preto Corvo + Olhos Castanhos Âmbar
        {
            "top_id": 89475537632859,
            "name": "custom_black_brown_eyes",
            "desc": "Preto Corvo + Olhos Castanhos",
            "cust": AvatarCustomization(face=FaceOption.ANIME_BROWN, hair_style=HairStyle.ANIME_LONG, hair_color=HairColor.BLACK),
        },
        # 5. Prateado Platinado + Olhos Violeta Ametista
        {
            "top_id": 9240757332,
            "name": "custom_silver_purple_eyes",
            "desc": "Prateado / Branco + Olhos Violeta",
            "cust": AvatarCustomization(face=FaceOption.ANIME_PURPLE, hair_style=HairStyle.ANIME_LONG, hair_color=HairColor.SILVER),
        },
        # 6. Sorriso Retrô Clássico + Castanho
        {
            "top_id": 97346273111638,
            "name": "custom_classic_smile",
            "desc": "Sorriso Retrô Clássico + Castanho",
            "cust": AvatarCustomization(face=FaceOption.CLASSIC_SMILE, hair_style=HairStyle.ANIME_LONG, hair_color=HairColor.BRUNETTE),
        },
        # 7. Careca + Rosto Anime Azul (Demonstra que o rosto funciona sem cabelo)
        {
            "top_id": 89475537632859,
            "name": "custom_bald_anime_face",
            "desc": "Careca + Rosto Anime",
            "cust": AvatarCustomization(face=FaceOption.ANIME_BLUE, hair_style=HairStyle.BALD),
        },
    ]

    for item in showcases:
        name = item["name"]
        desc = item["desc"]
        aid = item["top_id"]
        cust = item["cust"]
        print(f"\n==================================================")
        print(f"  CUSTOMIZAÇÃO: {desc.upper()} ({name})")
        print(f"==================================================")
        render_native_outfit(
            top_id=aid,
            bottom_id=bottom_id,
            label=name,
            output_front=os.path.join(out_dir, f"{name}_front.png"),
            output_back=os.path.join(out_dir, f"{name}_back.png"),
            output_iso=os.path.join(out_dir, f"{name}_iso.png"),
            customization=cust,
        )

if __name__ == "__main__":
    render_customization_showcase()
