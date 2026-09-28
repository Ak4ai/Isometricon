"""Render the accepted catalog sample on the female body (front and back), six garments per sheet.

Tops are worn with the default jeans; bottoms with the tank top; dresses alone.
Output: artifacts/runtime_female/catalogo_<n>.png
"""
import json
from pathlib import Path
import sys

import glfw
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.render_runtime_before_after as R
from src.rendering.shader import Shader

BOTTOM_TYPES = {66, 69, 70, 71, 72}
JEANS, TANK_TOP = 109837605892174, 137915688957785


def main():
    results = json.loads((ROOT / "artifacts/roblox_ground_truth/catalog_robustness.json").read_text(encoding="utf-8"))
    garments = [(asset, row) for asset, row in results.items() if row.get("aceita_pelo_runtime")]
    R.VIEWS = [("frente", [0.0, 1.0, 2.6]), ("costas", [0.0, 1.0, -2.6])]
    size = 300
    R.SIZE = size
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(size, size, "Catalog", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, size, size)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    for sheet_index in range(0, len(garments), 6):
        chunk = garments[sheet_index:sheet_index + 6]
        sheet = Image.new("RGB", (size * 2 * 3, (size + 24) * 2), "white")
        draw = ImageDraw.Draw(sheet)
        for slot, (asset, row) in enumerate(chunk):
            name = row["nome"].lower()
            if "dress" in name or "gown" in name:
                top, bottom = int(asset), None
            elif row["type_id"] in BOTTOM_TYPES:
                top, bottom = TANK_TOP, int(asset)
            else:
                top, bottom = int(asset), JEANS
            tiles = R.render_outfit(shader, top, bottom)
            x, y = (slot % 3) * size * 2, (slot // 3) * (size + 24)
            draw.text((x + 4, y + 5), f"{row['nome'][:34]} ({asset})", fill="black")
            for k, tile in enumerate(tiles):
                sheet.paste(tile, (x + k * size, y + 24))
        path = R.OUT / f"catalogo_{sheet_index // 6 + 1}.png"
        sheet.save(path)
        print("[OK]", path, flush=True)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
