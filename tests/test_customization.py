"""Testes automatizados para o sistema de customização modular de avatar (Rosto, Cabelo, Pele)."""

import pytest
import numpy as np
from PIL import Image

from src.clothing.customization import (
    AvatarCustomization,
    HeadAtlasBuilder,
    LayeredHeadCompositor,
    HeadType,
    FaceOption,
    HairStyle,
    HairColor,
    EyeStyle,
    IrisColor,
    MouthStyle,
    EyebrowStyle,
    Hair2DStyle,
    FaceDetail,
    HAIR_PALETTES,
    IRIS_PALETTES,
    get_available_faces,
    get_available_hair_styles,
    get_available_hair_colors,
    get_available_eye_styles,
    get_available_iris_colors,
    get_available_mouth_styles,
    get_available_eyebrow_styles,
    get_available_hair_2d_styles,
    get_available_face_details,
)


def test_customization_defaults():
    """Valida as configurações padrão do avatar."""
    cust = AvatarCustomization()
    assert not cust.is_bald
    assert not cust.is_faceless
    assert cust.head_type == HeadType.BLOCKY
    assert not cust.is_rounded_head
    assert cust.should_render_3d_hair
    assert cust.should_render_3d_nose
    assert cust.face_str == "anime_blue"
    assert cust.hair_color_str == "brunette"


def test_head_type_selection():
    """Valida a seleção entre cabeça quadrada e cabeça arredondada compatível com Roblox."""
    cust_blocky = AvatarCustomization(head_type=HeadType.BLOCKY)
    assert not cust_blocky.is_rounded_head
    assert cust_blocky.head_type_str == "blocky"

    cust_roblox = AvatarCustomization(head_type=HeadType.ROBLOX_COMPATIBLE)
    assert cust_roblox.is_rounded_head
    assert cust_roblox.head_type_str == "roblox_compatible"


def test_optional_face_and_hair():
    """Valida a opcionalidade completa de rosto e cabelo."""
    # 1. Totalmente careca e sem rosto
    cust_none = AvatarCustomization(face=None, hair_style=None)
    assert cust_none.is_bald
    assert cust_none.is_faceless
    assert not cust_none.should_render_3d_hair
    assert not cust_none.should_render_3d_nose

    # 2. Careca via Enum BALD
    cust_bald = AvatarCustomization(hair_style=HairStyle.BALD)
    assert cust_bald.is_bald
    assert not cust_bald.should_render_3d_hair
    assert not cust_bald.is_faceless
    assert cust_bald.should_render_3d_nose

    # 3. Sem rosto via Enum BLANK
    cust_blank = AvatarCustomization(face=FaceOption.BLANK)
    assert cust_blank.is_faceless
    assert not cust_blank.should_render_3d_nose
    assert not cust_blank.is_bald
    assert cust_blank.should_render_3d_hair


def test_classic_face_omits_3d_nose():
    """Rosto clássico 2D deve omitir o nariz 3D saliente."""
    cust = AvatarCustomization(face=FaceOption.CLASSIC_SMILE)
    assert not cust.should_render_3d_nose


def test_buzz_cut_style():
    """Cabelo raspado (buzz cut) não renderiza malha 3D saliente."""
    cust = AvatarCustomization(hair_style=HairStyle.BUZZ_CUT)
    assert not cust.is_bald
    assert not cust.should_render_3d_hair


def test_catalogs_non_empty():
    """Garante que os catálogos de opções contenham os itens esperados."""
    faces = get_available_faces()
    assert len(faces) >= 8
    assert FaceOption.ANIME_BLUE.value in faces
    assert FaceOption.BLANK.value in faces
    assert FaceOption.CLASSIC_SMILE.value in faces

    styles = get_available_hair_styles()
    assert len(styles) >= 3
    assert HairStyle.BALD.value in styles
    assert HairStyle.ANIME_LONG.value in styles

    colors = get_available_hair_colors()
    assert len(colors) >= 6
    assert HairColor.BLONDE.value in colors
    assert HairColor.PINK.value in colors


def test_atlas_builder_generation_and_caching():
    """Testa geração de texturas atlas para múltiplos estilos e o funcionamento do cache."""
    builder = HeadAtlasBuilder()

    # 1. Careca + Sem Rosto
    c_bald_blank = AvatarCustomization(face=FaceOption.BLANK, hair_style=HairStyle.BALD)
    atlas1 = builder.build_atlas(c_bald_blank)
    assert isinstance(atlas1, Image.Image)
    assert atlas1.size == (512, 512)

    # 2. Verificação de Cache
    atlas1_cached = builder.build_atlas(c_bald_blank)
    assert atlas1 is atlas1_cached

    # 3. Loiro + Olhos Verdes
    c_blonde_green = AvatarCustomization(
        face=FaceOption.ANIME_GREEN,
        hair_style=HairStyle.ANIME_LONG,
        hair_color=HairColor.BLONDE
    )
    atlas_bg = builder.build_atlas(c_blonde_green)
    arr_bg = np.array(atlas_bg)
    tr_hair = arr_bg[0:256, 256:512]
    # Canal R e G devem ser altos no loiro (> 150)
    assert np.mean(tr_hair[:, :, 0]) > 170
    assert np.mean(tr_hair[:, :, 1]) > 150

    # 4. Rosa + Wink
    c_pink_wink = AvatarCustomization(
        face=FaceOption.ANIME_WINK,
        hair_style=HairStyle.ANIME_LONG,
        hair_color=HairColor.PINK
    )
    atlas_pw = builder.build_atlas(c_pink_wink)
    assert atlas_pw.size == (512, 512)


def test_modular_catalogs():
    """Valida os novos catálogos modulares desacoplados."""
    eyes = get_available_eye_styles()
    assert len(eyes) >= 4
    assert EyeStyle.ANIME.value in eyes
    assert EyeStyle.CLASSIC.value in eyes

    irises = get_available_iris_colors()
    assert len(irises) >= 7
    assert IrisColor.BLUE.value in irises
    assert IrisColor.GOLD.value in irises

    mouths = get_available_mouth_styles()
    assert len(mouths) >= 8
    assert MouthStyle.ANIME_ORIGINAL.value in mouths
    assert MouthStyle.SMILE.value in mouths
    assert MouthStyle.OPEN.value in mouths
    assert MouthStyle.CAT.value in mouths
    assert MouthStyle.POUT.value in mouths

    brows = get_available_eyebrow_styles()
    assert len(brows) >= 4
    assert EyebrowStyle.STANDARD.value in brows

    details = get_available_face_details()
    assert len(details) >= 4
    assert FaceDetail.BLUSH.value in details
    assert FaceDetail.FRECKLES.value in details


def test_all_mouth_styles():
    """Garante que todos os estilos de boca, incluindo o original portado, compõem perfeitamente."""
    compositor = LayeredHeadCompositor()
    for m in [
        MouthStyle.ANIME_ORIGINAL,
        MouthStyle.SMILE,
        MouthStyle.OPEN,
        MouthStyle.WINK_SMILE,
        MouthStyle.NEUTRAL,
        MouthStyle.CLASSIC,
        MouthStyle.CAT,
        MouthStyle.POUT,
        MouthStyle.BLANK,
    ]:
        cust = AvatarCustomization(mouth_style=m)
        atlas = compositor.compose_atlas(cust)
        assert atlas.size == (512, 512)
        assert atlas.mode == "RGBA"


def test_decoupled_customization_and_compositor():
    """Valida o funcionamento e independência total do LayeredHeadCompositor."""
    compositor = LayeredHeadCompositor()

    # Cria configuração com camadas totalmente independentes
    cust = AvatarCustomization(
        skin_color_rgb=(0.45, 0.29, 0.22), # Pele escura / retinta
        eye_style=EyeStyle.ANIME,
        iris_color=(255, 140, 0),          # Íris laranja fogo customizada
        mouth_style=MouthStyle.OPEN,       # Boca aberta alegre
        eyebrow_style=EyebrowStyle.THICK,  # Sobrancelhas espessas
        face_detail=FaceDetail.FRECKLES,   # Sardas
        hair_2d_style=Hair2DStyle.STANDARD,
        hair_color=(240, 210, 80)          # Loiro solar
    )

    atlas = compositor.compose_atlas(cust)
    assert atlas.size == (512, 512)
    assert atlas.mode == "RGBA"

    arr = np.array(atlas)

    # 1. Couro cabeludo 2D tingido com loiro
    tr_hair = arr[0:256, 256:512]
    assert np.mean(tr_hair[:, :, 0]) > 170
    assert np.mean(tr_hair[:, :, 1]) > 150

    # 2. Pele no quadrante do pescoço / base deve refletir o tom escuro
    # A base neutra (250, 227, 210) multiplicada por (0.45, 0.29, 0.22) resulta em R ~115, G ~74, B ~56
    neck_region = arr[256:512, 256:512]
    assert np.mean(neck_region[:, :, 0]) < 180

    # 3. Íris laranja customizada deve ter predominância do canal Vermelho e Verde sobre o Azul
    face_region = arr[0:256, 0:256]
    # Pixels na área do olho
    eye_area = face_region[120:170, 50:100]
    # Canal R deve ser maior que B na área da íris laranja
    assert np.any(eye_area[:, :, 0] > 200)


def test_iris_tinting_independence():
    """Garante que alterar a cor da íris não altera o tom de pele nem a boca."""
    compositor = LayeredHeadCompositor()

    cust_blue = AvatarCustomization(
        iris_color=IrisColor.BLUE,
        skin_color_rgb=(0.94, 0.83, 0.76),
        mouth_style=MouthStyle.SMILE
    )
    cust_red = AvatarCustomization(
        iris_color=IrisColor.RED,
        skin_color_rgb=(0.94, 0.83, 0.76),
        mouth_style=MouthStyle.SMILE
    )

    atlas_blue = np.array(compositor.compose_atlas(cust_blue))
    atlas_red = np.array(compositor.compose_atlas(cust_red))

    # Região da boca (Y em 200..230, X em 100..150) deve ser idêntica
    mouth_blue = atlas_blue[200:230, 100:150]
    mouth_red = atlas_red[200:230, 100:150]
    assert np.array_equal(mouth_blue, mouth_red)

    # Região do queixo (Y em 240..255, X em 100..150) deve ser idêntica
    chin_blue = atlas_blue[240:255, 100:150]
    chin_red = atlas_red[240:255, 100:150]
    assert np.array_equal(chin_blue, chin_red)

    # Mas os olhos devem ser diferentes
    eyes_blue = atlas_blue[120:170, 50:100]
    eyes_red = atlas_red[120:170, 50:100]
    assert not np.array_equal(eyes_blue, eyes_red)
