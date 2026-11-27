"""Gera os ladrilhos do baú (``chest_<variante>_<tipo>_<peça>.png``) a partir de ``textures/entity/chest`` do jogo.

O baú do Minecraft é uma entidade: a textura dele é uma folha 64x64 fora de ``textures/block``. Este script recorta dela
as peças que o ``_chest`` de ``src/world/block_shapes.py`` usa (corpo, tampa, topo e fecho) em ladrilhos de 16x16 e os
grava em ``assets/textures/blocks``. Os ladrilhos do projeto saem do pacote Trailers Vision (open source) e ficam no
git; rode de novo ao trocar de pacote. Sem eles, o jogo desenha o baú como uma caixa de tábuas.

Uso:
    python scripts/make_chest_tiles.py FONTE [--saida PASTA]

``FONTE`` é a pasta ``.../textures/entity/chest``, a raiz de um pacote de texturas (pasta ou .zip, com
``assets/minecraft/textures/entity/chest``) ou o ``client.jar`` do jogo.
"""

import argparse
import io
import os
import sys
import zipfile

from PIL import Image

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "assets", "textures", "blocks")
INSIDE = "assets/minecraft/textures/entity/chest/"

# variante -> {tipo: arquivo da folha}
SHEETS = {
    "normal": {"single": "normal.png", "left": "normal_left.png", "right": "normal_right.png"},
    "trapped": {"single": "trapped.png", "left": "trapped_left.png", "right": "trapped_right.png"},
    "ender": {"single": "ender.png"},
}
DEPTH = 14


def open_sheet(source: str, name: str):
    """A folha ``name`` da fonte, ou ``None`` se não está lá."""
    if os.path.isdir(source):
        for root in (source, os.path.join(source, "chest"), os.path.join(source, INSIDE)):
            path = os.path.join(root, name)
            if os.path.isfile(path):
                return Image.open(path).convert("RGBA")
        return None
    with zipfile.ZipFile(source) as archive:
        try:
            return Image.open(io.BytesIO(archive.read(INSIDE + name))).convert("RGBA")
        except KeyError:
            return None


def tiles_of(sheet: Image.Image, kind: str):
    """Os ladrilhos de uma folha: corpo, tampa, topo, fecho e os dois interiores (visíveis com a tampa levantada)."""
    width = 14 if kind == "single" else 15   # cada metade do baú duplo tem 15 de largura
    x0 = 0 if kind == "left" else 1           # onde a arte encosta no ladrilho (a caixa começa em x=1, ou em 0 na "left")
    body = sheet.crop((DEPTH, DEPTH + 5 + DEPTH, DEPTH + width, DEPTH + 5 + DEPTH + 10))
    lid = sheet.crop((DEPTH, DEPTH, DEPTH + width, DEPTH + 5))
    # na folha da tampa o 1º quadrado do alto é o interior (escuro, o que se vê com o baú aberto) e o 2º é o topo de fora
    top = sheet.crop((DEPTH + width, 0, DEPTH + 2 * width, DEPTH))
    # o interior: o 1º quadrado da tampa (a face de baixo dela) e o 2º do corpo (a face de cima dele, o que se vê
    # olhando para dentro do baú); o 1º do corpo é o fundo
    lid_in = sheet.crop((DEPTH, 0, DEPTH + width, DEPTH))
    body_in = sheet.crop((DEPTH + width, DEPTH + 5, DEPTH + 2 * width, DEPTH + 5 + DEPTH))
    # a folha do jogo deixa o fundo do baú transparente ou preto: aqui ele vira madeira escura, para a boca do baú
    # aberto parecer um baú vazio e não um buraco
    INNER = (58, 36, 13, 255)

    def wood(piece: Image.Image) -> Image.Image:
        piece = Image.alpha_composite(Image.new("RGBA", piece.size, INNER), piece)
        pixels = piece.load()
        for x in range(piece.width):
            for y in range(piece.height):
                if sum(pixels[x, y][:3]) < 12:
                    pixels[x, y] = INNER
        return piece

    lid_in, body_in = wood(lid_in), wood(body_in)
    out = {}
    for name, piece, y in (("body", body, 0), ("lid", lid, 0), ("top", top, 1), ("lidin", lid_in, 1),
                           ("bodyin", body_in, 1)):
        tile = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        tile.paste(piece, (x0, y))
        out[name] = tile
    # o fecho: 2 de largura no baú simples; o duplo tem um pedaço de 1 em cada metade, na junção
    lock = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    lock.paste(sheet.crop((1, 1, 3 if kind == "single" else 2, 5)), (1, 1))
    out["lock"] = lock
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera os ladrilhos do baú a partir das texturas de entidade")
    parser.add_argument("fonte", help="pasta chest, raiz de pacote (pasta ou .zip) ou client.jar")
    parser.add_argument("--saida", default=DEFAULT_OUT, help="pasta dos ladrilhos (padrão: assets/textures/blocks)")
    args = parser.parse_args()
    os.makedirs(args.saida, exist_ok=True)
    written = 0
    for variant, kinds in SHEETS.items():
        for kind, filename in kinds.items():
            sheet = open_sheet(args.fonte, filename)
            if sheet is None or sheet.size != (64, 64):
                print(f"Aviso: sem a folha 64x64 '{filename}' nesta fonte; {variant}/{kind} fica sem ladrilhos.")
                continue
            for part, tile in tiles_of(sheet, kind).items():
                tile.save(os.path.join(args.saida, f"chest_{variant}_{kind}_{part}.png"))
                written += 1
    print(f"{written} ladrilhos gravados em {args.saida}.")
    if not written:
        sys.exit(1)


if __name__ == "__main__":
    main()
