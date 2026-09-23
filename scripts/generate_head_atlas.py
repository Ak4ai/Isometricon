"""Gera a textura completa com o rosto idêntico a roupa.jpeg:
- Expressão brava/focada (sobrancelhas inclinadas para dentro, olhar determinado)
- Sem blush (pele limpa sob os olhos)
- Boca larga no queixo
- Detalhe de sombra sob a boca (queixo esculpido)
- Franja 2D bem encaixada com a franja 3D"""
import os
from PIL import Image, ImageDraw

def generate_head_texture():
    os.makedirs("assets/models/textures", exist_ok=True)
    size = (512, 512)
    
    SKIN_BASE    = (250, 227, 210, 255) # Pele suave
    SKIN_SHADOW  = (235, 206, 188, 255) # Sombra base do queixo
    UNDER_MOUTH  = (202, 166, 150, 255) # Detalhe de sombra sob a boca (sulco do queixo)
    MOUTH_COL    = (226, 122, 110, 255) # Boca salmão/coral marcante
    MOUTH_LINE   = (188, 88, 78, 255)   # Linha interna da boca
    
    HAIR_DARK    = (26, 18, 17, 255)
    HAIR_BASE    = (42, 29, 27, 255)
    HAIR_MID     = (58, 40, 36, 255)
    HAIR_LIGHT   = (86, 60, 54, 255)
    
    RIBBON_WHITE = (246, 246, 248, 255)
    RIBBON_SHADE = (218, 218, 224, 255)
    RIBBON_SEAM  = (175, 175, 182, 255)
    
    img = Image.new("RGBA", size, SKIN_BASE)
    draw = ImageDraw.Draw(img)
    
    # =========================================================================
    # ÁREA 1: FACE FRONTAL (X: 0 a 256, Y: 0 a 256)
    # Semblante bravo / focado fiel a roupa.jpeg
    # =========================================================================
    draw.rectangle([0, 0, 256, 256], fill=SKIN_BASE)
    
    # 1.1 Cabelo 2D no topo da testa (Y: 0 a 55)
    draw.rectangle([0, 0, 256, 45], fill=HAIR_BASE)
    for x in range(0, 256, 16):
        col = HAIR_MID if (x // 16) % 2 == 0 else HAIR_BASE
        draw.rectangle([x, 0, x + 16, 45], fill=col)
    teeth = [
        (0, 32, 58), (32, 64, 52), (64, 112, 60),
        (112, 144, 54), (144, 192, 60), (192, 224, 52), (224, 256, 58),
    ]
    for x1, x2, y_bot in teeth:
        draw.rectangle([x1, 45, x2, y_bot], fill=HAIR_BASE)
        draw.rectangle([x1, y_bot - 6, x2, y_bot], fill=HAIR_DARK)
        
    # 1.2 Sobrancelhas Bravas / Determinadas (Inclinadas para dentro: \ / )
    # Canto externo mais alto, canto interno mais baixo!
    brow_col = (42, 28, 26, 255)
    # Sobrancelha esquerda: (X: 38 a 98, Y: 104 descendo para 114)
    draw.polygon([(38, 104), (98, 114), (98, 120), (38, 110)], fill=brow_col)
    # Sobrancelha direita: (X: 158 a 218, Y: 114 subindo para 104)
    draw.polygon([(158, 114), (218, 104), (218, 110), (158, 120)], fill=brow_col)
    
    # 1.3 Olhos Anime Focados / Bravos (Y: 122 a 156)
    # Olhar determinado: pálpebra superior firme inclinada levemente para dentro
    eye_lash = (24, 20, 22, 255)
    sclera = (250, 252, 255, 255)
    iris_dark = (32, 74, 132, 255)
    iris_mid = (48, 128, 202, 255)
    iris_light = (84, 190, 242, 255)
    pupil = (18, 36, 66, 255)
    white = (255, 255, 255, 255)
    
    for cx, is_right in [(70, False), (186, True)]:
        # Esclera
        draw.rectangle([cx - 26, 126, cx + 26, 156], fill=sclera)
        
        # Íris retangular
        draw.rectangle([cx - 19, 128, cx + 19, 155], fill=iris_mid)
        # Sombra superior da íris
        draw.rectangle([cx - 19, 128, cx + 19, 142], fill=iris_dark)
        # Faixa inferior iluminada
        draw.rectangle([cx - 17, 146, cx + 17, 155], fill=iris_light)
        
        # Pupila
        draw.rectangle([cx - 9, 132, cx + 9, 148], fill=pupil)
        
        # Catchlight no canto superior
        draw.rectangle([cx - 15, 130, cx - 5, 140], fill=white)
        # Segundo pequeno brilho
        draw.rectangle([cx + 6, 144, cx + 11, 150], fill=white)
        
        # Delineador superior marcante com inclinação brava/focada
        if is_right:
            # Olho direito: inclinado para dentro
            draw.polygon([(cx - 28, 126), (cx + 28, 120), (cx + 36, 124), (cx + 28, 128), (cx - 28, 132)], fill=eye_lash)
        else:
            # Olho esquerdo: inclinado para dentro
            draw.polygon([(cx - 36, 124), (cx - 28, 120), (cx + 28, 126), (cx + 28, 132), (cx - 28, 128)], fill=eye_lash)
            
        # Linha inferior sutil
        draw.line([(cx - 18, 156), (cx + 18, 156)], fill=(185, 162, 152, 255), width=1)
        
    # 1.4 PELE LIMPA SEM BLUSH (Removido o rosado sob os olhos conforme solicitado!)
    # Nada desenhado aqui: pele lisa e uniforme como na referência roupa.jpeg
    
    # 1.5 Nariz sutil anime (Y: 172 a 178)
    draw.polygon([(126, 172), (130, 172), (128, 178)], fill=(230, 196, 176, 255))
    
    # 1.6 BOCA LARGA NO QUEIXO (Y: 208 a 218, largura de 60px)
    # Posicionada no início do triângulo do queixo
    draw.rectangle([98, 208, 158, 217], fill=MOUTH_COL)
    draw.line([(100, 212), (156, 212)], fill=MOUTH_LINE, width=2)
    
    # 1.7 DETALHE EMBAIXO DA BOCA (Sulco do queixo como em roupa.jpeg!)
    # Sombra horizontal esculpindo o queixo logo abaixo dos lábios
    draw.rectangle([114, 222, 142, 227], fill=UNDER_MOUTH)
    draw.line([(116, 224), (140, 224)], fill=(186, 150, 134, 255), width=1)
    
    # 1.8 Sombra da ponta do queixo (Y: 246 a 256)
    draw.rectangle([0, 248, 256, 256], fill=SKIN_SHADOW)
    
    # =========================================================================
    # ÁREA 2: TOPO E TRASEIRA DO CABELO 2D (X: 256 a 512, Y: 0 a 256)
    # =========================================================================
    draw.rectangle([256, 0, 512, 160], fill=HAIR_BASE)
    for x in range(256, 512, 16):
        col = HAIR_MID if ((x - 256) // 16) % 2 == 0 else HAIR_BASE
        draw.rectangle([x, 0, x + 16, 160], fill=col)
    draw.rectangle([256, 32, 512, 52], fill=HAIR_LIGHT)
    draw.rectangle([348, 128, 420, 160], fill=SKIN_BASE)
    draw.rectangle([348, 128, 420, 136], fill=SKIN_SHADOW)
    
    draw.rectangle([256, 160, 512, 256], fill=HAIR_BASE)
    for x in range(256, 512, 32):
        draw.rectangle([x, 160, x + 16, 256], fill=HAIR_MID)
    draw.rectangle([280, 192, 488, 224], fill=HAIR_LIGHT)
    
    # =========================================================================
    # ÁREA 3: MECHAS 3D (X: 0 a 256, Y: 256 a 512)
    # =========================================================================
    draw.rectangle([0, 256, 256, 512], fill=HAIR_BASE)
    draw.rectangle([0, 256, 256, 320], fill=HAIR_MID)
    draw.rectangle([0, 270, 256, 296], fill=HAIR_LIGHT)
    draw.rectangle([0, 440, 256, 512], fill=HAIR_DARK)
    for x in range(0, 256, 24):
        draw.line([(x, 256), (x, 512)], fill=HAIR_DARK, width=2)
        
    # =========================================================================
    # ÁREA 4: LAÇOS DE FITA (X: 256 a 512, Y: 256 a 512)
    # =========================================================================
    draw.rectangle([256, 256, 512, 512], fill=RIBBON_WHITE)
    draw.rectangle([256, 256, 384, 290], fill=RIBBON_SHADE)
    draw.rectangle([384, 256, 512, 320], fill=RIBBON_SHADE)
    for y in range(260, 510, 10):
        draw.rectangle([318, y, 322, y + 5], fill=RIBBON_SEAM)
        draw.rectangle([446, y, 450, y + 5], fill=RIBBON_SEAM)
        
    out_path = "assets/models/textures/character_head_full.png"
    img.save(out_path)
    print(f"Textura com semblante bravo, sem blush e detalhe no queixo gerada em: {out_path}")

if __name__ == "__main__":
    generate_head_texture()
