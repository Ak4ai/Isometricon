"""Console de comando e chat interativo estilo Minecraft para o Isometricon.

Permite abrir a barra de chat com [T] ou [/], digitar comandos de personalização
em tempo real (ex: '/skin change eyes red', '/skin mouth cat', '/skin hair pink')
e visualizar o feedback colorido na interface gráfica.
"""

from dataclasses import dataclass
import os
import re
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.clothing.customization import (
    AvatarCustomization,
    BodyType,
    EyebrowStyle,
    EyeStyle,
    HairColor,
    HairStyle,
    HeadType,
    IrisColor,
    MouthStyle,
    IRIS_PALETTES,
    HAIR_PALETTES,
)
from src.clothing.character_model import (
    CharacterModel,
    OUTFIT_PRESETS,
    BOTTOM_PRESETS,
    SKIN_PRESETS,
)
from src.math import mat4_ortho
from src.rendering import Shader


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ChatMessage:
    """Mensagem de texto com cor e timestamp no chat."""
    text: str
    color: Tuple[int, int, int] = (255, 255, 255)
    timestamp: float = 0.0


_SLEEVE_SHIFT_OPTIONS = ["+1cm", "+2cm", "+3cm", "-1cm", "-2cm", "-3cm"]

_SLEEVE_SUBCOMMANDS: Dict[str, Any] = {
    "largura": ["0.8", "0.9", "1.1", "1.2", "1.3"],
    "comprimento": ["+2cm", "+4cm", "-2cm", "-4cm"],
    "horizontal": _SLEEVE_SHIFT_OPTIONS,
    "vertical": ["+1cm", "+2cm", "-1cm", "-2cm"],
    "lateral": _SLEEVE_SHIFT_OPTIONS,
    "fora": ["1cm", "2cm", "3cm"],
    "dentro": ["1cm", "2cm", "3cm"],
    "frente": ["+1cm", "+2cm", "-1cm", "-2cm"],
    "tras": ["1cm", "2cm"],
    "deslocar": {
        "horizontal": _SLEEVE_SHIFT_OPTIONS,
        "vertical": ["+1cm", "+2cm", "-1cm", "-2cm"],
        "fora": ["1cm", "2cm", "3cm"],
        "dentro": ["1cm", "2cm", "3cm"],
        "frente": ["1cm", "2cm"],
        "tras": ["1cm", "2cm"],
        "x": _SLEEVE_SHIFT_OPTIONS,
        "y": ["+1cm", "+2cm", "-1cm", "-2cm"],
        "z": ["+1cm", "+2cm", "-1cm", "-2cm"],
    },
    "width": ["0.8", "0.9", "1.1", "1.2", "1.3"],
    "length": ["+2cm", "+4cm", "-2cm", "-4cm"],
    "shift": {
        "horizontal": _SLEEVE_SHIFT_OPTIONS,
        "vertical": ["+1cm", "+2cm", "-1cm", "-2cm"],
        "out": ["1cm", "2cm", "3cm"],
        "in": ["1cm", "2cm", "3cm"],
        "x": _SLEEVE_SHIFT_OPTIONS,
        "y": ["+1cm", "+2cm", "-1cm", "-2cm"],
        "z": ["+1cm", "+2cm", "-1cm", "-2cm"],
    },
    "x": _SLEEVE_SHIFT_OPTIONS,
    "y": ["+1cm", "+2cm", "-1cm", "-2cm"],
    "z": ["+1cm", "+2cm", "-1cm", "-2cm"],
    "reset": [],
}

_ARM_SUBCOMMANDS: Dict[str, Any] = {
    "largura": ["0.85", "0.9", "1.1", "1.15"],
    "comprimento": ["0.95", "1.05", "1.1"],
    "width": ["0.85", "0.9", "1.1", "1.15"],
    "length": ["0.95", "1.05", "1.1"],
    "reset": [],
}

_HIP_SUBCOMMANDS: Dict[str, Any] = {
    "relevo": ["1.1", "1.2", "1.3", "1.4", "1.5", "+0.2", "+0.3"],
    "bunda": ["1.1", "1.2", "1.3", "1.4", "1.5"],
    "largura": ["0.9", "1.05", "1.1", "1.15", "1.2"],
    "reset": [],
}

_WAIST_SUBCOMMANDS: Dict[str, Any] = {
    "altura": ["+1cm", "+2cm", "+3cm", "-1cm", "-2cm", "-3cm", "1.00", "1.02", "1.07", "0.94", "meio", "alta", "baixa"],
    "sobe": ["1cm", "2cm", "3cm"],
    "desce": ["1cm", "2cm", "3cm"],
    "radius": ["-2cm", "-1cm", "+1cm", "+2cm", "reset"],
    "raio": ["-2cm", "-1cm", "+1cm", "+2cm", "reset"],
    "chanfro": ["0", "1cm", "1.5cm", "2cm", "3cm", "quadrado", "suave", "forte", "reset"],
    "bevel": ["0", "1cm", "1.5cm", "2cm", "3cm", "quadrado", "suave", "forte", "reset"],
    "meio": [],
    "alta": [],
    "baixa": [],
    "reset": [],
}

_BOTTOM_OPTIONS = ["jeans", "skater", "vintage", "baggy", "black_jeans", "none"]
_CALCA_SUBCOMMANDS: Dict[str, Any] = {
    "altura": _WAIST_SUBCOMMANDS["altura"],
    "cintura": _WAIST_SUBCOMMANDS["altura"],
    "sobe": _WAIST_SUBCOMMANDS["sobe"],
    "desce": _WAIST_SUBCOMMANDS["desce"],
    "meio": [],
    "alta": [],
    "baixa": [],
    "reset": [],
    **{opt: [] for opt in _BOTTOM_OPTIONS},
}

_HEM_SUBCOMMANDS: Dict[str, Any] = {
    "altura": ["+1cm", "+2cm", "+3cm", "+5cm", "+8cm", "-1cm", "-2cm", "-3cm", "0.985", "1.02", "1.07", "1.09", "meio", "alta", "cropped", "longa"],
    "sobe": ["1cm", "2cm", "3cm", "5cm"],
    "desce": ["1cm", "2cm", "3cm"],
    "cropped": [],
    "crop": [],
    "alta": [],
    "meio": [],
    "media": [],
    "longa": [],
    "baixa": [],
    "reset": [],
}

_TOP_OPTIONS = ["sweater", "boxy", "jersey", "bomber", "office", "none"]


def get_imported_top_options() -> Dict[str, int]:
    """Descobre dinamicamente todas as roupas superiores (tops) importadas no disco.
    Varre assets/models/clothing/*.obj e assets/models/character_native_*.obj,
    associando aliases amigáveis e IDs às roupas importadas."""
    import glob
    options: Dict[str, int] = dict(OUTFIT_PRESETS)
    bottom_ids = {109837605892174, 137146416353285, 16899958482, 110437430397470, 132042528605488, 16725232711, 16725234970, 331325}
    hair_ids = {76272109569287, 113437321002069, 85654511762633, 6413288640, 113688576496896, 126581321234305, 128696960382202, 116773763268018, 121967101597958, 129026774187807, 131607970996365, 136741436802401, 8529255674}
    tool_ids = {12187348}

    models_dir = os.path.join(PROJECT_ROOT, "assets", "models")
    clothing_dir = os.path.join(models_dir, "clothing")

    if os.path.exists(clothing_dir):
        for f in glob.glob(os.path.join(clothing_dir, "*.obj")):
            base = os.path.basename(f)
            m = re.search(r"(\d+)\.obj$", base)
            if m:
                aid = int(m.group(1))
                if aid in bottom_ids or aid in hair_ids or aid in tool_ids:
                    continue
                options[str(aid)] = aid
                clean_name = re.sub(r"_\d+\.obj$", "", base).lower()
                clean_name = re.sub(r"[^a-z0-9_]+", "_", clean_name).strip("_")
                if clean_name and clean_name not in options:
                    options[clean_name] = aid

    if os.path.exists(models_dir):
        for f in glob.glob(os.path.join(models_dir, "character_native_*.obj")):
            base = os.path.basename(f)
            m = re.match(r"character_native_(\d+)(?:_female)?\.obj$", base)
            if m:
                aid = int(m.group(1))
                if aid not in bottom_ids and aid not in hair_ids and aid not in tool_ids:
                    options[str(aid)] = aid

    return options


_TOP_SUBCOMMANDS: Dict[str, Any] = {
    "barra": _HEM_SUBCOMMANDS["altura"],
    "hem": _HEM_SUBCOMMANDS["altura"],
    "sobe": _HEM_SUBCOMMANDS["sobe"],
    "desce": _HEM_SUBCOMMANDS["desce"],
    "cropped": [],
    "crop": [],
    "alta": [],
    "meio": [],
    "media": [],
    "longa": [],
    "baixa": [],
    "reset": [],
    **{opt: [] for opt in _TOP_OPTIONS},
}

_POSTURA_OPTIONS = ["-4cm", "-3cm", "-5cm", "0", "reset", "padrao"]
_IMPORT_OPTIONS = [
    "9240757332",       # Knit Sweater
    "109837605892174",  # Designer Jeans
    "137146416353285",  # Vintage Baggy Skater Pants
    "89475537632859",   # Boxy Shirt
    "97346273111638",   # Basketball Jersey
    "133331049150205",  # Office Shirt
    "72628400373948",   # Bomber Jacket
    "12187348",         # Ronin Katana
    "131607970996365",  # Wavy Popstar Hair
    "sweater",
    "jeans",
    "skater",
    "boxy",
    "jersey",
    "bomber",
    "office",
    "hair",
]

_HAIR_ADJUST_OPTIONS = ["+1cm", "+2cm", "+3cm", "-1cm", "-2cm", "-3cm", "0", "reset"]
_HAIR_SCALE_OPTIONS = ["0.9", "0.95", "1.0", "1.05", "1.1", "1.15", "1.2", "reset"]

_HAIR_POS_DICT: Dict[str, Any] = {
    "x": _HAIR_ADJUST_OPTIONS,
    "y": _HAIR_ADJUST_OPTIONS,
    "z": _HAIR_ADJUST_OPTIONS,
    "reset": [],
    **{opt: [] for opt in _HAIR_ADJUST_OPTIONS},
}

_HAIR_SCALE_DICT: Dict[str, Any] = {
    "x": _HAIR_SCALE_OPTIONS,
    "y": _HAIR_SCALE_OPTIONS,
    "z": _HAIR_SCALE_OPTIONS,
    "reset": [],
    **{opt: [] for opt in _HAIR_SCALE_OPTIONS},
}

_HAIR_SUBCOMMANDS: Dict[str, Any] = {
    "blonde": [], "pink": [], "black": [], "silver": [], "brunette": [], "auburn": [], "cyan": [],
    "long": [], "buzz": [], "bald": [],
    "pos": _HAIR_POS_DICT,
    "posicao": _HAIR_POS_DICT,
    "scale": _HAIR_SCALE_DICT,
    "tamanho": _HAIR_SCALE_DICT,
    "escala": _HAIR_SCALE_DICT,
    "x": _HAIR_ADJUST_OPTIONS,
    "y": _HAIR_ADJUST_OPTIONS,
    "z": _HAIR_ADJUST_OPTIONS,
    "sobe": ["1cm", "2cm", "3cm"],
    "desce": ["1cm", "2cm", "3cm"],
    "cima": ["1cm", "2cm", "3cm"],
    "baixo": ["1cm", "2cm", "3cm"],
    "frente": ["1cm", "2cm", "3cm"],
    "tras": ["1cm", "2cm", "3cm"],
    "direita": ["1cm", "2cm", "3cm"],
    "esquerda": ["1cm", "2cm", "3cm"],
    "largura": _HAIR_SCALE_OPTIONS,
    "altura": _HAIR_SCALE_OPTIONS,
    "profundidade": _HAIR_SCALE_OPTIONS,
    "reset": ["pos", "scale", "tudo"],
    "status": [],
    "info": [],
}

_SKIN_SUBCOMMANDS: Dict[str, Any] = {
    "body": ["feminino", "masculino", "female", "male"],
    "corpo": ["feminino", "masculino", "female", "male"],
    "eyes": ["blue", "green", "brown", "purple", "red", "gold", "cyan", "anime", "wink", "classic", "blank"],
    "mouth": ["anime_original", "cat", ":3", "smile", "open", "wink_smile", "neutral", "classic", "pout", "blank"],
    "hair": _HAIR_SUBCOMMANDS,
    "cabelo": _HAIR_SUBCOMMANDS,
    "skin": ["pale", "fair", "tan", "olive", "brown", "dark", "gold"],
    "tone": ["pale", "fair", "tan", "olive", "brown", "dark", "gold"],
    "head": ["rounded", "blocky", "postura"],
    "postura": _POSTURA_OPTIONS,
    "import": _IMPORT_OPTIONS,
    "importar": _IMPORT_OPTIONS,
    "wear": _IMPORT_OPTIONS,
    "vestir": _IMPORT_OPTIONS,
    "roblox": _IMPORT_OPTIONS,
    "top": ["sweater", "boxy", "jersey", "bomber", "office", "none"],
    "bottom": _BOTTOM_OPTIONS,
    "calca": _BOTTOM_OPTIONS,
    "pants": _BOTTOM_OPTIONS,
    "tool": ["katana", "none"],
    "spin": ["on", "off"],
    "preset": ["blonde_cat", "dark_knight", "cyber_pink", "classic_vintage", "default"],
    "sleeve": _SLEEVE_SUBCOMMANDS,
    "manga": _SLEEVE_SUBCOMMANDS,
    "arm": _ARM_SUBCOMMANDS,
    "braco": _ARM_SUBCOMMANDS,
    "quadril": _HIP_SUBCOMMANDS,
    "hip": _HIP_SUBCOMMANDS,
    "reset": [],
    "help": [],
    "change": {
        "body": ["feminino", "masculino", "female", "male"],
        "corpo": ["feminino", "masculino", "female", "male"],
        "eyes": ["blue", "green", "brown", "purple", "red", "gold", "cyan", "anime", "wink", "classic", "blank"],
        "mouth": ["anime_original", "cat", ":3", "smile", "open", "wink_smile", "neutral", "classic", "pout", "blank"],
        "hair": _HAIR_SUBCOMMANDS,
        "cabelo": _HAIR_SUBCOMMANDS,
        "skin": ["pale", "fair", "tan", "olive", "brown", "dark", "gold"],
        "tone": ["pale", "fair", "tan", "olive", "brown", "dark", "gold"],
        "head": ["rounded", "blocky"],
        "top": ["sweater", "boxy", "jersey", "bomber", "office", "none"],
        "bottom": _BOTTOM_OPTIONS,
        "calca": _BOTTOM_OPTIONS,
        "pants": _BOTTOM_OPTIONS,
        "tool": ["katana", "none"],
        "sleeve": _SLEEVE_SUBCOMMANDS,
        "manga": _SLEEVE_SUBCOMMANDS,
        "arm": _ARM_SUBCOMMANDS,
        "braco": _ARM_SUBCOMMANDS,
    },
}

# Árvore hierárquica para sugestão e autocompletar estilo Minecraft
COMMAND_TREE: Dict[str, Any] = {
    "skin": _SKIN_SUBCOMMANDS,
    "eyes": ["blue", "green", "brown", "purple", "red", "gold", "cyan", "anime", "wink", "classic", "blank"],
    "mouth": ["anime_original", "cat", ":3", "smile", "open", "wink_smile", "neutral", "classic", "pout", "blank"],
    "hair": _HAIR_SUBCOMMANDS,
    "tone": ["pale", "fair", "tan", "olive", "brown", "dark", "gold"],
    "head": ["rounded", "blocky"],
    "top": ["sweater", "boxy", "jersey", "bomber", "office", "none"],
    "bottom": _BOTTOM_OPTIONS,
    "calca": _BOTTOM_OPTIONS,
    "pants": _BOTTOM_OPTIONS,
    "tool": ["katana", "none"],
    "spin": ["on", "off"],
    "preset": ["blonde_cat", "dark_knight", "cyber_pink", "classic_vintage", "default"],
    "sleeve": _SLEEVE_SUBCOMMANDS,
    "manga": _SLEEVE_SUBCOMMANDS,
    "arm": _ARM_SUBCOMMANDS,
    "braco": _ARM_SUBCOMMANDS,
    "deslocar": _SLEEVE_SUBCOMMANDS["deslocar"],
    "horizontal": _SLEEVE_SHIFT_OPTIONS,
    "vertical": ["+1cm", "+2cm", "-1cm", "-2cm"],
    "lateral": _SLEEVE_SHIFT_OPTIONS,
    "fora": ["1cm", "2cm", "3cm"],
    "dentro": ["1cm", "2cm", "3cm"],
    "shift": _SLEEVE_SUBCOMMANDS["shift"],
    "offset": _SLEEVE_SUBCOMMANDS["deslocar"],
    "reset": [],
    "help": [],
}

COMMAND_TREE["char"] = COMMAND_TREE["skin"]
COMMAND_TREE["avatar"] = COMMAND_TREE["skin"]
COMMAND_TREE["set"] = COMMAND_TREE["skin"]
COMMAND_TREE["body"] = _SKIN_SUBCOMMANDS["body"]
COMMAND_TREE["corpo"] = _SKIN_SUBCOMMANDS["corpo"]
COMMAND_TREE["olhos"] = COMMAND_TREE["eyes"]
COMMAND_TREE["boca"] = COMMAND_TREE["mouth"]
COMMAND_TREE["cabelo"] = COMMAND_TREE["hair"]
COMMAND_TREE["pele"] = _SKIN_SUBCOMMANDS["skin"]
COMMAND_TREE["cabeca"] = COMMAND_TREE["head"]
COMMAND_TREE["roupa"] = COMMAND_TREE["top"]
COMMAND_TREE["calca"] = _CALCA_SUBCOMMANDS
COMMAND_TREE["pants"] = _CALCA_SUBCOMMANDS
COMMAND_TREE["bottom"] = _CALCA_SUBCOMMANDS
COMMAND_TREE["arma"] = COMMAND_TREE["tool"]
COMMAND_TREE["rotacao"] = COMMAND_TREE["spin"]
COMMAND_TREE["turntable"] = COMMAND_TREE["spin"]
COMMAND_TREE["ajuda"] = COMMAND_TREE["help"]
COMMAND_TREE["quadril"] = _HIP_SUBCOMMANDS
COMMAND_TREE["hip"] = _HIP_SUBCOMMANDS
COMMAND_TREE["bunda"] = _HIP_SUBCOMMANDS["relevo"]
COMMAND_TREE["gluteos"] = _HIP_SUBCOMMANDS["relevo"]
COMMAND_TREE["cintura"] = _WAIST_SUBCOMMANDS
COMMAND_TREE["waist"] = _WAIST_SUBCOMMANDS
COMMAND_TREE["cos"] = _WAIST_SUBCOMMANDS
COMMAND_TREE["radius"] = _WAIST_SUBCOMMANDS["radius"]
COMMAND_TREE["raio"] = _WAIST_SUBCOMMANDS["raio"]
COMMAND_TREE["chanfro"] = _WAIST_SUBCOMMANDS["chanfro"]
COMMAND_TREE["bevel"] = _WAIST_SUBCOMMANDS["bevel"]
COMMAND_TREE["barra"] = _HEM_SUBCOMMANDS
COMMAND_TREE["hem"] = _HEM_SUBCOMMANDS
COMMAND_TREE["crop"] = _HEM_SUBCOMMANDS
COMMAND_TREE["cropped"] = _HEM_SUBCOMMANDS
COMMAND_TREE["top"] = _TOP_SUBCOMMANDS
COMMAND_TREE["camisa"] = _TOP_SUBCOMMANDS
COMMAND_TREE["blusa"] = _TOP_SUBCOMMANDS
COMMAND_TREE["postura"] = _POSTURA_OPTIONS
COMMAND_TREE["import"] = _IMPORT_OPTIONS
COMMAND_TREE["importar"] = _IMPORT_OPTIONS
COMMAND_TREE["wear"] = _IMPORT_OPTIONS
COMMAND_TREE["vestir"] = _IMPORT_OPTIONS
COMMAND_TREE["roblox"] = _IMPORT_OPTIONS
COMMAND_TREE["pos"] = _HAIR_SUBCOMMANDS["pos"]
COMMAND_TREE["posicao"] = _HAIR_SUBCOMMANDS["posicao"]
COMMAND_TREE["scale"] = _HAIR_SUBCOMMANDS["scale"]
COMMAND_TREE["tamanho"] = _HAIR_SUBCOMMANDS["tamanho"]
COMMAND_TREE["escala"] = _HAIR_SUBCOMMANDS["escala"]

SUGGESTIONS_EXPECTING_ARGS = {
    "/skin", "/char", "/avatar", "/set",
    "/body", "/corpo",
    "/eyes", "/mouth", "/hair", "/skin", "/head", "/top", "/bottom", "/tool", "/preset", "/spin",
    "/olhos", "/boca", "/cabelo", "/pele", "/cabeca", "/roupa", "/calca", "/arma", "/rotacao", "/turntable",
    "/sleeve", "/manga", "/arm", "/braco",
    "/quadril", "/hip", "/bunda", "/gluteos",
    "/cintura", "/waist", "/cos",
    "/radius", "/raio",
    "/chanfro", "/bevel",
    "/barra", "/hem", "/crop", "/cropped",
    "/postura",
    "/import", "/importar", "/wear", "/vestir", "/roblox",
    "/horizontal", "/vertical", "/lateral", "/deslocar", "/shift", "/offset",
    "/pos", "/posicao", "/scale", "/tamanho", "/escala",
    "cintura", "waist", "cos",
    "radius", "raio",
    "chanfro", "bevel",
    "barra", "hem", "crop", "cropped",
    "postura",
    "import", "importar", "wear", "vestir", "roblox",
    "skin", "char", "avatar", "set",
    "body", "corpo",
    "eyes", "eye", "olhos", "olho", "iris",
    "mouth", "boca", "lips", "expressao",
    "hair", "cabelo",
    "skin", "pele",
    "quadril", "hip", "bunda", "gluteos",
    "head", "cabeca",
    "top", "camisa", "roupa",
    "bottom", "calca",
    "tool", "arma", "item",
    "preset", "presets",
    "spin", "rotacao", "turntable",
    "sleeve", "manga", "cuff", "punho",
    "arm", "braco",
    "largura", "comprimento", "width", "length", "lar", "comp", "w", "l",
    "horizontal", "vertical", "lateral", "frente", "tras", "trás", "fora", "dentro",
    "deslocar", "shift", "offset", "mover", "x", "y", "z", "out", "in", "front", "back",
    "cima", "baixo", "sobe", "desce",
    "chanfro", "bevel",
    "change", "set", "mudar", "alterar",
    "pos", "posicao", "position", "scale", "tamanho", "escala", "size",
}


def _parse_distance(val_str: str, current: float = 0.0, allow_relative_minus: bool = False) -> float:
    """Converte strings de distância com unidades (cm, m) ou números para metros."""
    raw = val_str.lower().strip()
    is_relative = raw.startswith("+") or (allow_relative_minus and raw.startswith("-"))
    if raw.endswith("cm"):
        val_m = float(raw.rstrip("cm")) / 100.0
    elif raw.endswith("m"):
        val_m = float(raw.rstrip("m"))
    else:
        num = float(raw)
        val_m = (num / 100.0) if abs(num) > 0.5 else num
    return (current + val_m) if is_relative else val_m


def _parse_scale(val_str: str, current: float = 1.0) -> float:
    """Converte strings de escala (fator float, percentual ou relativo) para float (0.2x a 3.0x)."""
    raw = val_str.strip().lower()
    if raw in ("reset", "padrao", "default", "normal"):
        return 1.0
    if raw.endswith("%"):
        pct = float(raw.rstrip("%"))
        if raw.startswith(("+", "-")):
            val = current + (pct / 100.0)
        else:
            val = pct / 100.0
    elif raw.startswith(("+", "-")):
        val = current + float(raw)
    else:
        val = float(raw)
    return max(0.2, min(3.0, val))


class SkinCommandHandler:
    """Processador de comandos de personalização de skin e roupas."""

    def __init__(
        self,
        character_model: Optional[CharacterModel] = None,
        turntable_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.character_model = character_model
        self.turntable_state = turntable_state
        self.chat_console = None
        self.is_importing: bool = False
        self.import_status: str = ""
        self.import_asset_id: Optional[int] = None
        self._pending_main_thread_callbacks: List[Callable[[], None]] = []
        self._callback_lock = threading.Lock()

    def process_pending_callbacks(self) -> None:
        """Executa quaisquer tarefas agendadas por threads secundárias na thread principal (OpenGL)."""
        with self._callback_lock:
            if not self._pending_main_thread_callbacks:
                return
            callbacks = list(self._pending_main_thread_callbacks)
            self._pending_main_thread_callbacks.clear()
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                print(f"[SkinCommandHandler] Erro ao processar callback na thread principal: {e}")

    def execute(self, cmd_line: str, run_async: bool = True) -> Tuple[bool, str, Tuple[int, int, int]]:
        """Executa um comando de linha de chat.

        Retorna:
            (sucesso: bool, mensagem_feedback: str, cor_rgb: Tuple[int, int, int])
        """
        line = cmd_line.strip()
        if not line:
            return False, "", (255, 255, 255)

        # Remove barra inicial opcional
        if line.startswith("/"):
            line = line[1:].strip()

        tokens = line.split()
        if not tokens:
            return False, "", (255, 255, 255)

        cmd = tokens[0].lower()
        args = tokens[1:]

        # Atalhos e aliases: aceita '/skin', '/char', '/set' ou direto '/eyes', '/mouth', etc.
        if cmd in ("skin", "char", "avatar", "set"):
            if not args:
                return True, "Uso: /skin <manga|braco|top|eyes|mouth|hair|skin|head|bottom|tool|spin|preset|reset|help>", (255, 215, 0)
            # Ignora palavras intermediárias como 'change' ou 'set' (ex: /skin change eyes red)
            if args[0].lower() in ("change", "set", "alterar", "mudar") and len(args) > 1:
                sub_cmd = args[1].lower()
                sub_args = args[2:]
            else:
                sub_cmd = args[0].lower()
                sub_args = args[1:]
        elif cmd in (
            "deslocar", "mover", "offset", "shift",
            "horizontal", "vertical", "lateral",
            "fora", "dentro", "frente", "tras", "trás"
        ):
            sub_cmd = "manga"
            sub_args = [cmd] + args
        elif cmd in ("radius", "raio"):
            sub_cmd = "cintura"
            sub_args = ["radius"] + args
        elif cmd in ("chanfro", "bevel", "arredondar", "curvatura"):
            sub_cmd = "cintura"
            sub_args = ["chanfro"] + args
        elif cmd in ("postura", "posture"):
            sub_cmd = "postura"
            sub_args = args
        elif cmd in ("import", "importar", "wear", "vestir", "roblox"):
            sub_cmd = "import"
            sub_args = args
        elif cmd in ("pos", "posicao", "position", "pos_cabelo", "cabelo_pos", "hair_pos"):
            sub_cmd = "cabelo"
            sub_args = ["pos"] + args
        elif cmd in ("scale", "escala", "tamanho", "size", "scale_cabelo", "cabelo_scale", "hair_scale", "tamanho_cabelo"):
            sub_cmd = "cabelo"
            sub_args = ["scale"] + args
        else:
            sub_cmd = cmd
            sub_args = args

        return self._handle_subcommand(sub_cmd, sub_args, run_async=run_async)

    def _handle_subcommand(self, sub_cmd: str, args: List[str], run_async: bool = True) -> Tuple[bool, str, Tuple[int, int, int]]:
        GREEN = (85, 255, 85)
        GOLD = (255, 215, 0)
        RED = (255, 85, 85)
        CYAN = (85, 255, 255)

        if sub_cmd in ("help", "ajuda", "?"):
            help_lines = (
                "Comandos: /body <feminino|masculino> | /manga <largura|comprimento|reset> | /braco <largura|comprimento|reset> | "
                "/skin top <roupa> | /skin eyes <cor/estilo> | /skin mouth <estilo> | /skin hair <cor/estilo> | "
                "/skin head <tipo> | /skin tool <arma> | /skin spin | /skin reset"
            )
            return True, help_lines, GOLD

        # ------------------------------------------------------------------
        # 0. Modelo de Corpo (Body Type: Feminino vs Masculino)
        # ------------------------------------------------------------------
        if sub_cmd in ("body", "corpo", "gender", "genero", "sexo"):
            if not args:
                return False, "Uso: /body <feminino|masculino> OU /skin body <feminino|masculino>", GOLD

            val = args[0].lower()
            if val in ("fem", "female", "feminino", "mulher", "woman", "f"):
                if self.character_model:
                    self.character_model.customization.body_type = BodyType.FEMALE
                    self.character_model.reload()
                return True, "[Skin] Modelo de corpo alterado para FEMININO (Collection 6)", GREEN

            if val in ("masc", "male", "masculino", "homem", "man", "m"):
                if self.character_model:
                    self.character_model.customization.body_type = BodyType.MALE
                    self.character_model.reload()
                return True, "[Skin] Modelo de corpo alterado para MASCULINO (Padrão)", GREEN

            return False, f"[Erro] Modelo de corpo '{val}' desconhecido. Opcoes: feminino, masculino.", RED

        # ------------------------------------------------------------------
        # 1. Olhos (Eyes / Iris / Style)
        # ------------------------------------------------------------------
        if sub_cmd in ("eyes", "eye", "olhos", "olho", "iris"):
            if not args:
                opts = "blue, green, brown, purple, red, gold, cyan | estilos: anime, wink, classic, blank"
                return False, f"Uso: /skin eyes <opcao>. Opcoes: {opts}", GOLD

            val = args[0].lower()

            # Estilo de olhos
            if val in ("wink", "anime_wink", "piscadela", "piscar"):
                if self.character_model:
                    self.character_model.customization.eye_style = EyeStyle.ANIME_WINK
                    self.character_model.reload()
                return True, "[Skin] Estilo de olhos alterado para WINK (Piscadela Animada 😉)", GREEN

            if val in ("classic", "classico", "retro"):
                if self.character_model:
                    self.character_model.customization.eye_style = EyeStyle.CLASSIC
                    self.character_model.reload()
                return True, "[Skin] Estilo de olhos alterado para CLASSIC (Retrô Clássico)", GREEN

            if val in ("anime", "normal", "padrao"):
                if self.character_model:
                    self.character_model.customization.eye_style = EyeStyle.ANIME
                    self.character_model.reload()
                return True, "[Skin] Estilo de olhos alterado para ANIME (Expressivo)", GREEN

            if val in ("blank", "none", "sem", "liso"):
                if self.character_model:
                    self.character_model.customization.eye_style = EyeStyle.BLANK
                    self.character_model.reload()
                return True, "[Skin] Olhos ocultados (Sem olhos)", GREEN

            # Cor da íris
            found_color = None
            for c in IrisColor:
                if c.value.lower() == val:
                    found_color = c
                    break

            if found_color:
                if self.character_model:
                    self.character_model.customization.iris_color = found_color
                    # Se estava em classic ou blank, restaura anime para exibir a nova cor
                    if self.character_model.customization.resolved_eye_style in ("classic", "blank"):
                        self.character_model.customization.eye_style = EyeStyle.ANIME
                    self.character_model.reload()
                return True, f"[Skin] Íris alterada para {found_color.value.upper()}", GREEN

            return False, f"[Erro] Cor de olhos '{val}' desconhecida. Use: blue, green, brown, purple, red, gold, cyan.", RED

        # ------------------------------------------------------------------
        # 2. Boca (Mouth / Expression)
        # ------------------------------------------------------------------
        if sub_cmd in ("mouth", "boca", "lips", "labios", "expressao"):
            if not args:
                opts = "anime_original, cat (:3), smile, open, wink_smile, neutral, classic, pout, blank"
                return False, f"Uso: /skin mouth <estilo>. Opcoes: {opts}", GOLD

            val = args[0].lower()
            alias_map = {
                ":3": MouthStyle.CAT,
                "nya": MouthStyle.CAT,
                "gato": MouthStyle.CAT,
                "cat": MouthStyle.CAT,
                "anime_original": MouthStyle.ANIME_ORIGINAL,
                "original": MouthStyle.ANIME_ORIGINAL,
                "default": MouthStyle.ANIME_ORIGINAL,
                "anime": MouthStyle.ANIME_ORIGINAL,
                "smile": MouthStyle.SMILE,
                "sorriso": MouthStyle.SMILE,
                "open": MouthStyle.OPEN,
                "aberta": MouthStyle.OPEN,
                "wink_smile": MouthStyle.WINK_SMILE,
                "wink": MouthStyle.WINK_SMILE,
                "neutral": MouthStyle.NEUTRAL,
                "neutra": MouthStyle.NEUTRAL,
                "classic": MouthStyle.CLASSIC,
                "classica": MouthStyle.CLASSIC,
                "pout": MouthStyle.POUT,
                "beicinho": MouthStyle.POUT,
                "blank": MouthStyle.BLANK,
                "none": MouthStyle.BLANK,
                "sem": MouthStyle.BLANK,
            }

            if val in alias_map:
                mouth_style = alias_map[val]
                if self.character_model:
                    self.character_model.customization.mouth_style = mouth_style
                    self.character_model.reload()
                return True, f"[Skin] Boca alterada para {mouth_style.value.upper()}", GREEN

            return False, f"[Erro] Estilo de boca '{val}' desconhecido. Opcoes: anime_original, cat, smile, open, neutral, pout.", RED

        # ------------------------------------------------------------------
        # 3. Cabelo (Hair Color / Style)
        # ------------------------------------------------------------------
        if sub_cmd in ("hair", "cabelo"):
            if not self.character_model:
                return False, "[Cabelo] Modelo de personagem não disponível.", RED

            if not args or args[0].lower() in ("status", "info"):
                ox = self.character_model.hair_offset_x * 100.0
                oy = self.character_model.hair_offset_y * 100.0
                oz = self.character_model.hair_offset_z * 100.0
                sx = self.character_model.hair_scale_x
                sy = self.character_model.hair_scale_y
                sz = self.character_model.hair_scale_z
                return True, (
                    f"[Cabelo] Offset (Posição): X: {ox:+.1f}cm, Y: {oy:+.1f}cm, Z: {oz:+.1f}cm | "
                    f"Tamanho (Escala): X: {sx:.2f}x, Y: {sy:.2f}x, Z: {sz:.2f}x\n"
                    f"Comandos: /cabelo pos <x> <y> <z> | /cabelo scale <x> [y] [z] | "
                    f"/cabelo <x|y|z|sobe|desce|frente|tras|largura> <val> | /cabelo reset"
                ), GOLD

            val = args[0].lower()

            # 3.1 Reset de ajustes manuais
            if val in ("reset", "restaurar"):
                if len(args) > 1 and args[1].lower() in ("pos", "posicao", "position", "offset", "deslocar"):
                    self.character_model.reset_hair_position()
                    return True, "[Cabelo] Posição do cabelo restaurada para o padrão (0.0cm, 0.0cm, 0.0cm).", GREEN
                elif len(args) > 1 and args[1].lower() in ("scale", "tamanho", "escala", "size"):
                    self.character_model.reset_hair_scale()
                    return True, "[Cabelo] Tamanho/escala do cabelo restaurado para 1.00x (X, Y, Z).", GREEN
                else:
                    self.character_model.reset_hair_adjustments()
                    return True, "[Cabelo] Posição e escala do cabelo restaurados para o padrão original.", GREEN

            # 3.2 Ajuste Composto de Posição: /cabelo pos <x> <y> <z> OU /cabelo pos <x|y|z> <val>
            if val in ("pos", "posicao", "position", "offset", "deslocar"):
                if len(args) == 1:
                    ox = self.character_model.hair_offset_x * 100.0
                    oy = self.character_model.hair_offset_y * 100.0
                    oz = self.character_model.hair_offset_z * 100.0
                    return False, f"Uso: /cabelo pos <x> <y> <z> OU /cabelo pos <x|y|z> <val> (Atual: X: {ox:+.1f}cm, Y: {oy:+.1f}cm, Z: {oz:+.1f}cm)", GOLD

                if args[1].lower() in ("reset", "padrao", "default"):
                    self.character_model.reset_hair_position()
                    return True, "[Cabelo] Posição do cabelo restaurada para o padrão (0.0cm, 0.0cm, 0.0cm).", GREEN

                if args[1].lower() in ("x", "y", "z") and len(args) >= 3:
                    ax = args[1].lower()
                    cur_val = getattr(self.character_model, f"hair_offset_{ax}")
                    try:
                        new_val = _parse_distance(args[2], cur_val, allow_relative_minus=True)
                        self.character_model.set_hair_offset(**{ax: new_val})
                        res_cm = getattr(self.character_model, f"hair_offset_{ax}") * 100.0
                        return True, f"[Cabelo] Posição {ax.upper()} ajustada para {res_cm:+.1f}cm.", GREEN
                    except ValueError:
                        return False, f"[Erro] Valor de distância '{args[2]}' inválido. Ex: +2cm, -1cm, 0", RED

                if len(args) >= 4:
                    try:
                        cur_x = self.character_model.hair_offset_x
                        cur_y = self.character_model.hair_offset_y
                        cur_z = self.character_model.hair_offset_z
                        nx = _parse_distance(args[1], cur_x, allow_relative_minus=True)
                        ny = _parse_distance(args[2], cur_y, allow_relative_minus=True)
                        nz = _parse_distance(args[3], cur_z, allow_relative_minus=True)
                        self.character_model.set_hair_offset(x=nx, y=ny, z=nz)
                        return True, (
                            f"[Cabelo] Posição atualizada: X: {self.character_model.hair_offset_x*100:+.1f}cm, "
                            f"Y: {self.character_model.hair_offset_y*100:+.1f}cm, "
                            f"Z: {self.character_model.hair_offset_z*100:+.1f}cm"
                        ), GREEN
                    except ValueError:
                        return False, f"[Erro] Valores de posição inválidos: {' '.join(args[1:4])}. Ex: 0 +2cm -1cm", RED

                if len(args) == 2:
                    try:
                        cur_y = self.character_model.hair_offset_y
                        ny = _parse_distance(args[1], cur_y, allow_relative_minus=True)
                        self.character_model.set_hair_offset(y=ny)
                        return True, f"[Cabelo] Posição Y ajustada para {self.character_model.hair_offset_y*100:+.1f}cm.", GREEN
                    except ValueError:
                        return False, f"[Erro] Valor de posição '{args[1]}' inválido. Ex: +2cm, -1cm, 0", RED

            # 3.3 Eixos Diretos de Posição (X, Y, Z, sobe, desce, frente, tras, etc.)
            if val in ("x", "lateral", "horizontal"):
                if len(args) < 2:
                    return False, f"Uso: /cabelo x <distância> (Atual: {self.character_model.hair_offset_x*100:+.1f}cm)", GOLD
                try:
                    cur_x = self.character_model.hair_offset_x
                    nx = _parse_distance(args[1], cur_x, allow_relative_minus=True)
                    self.character_model.set_hair_offset(x=nx)
                    return True, f"[Cabelo] Posição X (lateral) ajustada para {self.character_model.hair_offset_x*100:+.1f}cm.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: +1cm, -1cm, 0", RED

            if val in ("y", "vertical"):
                if len(args) < 2:
                    return False, f"Uso: /cabelo y <distância> (Atual: {self.character_model.hair_offset_y*100:+.1f}cm)", GOLD
                try:
                    cur_y = self.character_model.hair_offset_y
                    ny = _parse_distance(args[1], cur_y, allow_relative_minus=True)
                    self.character_model.set_hair_offset(y=ny)
                    return True, f"[Cabelo] Posição Y (vertical) ajustada para {self.character_model.hair_offset_y*100:+.1f}cm.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: +2cm, -1cm, 0", RED

            if val in ("z", "sagital"):
                if len(args) < 2:
                    return False, f"Uso: /cabelo z <distância> (Atual: {self.character_model.hair_offset_z*100:+.1f}cm)", GOLD
                try:
                    cur_z = self.character_model.hair_offset_z
                    nz = _parse_distance(args[1], cur_z, allow_relative_minus=True)
                    self.character_model.set_hair_offset(z=nz)
                    return True, f"[Cabelo] Posição Z (frente/trás) ajustada para {self.character_model.hair_offset_z*100:+.1f}cm.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: +1cm, -1cm, 0", RED

            if val in ("sobe", "cima", "up"):
                if len(args) < 2:
                    return False, "Uso: /cabelo sobe <distância> (Ex: 2cm, 1.5cm)", GOLD
                try:
                    d = abs(_parse_distance(args[1], 0.0, allow_relative_minus=False))
                    ny = self.character_model.hair_offset_y + d
                    self.character_model.set_hair_offset(y=ny)
                    return True, f"[Cabelo] Cabelo elevado: Y = {self.character_model.hair_offset_y*100:+.1f}cm (+{d*100:.1f}cm).", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 2cm, 1cm", RED

            if val in ("desce", "baixo", "down"):
                if len(args) < 2:
                    return False, "Uso: /cabelo desce <distância> (Ex: 2cm, 1.5cm)", GOLD
                try:
                    d = abs(_parse_distance(args[1], 0.0, allow_relative_minus=False))
                    ny = self.character_model.hair_offset_y - d
                    self.character_model.set_hair_offset(y=ny)
                    return True, f"[Cabelo] Cabelo rebaixado: Y = {self.character_model.hair_offset_y*100:+.1f}cm (-{d*100:.1f}cm).", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 2cm, 1cm", RED

            if val in ("frente", "front"):
                if len(args) < 2:
                    return False, "Uso: /cabelo frente <distância> (Ex: 1cm)", GOLD
                try:
                    d = abs(_parse_distance(args[1], 0.0, allow_relative_minus=False))
                    nz = self.character_model.hair_offset_z + d
                    self.character_model.set_hair_offset(z=nz)
                    return True, f"[Cabelo] Cabelo movido para frente: Z = {self.character_model.hair_offset_z*100:+.1f}cm (+{d*100:.1f}cm).", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 1cm", RED

            if val in ("tras", "trás", "back"):
                if len(args) < 2:
                    return False, "Uso: /cabelo tras <distância> (Ex: 1cm)", GOLD
                try:
                    d = abs(_parse_distance(args[1], 0.0, allow_relative_minus=False))
                    nz = self.character_model.hair_offset_z - d
                    self.character_model.set_hair_offset(z=nz)
                    return True, f"[Cabelo] Cabelo movido para trás: Z = {self.character_model.hair_offset_z*100:+.1f}cm (-{d*100:.1f}cm).", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 1cm", RED

            if val in ("direita", "right"):
                if len(args) < 2:
                    return False, "Uso: /cabelo direita <distância> (Ex: 1cm)", GOLD
                try:
                    d = abs(_parse_distance(args[1], 0.0, allow_relative_minus=False))
                    nx = self.character_model.hair_offset_x + d
                    self.character_model.set_hair_offset(x=nx)
                    return True, f"[Cabelo] Cabelo movido para direita: X = {self.character_model.hair_offset_x*100:+.1f}cm.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 1cm", RED

            if val in ("esquerda", "left"):
                if len(args) < 2:
                    return False, "Uso: /cabelo esquerda <distância> (Ex: 1cm)", GOLD
                try:
                    d = abs(_parse_distance(args[1], 0.0, allow_relative_minus=False))
                    nx = self.character_model.hair_offset_x - d
                    self.character_model.set_hair_offset(x=nx)
                    return True, f"[Cabelo] Cabelo movido para esquerda: X = {self.character_model.hair_offset_x*100:+.1f}cm.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 1cm", RED

            # 3.4 Ajuste de Escala / Tamanho: /cabelo scale <val> OU /cabelo scale <sx> <sy> <sz> OU /cabelo scale <x|y|z> <val>
            if val in ("scale", "tamanho", "escala", "size"):
                if len(args) == 1:
                    sx = self.character_model.hair_scale_x
                    sy = self.character_model.hair_scale_y
                    sz = self.character_model.hair_scale_z
                    return False, f"Uso: /cabelo scale <valor> OU /cabelo scale <sx> <sy> <sz> OU /cabelo scale <x|y|z> <val> (Atual: X: {sx:.2f}x, Y: {sy:.2f}x, Z: {sz:.2f}x)", GOLD

                if args[1].lower() in ("reset", "padrao", "default"):
                    self.character_model.reset_hair_scale()
                    return True, "[Cabelo] Tamanho/escala do cabelo restaurado para 1.00x (X, Y, Z).", GREEN

                if args[1].lower() in ("x", "y", "z") and len(args) >= 3:
                    ax = args[1].lower()
                    cur_s = getattr(self.character_model, f"hair_scale_{ax}")
                    try:
                        new_s = _parse_scale(args[2], cur_s)
                        self.character_model.set_hair_scale(**{ax: new_s})
                        return True, f"[Cabelo] Tamanho/Escala {ax.upper()} ajustado para: {getattr(self.character_model, f'hair_scale_{ax}'):.2f}x", GREEN
                    except ValueError:
                        return False, f"[Erro] Valor de escala '{args[2]}' inválido. Ex: 1.1, 0.95, +10%", RED

                if len(args) >= 4:
                    try:
                        cur_sx = self.character_model.hair_scale_x
                        cur_sy = self.character_model.hair_scale_y
                        cur_sz = self.character_model.hair_scale_z
                        nsx = _parse_scale(args[1], cur_sx)
                        nsy = _parse_scale(args[2], cur_sy)
                        nsz = _parse_scale(args[3], cur_sz)
                        self.character_model.set_hair_scale(x=nsx, y=nsy, z=nsz)
                        return True, f"[Cabelo] Tamanho/Escala ajustado: X={nsx:.2f}x, Y={nsy:.2f}x, Z={nsz:.2f}x", GREEN
                    except ValueError:
                        return False, f"[Erro] Valores de escala inválidos: {' '.join(args[1:4])}. Ex: 1.05 1.0 1.05", RED

                if len(args) == 2:
                    try:
                        cur_s = self.character_model.hair_scale_x
                        ns = _parse_scale(args[1], cur_s)
                        self.character_model.set_hair_scale(ns)
                        return True, f"[Cabelo] Tamanho/Escala uniforme ajustado para {ns:.2f}x (X, Y, Z).", GREEN
                    except ValueError:
                        return False, f"[Erro] Valor de escala '{args[1]}' inválido. Ex: 1.1, 0.95, 110%, +0.05", RED

            # 3.5 Atalhos diretos de escala por dimensão
            if val in ("largura", "width", "sx"):
                if len(args) < 2:
                    return False, f"Uso: /cabelo largura <valor> (Atual: {self.character_model.hair_scale_x:.2f}x)", GOLD
                try:
                    cur_sx = self.character_model.hair_scale_x
                    nsx = _parse_scale(args[1], cur_sx)
                    self.character_model.set_hair_scale(x=nsx)
                    return True, f"[Cabelo] Largura (Escala X) ajustada para {self.character_model.hair_scale_x:.2f}x.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 1.1, 0.95, 110%", RED

            if val in ("altura", "height", "sy"):
                if len(args) < 2:
                    return False, f"Uso: /cabelo altura <valor> (Atual: {self.character_model.hair_scale_y:.2f}x)", GOLD
                if args[1].endswith(("cm", "mm", "m")):
                    try:
                        cur_y = self.character_model.hair_offset_y
                        ny = _parse_distance(args[1], cur_y, allow_relative_minus=True)
                        self.character_model.set_hair_offset(y=ny)
                        return True, f"[Cabelo] Posição Y ajustada para {self.character_model.hair_offset_y*100:+.1f}cm.", GREEN
                    except ValueError:
                        return False, f"[Erro] Valor '{args[1]}' inválido.", RED
                try:
                    cur_sy = self.character_model.hair_scale_y
                    nsy = _parse_scale(args[1], cur_sy)
                    self.character_model.set_hair_scale(y=nsy)
                    return True, f"[Cabelo] Altura (Escala Y) ajustada para {self.character_model.hair_scale_y:.2f}x.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 1.05, 0.95", RED

            if val in ("profundidade", "depth", "sz"):
                if len(args) < 2:
                    return False, f"Uso: /cabelo profundidade <valor> (Atual: {self.character_model.hair_scale_z:.2f}x)", GOLD
                if args[1].endswith(("cm", "mm", "m")) or args[1].startswith(("+", "-")):
                    try:
                        cur_z = self.character_model.hair_offset_z
                        nz = _parse_distance(args[1], cur_z, allow_relative_minus=True)
                        self.character_model.set_hair_offset(z=nz)
                        return True, f"[Cabelo] Posição Z ajustada para {self.character_model.hair_offset_z*100:+.1f}cm.", GREEN
                    except ValueError:
                        return False, f"[Erro] Valor '{args[1]}' inválido.", RED
                try:
                    cur_sz = self.character_model.hair_scale_z
                    nsz = _parse_scale(args[1], cur_sz)
                    self.character_model.set_hair_scale(z=nsz)
                    return True, f"[Cabelo] Profundidade (Escala Z) ajustada para {self.character_model.hair_scale_z:.2f}x.", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{args[1]}' inválido. Ex: 1.05, 0.95", RED

            # ID numérico do Roblox para equipar cabelo diretamente
            if val.isdigit() or ("roblox.com" in val):
                return self._handle_import_roblox(["import", val, "hair"], run_async=False)

            # Estilo
            if val in ("bald", "careca", "none", "sem"):
                if self.character_model:
                    self.character_model.update_customization(hair_id="none")
                    self.character_model.customization.hair_style = HairStyle.BALD
                    self.character_model.reload()
                return True, "[Skin] Cabelo alterado para BALD (Careca)", GREEN

            if val in ("buzz", "buzz_cut", "militar", "curto"):
                if self.character_model:
                    self.character_model.update_customization(hair_id="none")
                    self.character_model.customization.hair_style = HairStyle.BUZZ_CUT
                    self.character_model.reload()
                return True, "[Skin] Cabelo alterado para BUZZ CUT (Raspado 2D)", GREEN

            if val in ("long", "anime_long", "3d", "longo", "default", "padrao", "original"):
                if self.character_model:
                    self.character_model.update_customization(hair_id="116773763268018")
                    self.character_model.customization.hair_style = HairStyle.ANIME_LONG
                    self.character_model.reload()
                return True, "[Skin] Cabelo alterado para ANIME LONG (Malha 3D)", GREEN

            # Cor do cabelo
            found_hcolor = None
            for h in HairColor:
                if h.value.lower() == val:
                    found_hcolor = h
                    break

            if found_hcolor:
                if self.character_model:
                    self.character_model.customization.hair_color = found_hcolor
                    # Se estava careca e o usuário pediu cor, restaura anime_long
                    if self.character_model.customization.hair_style == HairStyle.BALD:
                        self.character_model.update_customization(hair_id="116773763268018")
                        self.character_model.customization.hair_style = HairStyle.ANIME_LONG
                    self.character_model.reload()
                return True, f"[Skin] Cor do cabelo alterada para {found_hcolor.value.upper()}", GREEN

            opts = "cores (blonde, pink, black...), estilos (bald, buzz, long, <ID>), posição (pos, x, y, z, sobe, desce...), tamanho (scale, largura, altura...) ou reset."
            return False, f"[Erro] Opção de cabelo '{val}' inválida. Opções: {opts}", RED

        # ------------------------------------------------------------------
        # 4. Tom de Pele (Skin Tone)
        # ------------------------------------------------------------------
        if sub_cmd in ("skin", "pele", "tone", "tom"):
            if not args:
                opts = "pale, fair, tan, dark, ebony"
                return False, f"Uso: /skin skin <tom>. Opcoes: {opts}", GOLD

            val = args[0].lower()
            if val in SKIN_PRESETS:
                skin_rgb = SKIN_PRESETS[val]
                if self.character_model:
                    self.character_model.customization.skin_color_rgb = skin_rgb
                    self.character_model.reload()
                return True, f"[Skin] Tom de pele alterado para {val.upper()}", GREEN

            return False, f"[Erro] Tom de pele '{val}' desconhecido. Opcoes: pale, fair, tan, dark, ebony.", RED

        # ------------------------------------------------------------------
        # 5. Tipo de Cabeça (Head Type: Rounded vs Blocky)
        # ------------------------------------------------------------------
        if sub_cmd in ("head", "cabeca"):
            if not args:
                return False, "Uso: /skin head <rounded|blocky> OU /postura <-4cm|reset>", GOLD

            val = args[0].lower()
            if val in ("postura", "posture", "recuo", "z", "alinhamento"):
                return self._handle_subcommand("postura", args[1:])

            if "round" in val or "roblox" in val or "arredond" in val:
                if self.character_model:
                    self.character_model.customization.head_type = HeadType.ROUNDED
                    self.character_model.reload()
                return True, "[Skin] Modelo de cabeça alterado para ROUNDED (Arredondada Anime/Roblox)", GREEN

            if "block" in val or "quadrad" in val or "voxel" in val or "cube" in val:
                if self.character_model:
                    self.character_model.customization.head_type = HeadType.BLOCKY
                    self.character_model.reload()
                return True, "[Skin] Modelo de cabeça alterado para BLOCKY (Voxel Quadrada)", GREEN

            return False, "Uso: /skin head <rounded|blocky> OU /postura <-4cm|reset>", RED

        # ------------------------------------------------------------------
        # 5.1 Postura e Recuo Sagital da Cabeça (/postura <-4cm|0|reset>)
        # ------------------------------------------------------------------
        if sub_cmd in ("postura", "posture"):
            if not self.character_model:
                return False, "[Postura] Modelo 3D não disponível.", RED
            if not args or args[0].lower() in ("status", "info"):
                cur_z = self.character_model.head_z_offset
                return True, (
                    f"[Postura] Recuo da cabeça e pescoço no eixo Z: {cur_z:+.3f}m ({cur_z*100:+.1f}cm) | "
                    f"Uso: /postura <-4cm|+1cm|0|reset>"
                ), GOLD

            val = args[0].lower().strip()
            if val in ("reset", "padrao", "default"):
                self.character_model.reset_head_z_offset()
                cur_z = self.character_model.head_z_offset
                return True, f"[Postura] Alinhamento da cabeça restaurado para o padrão ({cur_z*100:+.1f}cm).", GREEN
            if val in ("0", "zero", "reto", "neutro"):
                self.character_model.set_head_z_offset(0.0)
                return True, "[Postura] Recuo da cabeça zerado (0.0cm).", GREEN

            try:
                if val.endswith("cm"):
                    dist_m = float(val.rstrip("cm")) / 100.0
                elif val.endswith("mm"):
                    dist_m = float(val.rstrip("mm")) / 1000.0
                elif val.endswith("m"):
                    dist_m = float(val.rstrip("m"))
                else:
                    num = float(val)
                    dist_m = num if abs(num) <= 0.15 else num / 100.0
                self.character_model.set_head_z_offset(dist_m)
                cur_z = self.character_model.head_z_offset
                desc = "recuada" if cur_z < -1e-3 else ("avançada" if cur_z > 1e-3 else "neutra")
                return True, f"[Postura] Cabeça e pescoço ajustados ({desc}): {cur_z:+.3f}m ({cur_z*100:+.1f}cm).", GREEN
            except ValueError:
                return False, f"[Erro] Valor de postura '{args[0]}' inválido. Exemplo: -4cm, -3cm, 0, reset", RED

        # ------------------------------------------------------------------
        # 5.2 Importar Roupa / Asset do Roblox (/import <ID ou URL>)
        # ------------------------------------------------------------------
        if sub_cmd in ("import", "importar", "wear", "vestir", "roblox"):
            return self._handle_import_roblox(args, run_async=run_async)

        # ------------------------------------------------------------------
        # 6. Roupa Superior (Top / Torso / Shirt / Sweater)
        # ------------------------------------------------------------------
        if sub_cmd in ("top", "shirt", "camisa", "sueter", "blusa", "roupa"):
            imported_opts = get_imported_top_options()
            if not args or args[0].lower() in ("list", "lista", "listar", "ver", "todos", "todas"):
                primary_names = []
                for k in imported_opts:
                    if not k.isdigit() and len(k) <= 22 and not k.startswith("character_"):
                        primary_names.append(k)
                unique_names = sorted(list(set(primary_names)))
                display_str = ", ".join(unique_names)
                return True, f"[Top] Roupas importadas disponiveis ({len(unique_names)}):\n{display_str}, none (ou ID numerico).\nUso: /top <nome|ID> ou /top none", GOLD

            val = args[0].lower()
            if val in ("barra", "hem", "crop", "cropped", "sobe", "desce", "alta", "meio", "media", "longa", "baixa") or val.startswith(("+", "-")) or (val.endswith("cm") and (val[:-2].replace(".", "", 1).lstrip("-+").isdigit())):
                sub_cmd = "barra"
            elif val in ("none", "sem", "naked", "tirar", "nenhum", "0"):
                if self.character_model:
                    self.character_model.top_id = None
                    self.character_model.reload()
                return True, "[Skin] Camisa removida — Sem roupa superior (bracos completos visiveis)", GREEN
            else:
                top_id = imported_opts.get(val, None)
                if top_id is None:
                    try:
                        top_id = int(val)
                    except ValueError:
                        return False, f"[Erro] Roupa superior '{val}' desconhecida. Digite /top para ver todas as disponiveis.", RED

                if self.character_model:
                    self.character_model.update_customization(top_id=top_id)
                return True, f"[Skin] Roupa superior atualizada para: {val.upper()} ({top_id})", GREEN

        # ------------------------------------------------------------------
        # 6.1 Peça por cima do top (jaqueta sobre camisa)
        # ------------------------------------------------------------------
        if sub_cmd in ("jaqueta", "jacket", "casaco", "sobre"):
            usage = ("Uso: /jaqueta <ID|none>  |  /jaqueta folga <mm> (afasta da camisa, reencaixa)"
                     "  |  /jaqueta puxar <mm> (quanto a camisa entra por baixo)")
            if not args:
                if self.character_model:
                    m = self.character_model
                    return True, (f"[Jaqueta] atual: {m.outer_top_id} | folga {m.outer_top_gap_mm:.0f} mm | "
                                  f"puxar {m.outer_top_pull_mm:.0f} mm\n{usage}"), GOLD
                return False, usage, GOLD
            val = args[0].lower()
            if val in ("folga", "gap", "puxar", "pull"):
                if len(args) < 2:
                    return False, usage, GOLD
                try:
                    mm = float(args[1].lower().removesuffix("mm"))
                except ValueError:
                    return False, f"[Erro] Valor em mm inválido: {args[1]}", RED
                if not 0 <= mm <= 50:
                    return False, "[Erro] Use um valor entre 0 e 50 mm.", RED
                if self.character_model:
                    if val in ("folga", "gap"):
                        self.character_model.outer_top_gap_mm = mm
                    else:
                        self.character_model.outer_top_pull_mm = mm
                    self.character_model.reload()
                label = "Folga entre jaqueta e camisa" if val in ("folga", "gap") else "Puxar a camisa por baixo"
                return True, f"[Jaqueta] {label}: {mm:.0f} mm", GREEN
            if val in ("none", "sem", "tirar", "nenhum", "0"):
                if self.character_model:
                    self.character_model.outer_top_id = None
                    self.character_model.reload()
                return True, "[Jaqueta] Removida", GREEN
            try:
                outer_id = int(val)
            except ValueError:
                return False, f"[Erro] ID de jaqueta inválido: '{val}'. {usage}", RED
            if self.character_model:
                self.character_model.update_customization(outer_top_id=outer_id)
            return True, f"[Jaqueta] Vestida por cima do top: {outer_id} (primeira vez leva alguns segundos)", GREEN

        # ------------------------------------------------------------------
        # 6.2 Calçados em camadas (tênis, botas, salto)
        # ------------------------------------------------------------------
        if sub_cmd in ("sapato", "sapatos", "tenis", "shoes", "shoe", "calcado"):
            usage = "Uso: /sapato <ID do bundle | ID_esquerdo,ID_direito | none>"
            if not args:
                current = getattr(self.character_model, "shoes_id", None) if self.character_model else None
                return True, f"[Sapato] atual: {current}\n{usage}", GOLD
            val = args[0].lower()
            if val in ("none", "sem", "tirar", "nenhum", "0", "descalca", "descalço"):
                if self.character_model:
                    self.character_model.shoes_id = None
                    self.character_model.reload()
                return True, "[Sapato] Removido — pés descalços", GREEN
            ids = [i for i in val.split(",") if i]
            if not ids or not all(i.isdigit() for i in ids):
                return False, f"[Erro] ID de calçado inválido: '{val}'. {usage}", RED
            if self.character_model:
                self.character_model.update_customization(shoes_id=",".join(ids))
            return True, f"[Sapato] Calçado: {','.join(ids)} (primeira vez leva alguns segundos)", GREEN

        # ------------------------------------------------------------------
        # 7. Calça / Botas (Bottom / Pants)
        # ------------------------------------------------------------------
        if sub_cmd in ("bottom", "pants", "calca", "jeans"):
            if not args:
                return False, "Uso: /calca <jeans|skater|vintage|baggy|none|altura|cintura>", GOLD
            val = args[0].lower()
            if val in ("altura", "cintura", "radius", "raio", "chanfro", "bevel", "sobe", "desce", "alta", "baixa", "meio") or val.startswith(("+", "-")) or (val.endswith("cm") and (val[:-2].replace(".", "", 1).lstrip("-+").isdigit())):
                sub_cmd = "cintura"
            elif val in ("none", "sem", "naked", "tirar", "nenhum", "0"):
                if self.character_model:
                    self.character_model.bottom_id = None
                    self.character_model.reload()
                return True, "[Skin] Calca/botas removidas — Pernas e pelve visiveis", GREEN
            else:
                bottom_id = BOTTOM_PRESETS.get(val, None)
                if bottom_id is None:
                    try:
                        bottom_id = int(val)
                    except ValueError:
                        return False, f"[Erro] Calca/botas '{val}' desconhecida. Use: jeans, skater, vintage, baggy, none ou ID numerico.", RED
                if self.character_model:
                    self.character_model.update_customization(bottom_id=bottom_id)
                return True, f"[Skin] Calca/botas atualizadas para: {val.upper()} ({bottom_id})", GREEN

        # ------------------------------------------------------------------
        # 8. Tool / Arma / Katana
        # ------------------------------------------------------------------
        if sub_cmd in ("tool", "arma", "katana", "sword", "espada"):
            val = args[0].lower() if args else "katana"
            if val in ("none", "off", "remover", "sem", "0"):
                if self.character_model:
                    self.character_model.update_customization(tool_id=0)
                return True, "[Skin] Arma/Acessorio desequipado.", GREEN

            if val in ("katana", "sword", "espada", "ronin"):
                tool_id = 12187348
            else:
                try:
                    tool_id = int(val)
                except ValueError:
                    tool_id = 12187348

            if self.character_model:
                self.character_model.update_customization(tool_id=tool_id)
            return True, f"[Skin] Acessorio equipado: KATANA ({tool_id})", GREEN

        # ------------------------------------------------------------------
        # 9. Turntable / Rotação Automática (Spin)
        # ------------------------------------------------------------------
        if sub_cmd in ("spin", "turntable", "girar", "rotacao"):
            if self.turntable_state is not None:
                if args:
                    v = args[0].lower()
                    if v in ("on", "1", "true", "ativar"):
                        self.turntable_state["active"] = True
                    elif v in ("off", "0", "false", "pausar"):
                        self.turntable_state["active"] = False
                    else:
                        self.turntable_state["active"] = not self.turntable_state["active"]
                else:
                    self.turntable_state["active"] = not self.turntable_state["active"]
                st = "ATIVADO" if self.turntable_state["active"] else "PAUSADO"
                return True, f"[Turntable] Rotacao automatica {st}", CYAN
            return False, "[Turntable] Estado de rotacao indisponivel.", RED

        # ------------------------------------------------------------------
        # 10. Presets de Skin completos
        # ------------------------------------------------------------------
        if sub_cmd in ("preset", "presets"):
            if not args:
                opts = "anime_default, blonde_cat, dark_knight, cyber_pink, classic_vintage"
                return False, f"Uso: /skin preset <nome>. Opcoes: {opts}", GOLD

            val = args[0].lower()
            if val in ("anime_default", "default", "padrao"):
                cust = AvatarCustomization(
                    head_type=HeadType.ROUNDED,
                    mouth_style=MouthStyle.ANIME_ORIGINAL,
                    eye_style=EyeStyle.ANIME,
                    iris_color=IrisColor.BLUE,
                    hair_style=HairStyle.ANIME_LONG,
                    hair_color=HairColor.BRUNETTE,
                    skin_color_rgb=SKIN_PRESETS["pale"],
                )
                if self.character_model:
                    self.character_model.update_customization(customization=cust, top_id=OUTFIT_PRESETS["sweater"], tool_id=0)
                return True, "[Preset] Ativado: ANIME DEFAULT", GREEN

            if val in ("blonde_cat", "gato", "cat_girl", "cat"):
                cust = AvatarCustomization(
                    head_type=HeadType.ROUNDED,
                    mouth_style=MouthStyle.CAT,
                    eye_style=EyeStyle.ANIME,
                    iris_color=IrisColor.GREEN,
                    hair_style=HairStyle.ANIME_LONG,
                    hair_color=HairColor.BLONDE,
                    skin_color_rgb=SKIN_PRESETS["pale"],
                )
                if self.character_model:
                    self.character_model.update_customization(customization=cust, top_id=OUTFIT_PRESETS["sweater"])
                return True, "[Preset] Ativado: BLONDE CAT (:3)", GREEN

            if val in ("dark_knight", "cavaleiro", "silver_dark"):
                cust = AvatarCustomization(
                    head_type=HeadType.ROUNDED,
                    mouth_style=MouthStyle.ANIME_ORIGINAL,
                    eye_style=EyeStyle.ANIME,
                    iris_color=IrisColor.PURPLE,
                    hair_style=HairStyle.ANIME_LONG,
                    hair_color=HairColor.SILVER,
                    skin_color_rgb=SKIN_PRESETS["dark"],
                )
                if self.character_model:
                    self.character_model.update_customization(customization=cust, top_id=OUTFIT_PRESETS["boxy"], tool_id=12187348)
                return True, "[Preset] Ativado: DARK KNIGHT (Katana inclusa)", GREEN

            if val in ("cyber_pink", "pink"):
                cust = AvatarCustomization(
                    head_type=HeadType.ROUNDED,
                    mouth_style=MouthStyle.POUT,
                    eye_style=EyeStyle.ANIME,
                    iris_color=IrisColor.RED,
                    hair_style=HairStyle.ANIME_LONG,
                    hair_color=HairColor.PINK,
                    skin_color_rgb=SKIN_PRESETS["fair"],
                )
                if self.character_model:
                    self.character_model.update_customization(customization=cust, top_id=OUTFIT_PRESETS["boxy"])
                return True, "[Preset] Ativado: CYBER PINK", GREEN

            if val in ("classic_vintage", "vintage", "retro"):
                cust = AvatarCustomization(
                    head_type=HeadType.BLOCKY,
                    mouth_style=MouthStyle.CLASSIC,
                    eye_style=EyeStyle.CLASSIC,
                    iris_color=IrisColor.BLUE,
                    hair_style=HairStyle.ANIME_LONG,
                    hair_color=HairColor.BRUNETTE,
                    skin_color_rgb=SKIN_PRESETS["pale"],
                )
                if self.character_model:
                    self.character_model.update_customization(customization=cust, top_id=OUTFIT_PRESETS["sweater"], tool_id=0)
                return True, "[Preset] Ativado: CLASSIC VINTAGE", GREEN

            return False, f"[Erro] Preset '{val}' desconhecido. Opcoes: anime_default, blonde_cat, dark_knight, cyber_pink, classic_vintage.", RED

        # ------------------------------------------------------------------
        # 11. Ajuste de Manga (Sleeve / Cuff: Largura, Comprimento e Deslocamento)
        # ------------------------------------------------------------------
        if sub_cmd in ("sleeve", "manga", "cuff", "punho"):
            if not self.character_model:
                return False, "[Erro] Modelo de personagem nao disponivel.", RED

            if not args or args[0].lower() in ("status", "info"):
                w = self.character_model.sleeve_width_scale
                l_off = self.character_model.sleeve_length_offset
                sx = self.character_model.sleeve_shift_x
                sy = self.character_model.sleeve_shift_y
                sz = self.character_model.sleeve_shift_z
                return True, (
                    f"[Manga] Largura: {w:.2f}x | Comp: {l_off:+.3f}m | "
                    f"Offset: X: {sx:+.3f}m (fora/dentro), Y: {sy:+.3f}m (frente/tras), Z: {sz:+.3f}m (vertical) | "
                    f"Uso: /manga <largura|comprimento|horizontal|vertical|frente|fora|dentro|deslocar|reset> <valor>"
                ), GOLD

            action = args[0].lower()
            val_str = args[1] if len(args) > 1 else None

            if action in ("reset", "padrao", "default", "restaurar"):
                self.character_model.reset_sleeve_adjustments()
                return True, "[Manga] Largura, comprimento e deslocamento da manga restaurados para o padrao (1.0x / 0.00m).", GREEN

            # 11.1 Largura da ponta
            if action in ("width", "largura", "w", "lar", "espessura"):
                if val_str is None:
                    return False, f"Uso: /manga largura <valor> (Atual: {self.character_model.sleeve_width_scale:.2f}x)", GOLD
                try:
                    cur = self.character_model.sleeve_width_scale
                    if val_str.endswith("%"):
                        val = float(val_str.rstrip("%")) / 100.0
                    elif val_str.startswith(("+", "-")):
                        val = cur + float(val_str)
                    else:
                        val = float(val_str)
                    self.character_model.set_sleeve_width(val)
                    return True, f"[Manga] Largura da ponta ajustada para: {self.character_model.sleeve_width_scale:.2f}x", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: 1.2, 0.85, +0.1, -0.1, 120%", RED

            # 11.2 Comprimento (+ desce, - sobe)
            if action in ("length", "comprimento", "l", "comp", "tam", "tamanho"):
                if val_str is None:
                    return False, f"Uso: /manga comprimento <metros> (Atual: {self.character_model.sleeve_length_offset:+.3f}m)", GOLD
                try:
                    cur = self.character_model.sleeve_length_offset
                    new_off = _parse_distance(val_str, cur, allow_relative_minus=True)
                    self.character_model.set_sleeve_length(new_off)
                    return True, f"[Manga] Comprimento ajustado: {self.character_model.sleeve_length_offset:+.3f}m (+ desce, - sobe)", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: +0.02, -0.02, 2cm, -3cm", RED

            # 11.3 Deslocamento Horizontal Lateral (Dentro / Fora / X)
            if action in ("horizontal", "horiz", "h", "lateral", "lat", "x"):
                if val_str is None:
                    return False, f"Uso: /manga horizontal <valor> (Atual: {self.character_model.sleeve_shift_x:+.3f}m)", GOLD
                try:
                    cur = self.character_model.sleeve_shift_x
                    new_x = _parse_distance(val_str, cur)
                    self.character_model.set_sleeve_shift_x(new_x)
                    direc = "para fora" if self.character_model.sleeve_shift_x >= 0 else "para dentro"
                    return True, f"[Manga] Deslocamento horizontal: {self.character_model.sleeve_shift_x:+.3f}m ({direc})", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: +2cm, -1cm, +0.02, -0.02", RED

            # 11.4 Atalho semântico: Fora / Out (+X lateral)
            if action in ("fora", "out", "externo"):
                val_str = val_str or "1cm"
                try:
                    cur = self.character_model.sleeve_shift_x
                    dist = abs(_parse_distance(val_str, 0.0))
                    new_x = (cur - dist) if val_str.startswith("-") else (cur + dist if val_str.startswith("+") else dist)
                    self.character_model.set_sleeve_shift_x(new_x)
                    return True, f"[Manga] Deslocamento para FORA: {self.character_model.sleeve_shift_x:+.3f}m", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: 2cm, 0.02, +1cm", RED

            # 11.5 Atalho semântico: Dentro / In (-X lateral)
            if action in ("dentro", "in", "interno"):
                val_str = val_str or "1cm"
                try:
                    cur = self.character_model.sleeve_shift_x
                    dist = abs(_parse_distance(val_str, 0.0))
                    new_x = (cur + dist) if val_str.startswith("-") else (cur - dist if val_str.startswith("+") else -dist)
                    self.character_model.set_sleeve_shift_x(new_x)
                    return True, f"[Manga] Deslocamento para DENTRO: {self.character_model.sleeve_shift_x:+.3f}m", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: 2cm, 0.02, +1cm", RED

            # 11.6 Deslocamento Vertical (Subir / Descer / Z)
            if action in ("vertical", "vert", "v", "z", "altura", "alt", "cima", "baixo", "sobe", "desce"):
                if val_str is None:
                    if action in ("baixo", "desce"):
                        val_str = "-1cm"
                    elif action in ("cima", "sobe"):
                        val_str = "+1cm"
                    else:
                        return False, f"Uso: /manga vertical <valor> (Atual: {self.character_model.sleeve_shift_z:+.3f}m)", GOLD
                try:
                    cur = self.character_model.sleeve_shift_z
                    if action in ("baixo", "desce") and not val_str.startswith(("+", "-")):
                        val_str = "-" + val_str
                    elif action in ("cima", "sobe") and not val_str.startswith(("+", "-")):
                        val_str = "+" + val_str
                    new_z = _parse_distance(val_str, cur)
                    self.character_model.set_sleeve_shift_z(new_z)
                    direc = "para cima" if self.character_model.sleeve_shift_z >= 0 else "para baixo"
                    return True, f"[Manga] Deslocamento vertical: {self.character_model.sleeve_shift_z:+.3f}m ({direc})", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: +1cm, -2cm, +0.01", RED

            # 11.7 Profundidade (Frente / Trás / Y)
            if action in ("frente", "front", "tras", "trás", "back", "y", "profundidade", "prof"):
                if val_str is None:
                    if action in ("tras", "trás", "back"):
                        val_str = "-1cm"
                    elif action in ("frente", "front"):
                        val_str = "+1cm"
                    else:
                        return False, f"Uso: /manga frente <valor> (Atual: {self.character_model.sleeve_shift_y:+.3f}m)", GOLD
                try:
                    cur = self.character_model.sleeve_shift_y
                    if action in ("tras", "trás", "back") and not val_str.startswith(("+", "-")):
                        val_str = "-" + val_str
                    elif action in ("frente", "front") and not val_str.startswith(("+", "-")):
                        val_str = "+" + val_str
                    new_y = _parse_distance(val_str, cur)
                    self.character_model.set_sleeve_shift_y(new_y)
                    direc = "para frente" if self.character_model.sleeve_shift_y >= 0 else "para tras"
                    return True, f"[Manga] Deslocamento profundidade: {self.character_model.sleeve_shift_y:+.3f}m ({direc})", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: +1cm, -1cm, 2cm", RED

            # 11.8 Comando Composto: Deslocar / Offset / Shift / Mover
            if action in ("deslocar", "mover", "offset", "shift", "posicao", "pos"):
                if not val_str:
                    return False, "Uso: /manga deslocar <horizontal|vertical|frente|fora|dentro|x|y|z> <valor> OU /manga deslocar <x> [y] [z]", GOLD

                sub_axis = val_str.lower()
                sub_val_str = args[2] if len(args) > 2 else None

                if sub_axis in ("horizontal", "horiz", "h", "lateral", "x"):
                    if sub_val_str is None:
                        return False, "Uso: /manga deslocar horizontal <valor>", GOLD
                    new_val = _parse_distance(sub_val_str, self.character_model.sleeve_shift_x)
                    self.character_model.set_sleeve_shift_x(new_val)
                    return True, f"[Manga] Deslocamento horizontal: {self.character_model.sleeve_shift_x:+.3f}m", GREEN

                if sub_axis in ("fora", "out"):
                    sub_val = sub_val_str or "1cm"
                    dist = abs(_parse_distance(sub_val, 0.0))
                    self.character_model.set_sleeve_shift_x(dist)
                    return True, f"[Manga] Deslocamento para FORA: {self.character_model.sleeve_shift_x:+.3f}m", GREEN

                if sub_axis in ("dentro", "in"):
                    sub_val = sub_val_str or "1cm"
                    dist = abs(_parse_distance(sub_val, 0.0))
                    self.character_model.set_sleeve_shift_x(-dist)
                    return True, f"[Manga] Deslocamento para DENTRO: {self.character_model.sleeve_shift_x:+.3f}m", GREEN

                if sub_axis in ("vertical", "vert", "v", "z"):
                    if sub_val_str is None:
                        return False, "Uso: /manga deslocar vertical <valor>", GOLD
                    new_val = _parse_distance(sub_val_str, self.character_model.sleeve_shift_z)
                    self.character_model.set_sleeve_shift_z(new_val)
                    return True, f"[Manga] Deslocamento vertical: {self.character_model.sleeve_shift_z:+.3f}m", GREEN

                if sub_axis in ("frente", "front", "tras", "trás", "back", "y"):
                    sign = -1 if sub_axis in ("tras", "trás", "back") else 1
                    sub_val = sub_val_str or "1cm"
                    if sign == -1 and not sub_val.startswith(("+", "-")):
                        sub_val = "-" + sub_val
                    new_val = _parse_distance(sub_val, self.character_model.sleeve_shift_y)
                    self.character_model.set_sleeve_shift_y(new_val)
                    return True, f"[Manga] Deslocamento profundidade: {self.character_model.sleeve_shift_y:+.3f}m", GREEN

                # Se forem valores numéricos diretos (ex: /manga deslocar 2cm -1cm)
                try:
                    x_val = _parse_distance(args[1], self.character_model.sleeve_shift_x if args[1].startswith("+") else 0.0)
                    y_val = _parse_distance(args[2], self.character_model.sleeve_shift_y if args[2].startswith("+") else 0.0) if len(args) > 2 else self.character_model.sleeve_shift_y
                    z_val = _parse_distance(args[3], self.character_model.sleeve_shift_z if args[3].startswith("+") else 0.0) if len(args) > 3 else self.character_model.sleeve_shift_z
                    self.character_model.set_sleeve_offset(x=x_val, y=y_val, z=z_val)
                    return True, f"[Manga] Deslocamento: X: {x_val:+.3f}m, Y: {y_val:+.3f}m, Z: {z_val:+.3f}m", GREEN
                except ValueError:
                    return False, f"[Erro] Argumentos '{' '.join(args)}' invalidos. Uso: /manga deslocar <eixo> <valor> OU <x> [y] [z]", RED

            return False, "Uso: /manga <largura|comprimento|horizontal|vertical|frente|fora|dentro|deslocar|reset> <valor>", RED

        # ------------------------------------------------------------------
        # 12. Ajuste de Braço (Arm: Largura e Comprimento)
        # ------------------------------------------------------------------
        if sub_cmd in ("arm", "braco", "arms", "bracos"):
            if not self.character_model:
                return False, "[Erro] Modelo de personagem nao disponivel.", RED

            if not args:
                w = self.character_model.arm_width_scale
                l = self.character_model.arm_length_scale
                return True, f"[Braco] Largura: {w:.2f}x | Comprimento: {l:.2f}x | Uso: /braco <largura|comprimento|reset> <valor>", GOLD

            action = args[0].lower()
            val_str = args[1] if len(args) > 1 else None

            if action in ("reset", "padrao", "default", "restaurar"):
                self.character_model.reset_arm_adjustments()
                return True, "[Braco] Largura e comprimento do braco restaurados para o padrao (1.0x / 1.0x).", GREEN

            if action in ("width", "largura", "w", "lar", "espessura"):
                if val_str is None:
                    return False, f"Uso: /braco largura <valor> (Atual: {self.character_model.arm_width_scale:.2f}x)", GOLD
                try:
                    cur = self.character_model.arm_width_scale
                    if val_str.endswith("%"):
                        val = float(val_str.rstrip("%")) / 100.0
                    elif val_str.startswith(("+", "-")):
                        val = cur + float(val_str)
                    else:
                        val = float(val_str)
                    self.character_model.set_arm_width(val)
                    return True, f"[Braco] Largura ajustada para: {self.character_model.arm_width_scale:.2f}x", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: 0.9, 1.1, +0.1, -0.05, 90%", RED

            if action in ("length", "comprimento", "l", "comp", "tam", "tamanho"):
                if val_str is None:
                    return False, f"Uso: /braco comprimento <valor> (Atual: {self.character_model.arm_length_scale:.2f}x)", GOLD
                try:
                    cur = self.character_model.arm_length_scale
                    if val_str.endswith("%"):
                        val = float(val_str.rstrip("%")) / 100.0
                    elif val_str.startswith(("+", "-")):
                        val = cur + float(val_str)
                    else:
                        val = float(val_str)
                    self.character_model.set_arm_length(val)
                    return True, f"[Braco] Comprimento ajustado para: {self.character_model.arm_length_scale:.2f}x", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: 1.05, 0.95, +0.05, -0.05", RED

            return False, "Uso: /braco <largura|comprimento|reset> <valor>", RED

        # ------------------------------------------------------------------
        # 13. Ajuste de Quadril / Glúteos (Relevo da Bunda)
        # ------------------------------------------------------------------
        if sub_cmd in ("quadril", "hip", "gluteos", "gluteo", "bunda", "quadris"):
            if not self.character_model:
                return False, "[Erro] Modelo de personagem nao disponivel.", RED

            if not args or args[0].lower() in ("status", "info"):
                g = self.character_model.hip_glute_scale
                w = self.character_model.hip_width_scale
                return True, (
                    f"[Quadril] Relevo da Bunda: {g:.2f}x | Largura: {w:.2f}x | "
                    f"Uso: /quadril <valor> (ex: 1.3, 1.5, +0.2, 120%) OU /quadril <relevo|largura|reset> <valor>"
                ), GOLD

            action = args[0].lower()
            val_str = args[1] if len(args) > 1 else None

            if action in ("reset", "padrao", "default", "restaurar"):
                self.character_model.reset_quadril_adjustments()
                return True, "[Quadril] Relevo dos gluteos e largura restaurados para o padrao (1.0x).", GREEN

            # Se o primeiro argumento for número direto (ex: /quadril 1.3 ou /quadril +0.2)
            is_num = False
            try:
                if action.endswith("%") or action.startswith(("+", "-")):
                    float(action.rstrip("%"))
                    is_num = True
                else:
                    float(action)
                    is_num = True
            except ValueError:
                is_num = False

            if is_num:
                val_str = action
                action = "relevo"

            if action in ("relevo", "bunda", "gluteo", "gluteos", "volume", "profundidade", "y"):
                if val_str is None:
                    return False, f"Uso: /quadril relevo <valor> (Atual: {self.character_model.hip_glute_scale:.2f}x)", GOLD
                try:
                    cur = self.character_model.hip_glute_scale
                    if val_str.endswith("%"):
                        val = float(val_str.rstrip("%")) / 100.0
                    elif val_str.startswith(("+", "-")):
                        val = cur + float(val_str)
                    else:
                        val = float(val_str)
                    self.character_model.set_quadril(glute_scale=val)
                    return True, f"[Quadril] Relevo da bunda ajustado para: {self.character_model.hip_glute_scale:.2f}x", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: 1.3, 1.5, +0.2, 130%", RED

            if action in ("largura", "width", "lateral", "x", "lar"):
                if val_str is None:
                    return False, f"Uso: /quadril largura <valor> (Atual: {self.character_model.hip_width_scale:.2f}x)", GOLD
                try:
                    cur = self.character_model.hip_width_scale
                    if val_str.endswith("%"):
                        val = float(val_str.rstrip("%")) / 100.0
                    elif val_str.startswith(("+", "-")):
                        val = cur + float(val_str)
                    else:
                        val = float(val_str)
                    self.character_model.set_quadril(glute_scale=self.character_model.hip_glute_scale, width_scale=val)
                    return True, f"[Quadril] Largura do quadril ajustada para: {self.character_model.hip_width_scale:.2f}x", GREEN
                except ValueError:
                    return False, f"[Erro] Valor '{val_str}' invalido. Exemplo: 1.1, 0.95, +0.1", RED

        # ------------------------------------------------------------------
        # 14. Ajuste da Altura da Cintura / Cós da Calça
        # ------------------------------------------------------------------
        if sub_cmd in ("cintura", "waist", "cos"):
            if not self.character_model:
                return False, "[Erro] Modelo de personagem nao disponivel.", RED

            is_fem = getattr(self.character_model.customization, "is_female", False)
            base_z = 1.00 if is_fem else 0.935

            # Se veio de /calca altura <valor> ou /calca cintura <valor>
            if args and args[0].lower() in ("altura", "cintura", "alt", "h", "z"):
                args = args[1:]

            if not args or args[0].lower() in ("status", "info"):
                cur_off = self.character_model.waist_height_offset
                cur_r = self.character_model.waist_radius_offset
                cur_ch = self.character_model.waist_chamfer
                eff_z = base_z + cur_off
                return True, (
                    f"[Cintura] Altura: {eff_z:.3f}m (offset: {cur_off:+.3f}m) | "
                    f"Raio Torso: {cur_r:+.3f}m ({cur_r*100:+.1f}cm) | "
                    f"Chanfro: {cur_ch*100:.1f}cm | "
                    f"Uso: /cintura <+2cm|alta|baixa|reset> OU /cintura radius <-2cm> OU /cintura chanfro <1.5cm>"
                ), GOLD

            action = args[0].lower()
            val_str = args[1] if len(args) > 1 else None

            # 14.1 Raio / Afunilamento do Torso (/cintura radius <-2cm|+2cm|reset>)
            if action in ("radius", "raio", "espessura", "rad", "afunilar", "taper"):
                if val_str is None:
                    cur_r = self.character_model.waist_radius_offset
                    return True, f"[Cintura] Raio/Afunilamento do torso: {cur_r:+.3f}m ({cur_r*100:+.1f}cm) | Uso: /cintura radius <-2cm|+2cm|reset>", GOLD

                if val_str.lower() in ("reset", "padrao", "default", "0"):
                    self.character_model.reset_waist_radius()
                    return True, "[Cintura] Raio do torso restaurado para o padrao (0.00m).", GREEN

                try:
                    raw = val_str.lower().strip()
                    if raw.endswith("cm"):
                        dist_m = float(raw.rstrip("cm")) / 100.0
                    elif raw.endswith("mm"):
                        dist_m = float(raw.rstrip("mm")) / 1000.0
                    elif raw.endswith("m"):
                        dist_m = float(raw.rstrip("m"))
                    elif raw.endswith("x"):
                        factor = float(raw.rstrip("x"))
                        dist_m = (factor - 1.0) * 0.09
                    elif raw.endswith("%"):
                        pct = float(raw.rstrip("%"))
                        dist_m = (pct / 100.0) * 0.09 if raw.startswith(("+", "-")) else ((pct / 100.0) - 1.0) * 0.09
                    else:
                        num = float(raw)
                        if abs(num) <= 0.10:
                            dist_m = num
                        elif 0.40 <= num <= 2.0 and not raw.startswith(("+", "-")):
                            dist_m = (num - 1.0) * 0.09
                        else:
                            dist_m = num / 100.0

                    self.character_model.set_waist_radius(dist_m)
                    r_cm = self.character_model.waist_radius_offset * 100.0
                    desc = "afunilado" if r_cm < -1e-3 else ("alargado" if r_cm > 1e-3 else "neutro")
                    return True, f"[Cintura] Raio do torso {desc}: {self.character_model.waist_radius_offset:+.3f}m ({r_cm:+.1f}cm).", GREEN
                except ValueError:
                    return False, f"[Erro] Valor de raio '{val_str}' invalido. Exemplo: -2cm, +2cm, -0.02, reset, 0.9x", RED

            # 14.2 Chanfro / Arredondamento das Quinas (/cintura chanfro <0|1cm|1.5cm|2cm|3cm|quadrado|suave|forte|reset>)
            if action in ("chanfro", "bevel", "curvatura", "arredondar", "quina", "quinas"):
                if val_str is None:
                    cur_ch = self.character_model.waist_chamfer
                    return True, (
                        f"[Cintura] Chanfro atual das quinas: {cur_ch*100:.1f}cm ({cur_ch:.3f}m) | "
                        f"Uso: /cintura chanfro <0|1cm|1.5cm|2cm|3cm|quadrado|suave|forte|reset>"
                    ), GOLD

                raw = val_str.lower().strip()
                if raw in ("0", "zero", "none", "off", "quadrado", "square", "bloco", "reto", "sharp"):
                    dist_m = 0.0
                elif raw in ("reset", "padrao", "default", "suave", "normal", "original"):
                    dist_m = 0.015
                elif raw in ("medio", "med", "moderado"):
                    dist_m = 0.020
                elif raw in ("forte", "alto", "redondo", "round", "oval"):
                    dist_m = 0.035
                elif raw.endswith("cm"):
                    try:
                        dist_m = float(raw.rstrip("cm")) / 100.0
                    except ValueError:
                        return False, f"[Erro] Valor de chanfro '{val_str}' invalido. Exemplo: 0, 1.5cm, 2cm, quadrado, suave, forte, reset", RED
                elif raw.endswith("mm"):
                    try:
                        dist_m = float(raw.rstrip("mm")) / 1000.0
                    except ValueError:
                        return False, f"[Erro] Valor de chanfro '{val_str}' invalido. Exemplo: 0, 1.5cm, 2cm, quadrado, suave, forte, reset", RED
                elif raw.endswith("m"):
                    try:
                        dist_m = float(raw.rstrip("m"))
                    except ValueError:
                        return False, f"[Erro] Valor de chanfro '{val_str}' invalido. Exemplo: 0, 1.5cm, 2cm, quadrado, suave, forte, reset", RED
                elif raw.endswith("%"):
                    try:
                        pct = float(raw.rstrip("%"))
                        dist_m = (pct / 100.0) * 0.05
                    except ValueError:
                        return False, f"[Erro] Valor de chanfro '{val_str}' invalido. Exemplo: 0, 1.5cm, 2cm, quadrado, suave, forte, reset", RED
                else:
                    try:
                        num = float(raw)
                        if num > 0.1:
                            dist_m = num / 100.0
                        else:
                            dist_m = num
                    except ValueError:
                        return False, f"[Erro] Valor de chanfro '{val_str}' invalido. Exemplo: 0, 1.5cm, 2cm, quadrado, suave, forte, reset", RED

                self.character_model.set_waist_chamfer(dist_m)
                ch_cm = self.character_model.waist_chamfer * 100.0
                if ch_cm < 0.1:
                    style = "quadrado / sem chanfro (0.0cm)"
                elif abs(ch_cm - 1.5) < 0.2:
                    style = "suave (padrão 1.5cm)"
                elif ch_cm >= 3.0:
                    style = "forte / arredondado"
                else:
                    style = "moderado"
                return True, f"[Cintura] Chanfro das quinas (Bevel Blender) ajustado para: {ch_cm:.1f}cm ({style}).", GREEN

            if action in ("reset", "padrao", "default", "restaurar"):
                self.character_model.reset_waist_adjustments()
                return True, f"[Cintura] Altura, raio e chanfro da cintura restaurados para o padrao ({base_z:.2f}m / 0.0cm / 1.5cm).", GREEN

            if action in ("meio", "mid", "media"):
                self.character_model.set_waist_height(0.0)
                return True, f"[Cintura] Altura ajustada para o meio do declive ({base_z:.2f}m).", GREEN

            if action in ("alta", "high", "highwaist"):
                target_z = 1.070 if is_fem else 0.980
                self.character_model.set_waist_z(target_z)
                eff = base_z + self.character_model.waist_height_offset
                return True, f"[Cintura] Cintura alta ajustada para {eff:.3f}m.", GREEN

            if action in ("baixa", "low", "lowrise"):
                target_z = 0.940 if is_fem else 0.880
                self.character_model.set_waist_z(target_z)
                eff = base_z + self.character_model.waist_height_offset
                return True, f"[Cintura] Cintura baixa ajustada para {eff:.3f}m.", GREEN

            if action in ("sobe", "up", "cima"):
                step = _parse_distance(val_str, 0.0) if val_str else 0.01
                new_off = self.character_model.waist_height_offset + abs(step)
                self.character_model.set_waist_height(new_off)
                eff = base_z + self.character_model.waist_height_offset
                return True, f"[Cintura] Cós subido: {eff:.3f}m ({self.character_model.waist_height_offset:+.3f}m)", GREEN

            if action in ("desce", "down", "baixo"):
                step = _parse_distance(val_str, 0.0) if val_str else 0.01
                new_off = self.character_model.waist_height_offset - abs(step)
                self.character_model.set_waist_height(new_off)
                eff = base_z + self.character_model.waist_height_offset
                return True, f"[Cintura] Cós descido: {eff:.3f}m ({self.character_model.waist_height_offset:+.3f}m)", GREEN

            # Processamento numérico direto (ex: /cintura +2cm, /cintura -1cm, /cintura 1.02)
            try:
                cur_off = self.character_model.waist_height_offset
                if action.startswith(("+", "-")):
                    dist = _parse_distance(action, cur_off, allow_relative_minus=True)
                    self.character_model.set_waist_height(dist)
                elif action.endswith("cm"):
                    dist = float(action.rstrip("cm")) / 100.0
                    self.character_model.set_waist_height(cur_off + dist)
                else:
                    val_num = float(action)
                    if 0.70 <= val_num <= 1.30:
                        self.character_model.set_waist_z(val_num)
                    else:
                        step = val_num if abs(val_num) <= 0.30 else (val_num / 100.0)
                        self.character_model.set_waist_height(cur_off + step)

                eff = base_z + self.character_model.waist_height_offset
                return True, f"[Cintura] Altura do cós ajustada para: {eff:.3f}m (offset: {self.character_model.waist_height_offset:+.3f}m)", GREEN
            except ValueError:
                return False, f"[Erro] Valor de cintura '{action}' invalido. Exemplo: +2cm, -1cm, 1.00, meio, alta, baixa", RED

        # ------------------------------------------------------------------
        # 15. Ajuste da Altura da Barra da Blusa / Camisa
        # ------------------------------------------------------------------
        if sub_cmd in ("barra", "hem", "crop", "cropped"):
            if not self.character_model:
                return False, "[Erro] Modelo de personagem nao disponivel.", RED

            is_fem = getattr(self.character_model.customization, "is_female", False)
            base_z = 0.985 if is_fem else 0.890

            if sub_cmd in ("crop", "cropped") and not args:
                args = ["cropped"]

            # Se veio de /top barra <valor> ou /camisa barra <valor>
            if args and args[0].lower() in ("barra", "hem", "altura", "alt", "h", "z"):
                args = args[1:]

            if not args or args[0].lower() in ("status", "info"):
                cur_off = self.character_model.top_hem_offset
                eff_z = base_z + cur_off
                return True, (
                    f"[Barra] Altura base: {base_z:.3f}m | Deslocamento: {cur_off:+.3f}m ({cur_off*100:+.1f}cm) | "
                    f"Altura efetiva da barra: {eff_z:.3f}m | "
                    f"Uso: /barra <+2cm|-1cm|1.07|cropped|alta|meio|longa|sobe|desce|reset>"
                ), GOLD

            action = args[0].lower()
            val_str = args[1] if len(args) > 1 else None

            if action in ("reset", "padrao", "default", "restaurar"):
                self.character_model.reset_top_hem()
                def_off = self.character_model.top_hem_offset
                eff_z = base_z + def_off
                return True, f"[Barra] Altura da barra restaurada para o padrao ({eff_z:.3f}m, offset: {def_off:+.3f}m).", GREEN

            if action in ("meio", "mid", "media"):
                def_off = 0.0 if is_fem else -0.02
                self.character_model.set_top_hem(def_off)
                eff_z = base_z + def_off
                return True, f"[Barra] Barra ajustada para o caimento padrao ({eff_z:.3f}m).", GREEN

            if action in ("alta", "high"):
                target_z = 1.070 if is_fem else 0.980
                self.character_model.set_top_hem_z(target_z)
                eff = base_z + self.character_model.top_hem_offset
                return True, f"[Barra] Barra ajustada para cintura alta ({eff:.3f}m).", GREEN

            if action in ("cropped", "crop"):
                target_z = 1.090 if is_fem else 1.020
                self.character_model.set_top_hem_z(target_z)
                eff = base_z + self.character_model.top_hem_offset
                return True, f"[Barra] Barra ajustada para cropped ({eff:.3f}m), expondo a regiao da barriga.", GREEN

            if action in ("longa", "baixa", "low"):
                target_z = 0.950 if is_fem else 0.900
                self.character_model.set_top_hem_z(target_z)
                eff = base_z + self.character_model.top_hem_offset
                return True, f"[Barra] Barra alongada ajustada para {eff:.3f}m.", GREEN

            if action in ("sobe", "up", "cima"):
                step = _parse_distance(val_str, 0.0) if val_str else 0.01
                new_off = self.character_model.top_hem_offset + abs(step)
                self.character_model.set_top_hem(new_off)
                eff = base_z + self.character_model.top_hem_offset
                return True, f"[Barra] Barra subida: {eff:.3f}m ({self.character_model.top_hem_offset:+.3f}m)", GREEN

            if action in ("desce", "down", "baixo"):
                step = _parse_distance(val_str, 0.0) if val_str else 0.01
                new_off = self.character_model.top_hem_offset - abs(step)
                self.character_model.set_top_hem(new_off)
                eff = base_z + self.character_model.top_hem_offset
                return True, f"[Barra] Barra descida: {eff:.3f}m ({self.character_model.top_hem_offset:+.3f}m)", GREEN

            # Processamento numérico direto (ex: /barra +3cm, /barra -2cm, /barra 1.05)
            try:
                cur_off = self.character_model.top_hem_offset
                if action.startswith(("+", "-")):
                    dist = _parse_distance(action, cur_off, allow_relative_minus=True)
                    self.character_model.set_top_hem(dist)
                elif action.endswith("cm"):
                    dist = float(action.rstrip("cm")) / 100.0
                    self.character_model.set_top_hem(cur_off + dist)
                else:
                    val_num = float(action)
                    if 0.70 <= val_num <= 1.40:
                        self.character_model.set_top_hem_z(val_num)
                    else:
                        step = val_num if abs(val_num) <= 0.30 else (val_num / 100.0)
                        self.character_model.set_top_hem(cur_off + step)

                eff = base_z + self.character_model.top_hem_offset
                return True, f"[Barra] Altura da barra ajustada para: {eff:.3f}m (offset: {self.character_model.top_hem_offset:+.3f}m)", GREEN
            except ValueError:
                return False, f"[Erro] Valor de barra '{action}' invalido. Exemplo: +2cm, -1cm, 1.05, cropped, alta, meio, reset", RED

        # ------------------------------------------------------------------
        # 16. Reset
        # ------------------------------------------------------------------
        if sub_cmd in ("reset", "padrao", "restaurar"):
            cust = AvatarCustomization(
                head_type=HeadType.ROUNDED,
                mouth_style=MouthStyle.ANIME_ORIGINAL,
                hair_style=HairStyle.ANIME_LONG,
                hair_color=HairColor.BRUNETTE,
                skin_color_rgb=SKIN_PRESETS["pale"],
            )
            if self.character_model:
                self.character_model.update_customization(customization=cust, top_id=OUTFIT_PRESETS["sweater"], tool_id=0)
            return True, "[Skin] Personagem restaurado para configuracao padrao.", GREEN

        return False, f"[Erro] Comando desconhecido: '/{sub_cmd}'. Digite /help para a lista completa.", RED

    def _handle_import_roblox(self, args: List[str], run_async: bool = True) -> Tuple[bool, str, Tuple[int, int, int]]:
        GREEN = (85, 255, 85)
        GOLD = (255, 215, 0)
        RED = (255, 85, 85)
        CYAN = (85, 255, 255)

        if not self.character_model:
            return False, "[Import] Modelo 3D não disponível.", RED

        if not args or args[0].lower() in ("help", "ajuda", "?", "status", "info"):
            top_info = str(self.character_model.top_id) if self.character_model.top_id else "Nenhum"
            bot_info = str(self.character_model.bottom_id) if self.character_model.bottom_id else "Nenhum"
            hair_info = str(getattr(self.character_model, "hair_id", None)) or "Padrão"
            return True, (
                f"[Import] Uso: /import <ID ou Link do Roblox> [top|bottom|hair|calca|camisa] [force]\n"
                f"Exemplos:\n"
                f"  /import 131607970996365 (Popstar Hair)\n"
                f"  /import 9240757332 (Suéter)\n"
                f"  /import 109837605892174 (Jeans)\n"
                f"  /import 137146416353285 (Skater Pants)\n"
                f"  /import 89475537632859 (Boxy Shirt)\n"
                f"  /import https://www.roblox.com/catalog/...\n"
                f"Equipado atual: Top={top_info} | Calça={bot_info} | Cabelo={hair_info}"
            ), GOLD

        force_reload = False
        force_type = None  # "top", "bottom", "tool", "hair"
        remaining_tokens = []

        for arg in args:
            al = arg.lower().strip()
            if al in ("force", "forcar", "rebuild", "reload", "refit"):
                force_reload = True
            elif al in ("hair", "cabelo", "wig", "peruca"):
                force_type = "hair"
            elif al in ("top", "shirt", "camisa", "sueter", "blusa", "casaco", "jaqueta"):
                force_type = "top"
            elif al in ("bottom", "pants", "calca", "calça", "jeans", "shorts", "bermuda", "saia"):
                force_type = "bottom"
            elif al in ("tool", "arma", "katana", "sword", "espada"):
                force_type = "tool"
            else:
                remaining_tokens.append(arg)

        raw_target = " ".join(remaining_tokens).strip() if remaining_tokens else ""
        if not raw_target and not force_type:
            return False, "[Import] Digite o ID numérico ou link da peça do Roblox. Ex: /import 9240757332", RED

        asset_id = None
        digits_match = re.search(r"(\d{4,})", raw_target)
        if digits_match:
            asset_id = int(digits_match.group(1))
        else:
            clean_name = raw_target.lower().strip()
            if clean_name in OUTFIT_PRESETS:
                asset_id = OUTFIT_PRESETS[clean_name]
                if force_type is None:
                    force_type = "top"
            elif clean_name in BOTTOM_PRESETS:
                asset_id = BOTTOM_PRESETS[clean_name]
                if force_type is None:
                    force_type = "bottom"
            elif clean_name in ("katana", "sword", "espada"):
                asset_id = 12187348
                if force_type is None:
                    force_type = "tool"
            else:
                return False, f"[Import] ID ou URL do Roblox inválido: '{raw_target}'. Ex: /import 9240757332", RED

        is_fem = getattr(self.character_model.customization, "is_female", False)
        body_type = "female" if is_fem else "male"
        suffix = "_female.obj" if is_fem else ".obj"

        from src.clothing.wear_engine import RobloxWearEngine, TOP_ASSET_TYPES, BOTTOM_ASSET_TYPES
        engine = RobloxWearEngine(body_type=body_type)

        try:
            meta = engine.fetch_asset(asset_id)
        except Exception as e:
            return False, f"[Import] Falha ao consultar/baixar asset {asset_id} do Roblox: {e}", RED

        asset_name = meta.get("name", f"asset_{asset_id}").replace("_", " ")
        type_id = meta.get("type_id", 65)

        # 1. Cabelo 3D / Hair Accessory (AssetType 41 ou nome/argumento indicando cabelo)
        is_hair = force_type == "hair" or type_id == 41 or meta.get("is_hair", False) or any(k in asset_name.lower() for k in ["hair", "cabelo", "wig", "popstar", "ponytail", "pigtails", "braids"])
        if is_hair:
            try:
                engine.equip_hair(asset_id)
                self.character_model.update_customization(hair_id=asset_id)
                return True, f"[Import] Cabelo 3D '{asset_name}' ({asset_id}) equipado com sucesso!", GREEN
            except Exception as e:
                return False, f"[Import] Erro ao equipar cabelo {asset_id}: {e}", RED

        # 2. Acessório / Arma / Katana
        if force_type == "tool" or type_id == 19 or (type_id not in (64, 65, 66, 67, 68, 69, 72) and any(k in asset_name.lower() for k in ["katana", "sword", "blade", "gear"])):
            try:
                engine.equip_tool(asset_id)
                self.character_model.update_customization(tool_id=asset_id)
                return True, f"[Import] Acessório/Arma '{asset_name}' ({asset_id}) equipado com sucesso!", GREEN
            except Exception as e:
                return False, f"[Import] Erro ao equipar acessório {asset_id}: {e}", RED

        # 2. Calçados / Tênis isolados (apenas tipo 70/71 ou quando não for calça/camisa)
        is_known_clothing = (type_id in (64, 65, 66, 67, 68, 69, 72)) or any(k in asset_name.lower() for k in ["pants", "jeans", "trouser", "skirt", "shorts", "shirt", "sweater", "jacket", "jersey", "bomber"])
        if (type_id in (70, 71) or (not is_known_clothing and any(k in asset_name.lower() for k in ["shoe", "sneaker", "boot", "sapato", "tenis"]))):
            try:
                engine.equip_shoes(asset_id)
                return True, f"[Import] Calçados '{asset_name}' ({asset_id}) equipados com sucesso!", GREEN
            except Exception as e:
                return False, f"[Import] Erro ao equipar calçados {asset_id}: {e}", RED

        # 3. Determina se é top ou bottom
        if force_type == "top":
            is_top = True
        elif force_type == "bottom":
            is_top = False
        else:
            is_top = meta.get("is_top", type_id in TOP_ASSET_TYPES or type_id not in BOTTOM_ASSET_TYPES)

        # 4. Verifica se o modelo ajustado já existe
        models_dir = os.path.join(PROJECT_ROOT, "assets", "models")
        fitted_obj = os.path.join(models_dir, f"character_native_{asset_id}{suffix}")
        is_already_fitted = os.path.exists(fitted_obj) and not force_reload

        if is_already_fitted:
            if is_top:
                self.character_model.update_customization(top_id=asset_id)
                label = "Roupa Superior"
                return True, f"[Import] {label} '{asset_name}' ({asset_id}) vestida com sucesso!", GREEN
            else:
                self.character_model.update_customization(bottom_id=asset_id)
                label = "Calça / Roupa Inferior"
                return True, f"[Import] {label} '{asset_name}' ({asset_id}) vestida com sucesso!", GREEN

        # Se não está em cache e for modo síncrono (ex: unit tests com create_mesh=False)
        if not run_async or not getattr(self.character_model, "create_mesh", True):
            try:
                wear_res = engine.wear(asset_id, body_type=body_type)
            except Exception as e:
                return False, f"[Import] Erro ao adaptar/vestir o asset {asset_id} ({body_type}): {e}", RED

            if is_top:
                self.character_model.update_customization(top_id=asset_id)
                label = "Roupa Superior"
                sub_info = " (Manga adaptada)"
                return True, f"[Import] {label} '{asset_name}' ({asset_id}) vestida com sucesso!{sub_info}", GREEN
            else:
                self.character_model.update_customization(bottom_id=asset_id)
                label = "Calça / Roupa Inferior"
                return True, f"[Import] {label} '{asset_name}' ({asset_id}) vestida com sucesso!", GREEN

        # 5. Execução em segundo plano (Thread separada) para NÃO travar a interface/jogo
        self.is_importing = True
        self.import_asset_id = asset_id
        self.import_status = f"Importando #{asset_id}..."

        def worker():
            try:
                wear_res = engine.wear(asset_id, body_type=body_type)

                def on_success():
                    self.is_importing = False
                    self.import_status = ""
                    self.import_asset_id = None
                    if is_top:
                        self.character_model.update_customization(top_id=asset_id)
                        label = "Roupa Superior"
                    else:
                        self.character_model.update_customization(bottom_id=asset_id)
                        label = "Calça / Roupa Inferior"
                    if self.chat_console:
                        self.chat_console.add_message(
                            f"[Import] {label} '{asset_name}' (#{asset_id}) adaptada e vestida com sucesso!",
                            (85, 255, 85)
                        )

                with self._callback_lock:
                    self._pending_main_thread_callbacks.append(on_success)

            except Exception as e:
                def on_error():
                    self.is_importing = False
                    self.import_status = ""
                    self.import_asset_id = None
                    if self.chat_console:
                        self.chat_console.add_message(
                            f"[Import] Erro ao adaptar/vestir o asset #{asset_id}: {e}",
                            (255, 85, 85)
                        )

                with self._callback_lock:
                    self._pending_main_thread_callbacks.append(on_error)

        t = threading.Thread(target=worker, daemon=True, name=f"RobloxWear-{asset_id}")
        t.start()

        return True, (
            f"[Import] Baixando e adaptando '{asset_name}' (#{asset_id}) em segundo plano...\n"
            f"[Import] A interface continua liberada! A roupa será equipada automaticamente ao terminar."
        ), CYAN



class ChatConsole:
    """Console de Chat estilo Minecraft com entrada de comandos, histórico, autocompletar e HUD 2D."""

    def __init__(
        self,
        command_handler: Optional[SkinCommandHandler] = None,
        create_gl: bool = True,
        max_messages: int = 10,
        glfw_window: Optional[Any] = None,
    ) -> None:
        self.command_handler = command_handler
        if self.command_handler is not None:
            self.command_handler.chat_console = self
        self.create_gl = create_gl
        self.max_messages = max_messages
        self.glfw_window = glfw_window

        self.loading_frame: int = 0
        self.loading_timer: float = 0.0
        self.SPINNER_FRAMES = ["|", "/", "-", "\\"]

        self.is_open: bool = False
        self.input_text: str = ""
        self.cursor_pos: int = 0
        self.cursor_visible: bool = True
        self.cursor_timer: float = 0.0

        self.messages: List[ChatMessage] = [
            ChatMessage("[Isometricon] Pressione [T] para abrir o chat ou [/] para comandos", (200, 200, 200), time.time()),
            ChatMessage("[Dica] Digite / e use [TAB] para autocompletar comandos de skin em tempo real!", (255, 215, 0), time.time()),
        ]
        self.history: List[str] = []
        self.history_index: int = -1

        # Estado do Autocompletar / Sugestões inteligentes estilo Minecraft
        self.suggestions: List[str] = []
        self.suggestion_index: int = 0
        self.suggestion_prefix: str = ""
        self.suggestion_base: str = ""
        self.ghost_text: str = ""
        self.suggestion_chips: List[Tuple[str, int, int, int, int]] = []
        self._tab_cycle_active: bool = False
        self._tab_base_text: str = ""
        self._ignore_chars: set = set()

        self.hud_dirty: bool = True
        self.hud_tex_id: Optional[int] = None
        self.hud_shader: Optional[Shader] = None
        self.vao: int = 0
        self.vbo: int = 0
        self.ebo: int = 0

        # Carrega fontes
        self.font = self._load_font(15)
        self.font_small = self._load_font(12)

        if self.create_gl:
            self._init_gl()

    def _get_clipboard_string(self) -> str:
        """Obtém o conteúdo de texto da área de transferência (clipboard) como string garantida."""
        # 1. No Windows, prioriza a API Win32 nativa (CF_UNICODETEXT) - 100% confiável e direta
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.OpenClipboard.argtypes = [ctypes.c_void_p]
                user32.OpenClipboard.restype = ctypes.c_int
                user32.CloseClipboard.argtypes = []
                user32.CloseClipboard.restype = ctypes.c_int
                user32.GetClipboardData.restype = ctypes.c_void_p
                user32.GetClipboardData.argtypes = [ctypes.c_uint]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.restype = ctypes.c_int

                opened = False
                for _ in range(5):
                    if user32.OpenClipboard(None):
                        opened = True
                        break
                    time.sleep(0.005)

                if opened:
                    try:
                        h = user32.GetClipboardData(13)  # CF_UNICODETEXT
                        if h:
                            p = kernel32.GlobalLock(h)
                            if p:
                                try:
                                    val = ctypes.c_wchar_p(p).value
                                    if val:
                                        return str(val)
                                finally:
                                    kernel32.GlobalUnlock(h)
                    finally:
                        user32.CloseClipboard()
            except Exception:
                pass

        # 2. Fallback via GLFW (decodificando bytes se pyglfw retornar tipo binário)
        try:
            import glfw
            win = self.glfw_window or glfw.get_current_context()
            if win:
                t = glfw.get_clipboard_string(win)
                if t is not None:
                    if isinstance(t, bytes):
                        t = t.decode("utf-8", errors="replace")
                    if isinstance(t, str) and t:
                        return t
        except Exception:
            pass

        # 3. Fallback via tkinter se disponível
        try:
            import tkinter
            tk = tkinter.Tk()
            tk.withdraw()
            try:
                res = tk.clipboard_get()
                if res:
                    return str(res)
            finally:
                tk.destroy()
        except Exception:
            pass

        return ""

    def _set_clipboard_string(self, text: str) -> None:
        """Define o conteúdo de texto da área de transferência."""
        if not text:
            return

        text = str(text)

        # 1. No Windows, usa a API Win32 nativa (CF_UNICODETEXT)
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.OpenClipboard.argtypes = [ctypes.c_void_p]
                user32.OpenClipboard.restype = ctypes.c_int
                user32.CloseClipboard.argtypes = []
                user32.CloseClipboard.restype = ctypes.c_int
                user32.EmptyClipboard.argtypes = []
                user32.EmptyClipboard.restype = ctypes.c_int
                user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
                user32.SetClipboardData.restype = ctypes.c_void_p
                kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
                kernel32.GlobalAlloc.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.restype = ctypes.c_int

                opened = False
                for _ in range(5):
                    if user32.OpenClipboard(None):
                        opened = True
                        break
                    time.sleep(0.005)

                if opened:
                    try:
                        user32.EmptyClipboard()
                        encoded = text.encode("utf-16-le") + b"\x00\x00"
                        h = kernel32.GlobalAlloc(0x0002, len(encoded))  # GMEM_MOVEABLE
                        if h:
                            p = kernel32.GlobalLock(h)
                            if p:
                                ctypes.memmove(p, encoded, len(encoded))
                                kernel32.GlobalUnlock(h)
                                user32.SetClipboardData(13, h)
                    finally:
                        user32.CloseClipboard()
                return
            except Exception:
                pass

        # 2. Fallback via GLFW
        try:
            import glfw
            win = self.glfw_window or glfw.get_current_context()
            if win:
                glfw.set_clipboard_string(win, text)
                return
        except Exception:
            pass

    def _load_font(self, size: int = 15) -> Any:
        """Carrega fonte Consolas ou TrueType equivalente do sistema."""
        font_candidates = [
            "consola.ttf",
            "consolas.ttf",
            "C:/Windows/Fonts/consola.ttf",
            "segoeui.ttf",
            "arial.ttf",
        ]
        for f in font_candidates:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _init_gl(self) -> None:
        """Inicializa shaders e buffers OpenGL para o quad 2D do HUD."""
        import OpenGL.GL as gl

        v_shader = os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.vert")
        f_shader = os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.frag")
        self.hud_shader = Shader(v_shader, f_shader)

        # Quad unitário 2D (Pos2, UV2)
        quad_verts = np.array([
            0.0, 0.0,   0.0, 0.0,
            1.0, 0.0,   1.0, 0.0,
            1.0, 1.0,   1.0, 1.0,
            0.0, 1.0,   0.0, 1.0,
        ], dtype=np.float32)

        quad_indices = np.array([
            0, 1, 2,
            2, 3, 0,
        ], dtype=np.uint32)

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        self.ebo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self.vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, quad_verts.nbytes, quad_verts, gl.GL_STATIC_DRAW)

        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, gl.GL_STATIC_DRAW)

        stride = 4 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, None)

        gl.glEnableVertexAttribArray(1)
        import ctypes
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(2 * 4))

        gl.glBindVertexArray(0)

        # Textura do HUD
        self.hud_tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.hud_tex_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

    def add_message(self, text: str, color: Tuple[int, int, int] = (255, 255, 255)) -> None:
        """Adiciona uma nova mensagem ao histórico do chat."""
        msg = ChatMessage(text=text, color=color, timestamp=time.time())
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
        self.hud_dirty = True
        print(f"[Chat] {text}")

    def open(self, initial_text: str = "", ignore_char: Optional[str] = None) -> None:
        """Abre a barra de digitação do chat."""
        self.is_open = True
        self.input_text = initial_text
        self.cursor_pos = len(initial_text)
        self.cursor_visible = True
        self.cursor_timer = 0.0
        self.history_index = -1
        self._tab_cycle_active = False
        self._ignore_chars = {ignore_char.lower(), ignore_char.upper()} if ignore_char else set()
        self._update_autocomplete()
        self.hud_dirty = True

    def close(self) -> None:
        """Fecha a barra de digitação do chat sem executar."""
        self.is_open = False
        self.input_text = ""
        self.cursor_pos = 0
        self.history_index = -1
        self._tab_cycle_active = False
        self._ignore_chars.clear()
        self.suggestions = []
        self.ghost_text = ""
        self.hud_dirty = True

    def toggle(self, initial_text: str = "") -> None:
        """Alterna a abertura da barra de chat."""
        if self.is_open:
            self.close()
        else:
            self.open(initial_text)

    def handle_char(self, codepoint: int) -> bool:
        """Recebe entrada de caractere Unicode do GLFW."""
        if not self.is_open:
            return False

        # Ignora caracteres de controle ASCII (< 32, ex: Ctrl+V emitindo codepoint 22, ou DEL 127)
        if codepoint < 32 or codepoint == 127:
            return True

        try:
            char = chr(codepoint)
        except (ValueError, OverflowError):
            return False

        try:
            if self._ignore_chars:
                if char in self._ignore_chars:
                    self._ignore_chars.clear()
                    return True
                self._ignore_chars.clear()

            # Insere caractere na posição do cursor
            self.input_text = self.input_text[:self.cursor_pos] + char + self.input_text[self.cursor_pos:]
            self.cursor_pos += 1
            self.cursor_visible = True
            self.cursor_timer = 0.0
            self._tab_cycle_active = False
            self._update_autocomplete()
            self.hud_dirty = True
            return True
        except Exception as e:
            print(f"[Chat] Erro ao inserir caractere: {e}")
            return True

    def handle_key(self, key: int, action: int, mods: int) -> bool:
        """Processa eventos de teclas. Retorna True se o evento foi consumido."""
        import glfw

        # Abrir com 'T' ou '/' quando fechado
        if not self.is_open:
            if action == glfw.PRESS:
                if key == glfw.KEY_T:
                    self.open(ignore_char="t")
                    return True
                elif key == glfw.KEY_SLASH:
                    self.open("/", ignore_char="/")
                    return True
            return False

        # Quando aberto, teclas especiais
        if action in (glfw.PRESS, glfw.REPEAT):
            # Atalhos de Clipboard e Edição com Ctrl ou Cmd (Super)
            ctrl_or_cmd = bool(mods & (glfw.MOD_CONTROL | glfw.MOD_SUPER))
            if ctrl_or_cmd and key == glfw.KEY_V:
                try:
                    clip = self._get_clipboard_string()
                    if clip:
                        if isinstance(clip, bytes):
                            clip = clip.decode("utf-8", errors="replace")
                        clip = str(clip).replace("\r", "").replace("\n", " ").strip()
                        if clip:
                            self.input_text = self.input_text[:self.cursor_pos] + clip + self.input_text[self.cursor_pos:]
                            self.cursor_pos += len(clip)
                            self.cursor_visible = True
                            self.cursor_timer = 0.0
                            self._tab_cycle_active = False
                            self._update_autocomplete()
                            self.hud_dirty = True
                except Exception as e:
                    print(f"[Chat] Erro ao colar texto: {e}")
                return True

            if ctrl_or_cmd and key == glfw.KEY_C:
                try:
                    if self.input_text:
                        self._set_clipboard_string(str(self.input_text))
                except Exception as e:
                    print(f"[Chat] Erro ao copiar para área de transferência: {e}")
                return True

            if ctrl_or_cmd and key == glfw.KEY_A:
                self.cursor_pos = len(self.input_text)
                self.cursor_visible = True
                self.hud_dirty = True
                return True

            if key == glfw.KEY_ESCAPE:
                self.close()
                return True

            elif key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER):
                self._submit_input()
                return True

            elif key == glfw.KEY_TAB:
                self._apply_autocomplete(shift_held=bool(mods & glfw.MOD_SHIFT))
                return True

            elif key == glfw.KEY_BACKSPACE:
                if self.cursor_pos > 0:
                    self.input_text = self.input_text[:self.cursor_pos - 1] + self.input_text[self.cursor_pos:]
                    self.cursor_pos -= 1
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_DELETE:
                if self.cursor_pos < len(self.input_text):
                    self.input_text = self.input_text[:self.cursor_pos] + self.input_text[self.cursor_pos + 1:]
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_LEFT:
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_RIGHT:
                if self.cursor_pos < len(self.input_text):
                    self.cursor_pos += 1
                    self.cursor_visible = True
                    self.cursor_timer = 0.0
                    self._tab_cycle_active = False
                    self._update_autocomplete()
                    self.hud_dirty = True
                return True

            elif key == glfw.KEY_HOME:
                self.cursor_pos = 0
                self.cursor_visible = True
                self._tab_cycle_active = False
                self._update_autocomplete()
                self.hud_dirty = True
                return True

            elif key == glfw.KEY_END:
                self.cursor_pos = len(self.input_text)
                self.cursor_visible = True
                self._tab_cycle_active = False
                self._update_autocomplete()
                self.hud_dirty = True
                return True

            elif key == glfw.KEY_UP:
                self._navigate_history(-1)
                return True

            elif key == glfw.KEY_DOWN:
                self._navigate_history(1)
                return True

        # Consome todas as outras teclas quando o chat está aberto para não movimentar o jogo
        return True

    def _sugg_expects_args(self, chosen: str) -> bool:
        """Verifica se uma opção de comando ainda aceita argumentos posteriores."""
        return chosen.lower() in SUGGESTIONS_EXPECTING_ARGS

    def _get_suggestions_for_prefix(self, text: str) -> Tuple[List[str], str, str]:
        """Extrai as sugestões contextuais com base na árvore de comandos."""
        if not text.startswith("/"):
            return [], "", text

        clean = text[1:]

        # Caso 1: Ainda digitando o comando raiz (sem espaço)
        if " " not in clean:
            prefix = clean.lower()
            root_cmds = sorted(list(COMMAND_TREE.keys()))
            matches = [f"/{c}" for c in root_cmds if c.startswith(prefix)]
            return matches, text, ""

        # Caso 2: Já digitou o comando raiz e argumentos
        parts = clean.split(" ")
        root_cmd = parts[0].lower()
        args = parts[1:]

        node = COMMAND_TREE.get(root_cmd)
        if node is None:
            return [], "", text

        curr = node
        base_parts = ["/" + parts[0]]

        for part in args[:-1]:
            base_parts.append(part)
            if isinstance(curr, dict):
                curr = curr.get(part.lower())
                if curr is None:
                    return [], "", text
            elif isinstance(curr, list):
                return [], "", text

        curr_token = args[-1].lower()
        base_text = " ".join(base_parts) + " "

        is_top_cmd = (
            root_cmd in ("top", "shirt", "camisa", "sueter", "blusa", "roupa") or
            (root_cmd in ("skin", "char", "avatar", "set") and len(args) >= 2 and args[0].lower() in ("top", "shirt", "camisa", "sueter", "blusa", "roupa"))
        )

        if isinstance(curr, dict):
            options = list(curr.keys())
            if is_top_cmd:
                imported = get_imported_top_options()
                options = sorted(list(set(options + list(imported.keys()))))
            matches = [opt for opt in options if opt.lower().startswith(curr_token)]
            return matches, args[-1], base_text
        elif isinstance(curr, list):
            options = list(curr)
            if is_top_cmd:
                imported = get_imported_top_options()
                options = sorted(list(set(options + list(imported.keys()))))
            matches = [opt for opt in options if opt.lower().startswith(curr_token)]
            return matches, args[-1], base_text

        return [], "", text

    def _update_autocomplete(self, preserve_cycle: bool = False) -> None:
        """Calcula a lista de comandos e argumentos válidos para sugestão em tempo real."""
        if self._tab_cycle_active and preserve_cycle:
            self.ghost_text = ""
            return

        text = self.input_text[:self.cursor_pos]
        if not text.startswith("/"):
            self.suggestions = []
            self.suggestion_index = 0
            self.suggestion_prefix = ""
            self.suggestion_base = ""
            self.ghost_text = ""
            return

        suggestions, prefix, base_text = self._get_suggestions_for_prefix(text)
        self.suggestions = suggestions
        self.suggestion_prefix = prefix
        self.suggestion_base = base_text

        if self.suggestion_index >= len(self.suggestions):
            self.suggestion_index = 0

        if self.suggestions:
            chosen = self.suggestions[self.suggestion_index]
            if chosen.lower().startswith(prefix.lower()):
                suffix = chosen[len(prefix):]
            else:
                suffix = chosen

            needs_space = self._sugg_expects_args(chosen)
            self.ghost_text = suffix + (" " if needs_space and not suffix.endswith(" ") else "")
        else:
            self.ghost_text = ""

    def _apply_autocomplete(self, shift_held: bool = False) -> None:
        """Aplica a sugestão ativa do autocomplete ou avança para a próxima com TAB."""
        if not self.suggestions:
            return

        if self._tab_cycle_active:
            if shift_held:
                self.suggestion_index = (self.suggestion_index - 1) % len(self.suggestions)
            else:
                self.suggestion_index = (self.suggestion_index + 1) % len(self.suggestions)
        else:
            self._tab_cycle_active = True
            self._tab_base_text = self.suggestion_base

        chosen = self.suggestions[self.suggestion_index]
        needs_space = self._sugg_expects_args(chosen)
        new_word = chosen + (" " if needs_space else "")

        if chosen.startswith("/"):
            self.input_text = new_word
        else:
            self.input_text = self._tab_base_text + new_word

        self.cursor_pos = len(self.input_text)
        self.cursor_visible = True
        self.cursor_timer = 0.0

        if needs_space:
            self._tab_cycle_active = False
            self._update_autocomplete()
        else:
            self._update_autocomplete(preserve_cycle=True)

        self.hud_dirty = True

    def handle_mouse_click(self, x: float, y: float) -> bool:
        """Processa clique do mouse sobre os chips de sugestão do autocomplete."""
        if not self.is_open or not self.suggestion_chips:
            return False

        for sugg, x0, y0, x1, y1 in self.suggestion_chips:
            if x0 <= x <= x1 and y0 <= y <= y1:
                if sugg in self.suggestions:
                    self.suggestion_index = self.suggestions.index(sugg)
                else:
                    self.suggestions = [sugg]
                    self.suggestion_index = 0

                self._tab_cycle_active = False
                self._apply_autocomplete()
                return True
        return False

    def _navigate_history(self, direction: int) -> None:
        """Navega para comandos anteriores ou posteriores no histórico."""
        if not self.history:
            return

        if self.history_index == -1:
            if direction < 0:
                self.history_index = len(self.history) - 1
        else:
            self.history_index += direction

        if self.history_index < 0:
            self.history_index = 0
        elif self.history_index >= len(self.history):
            self.history_index = -1
            self.input_text = ""
            self.cursor_pos = 0
            self._tab_cycle_active = False
            self._update_autocomplete()
            self.hud_dirty = True
            return

        self.input_text = self.history[self.history_index]
        self.cursor_pos = len(self.input_text)
        self.cursor_visible = True
        self._tab_cycle_active = False
        self._update_autocomplete()
        self.hud_dirty = True

    def _submit_input(self) -> None:
        """Executa a linha digitada e fecha a barra de chat."""
        cmd = self.input_text.strip()
        self.close()

        if not cmd:
            return

        # Registra no histórico
        if not self.history or self.history[-1] != cmd:
            self.history.append(cmd)

        # Executa no CommandHandler
        if self.command_handler:
            success, feedback, color = self.command_handler.execute(cmd)
            if feedback:
                self.add_message(feedback, color)
        else:
            self.add_message(f"> {cmd}", (255, 255, 255))

    def update(self, dt: float) -> None:
        """Atualiza temporizador do cursor, processa callbacks na thread principal e anima spinner."""
        if self.command_handler is not None:
            self.command_handler.process_pending_callbacks()

        # Atualiza animação do loading spinner se estiver importando roupa em background
        is_importing = bool(self.command_handler and self.command_handler.is_importing)
        if is_importing:
            self.loading_timer += dt
            if self.loading_timer >= 0.12:
                self.loading_timer = 0.0
                self.loading_frame = (self.loading_frame + 1) % len(self.SPINNER_FRAMES)
                self.hud_dirty = True

        if self.is_open:
            self.cursor_timer += dt
            if self.cursor_timer >= 0.45:
                self.cursor_timer = 0.0
                self.cursor_visible = not self.cursor_visible
                self.hud_dirty = True

    def render(self, window_width: int, window_height: int) -> None:
        """Renderiza a caixa de chat e mensagens na tela usando OpenGL 3.3 Core."""
        if not self.create_gl or self.hud_shader is None:
            return

        now = time.time()
        # Filtra mensagens recentes (exibe mensagens nos últimos 8 segundos quando chat fechado)
        visible_messages = [
            m for m in self.messages
            if self.is_open or (now - m.timestamp < 8.0)
        ]

        is_importing = bool(self.command_handler and self.command_handler.is_importing)
        if not self.is_open and not visible_messages and not is_importing:
            return

        import OpenGL.GL as gl

        # 1. Desenha a textura do HUD se modificada
        if self.hud_dirty:
            hud_img = self._generate_hud_image(window_width, window_height, visible_messages)
            img_data = np.array(hud_img, dtype=np.uint8)

            gl.glBindTexture(gl.GL_TEXTURE_2D, self.hud_tex_id)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                hud_img.width, hud_img.height, 0,
                gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data
            )
            self.hud_dirty = False

        # 2. Configura pipeline 2D ortográfico
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDepthMask(gl.GL_FALSE)

        self.hud_shader.use()
        proj = mat4_ortho(0.0, float(window_width), float(window_height), 0.0, -1.0, 1.0)
        self.hud_shader.set_mat4("u_Projection", proj)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.hud_tex_id)
        self.hud_shader.set_int("u_Texture", 0)

        # Ajusta vértices para as dimensões exatas da janela
        w = float(window_width)
        h = float(window_height)
        quad_verts = np.array([
            0.0, 0.0,   0.0, 0.0,
            w,   0.0,   1.0, 0.0,
            w,   h,     1.0, 1.0,
            0.0, h,     0.0, 1.0,
        ], dtype=np.float32)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, quad_verts.nbytes, quad_verts)

        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_BLEND)

    def _generate_hud_image(
        self,
        width: int,
        height: int,
        visible_messages: List[ChatMessage],
    ) -> Image.Image:
        """Desenha a imagem RGBA contendo as mensagens, sugestões de autocompletar e campo de texto estilo Minecraft."""
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Dimensões da caixa de chat (canto inferior esquerdo)
        box_x = 16
        box_w = min(740, width - 32)
        line_height = 20
        max_lines = 8
        messages_to_show = visible_messages[-max_lines:]

        # Altura calculada da caixa
        hist_h = len(messages_to_show) * line_height + 10
        has_suggestions = self.is_open and bool(self.suggestions)
        sugg_h = 34 if has_suggestions else 0
        input_h = 28 if self.is_open else 0
        total_h = hist_h + sugg_h + input_h + (8 if has_suggestions else 6)
        box_y = height - total_h - 16

        # Fundo semitransparente escuro estilo Minecraft Chat
        if self.is_open or messages_to_show:
            draw.rectangle(
                [box_x - 6, box_y - 4, box_x + box_w + 6, box_y + total_h + 2],
                fill=(0, 0, 0, 165 if self.is_open else 115),
                outline=(50, 50, 60, 180) if self.is_open else None,
                width=1,
            )

        # Desenha mensagens do histórico
        curr_y = box_y + 4
        for msg in messages_to_show:
            r, g, b = msg.color
            draw.text((box_x + 1, curr_y + 1), msg.text, font=self.font, fill=(20, 20, 20, 220))
            draw.text((box_x, curr_y), msg.text, font=self.font, fill=(r, g, b, 255))
            curr_y += line_height

        # Painel de sugestões e autocomplete (quando aberto e com sugestões)
        self.suggestion_chips = []
        if has_suggestions:
            sugg_y = box_y + hist_h + 2
            draw.rectangle(
                [box_x - 4, sugg_y, box_x + box_w + 4, sugg_y + sugg_h],
                fill=(12, 16, 24, 235),
                outline=(45, 65, 95, 210),
                width=1,
            )

            # Badge indicadora de tecla TAB
            tab_badge_w = 48
            draw.rounded_rectangle(
                [box_x + 4, sugg_y + 6, box_x + 4 + tab_badge_w, sugg_y + 28],
                radius=3,
                fill=(210, 165, 25, 240),
            )
            draw.text((box_x + 8, sugg_y + 9), "TAB ⇥", font=self.font_small, fill=(15, 15, 15, 255))

            # Chips horizontais de sugestões
            cx = box_x + 4 + tab_badge_w + 8
            cy = sugg_y + 6
            for i, sugg in enumerate(self.suggestions):
                try:
                    sugg_text_w = int(draw.textlength(sugg, font=self.font))
                except AttributeError:
                    sugg_text_w = len(sugg) * 9
                chip_w = sugg_text_w + 12

                # Se estourar a largura do painel, exibe contagem restante
                if cx + chip_w > box_x + box_w - 45:
                    remaining = len(self.suggestions) - i
                    draw.text((cx + 2, cy + 4), f"+{remaining}", font=self.font_small, fill=(160, 175, 195, 220))
                    break

                if i == self.suggestion_index:
                    # Chip ativo em destaque
                    draw.rounded_rectangle(
                        [cx, cy, cx + chip_w, cy + 22],
                        radius=4,
                        fill=(28, 92, 185, 250),
                        outline=(120, 215, 255, 255),
                        width=1,
                    )
                    draw.text((cx + 6, cy + 3), sugg, font=self.font, fill=(255, 255, 255, 255))
                else:
                    # Chip inativo
                    draw.rounded_rectangle(
                        [cx, cy, cx + chip_w, cy + 22],
                        radius=4,
                        fill=(22, 28, 38, 215),
                        outline=(52, 64, 82, 180),
                        width=1,
                    )
                    draw.text((cx + 6, cy + 3), sugg, font=self.font, fill=(180, 195, 215, 225))

                self.suggestion_chips.append((sugg, cx, cy, cx + chip_w, cy + 22))
                cx += chip_w + 6

        # Campo de entrada de comando (quando aberto)
        if self.is_open:
            input_y = box_y + hist_h + (sugg_h + 4 if has_suggestions else 0)
            draw.rectangle(
                [box_x - 4, input_y, box_x + box_w + 4, input_y + input_h],
                fill=(10, 12, 16, 235),
                outline=(80, 135, 215, 230),
                width=1,
            )

            prompt_symbol = "> "
            draw.text((box_x + 6, input_y + 6), prompt_symbol, font=self.font, fill=(255, 215, 0, 255))

            try:
                prompt_w = draw.textlength(prompt_symbol, font=self.font)
            except AttributeError:
                prompt_w = 18

            text_x = box_x + 6 + prompt_w
            draw.text((text_x, input_y + 6), self.input_text, font=self.font, fill=(255, 255, 255, 255))

            # Texto fantasma (ghost text) da sugestão atual
            if self.ghost_text:
                try:
                    user_w = draw.textlength(self.input_text, font=self.font)
                except AttributeError:
                    user_w = len(self.input_text) * 9
                draw.text((text_x + user_w, input_y + 6), self.ghost_text, font=self.font, fill=(140, 150, 175, 180))

            # Cursor piscante
            if self.cursor_visible:
                text_before_cursor = self.input_text[:self.cursor_pos]
                try:
                    cursor_offset = draw.textlength(text_before_cursor, font=self.font)
                except AttributeError:
                    cursor_offset = len(text_before_cursor) * 9
                cursor_x = text_x + cursor_offset
                draw.text((cursor_x, input_y + 6), "_", font=self.font, fill=(255, 255, 255, 255))
        else:
            hint_text = "[T] Abrir Chat / Comandos | [/] Digitar Comando"
            draw.text((box_x, height - 22), hint_text, font=self.font, fill=(160, 160, 170, 160))

        # Badge animada de Loading / Importando em segundo plano (canto superior direito)
        if self.command_handler and self.command_handler.is_importing:
            spinner = self.SPINNER_FRAMES[self.loading_frame % len(self.SPINNER_FRAMES)]
            status_text = self.command_handler.import_status or f"Importando #{self.command_handler.import_asset_id}..."
            badge_text = f"[ {spinner} ] {status_text}"

            try:
                badge_w = int(draw.textlength(badge_text, font=self.font)) + 24
            except AttributeError:
                badge_w = len(badge_text) * 10 + 24
            badge_h = 32
            badge_x = width - badge_w - 20
            badge_y = 20

            # Fundo translúcido estilizado com borda neon ciano
            draw.rounded_rectangle(
                [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
                radius=6,
                fill=(12, 22, 34, 230),
                outline=(85, 255, 255, 240),
                width=2,
            )
            # Texto e spinner em ciano neon brilhante
            draw.text(
                (badge_x + 12, badge_y + 7),
                badge_text,
                font=self.font,
                fill=(85, 255, 255, 255),
            )

        return img

    def delete(self) -> None:
        """Libera os recursos OpenGL do HUD."""
        if not self.create_gl:
            return
        import OpenGL.GL as gl

        if self.hud_tex_id:
            try:
                gl.glDeleteTextures(1, [self.hud_tex_id])
            except Exception:
                pass
            self.hud_tex_id = None

        if self.vao:
            try:
                gl.glDeleteVertexArrays(1, [self.vao])
            except Exception:
                pass
            self.vao = 0

        if self.vbo:
            try:
                gl.glDeleteBuffers(1, [self.vbo])
            except Exception:
                pass
            self.vbo = 0

        if self.ebo:
            try:
                gl.glDeleteBuffers(1, [self.ebo])
            except Exception:
                pass
            self.ebo = 0

        if self.hud_shader:
            try:
                self.hud_shader.delete()
            except Exception:
                pass
            self.hud_shader = None
