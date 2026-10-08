"""Sistema de Customização Modular de Avatar: Rostos, Cabelos, Tons de Pele e Acessórios.

Permite desacoplamento total entre:
- Tom de Pele (Skin Tone)
- Olhos (Estilo e Cor da Íris)
- Boca (Expressões)
- Sobrancelhas (Estilo e Cor harmonizada)
- Detalhes Faciais (Blush, Sardas)
- Cabelo 2D (Franja e Couro Cabeludo no Atlas)
- Cabelo 3D (Malha OBJ com cor sincronizada)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, Dict, Any, Union
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


class BodyType(str, Enum):
    """Tipos de Corpo disponíveis."""
    MALE = "male"       # Modelo masculino padrão
    FEMALE = "female"   # Novo modelo feminino


class HeadType(str, Enum):
    """Tipos de Cabeça disponíveis."""
    BLOCKY = "blocky"                       # Cabeça quadrada original voxel/Minecraft
    ROBLOX_COMPATIBLE = "roblox_compatible" # Cabeça arredondada compatível com cabelos Roblox
    ROUNDED = "rounded"                     # Sinônimo de roblox_compatible


class FaceOption(str, Enum):
    """Opções de Rosto integradas (Presets legados e atalhos rápidos)."""
    ANIME_BLUE = "anime_blue"           # Padrão: Olhos azuis anime vibrantes
    ANIME_GREEN = "anime_green"         # Olhos verde esmeralda
    ANIME_BROWN = "anime_brown"         # Olhos castanho âmbar
    ANIME_PURPLE = "anime_purple"       # Olhos violeta / ametista
    ANIME_RED = "anime_red"             # Olhos rubi / carmesim
    ANIME_WINK = "anime_wink"           # Olho piscando com bochechas coradas 😉
    ANIME_DETERMINED = "anime_determined" # Olhos determinados e confiantes
    CLASSIC_SMILE = "classic_smile"     # Sorriso clássico e amigável
    BLANK = "blank"                     # Sem rosto / liso (manequim/voxel)
    NONE = "none"                       # Sinônimo de sem rosto


class EyeStyle(str, Enum):
    """Estilos de Olhos modulares independentes."""
    ANIME = "anime"                     # Olhos expressivos estilo anime
    ANIME_WINK = "anime_wink"           # Olho aberto + piscadela 😉
    CLASSIC = "classic"                 # Olhos retrô clássicos ovais
    BLANK = "blank"                     # Sem olhos
    NONE = "none"                       # Sinônimo de sem olhos


class IrisColor(str, Enum):
    """Cores pré-definidas de Íris."""
    BLUE = "blue"                       # Azul celeste / safira
    GREEN = "green"                     # Verde esmeralda
    BROWN = "brown"                     # Castanho âmbar
    PURPLE = "purple"                   # Roxo ametista
    RED = "red"                         # Vermelho rubi
    GOLD = "gold"                       # Dourado âmbar brilhante
    CYAN = "cyan"                       # Ciano / turquesa
    CUSTOM = "custom"                   # Cor RGB personalizada


class MouthStyle(str, Enum):
    """Estilos de Boca e Expressões faciais modulares."""
    ANIME_ORIGINAL = "anime_original"   # Boca/Lábios anime originais (padrão original de character_head_full.png)
    SMILE = "smile"                     # Sorriso padrão suave curvado
    OPEN = "open"                       # Boca aberta alegre com dentes e língua
    WINK_SMILE = "wink_smile"           # Sorriso expressivo animado
    NEUTRAL = "neutral"                 # Linha neutra sutil fechada
    CLASSIC = "classic"                 # Arco retrô clássico
    CAT = "cat"                         # Boquinha fofa estilo gato (:3 / nya)
    POUT = "pout"                       # Beicinho suave (pout)
    BLANK = "blank"                     # Sem boca
    NONE = "none"                       # Sinônimo de sem boca


class EyebrowStyle(str, Enum):
    """Estilos de Sobrancelha modulares."""
    STANDARD = "standard"               # Sobrancelhas anime padrão
    THICK = "thick"                     # Sobrancelhas mais marcadas / espessas
    DETERMINED = "determined"           # Inclinadas em foco confiante
    NONE = "none"                       # Sem sobrancelhas


class Hair2DStyle(str, Enum):
    """Estilos do Couro Cabeludo / Cabelo 2D na textura da cabeça."""
    STANDARD = "standard"               # Franja, topo, laterais e nuca para cabelos longos
    BUZZ = "buzz"                       # Raspado / militar uniforme
    BALD = "bald"                       # Totalmente liso / pele limpa
    NONE = "none"                       # Sinônimo de careca


class FaceDetail(str, Enum):
    """Detalhes faciais opcionais (Blush, Sardas, etc.)."""
    NONE = "none"                       # Sem detalhes adicionais
    BLUSH = "blush"                     # Bochechas coradas suaves
    FRECKLES = "freckles"               # Sardas delicadas no nariz e bochechas
    BLUSH_AND_FRECKLES = "blush_and_freckles" # Blush com sardas combinados


class HairStyle(str, Enum):
    """Estilos de Cabelo (Geometria 3D + Textura)."""
    ANIME_LONG = "anime_long"           # Malha 3D completa com franja, mechas e laços
    BUZZ_CUT = "buzz_cut"               # Cabelo raspado / curto na textura (sem malha 3D)
    BALD = "bald"                       # Totalmente careca / sem cabelo
    NONE = "none"                       # Sinônimo de careca


class HairColor(str, Enum):
    """Cores e Paletas de Cabelo pré-definidas."""
    BRUNETTE = "brunette"               # Castanho chocolate original
    BLONDE = "blonde"                   # Loiro dourado reluzente
    BLACK = "black"                     # Preto corvo elegante
    PINK = "pink"                       # Rosa pastel anime
    SILVER = "silver"                   # Branco / prateado platinado
    AUBURN = "auburn"                   # Ruivo acobreado
    CYAN = "cyan"                       # Azul celeste anime


HAIR_PALETTES: Dict[str, Tuple[int, int, int]] = {
    "brunette": (92, 62, 54),
    "blonde": (230, 185, 95),
    "black": (38, 38, 42),
    "pink": (235, 140, 175),
    "silver": (215, 220, 230),
    "auburn": (180, 65, 45),
    "cyan": (60, 150, 210),
}

IRIS_PALETTES: Dict[str, Tuple[int, int, int]] = {
    "blue": (60, 140, 220),
    "green": (50, 180, 90),
    "brown": (130, 80, 45),
    "purple": (150, 75, 200),
    "red": (210, 50, 55),
    "gold": (230, 180, 40),
    "cyan": (40, 200, 220),
}


@dataclass
class AvatarCustomization:
    """Configuração de customização do avatar (compatível com presets rápidos e controle modular desacoplado)."""
    body_type: Union[BodyType, str] = BodyType.MALE
    head_type: Union[HeadType, str] = HeadType.BLOCKY
    face: Optional[Union[FaceOption, str]] = FaceOption.ANIME_BLUE
    hair_style: Optional[Union[HairStyle, str]] = HairStyle.ANIME_LONG
    hair_color: Union[HairColor, str, Tuple[int, int, int]] = HairColor.BRUNETTE
    skin_color_rgb: Tuple[float, float, float] = (0.94, 0.83, 0.76) # Normalizado OpenGL [0, 1] ou int 0-255
    has_3d_nose: Optional[bool] = None # Se None, deduz automaticamente baseado no rosto
    custom_face_path: Optional[str] = None # Caminho para PNG customizado de rosto 256x256
    custom_hair_obj: Optional[str] = None # Caminho para OBJ customizado de cabelo 3D
    custom_hair_tex: Optional[str] = None # Caminho para textura PNG customizada do cabelo 3D
    hair_offset_x: float = 0.0            # Deslocamento lateral (+ direita, - esquerda em metros)
    hair_offset_y: float = 0.0            # Deslocamento vertical (+ cima, - baixo em metros)
    hair_offset_z: float = 0.0            # Deslocamento sagital (+ frente, - trás em metros)
    hair_scale_x: float = 1.0             # Escala horizontal X (largura)
    hair_scale_y: float = 1.0             # Escala vertical Y (altura)
    hair_scale_z: float = 1.0             # Escala sagital Z (profundidade)

    # Configurações Modulares Desacopladas (Se None, deduzidas harmonicamente dos campos acima)
    eye_style: Optional[Union[EyeStyle, str]] = None
    iris_color: Optional[Union[IrisColor, str, Tuple[int, int, int]]] = None
    mouth_style: Optional[Union[MouthStyle, str]] = None
    eyebrow_style: Optional[Union[EyebrowStyle, str]] = None
    eyebrow_color: Optional[Union[HairColor, str, Tuple[int, int, int]]] = None
    hair_2d_style: Optional[Union[Hair2DStyle, str]] = None
    face_detail: Optional[Union[FaceDetail, str]] = None
    nose_style: str = "padrao"  # formato do nariz 3D (ver nose.STYLE_NAMES)
    eye_shape: str = "padrao"   # formato dos olhos anime (ver eye_shapes.SHAPE_NAMES)
    # Cor da íris do outro olho (o esquerdo do personagem), para olhos de cores diferentes; None = igual.
    iris_color_other: Optional[Union[IrisColor, str, Tuple[int, int, int]]] = None
    # Maquiagem: "batom" e "sombra", cada um com o nome de uma cor de MAKEUP_COLORS.
    makeup: Dict[str, str] = field(default_factory=dict)
    # Ajustes de proporção, de -1 a 1 (ver body_shape.ADJUSTMENTS): corpo e rosto.
    body_adjust: Dict[str, float] = field(default_factory=dict)

    @property
    def body_type_str(self) -> str:
        if hasattr(self.body_type, "value"):
            return self.body_type.value.lower()
        return str(self.body_type).lower()

    @property
    def is_female(self) -> bool:
        return self.body_type_str in ("female", "feminino", "f", "mulher", "woman")

    @property
    def head_type_str(self) -> str:
        if hasattr(self.head_type, "value"):
            return self.head_type.value.lower()
        return str(self.head_type).lower()

    @property
    def is_rounded_head(self) -> bool:
        return self.head_type_str in ("roblox_compatible", "rounded", "roblox")

    @property
    def face_str(self) -> str:
        if self.face is None:
            return "blank"
        return self.face.value.lower() if hasattr(self.face, "value") else str(self.face).lower()

    @property
    def hair_style_str(self) -> str:
        if self.hair_style is None:
            return "bald"
        return self.hair_style.value.lower() if hasattr(self.hair_style, "value") else str(self.hair_style).lower()

    @property
    def hair_color_str(self) -> str:
        if isinstance(self.hair_color, tuple):
            return f"rgb_{self.hair_color[0]}_{self.hair_color[1]}_{self.hair_color[2]}"
        if hasattr(self.hair_color, "value"):
            return self.hair_color.value.lower()
        return str(self.hair_color).lower()

    @property
    def is_bald(self) -> bool:
        return self.hair_style_str in ("none", "bald")

    @property
    def is_faceless(self) -> bool:
        return self.face_str in ("none", "blank")

    @property
    def should_render_3d_nose(self) -> bool:
        if self.has_3d_nose is not None:
            return self.has_3d_nose
        if self.is_faceless or self.face_str == "classic_smile" or self.resolved_eye_style == "classic":
            return False
        return True

    @property
    def should_render_3d_hair(self) -> bool:
        if self.is_bald or self.hair_style_str == "buzz_cut":
            return False
        return True

    @property
    def skin_rgb_255(self) -> Tuple[int, int, int]:
        """Retorna a cor da pele em inteiros 0..255."""
        if isinstance(self.skin_color_rgb, tuple) and len(self.skin_color_rgb) >= 3:
            c = self.skin_color_rgb
            if any(x > 1.0 for x in c[:3]):
                return (int(c[0]), int(c[1]), int(c[2]))
            return (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
        return (240, 212, 194)

    @property
    def hair_rgb_255(self) -> Tuple[int, int, int]:
        """Retorna a cor do cabelo em inteiros 0..255 (sincronizada para 2D e 3D)."""
        if isinstance(self.hair_color, tuple) and len(self.hair_color) >= 3:
            return (int(self.hair_color[0]), int(self.hair_color[1]), int(self.hair_color[2]))
        key = self.hair_color_str
        return HAIR_PALETTES.get(key, (92, 62, 54))

    @property
    def resolved_eye_style(self) -> str:
        """Estilo de olhos resolvido a partir da configuração explícita ou do preset de face."""
        if self.eye_style is not None:
            val = self.eye_style.value if hasattr(self.eye_style, "value") else str(self.eye_style)
            return val.lower()
        if self.is_faceless:
            return "blank"
        if self.face_str == "classic_smile":
            return "classic"
        if self.face_str == "anime_wink":
            return "anime_wink"
        return "anime"

    @property
    def resolved_iris_color(self) -> Tuple[int, int, int]:
        """Cor da íris resolvida em inteiros 0..255."""
        if self.iris_color is not None:
            if isinstance(self.iris_color, tuple) and len(self.iris_color) >= 3:
                return (int(self.iris_color[0]), int(self.iris_color[1]), int(self.iris_color[2]))
            val = self.iris_color.value if hasattr(self.iris_color, "value") else str(self.iris_color)
            return IRIS_PALETTES.get(val.lower(), IRIS_PALETTES["blue"])
        # Deduz do face_str legado
        f = self.face_str
        if "green" in f:
            return IRIS_PALETTES["green"]
        if "brown" in f:
            return IRIS_PALETTES["brown"]
        if "purple" in f:
            return IRIS_PALETTES["purple"]
        if "red" in f:
            return IRIS_PALETTES["red"]
        return IRIS_PALETTES["blue"]

    @property
    def resolved_mouth_style(self) -> str:
        """Estilo de boca resolvido."""
        if self.mouth_style is not None:
            val = self.mouth_style.value if hasattr(self.mouth_style, "value") else str(self.mouth_style)
            v_lower = val.lower()
            if v_lower in ("original", "default", "anime", "lips", "anime_lips"):
                return "anime_original"
            return v_lower
        if self.is_faceless:
            return "blank"
        if self.face_str == "classic_smile":
            return "classic"
        if self.face_str == "anime_wink":
            return "wink_smile"
        return "anime_original"

    @property
    def resolved_eyebrow_style(self) -> str:
        """Estilo de sobrancelhas resolvido."""
        if self.eyebrow_style is not None:
            val = self.eyebrow_style.value if hasattr(self.eyebrow_style, "value") else str(self.eyebrow_style)
            return val.lower()
        if self.is_faceless or self.face_str == "classic_smile":
            return "none"
        if self.face_str == "anime_determined":
            return "determined"
        return "standard"

    @property
    def resolved_eyebrow_color(self) -> Tuple[int, int, int]:
        """Cor das sobrancelhas resolvida (harmonizada com a cor do cabelo por padrão)."""
        if self.eyebrow_color is not None:
            if isinstance(self.eyebrow_color, tuple) and len(self.eyebrow_color) >= 3:
                return (int(self.eyebrow_color[0]), int(self.eyebrow_color[1]), int(self.eyebrow_color[2]))
            val = self.eyebrow_color.value if hasattr(self.eyebrow_color, "value") else str(self.eyebrow_color)
            return HAIR_PALETTES.get(val.lower(), (92, 62, 54))
        # Harmonização elegante: 75% da cor do cabelo com leve sombreamento
        h = self.hair_rgb_255
        return (int(h[0] * 0.75), int(h[1] * 0.75), int(h[2] * 0.75))

    @property
    def resolved_hair_2d_style(self) -> str:
        """Estilo do couro cabeludo 2D resolvido."""
        if self.custom_hair_obj:
            return "none"
        if self.hair_2d_style is not None:
            val = self.hair_2d_style.value if hasattr(self.hair_2d_style, "value") else str(self.hair_2d_style)
            return val.lower()
        if self.is_bald:
            return "bald"
        if self.hair_style_str == "buzz_cut":
            return "buzz"
        return "standard"

    @property
    def resolved_face_detail(self) -> str:
        """Detalhe facial resolvido."""
        if self.face_detail is not None:
            val = self.face_detail.value if hasattr(self.face_detail, "value") else str(self.face_detail)
            return val.lower()
        if self.face_str in ("anime_wink", "classic_smile"):
            return "blush"
        return "none"

    def get_cache_key(self) -> str:
        return (
            f"h_{self.head_type_str}_e_{self.resolved_eye_style}_i_{self.resolved_iris_color}_"
            f"m_{self.resolved_mouth_style}_eb_{self.resolved_eyebrow_style}_ebc_{self.resolved_eyebrow_color}_"
            f"h2_{self.resolved_hair_2d_style}_fd_{self.resolved_face_detail}_"
            f"hc_{self.hair_rgb_255}_sk_{self.skin_rgb_255}_cf_{self.custom_face_path}_"
            f"fa_{[round(self.face_adjust(k), 3) for k in ('olhos_tamanho', 'olhos_altura', 'olhos_distancia', 'sobrancelha_altura')]}_"
            f"n_{self.should_render_3d_nose}_{[round(self.face_adjust(k), 3) for k in ('nariz_tamanho', 'nariz_largura', 'nariz_altura', 'nariz_sombra')]}_"
            f"io_{self.resolved_iris_color_other}_mk_{sorted((self.makeup or {}).items())}_es_{self.eye_shape}"
        )

    @property
    def resolved_iris_color_other(self) -> Tuple[int, int, int]:
        """Cor da íris do outro olho (a mesma do primeiro quando não foi escolhida)."""
        other = self.iris_color_other
        if other is None:
            return self.resolved_iris_color
        if isinstance(other, (tuple, list)) and len(other) >= 3:
            return (int(other[0]), int(other[1]), int(other[2]))
        return IRIS_PALETTES.get(str(getattr(other, "value", other)).lower(), self.resolved_iris_color)

    def makeup_color(self, what: str) -> Optional[Tuple[int, int, int]]:
        """A cor de um item de maquiagem ("batom", "sombra"), ou None se não é usado."""
        return MAKEUP_COLORS.get(str((self.makeup or {}).get(what, "")).lower())

    def face_adjust(self, name: str) -> float:
        """Um ajuste do rosto, de -1 a 1 (0 = como desenhado)."""
        try:
            return max(-1.0, min(1.0, float((self.body_adjust or {}).get(name, 0.0))))
        except (TypeError, ValueError):
            return 0.0


def place_face_layer(layer: Image.Image, scale: float = 1.0, lift: float = 0.0, spread: float = 0.0) -> Image.Image:
    """Uma camada do rosto (os dois olhos, as duas sobrancelhas) com cada lado escalado em
    torno do próprio centro, erguido ``lift`` pixels e afastado ``spread`` pixels do outro."""
    box = layer.getbbox()
    if box is None or (scale == 1.0 and not lift and not spread):
        return layer
    middle = (box[0] + box[2]) // 2
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    for side, (x0, x1) in ((-1, (0, middle)), (1, (middle, layer.width))):
        half = layer.crop((x0, 0, x1, layer.height))
        inner = half.getbbox()
        if inner is None:
            continue
        piece = half.crop(inner)
        if scale != 1.0:
            piece = piece.resize((max(1, round(piece.width * scale)), max(1, round(piece.height * scale))), Image.LANCZOS)
        cx = x0 + (inner[0] + inner[2]) / 2 + side * spread
        cy = (inner[1] + inner[3]) / 2 - lift
        frame = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        frame.paste(piece, (int(round(cx - piece.width / 2)), int(round(cy - piece.height / 2))))
        out.alpha_composite(frame)
    return out


# How far the face adjustments go at 1: the eyes' size (share), and pixels of the 512 px head
# atlas for their height and distance and for the height of the eyebrows over them.
EYE_SIZE, EYE_LIFT, EYE_SPREAD, BROW_LIFT = 0.22, 10.0, 8.0, 8.0
# Makeup: the colours on offer, how strongly the eye shadow is laid over the skin, and how far it
# reaches above the eye and down over it (shares of the eye's height).
MAKEUP_COLORS = {"vermelho": (200, 40, 55), "rosa": (235, 120, 150), "nude": (196, 132, 112), "vinho": (120, 30, 55),
                 "roxo": (140, 85, 175), "azul": (70, 115, 205), "verde": (70, 150, 115), "dourado": (212, 170, 80),
                 "marrom": (120, 80, 60), "preto": (40, 36, 42)}
EYE_SHADOW, EYE_SHADOW_REACH = 0.55, (0.36, 0.30)
# The nose's shadow, as the old head texture had it: its box in the 512 px atlas, how much of the
# darker tone is laid over the skin (and that tone, as a share of the skin's), and how it follows
# the nose's adjustments (its size, its width, and pixels of its height).
NOSE_SHADOW_BOX, NOSE_SHADOW, NOSE_SHADOW_TONE = (117, 143, 139, 198), 0.14, 0.55
NOSE_SHADOW_GROWTH = (0.5, 0.6, 12.0)


class LayeredHeadCompositor:
    """Compositor modular de atlas de textura da cabeça (512x512) baseado em camadas e blending."""

    def __init__(self, layers_dir: Optional[str] = None):
        if layers_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            layers_dir = os.path.join(base_dir, "assets", "models", "textures", "layers")

        self.layers_dir = layers_dir
        self._raw_cache: Dict[str, Image.Image] = {}
        self._cache: Dict[str, Image.Image] = {}

    def _load_layer(self, subpath: str) -> Optional[Image.Image]:
        if subpath in self._raw_cache:
            return self._raw_cache[subpath].copy()

        full_path = os.path.join(self.layers_dir, subpath)
        if not os.path.exists(full_path):
            # Tenta na raiz de layers se não achou na subpasta
            flat_name = "layer_" + os.path.basename(subpath)
            flat_path = os.path.join(self.layers_dir, flat_name)
            if os.path.exists(flat_path):
                full_path = flat_path
            else:
                return None

        img = Image.open(full_path).convert("RGBA")
        self._raw_cache[subpath] = img
        return img.copy()

    def compose_atlas(self, cust: AvatarCustomization) -> Image.Image:
        """Gera ou retorna do cache a textura atlas 512x512 com composição desacoplada em tempo real."""
        key = cust.get_cache_key()
        if key in self._cache:
            return self._cache[key]

        # ---------------------------------------------------------
        # 1. BASE DE PELE & SOMBREAMENTO (Skin Base Tinting)
        # ---------------------------------------------------------
        skin_img = self._load_layer("skin/skin_base_neutral.png")
        if skin_img is None:
            skin_img = self._load_layer("layer_skin_base.png")
        if skin_img is None:
            skin_img = Image.new("RGBA", (512, 512), (250, 227, 210, 255))

        arr_skin = np.array(skin_img, dtype=float)
        ref_rgb = np.array([250.0, 227.0, 210.0])
        target_skin = np.array(cust.skin_rgb_255, dtype=float)
        factor = target_skin / ref_rgb

        for ch in range(3):
            arr_skin[:, :, ch] = np.clip(arr_skin[:, :, ch] * factor[ch], 0, 255)

        canvas = Image.fromarray(arr_skin.astype(np.uint8))

        # ---------------------------------------------------------
        # 2. CABELO 2D / COURO CABELUDO (Scalp & Bangs)
        # ---------------------------------------------------------
        h2d_style = cust.resolved_hair_2d_style
        if h2d_style not in ("bald", "none"):
            subpath = "hair_2d/scalp_buzz.png" if h2d_style == "buzz" else "hair_2d/scalp_standard.png"
            hair_img = self._load_layer(subpath)
            if hair_img is None:
                hair_img = self._load_layer("layer_hair_2d.png")

            if hair_img is not None:
                arr_h = np.array(hair_img, dtype=float)
                alpha_h = arr_h[:, :, 3] > 0
                hair_rgb = cust.hair_rgb_255
                # Normalização de luma calibrada para brilho e contraste vibrantes
                luma = np.clip(arr_h[:, :, 0] / 130.0, 0.4, 1.5)
                for ch in range(3):
                    arr_h[alpha_h, ch] = np.clip(hair_rgb[ch] * luma[alpha_h], 0, 255)
                canvas.alpha_composite(Image.fromarray(arr_h.astype(np.uint8)))

        # ---------------------------------------------------------
        # 3. DETALHES FACIAIS (Blush / Sardas)
        # ---------------------------------------------------------
        detail_style = cust.resolved_face_detail
        if detail_style in ("blush", "blush_and_freckles"):
            blush_img = self._load_layer("face_details/blush_soft.png")
            if blush_img is not None:
                canvas.alpha_composite(blush_img)

        if detail_style in ("freckles", "blush_and_freckles"):
            freckles_img = self._load_layer("face_details/freckles.png")
            if freckles_img is not None:
                canvas.alpha_composite(freckles_img)

        # ---------------------------------------------------------
        # 3.1 SOMBRA DO NARIZ: um trecho um pouco mais escuro entre os olhos, onde o nariz 3D se apoia
        # (a malha do nariz usa esse pedaço da textura, então escurece com ele).
        # ---------------------------------------------------------
        shadow = NOSE_SHADOW * (1.0 + cust.face_adjust("nariz_sombra"))
        if cust.should_render_3d_nose and shadow > 0.0:
            unit = canvas.width / 512.0
            size = 1.0 + NOSE_SHADOW_GROWTH[0] * cust.face_adjust("nariz_tamanho")
            half_w = (NOSE_SHADOW_BOX[2] - NOSE_SHADOW_BOX[0]) / 2 * size * (1.0 + NOSE_SHADOW_GROWTH[1] * cust.face_adjust("nariz_largura"))
            half_h = (NOSE_SHADOW_BOX[3] - NOSE_SHADOW_BOX[1]) / 2 * size
            cx = (NOSE_SHADOW_BOX[0] + NOSE_SHADOW_BOX[2]) / 2
            cy = (NOSE_SHADOW_BOX[1] + NOSE_SHADOW_BOX[3]) / 2 - NOSE_SHADOW_GROWTH[2] * cust.face_adjust("nariz_altura")
            mask = Image.new("L", canvas.size, 0)
            ImageDraw.Draw(mask).rectangle([(cx - half_w) * unit, (cy - half_h) * unit, (cx + half_w) * unit, (cy + half_h) * unit],
                                           fill=int(round(255 * min(shadow, 1.0))))
            mask = mask.filter(ImageFilter.GaussianBlur(1.5 * unit))
            dark = Image.new("RGBA", canvas.size, tuple(int(c * NOSE_SHADOW_TONE) for c in cust.skin_rgb_255) + (255,))
            dark.putalpha(mask)
            canvas.alpha_composite(dark)

        # ---------------------------------------------------------
        # 4. OLHOS & TINGIMENTO DA ÍRIS (Eyes & Iris Tint)
        # ---------------------------------------------------------
        eye_style = cust.resolved_eye_style
        if eye_style not in ("blank", "none"):
            if eye_style == "classic":
                eye_img = self._load_layer("eyes/eye_classic.png")
            elif eye_style == "anime_wink":
                eye_img = self._load_layer("eyes/eye_anime_wink.png")
            else:
                # Olhos Anime com suporte a qualquer cor de íris
                eye_img = self._load_layer("eyes/eye_anime_blue.png")
                if eye_img is None:
                    eye_img = self._load_layer("layer_eyes_anime_blue.png")

                # Another model of eye, drawn in the same pixel art (and in blue, to take the colour below).
                from .eye_shapes import draw_eyes
                drawn_eyes = draw_eyes(getattr(cust, "eye_shape", "padrao"), eye_img.size if eye_img is not None else (512, 512))
                if drawn_eyes is not None:
                    eye_img = drawn_eyes

                if eye_img is not None:
                    arr_e = np.array(eye_img)
                    is_iris = (arr_e[:, :, 3] > 0) & (
                        (arr_e[:, :, 2].astype(int) - arr_e[:, :, 0].astype(int) > 15) & (arr_e[:, :, 2] > 80)
                    )
                    # Each eye takes its own colour: the layer is split between the two eyes.
                    columns = np.nonzero(is_iris.any(axis=0))[0]
                    middle = (int(columns.min()) + int(columns.max())) // 2 if len(columns) else arr_e.shape[1] // 2
                    first = np.arange(arr_e.shape[1])[None, :] <= middle
                    for half, iris_rgb in ((first, cust.resolved_iris_color), (~first, cust.resolved_iris_color_other)):
                        tinted = is_iris & half
                        intensity = np.clip((arr_e[tinted, 2].astype(float) - 50.0) / 190.0, 0.0, 1.0)
                        for ch in range(3):
                            arr_e[tinted, ch] = np.clip(iris_rgb[ch] * (0.35 + 0.95 * intensity), 0, 255).astype(np.uint8)

                    eye_img = Image.fromarray(arr_e)

            if eye_img is not None and eye_style != "classic":
                from .eye_shapes import shape_eyes
                eye_img = shape_eyes(eye_img, getattr(cust, "eye_shape", "padrao"))
            if eye_img is not None:
                placed = place_face_layer(
                    eye_img, 1.0 + EYE_SIZE * cust.face_adjust("olhos_tamanho"), EYE_LIFT * cust.face_adjust("olhos_altura"),
                    EYE_SPREAD * cust.face_adjust("olhos_distancia"))
                shadow_rgb = cust.makeup_color("sombra")
                box = placed.getbbox()
                if shadow_rgb is not None and box is not None:
                    # Eye shadow: a soft patch of colour over each eyelid, under the eye's own drawing.
                    mask = Image.new("L", canvas.size, 0)
                    pen = ImageDraw.Draw(mask)
                    centre = (box[0] + box[2]) // 2
                    for x0, x1 in ((0, centre), (centre, placed.width)):
                        eye = placed.crop((x0, 0, x1, placed.height)).getbbox()
                        if eye is None:
                            continue
                        tall = eye[3] - eye[1]
                        pen.ellipse([x0 + eye[0], eye[1] - EYE_SHADOW_REACH[0] * tall, x0 + eye[2],
                                     eye[1] + EYE_SHADOW_REACH[1] * tall], fill=int(255 * EYE_SHADOW))
                    mask = mask.filter(ImageFilter.GaussianBlur(2.0 * canvas.width / 512.0))
                    colour = Image.new("RGBA", canvas.size, tuple(shadow_rgb) + (255,))
                    colour.putalpha(mask)
                    canvas.alpha_composite(colour)
                canvas.alpha_composite(placed)

        # ---------------------------------------------------------
        # 5. SOBRANCELHAS (Eyebrows)
        # ---------------------------------------------------------
        brow_style = cust.resolved_eyebrow_style
        if brow_style not in ("none", "blank"):
            if brow_style == "thick":
                brow_img = self._load_layer("brows/brows_thick.png")
            elif brow_style == "determined":
                brow_img = self._load_layer("brows/brows_determined.png")
            else:
                brow_img = self._load_layer("brows/brows_standard.png")
                if brow_img is None:
                    brow_img = self._load_layer("layer_brows_standard.png")

            if brow_img is not None:
                arr_b = np.array(brow_img, dtype=float)
                alpha_b = arr_b[:, :, 3] > 0
                eb_rgb = cust.resolved_eyebrow_color
                for ch in range(3):
                    arr_b[alpha_b, ch] = np.clip(eb_rgb[ch], 0, 255)
                canvas.alpha_composite(place_face_layer(
                    Image.fromarray(arr_b.astype(np.uint8)), 1.0,
                    BROW_LIFT * cust.face_adjust("sobrancelha_altura") + EYE_LIFT * cust.face_adjust("olhos_altura"),
                    EYE_SPREAD * cust.face_adjust("olhos_distancia")))

        # ---------------------------------------------------------
        # 6. BOCA / EXPRESSÃO (Mouth)
        # ---------------------------------------------------------
        mouth_style = cust.resolved_mouth_style
        if mouth_style not in ("blank", "none"):
            subpath = f"mouth/mouth_{mouth_style}.png"
            mouth_img = self._load_layer(subpath)
            if mouth_img is None:
                if mouth_style in ("anime_original", "original", "default"):
                    mouth_img = self._load_layer("mouth/mouth_anime_original.png")
                elif mouth_style == "smile":
                    mouth_img = self._load_layer("mouth/mouth_smile.png")
                else:
                    mouth_img = self._load_layer("mouth/mouth_anime_original.png")
                if mouth_img is None:
                    mouth_img = self._load_layer("layer_mouth_smile.png")

            lipstick = cust.makeup_color("batom")
            if mouth_img is not None and lipstick is not None:
                # Lipstick: the mouth in another colour, keeping its light and dark.
                arr_m = np.array(mouth_img.convert("RGBA"), dtype=float)
                drawn = arr_m[:, :, 3] > 0
                if drawn.any():
                    light = arr_m[:, :, :3].mean(axis=2)
                    light = light / max(float(light[drawn].mean()), 1.0)
                    for ch in range(3):
                        arr_m[:, :, ch] = np.where(drawn, np.clip(lipstick[ch] * light, 0, 255), arr_m[:, :, ch])
                    mouth_img = Image.fromarray(arr_m.astype(np.uint8))
            if mouth_img is not None:
                canvas.alpha_composite(mouth_img)

        # ---------------------------------------------------------
        # 7. ROSTO CUSTOMIZADO EM PNG (Se fornecido)
        # ---------------------------------------------------------
        if cust.custom_face_path and os.path.exists(cust.custom_face_path):
            custom_face = Image.open(cust.custom_face_path).convert("RGBA").resize((256, 256))
            canvas.paste(custom_face, (0, 0), custom_face)

        self._cache[key] = canvas
        return canvas

    def save_atlas(self, cust: AvatarCustomization, filepath: str) -> str:
        """Gera e salva a textura atlas em um arquivo PNG."""
        img = self.compose_atlas(cust)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        img.save(filepath)
        return filepath

    def clear_cache(self) -> None:
        """Limpa o cache de texturas compostas."""
        self._cache.clear()


class HeadAtlasBuilder:
    """Construtor dinâmico de atlas de textura da cabeça (512x512).
    
    Mantém compatibilidade total com a interface legada utilizando o LayeredHeadCompositor.
    """

    def __init__(self, base_texture_path: Optional[str] = None, layers_dir: Optional[str] = None):
        self.compositor = LayeredHeadCompositor(layers_dir=layers_dir)
        self._cache: Dict[str, Image.Image] = self.compositor._cache

    def build_atlas(self, cust: AvatarCustomization) -> Image.Image:
        """Gera ou retorna do cache a textura atlas 512x512 completa."""
        return self.compositor.compose_atlas(cust)

    def save_atlas(self, cust: AvatarCustomization, filepath: str) -> str:
        """Gera e salva a textura atlas em um arquivo PNG."""
        return self.compositor.save_atlas(cust, filepath)


def get_available_faces() -> Dict[str, str]:
    """Retorna dicionário de rostos integrados disponíveis com descrições."""
    return {
        FaceOption.ANIME_BLUE.value: "Olhos Azuis Anime (Padrão)",
        FaceOption.ANIME_GREEN.value: "Olhos Verdes Esmeralda Anime",
        FaceOption.ANIME_BROWN.value: "Olhos Castanhos Âmbar Anime",
        FaceOption.ANIME_PURPLE.value: "Olhos Violeta Ametista Anime",
        FaceOption.ANIME_RED.value: "Olhos Rubis Carmesim Anime",
        FaceOption.ANIME_WINK.value: "Piscadela Animada com Bochechas Coradas 😉",
        FaceOption.ANIME_DETERMINED.value: "Expressão Confiante / Determinada",
        FaceOption.CLASSIC_SMILE.value: "Sorriso Retrô Clássico",
        FaceOption.BLANK.value: "Sem Rosto (Manequim / Superfície Lisa)",
    }


def get_available_hair_styles() -> Dict[str, str]:
    """Retorna dicionário de estilos de cabelo com descrições."""
    return {
        HairStyle.ANIME_LONG.value: "Cabelo Longo Anime 3D (com Franja e Laços)",
        HairStyle.BUZZ_CUT.value: "Cabelo Raspado / Militar (Texturizado sem malha 3D)",
        HairStyle.BALD.value: "Careca / Sem Cabelo (Cabeça Base Lisa)",
    }


def get_available_hair_colors() -> Dict[str, str]:
    """Retorna dicionário de cores de cabelo com descrições."""
    return {
        HairColor.BRUNETTE.value: "Castanho Chocolate (Original)",
        HairColor.BLONDE.value: "Loiro Dourado",
        HairColor.BLACK.value: "Preto Corvo",
        HairColor.PINK.value: "Rosa Pastel Anime",
        HairColor.SILVER.value: "Prateado / Branco Platinado",
        HairColor.AUBURN.value: "Ruivo Acobreado",
        HairColor.CYAN.value: "Azul Celeste Anime",
    }


def get_available_eye_styles() -> Dict[str, str]:
    """Retorna estilos de olhos modulares disponíveis."""
    return {
        EyeStyle.ANIME.value: "Olhos Anime Expressivos",
        EyeStyle.ANIME_WINK.value: "Piscadela Animada 😉",
        EyeStyle.CLASSIC.value: "Olhos Retrô Clássicos",
        EyeStyle.BLANK.value: "Sem Olhos",
    }


def get_available_iris_colors() -> Dict[str, str]:
    """Retorna opções de cores de íris disponíveis."""
    return {
        IrisColor.BLUE.value: "Azul Safira",
        IrisColor.GREEN.value: "Verde Esmeralda",
        IrisColor.BROWN.value: "Castanho Âmbar",
        IrisColor.PURPLE.value: "Violeta Ametista",
        IrisColor.RED.value: "Vermelho Rubi",
        IrisColor.GOLD.value: "Dourado Solar",
        IrisColor.CYAN.value: "Ciano Celeste",
        IrisColor.CUSTOM.value: "Cor RGB Personalizada",
    }


def get_available_mouth_styles() -> Dict[str, str]:
    """Retorna estilos de boca modulares disponíveis."""
    return {
        MouthStyle.ANIME_ORIGINAL.value: "Lábios Anime Originais (Padrão Original)",
        MouthStyle.SMILE.value: "Sorriso Curvado Suave",
        MouthStyle.OPEN.value: "Boca Aberta Alegre (com dentes e língua)",
        MouthStyle.WINK_SMILE.value: "Sorriso Expressivo Animado",
        MouthStyle.NEUTRAL.value: "Linha Neutra Fechada",
        MouthStyle.CLASSIC.value: "Sorriso Arco Retrô Clássico",
        MouthStyle.CAT.value: "Boquinha Fofa Estilo Gato (:3 / nya)",
        MouthStyle.POUT.value: "Beicinho Suave (Pout)",
        MouthStyle.BLANK.value: "Sem Boca (Superfície Lisa)",
    }


def get_available_eyebrow_styles() -> Dict[str, str]:
    """Retorna estilos de sobrancelha modulares disponíveis."""
    return {
        EyebrowStyle.STANDARD.value: "Sobrancelhas Padrão Harmonizadas",
        EyebrowStyle.THICK.value: "Sobrancelhas Marcadas / Espessas",
        EyebrowStyle.DETERMINED.value: "Sobrancelhas Inclinadas / Confiantes",
        EyebrowStyle.NONE.value: "Sem Sobrancelhas",
    }


def get_available_hair_2d_styles() -> Dict[str, str]:
    """Retorna estilos de textura 2D do couro cabeludo."""
    return {
        Hair2DStyle.STANDARD.value: "Couro Cabeludo Completo com Franja",
        Hair2DStyle.BUZZ.value: "Cabelo Raspado / Militar 2D",
        Hair2DStyle.BALD.value: "Careca / Couro Cabeludo Liso",
    }


def get_available_face_details() -> Dict[str, str]:
    """Retorna detalhes faciais opcionais."""
    return {
        FaceDetail.NONE.value: "Nenhum detalhe adicional",
        FaceDetail.BLUSH.value: "Bochechas Coradas (Blush)",
        FaceDetail.FRECKLES.value: "Sardas Delicadas",
        FaceDetail.BLUSH_AND_FRECKLES.value: "Blush e Sardas Combinados",
    }
