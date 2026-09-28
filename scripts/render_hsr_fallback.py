"""Garments without usable Roblox HSR (old 0x10/0x11 data) with the geometric fallback mask.

Output: artifacts/runtime_female/hsr_geometrico_<n>.png (front, 3/4 and back per outfit).
"""
from pathlib import Path
import sys

import glfw
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.render_runtime_before_after as R
from src.rendering.shader import Shader

JEANS, TANK_TOP = 109837605892174, 137915688957785
OUTFITS = [
    ("jaqueta rosa ombro de fora", 9059176760, JEANS),
    ("top branco ombro de fora", 9342134700, JEANS),
    ("bermuda", TANK_TOP, 9174391966),
    ("sunga floral", TANK_TOP, 7192685245),
    ("suéter padrão", 9240757332, JEANS),
    ("suéter oversized", 16185652164, JEANS),
    ("controle: regata + jeans (HSR oficial)", TANK_TOP, JEANS),
    ("moletom com zíper", 7192553841, JEANS),
]


def main():
    R.VIEWS = [("frente", [0.0, 1.0, 2.6]), ("3/4", [-1.8, 1.45, 2.0]), ("costas", [0.0, 1.0, -2.6])]
    size = 300
    R.SIZE = size
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(size, size, "HsrFallback", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, size, size)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    for sheet_index in range(0, len(OUTFITS), 4):
        chunk = OUTFITS[sheet_index:sheet_index + 4]
        sheet = Image.new("RGB", (size * 3 * 2, (size + 24) * 2), "white")
        draw = ImageDraw.Draw(sheet)
        for slot, (name, top, bottom) in enumerate(chunk):
            tiles = R.render_outfit(shader, top, bottom)
            x, y = (slot % 2) * size * 3, (slot // 2) * (size + 24)
            draw.text((x + 4, y + 5), name, fill="black")
            for k, tile in enumerate(tiles):
                sheet.paste(tile, (x + k * size, y + 24))
        path = R.OUT / f"hsr_geometrico_{sheet_index // 4 + 1}.png"
        sheet.save(path)
        print("[OK]", path, flush=True)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
