"""Comandos do chat para o personagem: aparência, roupas e visualizador.

Tudo o que muda o personagem fica sob ``/skin`` (``/skin olhos azul``, ``/skin top sweater``,
``/skin vestir <id>``). No primeiro nível só existem ``/skin``, ``/ajuda`` e ``/girar``.

Um único quadro (``SKIN_COMMANDS`` e ``ROOT_COMMANDS``) define cada comando: seus nomes, uso,
resumo, opções para o autocompletar e a função que o executa. A ajuda e o autocompletar do
chat saem desse mesmo quadro, então não divergem da execução.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import glob
import os
import re
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.clothing.body_shape import ADJUSTMENTS
from src.clothing.eye_shapes import SHAPE_NAMES as EYE_SHAPE_NAMES
from src.clothing.ears import STYLE_NAMES as EAR_STYLE_NAMES
from src.clothing.nose import STYLE_NAMES as NOSE_STYLE_NAMES
from src.clothing.character_model import BOTTOM_PRESETS, DEFAULT_HAIR_ID, HANDMADE_HAIR, OUTFIT_PRESETS, SKIN_PRESETS, CharacterModel
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
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLOTHING_DIR = os.path.join(PROJECT_ROOT, "assets", "models", "clothing")

GREEN = (85, 255, 85)
GOLD = (255, 215, 0)
HSR_HISTORY = 100  # changes of the skin under the clothes that can be undone

RED = (255, 85, 85)
CYAN = (85, 255, 255)

Result = Tuple[bool, str, Tuple[int, int, int]]
KATANA_ID = 12187348

# Valores aceitos (português primeiro; o inglês do próprio enum também vale).
EYE_COLORS = {"azul": IrisColor.BLUE, "verde": IrisColor.GREEN, "castanho": IrisColor.BROWN, "roxo": IrisColor.PURPLE,
              "vermelho": IrisColor.RED, "dourado": IrisColor.GOLD, "ciano": IrisColor.CYAN,
              "rosa": "rosa", "laranja": "laranja", "ambar": "ambar", "turquesa": "turquesa", "lilas": "lilas",
              "cinza": "cinza", "branco": "branco", "preto": "preto"}


def eye_colour(words: List[str]):
    """The colour of an eye from the words of a command: a name, "#rrggbb" or "r,g,b" (which may come in
    pieces); None when it is none. A colour of its own is kept as "#rrggbb"."""
    from src.clothing.customization import parse_iris_colour
    text = "".join(words).lower()
    if not text:
        return None
    named = EYE_COLORS.get(text) or _english(IrisColor).get(text)
    if named is not None:
        return named
    rgb = parse_iris_colour(text) if text.startswith("#") or "," in text else None
    return "#%02x%02x%02x" % rgb if rgb is not None else None


def free_colour(words: List[str]) -> Optional[Tuple[int, int, int]]:
    """A colour written as "#rrggbb" or "r,g,b" (which may come in pieces), or None."""
    from src.clothing.customization import parse_makeup_colour
    text = "".join(words).lower()
    return parse_makeup_colour(text) if text.startswith("#") or "," in text else None


def reset_eye_tones(custom, *eyes: str) -> None:
    """A colour newly chosen is the one shown: the adjustments that moved the old one go back to 0."""
    custom.body_adjust = {name: value for name, value in (custom.body_adjust or {}).items()
                          if not name.startswith(tuple(f"{eye}_" for eye in eyes))
                          or name.split("_")[-1] not in ("matiz", "saturacao", "brilho")}
EYE_STYLES = {"anime": EyeStyle.ANIME, "piscando": EyeStyle.ANIME_WINK, "classico": EyeStyle.CLASSIC,
              "sem": EyeStyle.BLANK, "wink": EyeStyle.ANIME_WINK, "classic": EyeStyle.CLASSIC, "blank": EyeStyle.BLANK}
MOUTHS = {"anime": MouthStyle.ANIME_ORIGINAL, "sorriso": MouthStyle.SMILE, "aberta": MouthStyle.OPEN,
          "piscando": MouthStyle.WINK_SMILE, "neutra": MouthStyle.NEUTRAL, "classica": MouthStyle.CLASSIC,
          "gato": MouthStyle.CAT, ":3": MouthStyle.CAT, "beicinho": MouthStyle.POUT, "vampiro": MouthStyle.VAMPIRE, "sem": MouthStyle.BLANK,
          "anime_original": MouthStyle.ANIME_ORIGINAL, "smile": MouthStyle.SMILE, "open": MouthStyle.OPEN,
          "wink_smile": MouthStyle.WINK_SMILE, "neutral": MouthStyle.NEUTRAL, "classic": MouthStyle.CLASSIC,
          "cat": MouthStyle.CAT, "pout": MouthStyle.POUT, "blank": MouthStyle.BLANK}
HAIR_COLORS = {"castanho": HairColor.BRUNETTE, "loiro": HairColor.BLONDE, "preto": HairColor.BLACK, "rosa": HairColor.PINK,
               "prata": HairColor.SILVER, "ruivo": HairColor.AUBURN, "ciano": HairColor.CYAN}
SKIN_TONES = {"palida": "pale", "clara": "fair", "bronzeada": "tan", "morena": "dark", "negra": "ebony"}
HEADS = {"arredondada": HeadType.ROUNDED, "quadrada": HeadType.BLOCKY, "rounded": HeadType.ROUNDED, "blocky": HeadType.BLOCKY}
BODIES = {"feminino": BodyType.FEMALE, "masculino": BodyType.MALE, "female": BodyType.FEMALE, "male": BodyType.MALE}
EYEBROWS = {"padrao": EyebrowStyle.STANDARD, "grossa": EyebrowStyle.THICK, "decidida": EyebrowStyle.DETERMINED,
            "sem": EyebrowStyle.NONE}
NONE_WORDS = ("none", "nenhum", "sem", "tirar", "0")


def _english(enum) -> Dict[str, Any]:
    return {member.value: member for member in enum if member.value not in ("custom", "none")}


def catalog_names() -> Dict[str, int]:
    """Nome amigável -> id de cada item baixado em assets/models/clothing, mais os atalhos fixos."""
    names: Dict[str, int] = {}
    for path in sorted(glob.glob(os.path.join(CLOTHING_DIR, "*.rbxm"))):
        match = re.search(r"_(\d{6,})\.rbxm$", os.path.basename(path))
        if match:
            name = re.sub(r"[^a-z0-9]+", "_", os.path.basename(path)[:match.start()].lower()).strip("_")
            if name:
                names.setdefault(name, int(match.group(1)))
    names.update(OUTFIT_PRESETS)
    names.update({k: v for k, v in BOTTOM_PRESETS.items() if not k.isdigit()})
    names["katana"] = KATANA_ID
    return names


def item_name(asset_id) -> str:
    """Nome do item a partir dos arquivos baixados, ou o próprio id."""
    if asset_id in (None, "none", 0, "0"):
        return "nenhum"
    for name, made in HANDMADE_HAIR.items():
        if str(asset_id) == made:
            return f"{name.capitalize()} ({asset_id})"
    for path in glob.glob(os.path.join(CLOTHING_DIR, f"*{asset_id}.rbxm")):
        base = os.path.basename(path)
        return f"{base[:-len(f'_{asset_id}.rbxm')].replace('_', ' ').strip()} ({asset_id})"
    return str(asset_id)


def _parse_distance(text: str, current: float) -> float:
    """Distância em metros: '2cm', '-1cm', '0.02' (absoluta) ou '+2cm' (relativa ao valor atual)."""
    raw = text.lower().strip()
    relative = raw.startswith("+")
    if raw.endswith("cm"):
        value = float(raw[:-2]) / 100.0
    elif raw.endswith("mm"):
        value = float(raw[:-2]) / 1000.0
    elif raw.endswith("m"):
        value = float(raw[:-1])
    else:
        value = float(raw)
        value = value / 100.0 if abs(value) > 0.5 else value
    return current + value if relative else value


def _parse_scale(text: str, current: float) -> float:
    """Fator de escala: '1.1', '110%', '+0.05' ou '+10%' (relativos); limitado a 0.2x..3x."""
    raw = text.lower().strip()
    if raw.endswith("%"):
        value = float(raw[:-1]) / 100.0
        value = current + value if raw.startswith(("+", "-")) else value
    elif raw.startswith(("+", "-")):
        value = current + float(raw)
    else:
        value = float(raw)
    return max(0.2, min(3.0, value))


@dataclass
class Command:
    """Um comando: ``names[0]`` é o nome principal, os demais são apelidos aceitos."""
    names: Tuple[str, ...]
    usage: str
    summary: str
    run: Callable[["SkinCommandHandler", List[str]], Result]
    options: Any = field(default_factory=list)  # lista, dicionário (subníveis) ou função que devolve a lista
    group: str = ""


class SkinCommandHandler:
    """Executa os comandos do chat sobre um CharacterModel."""

    def __init__(self, character_model: Optional[CharacterModel] = None,
                 turntable_state: Optional[Dict[str, Any]] = None) -> None:
        self.character_model = character_model
        self.turntable_state = turntable_state
        self.chat_console = None
        self.editor_requested: bool = False  # /skin interface: the main loop opens the editor
        self.save_path: Optional[str] = None  # where /skin salvar writes (the default file when None)
        self.is_importing: bool = False
        self.import_status: str = ""
        self.import_asset_id: Optional[Any] = None
        self._pending_main_thread_callbacks: List[Callable[[], None]] = []
        self._callback_lock = threading.Lock()
        self._run_async = True

    # ------------------------------------------------------------------ estado e fila
    @property
    def busy_status(self) -> str:
        """Texto do aviso de carregamento, ou "" quando nada roda em segundo plano."""
        if self.is_importing:
            return self.import_status or f"Importando #{self.import_asset_id}..."
        model = self.character_model
        if model is not None and getattr(model, "is_loading", False):
            return model.loading_status or "Atualizando personagem..."
        return ""

    def process_pending_callbacks(self) -> None:
        """Roda na thread principal (OpenGL) o que as threads de importação agendaram."""
        if self.character_model is not None and hasattr(self.character_model, "poll"):
            self.character_model.poll()  # troca pelo personagem montado em segundo plano
        with self._callback_lock:
            callbacks = list(self._pending_main_thread_callbacks)
            self._pending_main_thread_callbacks.clear()
        for callback in callbacks:
            try:
                callback()
            except Exception as exc:
                print(f"[Comandos] Erro ao processar callback na thread principal: {exc}")

    # ------------------------------------------------------------------ execução
    def execute(self, cmd_line: str, run_async: bool = True) -> Result:
        """Executa uma linha do chat. Devolve (sucesso, mensagem, cor)."""
        words = cmd_line.strip().lstrip("/").split()
        if not words:
            return False, "", (255, 255, 255)
        root = find_command(ROOT_COMMANDS, words[0])
        if root is None:
            return False, f"[Erro] Comando desconhecido: /{words[0]}. Use /ajuda.", RED
        self._run_async = run_async
        return root.run(self, words[1:])

    @property
    def model(self) -> Optional[CharacterModel]:
        return self.character_model

    def _need_model(self) -> Optional[Result]:
        return None if self.character_model is not None else (False, "[Skin] Personagem não disponível.", RED)

    def _change(self, apply: Callable[[AvatarCustomization], None], face: bool = False) -> None:
        """Aplica uma mudança de aparência. ``face``: a mudança é só no desenho do rosto, e a
        textura da cabeça é refeita no lugar (sem reconstruir o personagem) quando a geometria
        não muda com ela (o nariz 3D depende do estilo dos olhos)."""
        model = self.character_model
        if model is None:
            return
        nose = getattr(model.customization, "should_render_3d_nose", None)
        apply(model.customization)
        if face and nose == getattr(model.customization, "should_render_3d_nose", None) \
                and getattr(model, "refresh_face", lambda: False)():
            return
        model.reload()

    # ------------------------------------------------------------------ /skin
    def skin(self, args: List[str]) -> Result:
        if not args:
            return True, "Uso: /skin <comando> ... — /ajuda mostra a lista.", GOLD
        command = find_command(SKIN_COMMANDS, args[0])
        if command is None:
            return False, f"[Erro] /skin {args[0]} não existe. Use /ajuda.", RED
        return command.run(self, args[1:])

    def help(self, args: List[str]) -> Result:
        if args:
            name = args[1] if args[0].lower() == "skin" and len(args) > 1 else args[0]
            command = find_command(SKIN_COMMANDS, name) or find_command(ROOT_COMMANDS, name)
            if command is None:
                return False, f"[Ajuda] Comando '{name}' não existe.", RED
            aliases = f" (também: {', '.join(command.names[1:])})" if len(command.names) > 1 else ""
            return True, f"[Ajuda] {command.usage} — {command.summary}{aliases}", GOLD
        lines = []
        for group in ("Aparência", "Roupas", "Personagem"):
            items = [c for c in SKIN_COMMANDS if c.group == group]
            lines.append(f"{group}: " + " | ".join(f"/skin {c.names[0]}" for c in items))
        lines.append("Visualizador: /girar | Detalhes de um comando: /ajuda <comando>")
        return True, "\n".join(lines), GOLD

    def spin(self, args: List[str]) -> Result:
        if self.turntable_state is None:
            return False, "[Girar] Só funciona no visualizador (--char).", RED
        value = args[0].lower() if args else ""
        if value in ("on", "ligar", "sim"):
            self.turntable_state["active"] = True
        elif value in ("off", "desligar", "nao", "não"):
            self.turntable_state["active"] = False
        else:
            self.turntable_state["active"] = not self.turntable_state["active"]
        return True, f"[Girar] Rotação automática {'ligada' if self.turntable_state['active'] else 'desligada'}.", CYAN

    # ------------------------------------------------------------------ aparência
    def body(self, args: List[str]) -> Result:
        body = BODIES.get(args[0].lower()) if args else None
        if body is None:
            return False, "Uso: /skin corpo <feminino|masculino>", GOLD
        self._change(lambda c: setattr(c, "body_type", body))
        return True, f"[Skin] Corpo {'feminino' if body == BodyType.FEMALE else 'masculino'}.", GREEN

    def race(self, args: List[str]) -> Result:
        """/skin raca <nome>: um corpo pronto de raça, sobre o corpo feminino ou masculino em uso."""
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing import races
        value = args[0].lower() if args else ""
        if value not in races.RACES:
            return False, f"Uso: /skin raca <{'|'.join(races.RACES)}>", GOLD
        self._change(lambda c: races.apply(c, value))
        return True, f"[Skin] Raça: {races.RACES[value].label}.", GREEN

    def tone(self, args: List[str]) -> Result:
        value = args[0].lower() if args else ""
        tone = SKIN_TONES.get(value, value)
        own = free_colour(args)
        if own is not None:  # a tone of its own
            self._change(lambda c: setattr(c, "skin_color_rgb", tuple(round((v + 0.25) / 255.0, 5) for v in own)))  # read back cut to whole numbers
            return True, "[Skin] Tom de pele: #%02x%02x%02x." % own, GREEN
        if tone not in SKIN_PRESETS:
            return False, f"Uso: /skin pele <{'|'.join(SKIN_TONES)}|#rrggbb|r,g,b>", GOLD
        self._change(lambda c: setattr(c, "skin_color_rgb", SKIN_PRESETS[tone]))
        return True, f"[Skin] Tom de pele: {value}.", GREEN

    def eyes(self, args: List[str]) -> Result:
        from src.clothing.eye_shapes import SHAPE_NAMES
        value = args[0].lower() if args else ""
        if value in ("formato", "forma") and len(args) > 1:
            value = args[1].lower()
        if value in SHAPE_NAMES and value not in EYE_STYLES:
            def shape(c):
                c.eye_shape = value
                if c.resolved_eye_style in ("classic", "blank"):
                    c.eye_style = EyeStyle.ANIME  # os formatos são do olho anime
            self._change(shape, face=True)
            return True, f"[Skin] Olhos: formato {value.replace('_', ' ')}.", GREEN
        if value in EYE_STYLES:
            self._change(lambda c: setattr(c, "eye_style", EYE_STYLES[value]), face=True)
            return True, f"[Skin] Olhos: estilo {value}.", GREEN
        if value in ("cor", "color") and len(args) > 1:
            args = args[1:]
        color = eye_colour(args)
        value = "".join(args).lower()
        if color is None:
            return False, (f"Uso: /skin olhos <cor: {', '.join(EYE_COLORS)}, #rrggbb ou r,g,b | estilo: anime, piscando, classico, sem | "
                           f"formato: {', '.join(SHAPE_NAMES)}>"), GOLD

        def apply(c):
            c.iris_color = color
            c.iris_color_other = None  # os dois olhos da mesma cor
            reset_eye_tones(c, "olhos", "olho_direito", "olho_esquerdo")
            if c.resolved_eye_style in ("classic", "blank"):
                c.eye_style = EyeStyle.ANIME  # a cor só aparece nos olhos anime
        self._change(apply, face=True)
        return True, f"[Skin] Olhos: cor {value}.", GREEN

    def eye(self, args: List[str]) -> Result:
        """/skin olho <direito|esquerdo> <cor>: a cor de um olho só (olhos de cores diferentes)."""
        missing = self._need_model()
        if missing:
            return missing
        side = args[0].lower() if args else ""
        color = eye_colour(args[1:])
        if side not in ("direito", "esquerdo") or color is None:
            return False, f"[Erro] Uso: /skin olho <direito|esquerdo> <{'|'.join(EYE_COLORS)}|#rrggbb|r,g,b>", RED

        def apply(c):
            base = c.iris_color if c.iris_color is not None else "#%02x%02x%02x" % c._iris_base
            if c.iris_color_other is None:
                c.iris_color_other = base
            c.iris_color = base
            setattr(c, "iris_color" if side == "direito" else "iris_color_other", color)
            reset_eye_tones(c, f"olho_{side}")
            if c.resolved_eye_style in ("classic", "blank"):
                c.eye_style = EyeStyle.ANIME
        self._change(apply, face=True)
        return True, f"[Skin] Olho {side}: {''.join(args[1:]).lower()}.", GREEN

    def makeup(self, args: List[str]) -> Result:
        """/skin maquiagem <batom|sombra|blush> <cor|#rrggbb|sem> | contorno <suave|marcado|sem> | sardas <sim|nao> | sem"""
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing.customization import CONTOURS, MAKEUP_COLORS, FaceDetail, parse_makeup_colour
        usage = (f"Uso: /skin maquiagem <batom|sombra|blush> <{'|'.join(MAKEUP_COLORS)}|#rrggbb|sem> | "
                 f"contorno <{'|'.join(CONTOURS)}|sem> | sardas <sim|nao> | sem")
        what = args[0].lower() if args else ""
        value = args[1].lower() if len(args) > 1 else ""
        details = {(False, False): FaceDetail.NONE, (True, False): FaceDetail.BLUSH, (False, True): FaceDetail.FRECKLES,
                   (True, True): FaceDetail.BLUSH_AND_FRECKLES}
        if what == "sem":
            def clear(c):
                c.makeup, c.face_detail = {}, FaceDetail.NONE
            self._change(clear, face=True)
            return True, "[Maquiagem] Sem maquiagem.", GREEN
        colour = "".join(args[1:]).lower() if len(args) > 1 else ""  # "200, 40, 55" comes in pieces
        painted = parse_makeup_colour(colour) is not None
        if what in ("batom", "sombra", "blush") and (painted or value in NONE_WORDS):
            def paint(c):
                worn = dict(c.makeup or {})
                worn.pop(what, None)
                if painted:
                    worn[what] = colour
                c.makeup = worn
                if what == "blush":  # the drawn blush takes the place of the old layer of the same name
                    c.face_detail = FaceDetail.FRECKLES if "freckles" in c.resolved_face_detail else FaceDetail.NONE
            self._change(paint, face=True)
            return True, f"[Maquiagem] {what.capitalize()}: {colour if painted else 'sem'}.", GREEN
        if what == "contorno" and (value in CONTOURS or value in NONE_WORDS):
            def shade(c):
                worn = dict(c.makeup or {})
                worn.pop("contorno", None)
                if value in CONTOURS:
                    worn["contorno"] = value
                c.makeup = worn
            self._change(shade, face=True)
            return True, f"[Maquiagem] Contorno: {value if value in CONTOURS else 'sem'}.", GREEN
        if what in ("blush", "sardas") and value in ("sim", "nao", "não", "on", "off", "alternar"):
            def mark(c):
                now = c.resolved_face_detail
                blush, freckles = "blush" in now, "freckles" in now
                if what == "blush":
                    blush = not blush if value == "alternar" else value in ("sim", "on")
                else:
                    freckles = not freckles if value == "alternar" else value in ("sim", "on")
                c.face_detail = details[(blush, freckles)]
            self._change(mark, face=True)
            return True, f"[Maquiagem] {what.capitalize()}: {value}.", GREEN
        return False, f"[Erro] {usage}", RED

    def mouth(self, args: List[str]) -> Result:
        value = args[0].lower() if args else ""
        if value not in MOUTHS:
            return False, "Uso: /skin boca <anime|sorriso|aberta|piscando|neutra|classica|gato|beicinho|vampiro|sem>", GOLD
        self._change(lambda c: setattr(c, "mouth_style", MOUTHS[value]), face=True)
        return True, f"[Skin] Boca: {value}.", GREEN

    def head(self, args: List[str]) -> Result:
        head = HEADS.get(args[0].lower()) if args else None
        if head is None:
            return False, "Uso: /skin cabeca <arredondada|quadrada>", GOLD
        self._change(lambda c: setattr(c, "head_type", head))
        return True, f"[Skin] Cabeça {args[0].lower()}.", GREEN

    def hair(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        m = self.character_model
        if not args:
            return True, (f"[Cabelo] {item_name(getattr(m, 'hair_id', None))} | posição X {m.hair_offset_x*100:+.1f} "
                          f"Y {m.hair_offset_y*100:+.1f} Z {m.hair_offset_z*100:+.1f} cm | escala "
                          f"{m.hair_scale_x:.2f} {m.hair_scale_y:.2f} {m.hair_scale_z:.2f}\n"
                          "Uso: /skin cabelo <id|cor|careca|raspado|padrao|nudred> | posicao <x|y|z> <cm> | escala [x|y|z] <fator> | reset"), GOLD
        value, rest = args[0].lower(), args[1:]
        if value in ("posicao", "pos", "position"):
            return self._hair_position(rest)
        if value in ("escala", "tamanho", "scale"):
            return self._hair_scale(rest)
        if value == "reset":
            m.reset_hair_adjustments()
            return True, "[Cabelo] Posição e escala restauradas.", GREEN
        if value in HANDMADE_HAIR or value in HANDMADE_HAIR.values():  # a hair made by hand: nothing to download
            name = value if value in HANDMADE_HAIR else next(k for k, v in HANDMADE_HAIR.items() if v == value)
            m.update_customization(hair_id=HANDMADE_HAIR[name])
            self._change(lambda c: setattr(c, "hair_style", HairStyle.ANIME_LONG))
            return True, f"[Cabelo] {name.capitalize()}.", GREEN
        if value.isdigit() or "roblox.com" in value:
            return self._wear([value, "cabelo"])
        if value in ("careca", "bald"):
            m.update_customization(hair_id="none")
            self._change(lambda c: setattr(c, "hair_style", HairStyle.BALD))
            return True, "[Cabelo] Careca.", GREEN
        if value in ("raspado", "buzz"):
            m.update_customization(hair_id="none")
            self._change(lambda c: setattr(c, "hair_style", HairStyle.BUZZ_CUT))
            return True, "[Cabelo] Raspado.", GREEN
        if value in ("padrao", "default"):
            m.update_customization(hair_id=str(DEFAULT_HAIR_ID))
            self._change(lambda c: setattr(c, "hair_style", HairStyle.ANIME_LONG))
            return True, "[Cabelo] Cabelo padrão.", GREEN
        color = HAIR_COLORS.get(value) or _english(HairColor).get(value) or free_colour(args)  # or one of its own, kept as three numbers
        if color is None:
            return False, f"[Erro] Opção de cabelo '{value}' não existe. Cores: {', '.join(HAIR_COLORS)}.", RED

        def apply(c):
            c.hair_color = color
            if c.hair_style == HairStyle.BALD:
                m.update_customization(hair_id=str(DEFAULT_HAIR_ID))
                c.hair_style = HairStyle.ANIME_LONG
        self._change(apply)
        return True, f"[Cabelo] Cor {value}.", GREEN

    def _hair_position(self, args: List[str]) -> Result:
        m = self.character_model
        usage = "Uso: /skin cabelo posicao <x|y|z> <distância> | posicao <x> <y> <z> (ex.: +2cm, -1cm, 0)"
        try:
            if len(args) >= 2 and args[0].lower() in ("x", "y", "z"):
                axis = args[0].lower()
                m.set_hair_offset(**{axis: _parse_distance(args[1], getattr(m, f"hair_offset_{axis}"))})
            elif len(args) >= 3:
                m.set_hair_offset(x=_parse_distance(args[0], m.hair_offset_x), y=_parse_distance(args[1], m.hair_offset_y),
                                  z=_parse_distance(args[2], m.hair_offset_z))
            else:
                return False, usage, GOLD
        except ValueError:
            return False, usage, RED
        return True, (f"[Cabelo] Posição X {m.hair_offset_x*100:+.1f} Y {m.hair_offset_y*100:+.1f} "
                      f"Z {m.hair_offset_z*100:+.1f} cm."), GREEN

    def _hair_scale(self, args: List[str]) -> Result:
        m = self.character_model
        usage = "Uso: /skin cabelo escala <fator> | escala <x|y|z> <fator> (ex.: 1.1, 95%, +0.05)"
        try:
            if len(args) >= 2 and args[0].lower() in ("x", "y", "z"):
                axis = args[0].lower()
                m.set_hair_scale(**{axis: _parse_scale(args[1], getattr(m, f"hair_scale_{axis}"))})
            elif len(args) == 1:
                m.set_hair_scale(_parse_scale(args[0], m.hair_scale_x))
            else:
                return False, usage, GOLD
        except ValueError:
            return False, usage, RED
        return True, f"[Cabelo] Escala X {m.hair_scale_x:.2f} Y {m.hair_scale_y:.2f} Z {m.hair_scale_z:.2f}.", GREEN

    # ------------------------------------------------------------------ roupas
    def _slot(self, args: List[str], slot: str, label: str, presets: Dict[str, int]) -> Result:
        """/skin top|calca <nome|id|none>: veste ou tira a peça desse lugar."""
        missing = self._need_model()
        if missing:
            return missing
        if not args:
            return True, f"[{label}] atual: {item_name(getattr(self.character_model, slot))}", GOLD
        value = args[0].lower()
        if value in NONE_WORDS:
            setattr(self.character_model, slot, None)
            self.character_model.reload()
            return True, f"[{label}] Removido.", GREEN
        asset_id = presets.get(value) or catalog_names().get(value) or (int(value) if value.isdigit() else None)
        if asset_id is None:
            return False, f"[Erro] {label} '{value}' não encontrado. Use um nome da lista ou o id do Roblox.", RED
        self.character_model.update_customization(**{slot: asset_id})
        return self._worn(f"[{label}] {item_name(asset_id)}.", asset_id)

    def top(self, args: List[str]) -> Result:
        return self._slot(args, "top_id", "Top", OUTFIT_PRESETS)

    def bottom(self, args: List[str]) -> Result:
        return self._slot(args, "bottom_id", "Calça", BOTTOM_PRESETS)

    def jacket(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        m = self.character_model
        usage = "Uso: /skin jaqueta <id|none> | jaqueta folga <mm> | jaqueta puxar <mm>"
        if not args:
            return True, (f"[Jaqueta] atual: {item_name(m.outer_top_id)} | folga {m.outer_top_gap_mm:.0f} mm | "
                          f"puxar {m.outer_top_pull_mm:.0f} mm\n{usage}"), GOLD
        value = args[0].lower()
        if value in ("folga", "puxar", "gap", "pull"):
            try:
                mm = float(args[1].lower().removesuffix("mm"))
            except (IndexError, ValueError):
                return False, usage, GOLD
            if not 0 <= mm <= 50:
                return False, "[Erro] Use um valor entre 0 e 50 mm.", RED
            setattr(m, "outer_top_gap_mm" if value in ("folga", "gap") else "outer_top_pull_mm", mm)
            m.reload()
            return True, f"[Jaqueta] {'Folga até a camisa' if value in ('folga', 'gap') else 'Camisa puxada por baixo'}: {mm:.0f} mm.", GREEN
        if value in NONE_WORDS:
            m.outer_top_id = None
            m.reload()
            return True, "[Jaqueta] Removida.", GREEN
        asset_id = catalog_names().get(value) or (int(value) if value.isdigit() else None)
        if asset_id is None:
            return False, f"[Erro] Jaqueta '{value}' não encontrada. {usage}", RED
        m.update_customization(outer_top_id=asset_id)
        return self._worn(f"[Jaqueta] {item_name(asset_id)} por cima do top (a primeira vez leva alguns segundos).", asset_id)

    def hsr(self, args: List[str]) -> Result:
        """/skin hsr espelhar <sim|nao> | <esconder|mostrar|apagar> <pontos> | limpar: a pele sob a roupa."""
        missing = self._need_model()
        if missing:
            return missing
        model = self.character_model
        custom = model.customization
        usage = "Uso: /skin hsr espelhar <sim|nao> | <esconder|mostrar|apagar> <pontos> | limpar | desfazer | refazer"
        mirror = bool(getattr(custom, "hsr_mirror", False))
        hide, show = set(getattr(custom, "hsr_hide", ()) or ()), set(getattr(custom, "hsr_show", ()) or ())
        what = args[0].lower() if args else ""
        before = (mirror, tuple(sorted(hide)), tuple(sorted(show)))
        undone, redone = self.hsr_history
        if what in ("desfazer", "undo", "refazer", "redo"):
            back = what in ("desfazer", "undo")
            source, target = (undone, redone) if back else (redone, undone)
            if not source:
                return False, f"[Pele] Nada para {'desfazer' if back else 'refazer'}.", GOLD
            target.append(before)
            custom.hsr_mirror, custom.hsr_hide, custom.hsr_show = source.pop()
            if not getattr(model, "refresh_skin", lambda: False)():
                model.reload()
            return True, f"[Pele] {'Desfeito' if back else 'Refeito'}.", GREEN
        if not what:
            return True, (f"[Pele] Espelhar: {'sim' if mirror else 'não'}; pintados para esconder: {len(hide)}, "
                          f"para mostrar: {len(show)}.\n{usage}"), GOLD
        if what in ("espelhar", "mirror") and len(args) > 1 and args[1].lower() in ("sim", "nao", "não", "on", "off", "alternar"):
            mirror = not mirror if args[1].lower() == "alternar" else args[1].lower() in ("sim", "on")
            feedback = f"[Pele] Espelhar os dois lados: {'sim' if mirror else 'não'}."
        elif what in ("limpar", "clear"):
            hide, show = set(), set()
            feedback = "[Pele] Pintura apagada."
        elif what in ("esconder", "mostrar", "apagar") and len(args) > 1:
            try:
                points = {int(v) for v in ",".join(args[1:]).replace(";", ",").split(",") if v.strip()}
            except ValueError:
                return False, f"[Erro] {usage}", RED
            if not points or min(points) < 0:
                return False, f"[Erro] {usage}", RED
            hide, show = hide - points, show - points
            if what == "esconder":
                hide |= points
            elif what == "mostrar":
                show |= points
            feedback = f"[Pele] {len(points)} ponto(s): {what}."
        else:
            return False, f"[Erro] {usage}", RED
        after = (mirror, tuple(sorted(hide)), tuple(sorted(show)))
        if after != before:  # what was there can be had back (/skin hsr desfazer)
            undone.append(before)
            del undone[:-HSR_HISTORY], redone[:]
        custom.hsr_mirror, custom.hsr_hide, custom.hsr_show = after
        if not getattr(model, "refresh_skin", lambda: False)():
            model.reload()
        return True, feedback, GREEN

    @property
    def hsr_history(self):
        """(o que há para desfazer, o que há para refazer) nas correções da pele sob a roupa:
        duas pilhas de (espelhar, pontos escondidos, pontos mostrados), desta sessão."""
        if not hasattr(self, "_hsr_history"):
            self._hsr_history = ([], [])
        return self._hsr_history

    def extra(self, args: List[str]) -> Result:
        """/skin extra <nome|id|none>: veste (ou tira) uma peça a mais, junto com as outras."""
        missing = self._need_model()
        if missing:
            return missing
        model = self.character_model
        worn = [str(i) for i in getattr(model, "extra_ids", [])]
        if not args:
            return True, (f"[Extra] vestidas: {', '.join(item_name(i) for i in worn) or 'nenhuma'}\n"
                          "Uso: /skin extra <nome|id> (veste ou tira) | none (tira todas)"), GOLD
        value = args[0].lower()
        if value in NONE_WORDS:
            model.extra_ids = []
            model.reload()
            return True, "[Extra] Peças extras removidas.", GREEN
        asset_id = catalog_names().get(value) or (int(value) if value.isdigit() else None)
        if asset_id is None:
            return False, f"[Erro] Peça '{value}' não encontrada. Use um nome da lista ou o id do Roblox.", RED
        if str(asset_id) in worn:
            model.extra_ids = [i for i in model.extra_ids if str(i) != str(asset_id)]
            model.reload()
            return True, f"[Extra] {item_name(asset_id)} removida.", GREEN
        model.extra_ids = list(getattr(model, "extra_ids", [])) + [asset_id]
        model.reload()
        return self._worn(f"[Extra] {item_name(asset_id)} vestida junto com as outras.", asset_id)

    def shoes(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        usage = "Uso: /skin sapato <id do pacote | id_esquerdo,id_direito | none>"
        if not args:
            return True, f"[Sapato] atual: {self.character_model.shoes_id or 'nenhum'}\n{usage}", GOLD
        value = args[0].lower()
        if value in NONE_WORDS:
            self.character_model.shoes_id = None
            self.character_model.reload()
            return True, "[Sapato] Removido.", GREEN
        ids = [i for i in value.split(",") if i]
        if not ids or not all(i.isdigit() for i in ids):
            return False, f"[Erro] Id de calçado inválido: '{value}'. {usage}", RED
        self.character_model.update_customization(shoes_id=",".join(ids))
        return True, f"[Sapato] {','.join(ids)} (a primeira vez leva alguns segundos).", GREEN

    def tool(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        value = args[0].lower() if args else "katana"
        if value in NONE_WORDS:
            self.character_model.update_customization(tool_id=0)
            return True, "[Arma] Removida.", GREEN
        tool_id = KATANA_ID if value in ("katana", "espada", "sword") else (int(value) if value.isdigit() else None)
        if tool_id is None:
            return False, "Uso: /skin arma <katana|id|none>", GOLD
        self.character_model.update_customization(tool_id=tool_id)
        return True, f"[Arma] {item_name(tool_id)}.", GREEN

    def remove(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        slots = {"top": "top", "calca": "bottom", "jaqueta": "jacket", "sapato": "shoes", "arma": "tool", "cabelo": "hair"}
        value = args[0].lower() if args else ""
        if value == "tudo":
            m = self.character_model
            m.top_id = m.bottom_id = m.outer_top_id = m.shoes_id = None
            m.extra_ids = []
            m.update_customization(tool_id=0)
            m.reload()
            return True, "[Tirar] Roupas, sapatos e arma removidos (o cabelo fica).", GREEN
        target = find_command(SKIN_COMMANDS, value) if value else None
        if value not in slots and (target is None or target.names[0] not in slots):
            return False, f"Uso: /skin tirar <{'|'.join(slots)}|tudo>", GOLD
        name = slots.get(value) or slots[target.names[0]]
        if name == "hair":
            return self.hair(["careca"])
        return getattr(self, name)(["none"])

    def outfit(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        m = self.character_model
        c = m.customization
        value = lambda option: getattr(option, "value", "padrão")
        lines = [f"Corpo {'feminino' if c.body_type == BodyType.FEMALE else 'masculino'} | olhos {value(c.iris_color)} | "
                 f"boca {value(c.mouth_style)} | cabelo {value(c.hair_color)}",
                 f"Top: {item_name(m.top_id)}", f"Calça: {item_name(m.bottom_id)}", f"Jaqueta: {item_name(m.outer_top_id)}",
                 f"Sapato: {m.shoes_id or 'nenhum'}", f"Cabelo: {item_name(getattr(m, 'hair_id', None))}",
                 f"Arma: {item_name(getattr(m, 'tool_id', None))}"]
        return True, "[Roupas]\n" + "\n".join(lines), GOLD

    def wear(self, args: List[str]) -> Result:
        """/skin vestir <id|link|nome> [top|calca|jaqueta|sapato|cabelo|arma] [refazer]"""
        missing = self._need_model()
        if missing:
            return missing
        if not args:
            return True, ("Uso: /skin vestir <id ou link do Roblox | nome> [top|calca|jaqueta|sapato|cabelo|arma] [refazer]\n"
                          "O tipo da peça vem do próprio Roblox; o segundo argumento só força quando ele erra."), GOLD
        if self._run_async and getattr(self.character_model, "create_mesh", False):
            if self.is_importing:
                return False, "[Vestir] Já existe uma importação em andamento; aguarde terminar.", GOLD
            target = next((a for a in args if a.isdigit()), args[0])
            self.is_importing = True
            self.import_asset_id = target
            self.import_status = f"Importando {target}..."

            def worker():
                try:
                    result = self._wear(args)
                except Exception as exc:
                    result = (False, f"[Vestir] Erro: {exc}", RED)

                def done():
                    self.is_importing = False
                    self.import_status = ""
                    self.import_asset_id = None
                    if self.chat_console:
                        self.chat_console.add_message(result[1], result[2])
                with self._callback_lock:
                    self._pending_main_thread_callbacks.append(done)

            threading.Thread(target=worker, daemon=True, name="RobloxImport").start()
            return True, "[Vestir] Importando em segundo plano; a interface continua liberada.", CYAN
        return self._wear(args)

    def _wear(self, args: List[str]) -> Result:
        """Baixa (se preciso), encaixa e veste um item do Roblox no lugar certo."""
        model = self.character_model
        kinds = {"top": "top", "camisa": "top", "calca": "bottom", "saia": "bottom", "shorts": "bottom",
                 "jaqueta": "jacket", "casaco": "jacket", "sapato": "shoes", "cabelo": "hair", "arma": "tool"}
        kind, redo, words = None, False, []
        for arg in args:
            word = arg.lower()
            if word in kinds:
                kind = kinds[word]
            elif word in ("refazer", "force"):
                redo = True
            else:
                words.append(arg)
        target = " ".join(words).strip()
        digits = re.search(r"(\d{4,})", target)
        if digits:
            asset_id = int(digits.group(1))
        elif target.lower() in catalog_names():
            asset_id = catalog_names()[target.lower()]
            if kind is None and target.lower() in BOTTOM_PRESETS:
                kind = "bottom"
        else:
            return False, f"[Vestir] Item '{target}' inválido: use o id, o link do catálogo ou um nome da lista.", RED
        if asset_id == KATANA_ID and kind is None:
            kind = "tool"

        from src.clothing.wear_engine import BOTTOM_ASSET_TYPES, TOP_ASSET_TYPES, RobloxWearEngine
        engine = RobloxWearEngine(body_type=model.body)
        try:
            meta = engine.fetch_asset(asset_id)
        except Exception as exc:
            return False, f"[Vestir] Falha ao baixar o item {asset_id} do Roblox: {exc}", RED
        name = meta.get("name", f"asset_{asset_id}").replace("_", " ")
        type_id = meta.get("type_id", 65)
        lower = name.lower()
        clothing_types = (64, 65, 66, 67, 68, 69, 72)
        if kind is None:
            if type_id == 41 or meta.get("is_hair") or any(k in lower for k in ("hair", "cabelo", "wig", "ponytail", "pigtails", "braids")):
                kind = "hair"
            elif type_id == 19 or (type_id not in clothing_types and any(k in lower for k in ("katana", "sword", "blade", "gear"))):
                kind = "tool"
            elif type_id in (70, 71):
                kind = "shoes"
            elif meta.get("is_top", type_id in TOP_ASSET_TYPES or type_id not in BOTTOM_ASSET_TYPES):
                kind = "top"
            else:
                kind = "bottom"
        try:
            if kind == "hair":
                engine.equip_hair(asset_id)
                model.update_customization(hair_id=asset_id)
                return True, f"[Vestir] Cabelo 3D '{name}' ({asset_id}) equipado.", GREEN
            if kind == "tool":
                engine.equip_tool(asset_id)
                model.update_customization(tool_id=asset_id)
                return True, f"[Vestir] Arma '{name}' ({asset_id}) equipada.", GREEN
            if kind == "shoes":
                model.update_customization(shoes_id=str(asset_id))
                return True, f"[Vestir] Calçado '{name}' ({asset_id}). Para o par, use /skin sapato <esquerdo,direito>.", GREEN
            if redo or not os.path.exists(model.fitted_path(asset_id)):
                engine.wear(asset_id, body_type=model.body)
        except Exception as exc:
            return False, f"[Vestir] Erro ao vestir {asset_id}: {exc}", RED
        slot = {"top": "top_id", "bottom": "bottom_id", "jacket": "outer_top_id"}[kind]
        model.update_customization(**{slot: asset_id})
        label = {"top": "Roupa de cima", "bottom": "Roupa de baixo", "jacket": "Jaqueta"}[kind]
        return self._worn(f"[Vestir] {label} '{name}' ({asset_id}) vestida.", asset_id)

    def _worn(self, message: str, asset_id) -> Result:
        """What is said when a garment is put on: with its known defect on this body, when it has one (it is
        worn all the same)."""
        from src.clothing.known_defects import defect_of
        defect = defect_of(asset_id, getattr(self.character_model, "body", ""))
        return (True, f"{message} Defeito conhecido neste corpo: {defect}.", GOLD) if defect else (True, message, GREEN)

    # ------------------------------------------------------------------ personagem inteiro
    def preset(self, args: List[str]) -> Result:
        value = args[0].lower() if args else ""
        preset = PRESETS.get(value)
        if preset is None:
            return False, f"Uso: /skin preset <{'|'.join(PRESETS)}>", GOLD
        self._apply_look(**preset)
        return True, f"[Preset] {value}.", GREEN

    def save(self, args: Optional[List[str]] = None) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing import character_save
        try:
            path = character_save.save(self.character_model, self.save_path or character_save.SAVE_PATH)
        except OSError as exc:
            return False, f"[Skin] Não foi possível salvar o personagem: {exc}", RED
        return True, f"[Skin] Personagem salvo em {os.path.relpath(path, PROJECT_ROOT)}.", GREEN

    def load(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing import character_save
        data = character_save.load(self.save_path or character_save.SAVE_PATH)
        if data is None:
            return False, "[Skin] Não há personagem salvo.", RED
        character_save.apply(self.character_model, data)
        return True, "[Skin] Personagem salvo carregado.", GREEN

    def adjust(self, args: List[str]) -> Result:
        """/skin ajuste <nome> <-100..100> | reset: proporções do corpo e do rosto."""
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing.body_shape import ADJUSTMENTS, DEFAULTS, GARMENTS, REDRAWS_FACE, REDRAWS_SHADOW
        model = self.character_model
        # The skin under a moved edge is cut again, unless the caller does that when it is done (a slider being dragged).
        recut = (lambda: None) if getattr(self, "defer_skin", False) else self.recut_skin
        custom = self.character_model.customization
        FACE = REDRAWS_FACE | (REDRAWS_SHADOW if getattr(custom, "nose_shadow", "legado") == "calculada" else set())
        current = dict(getattr(custom, "body_adjust", None) or {})
        usage = f"Uso: /skin ajuste <{'|'.join(ADJUSTMENTS)}> <-100 a 100> | reset"
        if not args:
            shown = ", ".join(f"{k} {round(v * 100):+d}" for k, v in current.items() if v) or "nenhum"
            return True, f"[Ajuste] {shown}\n{usage}", GOLD
        name = args[0].lower()
        if name == "reset":
            face = any(k in current for k in FACE)
            if face:
                self._change(lambda c: setattr(c, "body_adjust", {}), face=True)
            else:
                custom.body_adjust = {}
            if any(current.get(k) for k in GARMENTS):
                recut()
            return True, "[Ajuste] Proporções de volta ao padrão.", GREEN
        if name not in ADJUSTMENTS or len(args) < 2:
            return False, f"[Erro] {usage}", RED
        try:
            value = max(-100.0, min(100.0, float(args[1].replace("%", "").replace(",", "."))))
        except ValueError:
            return False, f"[Erro] Valor inválido: '{args[1]}'. {usage}", RED
        before = getattr(custom, "resolved_body_adjust", None) or current
        changed = round(value) != round(before.get(name, 0.0) * 100)
        current[name] = value / 100.0
        kept = {k for defaults in DEFAULTS.values() for k in defaults}  # a zero there is a choice, not the default
        adjusted = {k: v for k, v in current.items() if v or k in kept}
        if name in FACE and changed:
            self._change(lambda c: setattr(c, "body_adjust", adjusted), face=True)  # the face is drawn again
        else:
            custom.body_adjust = adjusted
            if name in GARMENTS and changed:
                recut()
        return True, f"[Ajuste] {ADJUSTMENTS[name]}: {round(value):+d}.", GREEN

    def ears(self, args: List[str]) -> Result:
        """/skin orelha <sem|modelo> | cor <auto|pele|cabelo|nome|#rrggbb>: as orelhas 3D e a cor delas."""
        missing = self._need_model()
        if missing:
            return missing
        value = args[0].lower() if args else ""
        if value in ("cor", "color"):
            from src.clothing import ears
            custom = self.character_model.customization
            wanted = args[1].lower() if len(args) > 1 else ""
            toggled = len(args) > 2 and args[2].lower() == "alternar"  # a check of the editor: again takes it off
            names = (ears.SKIN_COAT, ears.HAIR_COAT) + tuple(ears.EAR_COLORS)
            valid = wanted in names or (wanted.startswith("#") and len(wanted) == 7)
            if wanted in ("auto", "automatica", "automática") + NONE_WORDS or (toggled and getattr(custom, "ear_color", "") == wanted):
                custom.ear_color = ""
                return True, "[Orelhas] Cor: a do modelo.", GREEN
            if not valid:
                return False, f"[Erro] Uso: /skin orelha cor <auto|{'|'.join(names)}|#rrggbb>", RED
            custom.ear_color = wanted
            return True, f"[Orelhas] Cor: {wanted}.", GREEN
        value = "sem" if value in NONE_WORDS else value
        if value not in EAR_STYLE_NAMES:
            return False, f"[Erro] Uso: /skin orelha <{'|'.join(EAR_STYLE_NAMES)}>", RED
        custom = self.character_model.customization
        before = getattr(custom, "ear_style", "sem")
        custom.ear_style = value
        if (before == "sem") != (value == "sem"):
            self.character_model.reload()  # the ears are a mesh the model has or has not; between models they are moved in place
        return True, f"[Orelhas] {value.replace('_', ' ').capitalize()}.", GREEN

    def horns(self, args: List[str]) -> Result:
        """/skin chifre <sem|modelo> | cor <auto|nome|#rrggbb>: os chifres 3D e a cor deles."""
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing import horns
        custom = self.character_model.customization
        value = args[0].lower() if args else ""
        if value in ("cor", "color"):
            wanted = args[1].lower() if len(args) > 1 else ""
            if wanted in ("auto", "automatica", "automática") + NONE_WORDS:
                custom.horn_color = ""
                return True, "[Chifres] Cor: a do modelo.", GREEN
            if wanted not in horns.HORN_COLORS and not (wanted.startswith("#") and len(wanted) == 7):
                return False, f"[Erro] Uso: /skin chifre cor <auto|{'|'.join(horns.HORN_COLORS)}|#rrggbb>", RED
            custom.horn_color = wanted
            return True, f"[Chifres] Cor: {wanted}.", GREEN
        value = "sem" if value in NONE_WORDS else value
        if value not in horns.STYLE_NAMES:
            return False, f"[Erro] Uso: /skin chifre <{'|'.join(horns.STYLE_NAMES)}> | cor <auto|nome|#rrggbb>", RED
        before = getattr(custom, "horn_style", "sem")
        custom.horn_style = value
        if (before == "sem") != (value == "sem"):
            self.character_model.reload()  # the horns are a mesh the model has or has not; between models they are moved in place
        return True, f"[Chifres] {value.replace('_', ' ').capitalize()}.", GREEN

    def tail(self, args: List[str]) -> Result:
        """/skin cauda <sem|modelo> | cor <auto|pele|cabelo|nome|#rrggbb>: a cauda 3D e a cor dela."""
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing import ears, tails
        custom = self.character_model.customization
        value = args[0].lower() if args else ""
        if value in ("cor", "color"):
            wanted = args[1].lower() if len(args) > 1 else ""
            toggled = len(args) > 2 and args[2].lower() == "alternar"  # a check of the editor: again takes it off
            names = (ears.SKIN_COAT, ears.HAIR_COAT) + tuple(ears.EAR_COLORS)
            if wanted in ("auto", "automatica", "automática") + NONE_WORDS or (toggled and getattr(custom, "tail_color", "") == wanted):
                custom.tail_color = ""
                return True, "[Cauda] Cor: a do modelo.", GREEN
            if wanted not in names and not (wanted.startswith("#") and len(wanted) == 7):
                return False, f"[Erro] Uso: /skin cauda cor <auto|{'|'.join(names)}|#rrggbb>", RED
            custom.tail_color = wanted
            return True, f"[Cauda] Cor: {wanted}.", GREEN
        value = "sem" if value in NONE_WORDS else value
        if value not in tails.STYLE_NAMES:
            return False, f"[Erro] Uso: /skin cauda <{'|'.join(tails.STYLE_NAMES)}> | cor <auto|pele|cabelo|nome|#rrggbb>", RED
        before = getattr(custom, "tail_style", "sem")
        custom.tail_style = value
        if (before == "sem") != (value == "sem"):
            self.character_model.reload()  # the tail is a mesh the model has or has not; between models it is moved in place
        return True, f"[Cauda] {value.replace('_', ' ').capitalize()}.", GREEN

    def wings(self, args: List[str]) -> Result:
        """/skin asa <sem|modelo> | cor <auto|pele|cabelo|nome|#rrggbb>: as asas 3D e a cor delas."""
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing import ears, wings
        custom = self.character_model.customization
        value = args[0].lower() if args else ""
        if value in ("cor", "color"):
            wanted = args[1].lower() if len(args) > 1 else ""
            toggled = len(args) > 2 and args[2].lower() == "alternar"  # a check of the editor: again takes it off
            names = (ears.SKIN_COAT, ears.HAIR_COAT) + tuple(ears.EAR_COLORS)
            if wanted in ("auto", "automatica", "automática") + NONE_WORDS or (toggled and getattr(custom, "wing_color", "") == wanted):
                custom.wing_color = ""
                return True, "[Asas] Cor: a do modelo.", GREEN
            if wanted not in names and not (wanted.startswith("#") and len(wanted) == 7):
                return False, f"[Erro] Uso: /skin asa cor <auto|{'|'.join(names)}|#rrggbb>", RED
            custom.wing_color = wanted
            return True, f"[Asas] Cor: {wanted}.", GREEN
        value = "sem" if value in NONE_WORDS else value
        if value not in wings.STYLE_NAMES:
            return False, f"[Erro] Uso: /skin asa <{'|'.join(wings.STYLE_NAMES)}> | cor <auto|pele|cabelo|nome|#rrggbb>", RED
        before = getattr(custom, "wing_style", "sem")
        custom.wing_style = value
        if (before == "sem") != (value == "sem"):
            self.character_model.reload()  # the wings are a mesh the model has or has not; between models they are moved in place
        return True, f"[Asas] {value.replace('_', ' ').capitalize()}.", GREEN

    def underwear(self, args: List[str]) -> Result:
        """/skin intima <sem|cor|#rrggbb>: a roupa de baixo pintada na pele."""
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing import underwear
        custom = self.character_model.customization
        value = args[0].lower() if args else ""
        if value in ("alternar",):  # a check of the editor: on in the colour it had last, or off
            value = "sem" if underwear.colour_of(custom) is not None else (getattr(self, "_underwear_before", "") or underwear.DEFAULT)
        if value in NONE_WORDS + ("nao", "não"):
            if underwear.colour_of(custom) is not None:
                self._underwear_before = custom.underwear
            custom.underwear = "sem"
            return True, "[Skin] Sem roupa de baixo.", GREEN
        if value in ("sim", "on"):
            value = getattr(self, "_underwear_before", "") or underwear.DEFAULT
        if value not in underwear.COLORS and not (value.startswith("#") and len(value) == 7):
            return False, f"[Erro] Uso: /skin intima <sem|sim|{'|'.join(underwear.COLORS)}|#rrggbb>", RED
        custom.underwear = value
        return True, f"[Skin] Roupa de baixo: {value}.", GREEN

    def recut_skin(self) -> None:
        """Recorta de novo a pele sob as roupas (rápido), ou reconstrói o personagem se não der."""
        model = self.character_model
        if model is not None and not getattr(model, "refresh_skin", lambda: False)():
            model.reload()

    def nose(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        from src.clothing.customization import NOSE_SHADOWS
        from src.clothing.nose import BLOCKS, STYLE_NAMES
        value = args[0].lower() if args else ""
        custom = self.character_model.customization
        if value in ("sombra", "shadow"):
            kind = args[1].lower() if len(args) > 1 else ""
            if kind not in NOSE_SHADOWS:
                return False, f"[Erro] Uso: /skin nariz sombra <{'|'.join(NOSE_SHADOWS)}>", RED
            self._change(lambda c: setattr(c, "nose_shadow", kind), face=True)
            return True, f"[Nariz] Sombra {kind}.", GREEN
        if value in STYLE_NAMES:
            before = getattr(custom, "nose_style", "padrao")
            hidden = not custom.should_render_3d_nose
            custom.nose_style = value
            if hidden or (before != value and (before in BLOCKS or value in BLOCKS)):
                # No nose on the model yet, or an old block nose (a mesh of its own): rebuilt.
                self._change(lambda c: setattr(c, "has_3d_nose", True))
            elif before != value and getattr(custom, "nose_shadow", "legado") == "calculada":
                getattr(self.character_model, "refresh_face", lambda: False)()  # the shadow follows the nose
            return True, f"[Nariz] Formato {value.replace('_', ' ')}.", GREEN
        if value not in ("sim", "nao", "não", "on", "off"):
            return False, f"[Erro] Uso: /skin nariz <sim|nao|sombra legado|sombra calculada|{'|'.join(STYLE_NAMES)}>", RED
        shown = value in ("sim", "on")
        self._change(lambda c: setattr(c, "has_3d_nose", shown))
        return True, f"[Nariz] {'Com' if shown else 'Sem'} nariz.", GREEN

    def eyebrows(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        if not args or args[0].lower() not in EYEBROWS:
            return False, f"[Erro] Uso: /skin sobrancelha <{'|'.join(EYEBROWS)}>", RED
        self._change(lambda c: setattr(c, "eyebrow_style", EYEBROWS[args[0].lower()]), face=True)
        return True, f"[Sobrancelha] {args[0].lower()}.", GREEN

    def interface(self, args: List[str]) -> Result:
        missing = self._need_model()
        if missing:
            return missing
        self.editor_requested = True
        return True, "[Skin] Tela de criação de personagem aberta (Esc fecha).", GREEN

    def reset(self, args: List[str]) -> Result:
        self._apply_look(**PRESETS["padrao"])
        return True, "[Skin] Personagem de volta ao padrão (o corpo escolhido fica).", GREEN

    def _apply_look(self, top, tool=0, **look) -> None:
        if self.character_model is None:
            return
        body = self.character_model.customization.body_type
        self.character_model.update_customization(customization=AvatarCustomization(body_type=body, **look),
                                                  top_id=top, tool_id=tool)


PRESETS: Dict[str, Dict[str, Any]] = {
    "padrao": dict(top=OUTFIT_PRESETS["sweater"], head_type=HeadType.ROUNDED, mouth_style=MouthStyle.ANIME_ORIGINAL,
                   eye_style=EyeStyle.ANIME, iris_color=IrisColor.BLUE, hair_style=HairStyle.ANIME_LONG,
                   hair_color=HairColor.BRUNETTE, skin_color_rgb=SKIN_PRESETS["pale"]),
    "gato_loiro": dict(top=OUTFIT_PRESETS["sweater"], head_type=HeadType.ROUNDED, mouth_style=MouthStyle.CAT,
                       eye_style=EyeStyle.ANIME, iris_color=IrisColor.GREEN, hair_style=HairStyle.ANIME_LONG,
                       hair_color=HairColor.BLONDE, skin_color_rgb=SKIN_PRESETS["pale"]),
    "cavaleiro": dict(top=OUTFIT_PRESETS["boxy"], tool=KATANA_ID, head_type=HeadType.ROUNDED,
                      mouth_style=MouthStyle.ANIME_ORIGINAL, eye_style=EyeStyle.ANIME, iris_color=IrisColor.PURPLE,
                      hair_style=HairStyle.ANIME_LONG, hair_color=HairColor.SILVER, skin_color_rgb=SKIN_PRESETS["dark"]),
    "rosa": dict(top=OUTFIT_PRESETS["boxy"], head_type=HeadType.ROUNDED, mouth_style=MouthStyle.POUT,
                 eye_style=EyeStyle.ANIME, iris_color=IrisColor.RED, hair_style=HairStyle.ANIME_LONG,
                 hair_color=HairColor.PINK, skin_color_rgb=SKIN_PRESETS["fair"]),
    "classico": dict(top=OUTFIT_PRESETS["sweater"], head_type=HeadType.BLOCKY, mouth_style=MouthStyle.CLASSIC,
                     eye_style=EyeStyle.CLASSIC, iris_color=IrisColor.BLUE, hair_style=HairStyle.ANIME_LONG,
                     hair_color=HairColor.BRUNETTE, skin_color_rgb=SKIN_PRESETS["pale"]),
}

_DISTANCES = ["+1cm", "+2cm", "-1cm", "-2cm", "0"]
_SCALES = ["0.9", "0.95", "1.0", "1.05", "1.1"]


def _catalog_options() -> List[str]:
    return sorted(catalog_names())


SKIN_COMMANDS: List[Command] = [
    Command(("corpo", "body"), "/skin corpo <feminino|masculino>", "troca o corpo", SkinCommandHandler.body,
            ["feminino", "masculino"], "Aparência"),
    Command(("pele", "tone"), "/skin pele <tom|#rrggbb|r,g,b>", "tom de pele", SkinCommandHandler.tone, list(SKIN_TONES), "Aparência"),
    Command(("olhos", "eyes"), "/skin olhos <cor|#rrggbb|r,g,b|estilo|formato>", "cor, estilo ou formato dos olhos", SkinCommandHandler.eyes,
            list(EYE_COLORS) + ["anime", "piscando", "classico", "sem"] + list(EYE_SHAPE_NAMES), "Aparência"),
    Command(("olho", "eye"), "/skin olho <direito|esquerdo> <cor|#rrggbb|r,g,b>", "cor de um olho só", SkinCommandHandler.eye,
            {"direito": list(EYE_COLORS), "esquerdo": list(EYE_COLORS)}, "Aparência"),
    Command(("maquiagem", "makeup"), "/skin maquiagem <batom|sombra|blush> <cor|#rrggbb|sem> | contorno <suave|marcado|sem> | sardas <sim|nao> | sem",
            "batom, sombra, contorno, blush e sardas", SkinCommandHandler.makeup, ["batom", "sombra", "contorno", "blush", "sardas", "sem"],
            "Aparência"),
    Command(("boca", "mouth"), "/skin boca <estilo>", "estilo da boca", SkinCommandHandler.mouth,
            ["anime", "sorriso", "aberta", "piscando", "neutra", "classica", "gato", "beicinho", "vampiro", "sem"], "Aparência"),
    Command(("nariz", "nose"), "/skin nariz <sim|nao|formato|sombra legado|sombra calculada>", "nariz 3D, seu formato e o tipo de sombra (ajustes em /skin ajuste nariz_...)",
            SkinCommandHandler.nose, ["sim", "nao", "sombra"] + list(NOSE_STYLE_NAMES), "Aparência"),
    Command(("raca", "raça", "race"), "/skin raca <nome>", "corpo pronto de uma raça: pele, orelhas, olhos, nariz e proporções",
            SkinCommandHandler.race, lambda: list(__import__("src.clothing.races", fromlist=["RACES"]).RACES), "Aparência"),
    Command(("intima", "íntima", "roupa_intima", "underwear"), "/skin intima <sem|sim|cor|#rrggbb>",
            "roupa de baixo pintada na pele: cueca, ou calcinha e sutiã",
            SkinCommandHandler.underwear, lambda: ["sem", "sim"] + list(__import__("src.clothing.underwear", fromlist=["COLORS"]).COLORS),
            "Roupas"),
    Command(("asa", "asas", "wings"), "/skin asa <sem|modelo> | cor <auto|pele|cabelo|nome|#rrggbb>",
            "asas 3D e a cor delas (ajustes em /skin ajuste asa_...)",
            SkinCommandHandler.wings, lambda: list(__import__("src.clothing.wings", fromlist=["STYLE_NAMES"]).STYLE_NAMES) + ["cor"],
            "Aparência"),
    Command(("cauda", "rabo", "tail"), "/skin cauda <sem|modelo> | cor <auto|pele|cabelo|nome|#rrggbb>",
            "cauda 3D e a cor dela (ajustes em /skin ajuste cauda_...)",
            SkinCommandHandler.tail, lambda: list(__import__("src.clothing.tails", fromlist=["STYLE_NAMES"]).STYLE_NAMES) + ["cor"],
            "Aparência"),
    Command(("chifre", "chifres", "horns"), "/skin chifre <sem|modelo> | cor <auto|nome|#rrggbb>",
            "chifres 3D e a cor deles (ajustes em /skin ajuste chifre_...)",
            SkinCommandHandler.horns, lambda: list(__import__("src.clothing.horns", fromlist=["STYLE_NAMES"]).STYLE_NAMES) + ["cor"],
            "Aparência"),
    Command(("orelha", "orelhas", "ears"), "/skin orelha <sem|modelo> | cor <auto|pele|cabelo|nome|#rrggbb>",
            "orelhas 3D e a cor delas (ajustes em /skin ajuste orelha_...)",
            SkinCommandHandler.ears, list(EAR_STYLE_NAMES) + ["cor"], "Aparência"),
    Command(("sobrancelha", "eyebrows"), "/skin sobrancelha <padrao|grossa|decidida|sem>", "estilo das sobrancelhas",
            SkinCommandHandler.eyebrows, list(EYEBROWS), "Aparência"),
    Command(("ajuste", "adjust"), "/skin ajuste <nome> <-100 a 100> | reset", "proporções do corpo e do rosto",
            SkinCommandHandler.adjust, list(ADJUSTMENTS) + ["reset"], "Aparência"),
    Command(("cabeca", "head"), "/skin cabeca <arredondada|quadrada>", "formato da cabeça", SkinCommandHandler.head,
            ["arredondada", "quadrada"], "Aparência"),
    Command(("cabelo", "hair"), "/skin cabelo <id|cor|careca|raspado|padrao> | posicao ... | escala ... | reset",
            "troca, pinta ou ajusta o cabelo", SkinCommandHandler.hair,
            {**{k: [] for k in list(HAIR_COLORS) + ["careca", "raspado", "padrao", "reset"]},
             "posicao": {"x": _DISTANCES, "y": _DISTANCES, "z": _DISTANCES},
             "escala": {"x": _SCALES, "y": _SCALES, "z": _SCALES, **{s: [] for s in _SCALES}}}, "Aparência"),
    Command(("vestir", "wear", "import"), "/skin vestir <id|link|nome> [tipo] [refazer]",
            "veste qualquer item do Roblox no lugar certo", SkinCommandHandler.wear, _catalog_options, "Roupas"),
    Command(("top", "camisa"), "/skin top <nome|id|none>", "roupa de cima", SkinCommandHandler.top,
            lambda: sorted(set(OUTFIT_PRESETS) | {"none"}), "Roupas"),
    Command(("calca", "bottom", "pants"), "/skin calca <nome|id|none>", "roupa de baixo", SkinCommandHandler.bottom,
            lambda: sorted({k for k in BOTTOM_PRESETS if not k.isdigit()} | {"none"}), "Roupas"),
    Command(("jaqueta", "jacket"), "/skin jaqueta <id|none> | folga <mm> | puxar <mm>", "peça por cima do top",
            SkinCommandHandler.jacket, {"folga": ["3", "6", "10"], "puxar": ["10", "15", "20"], "none": []}, "Roupas"),
    Command(("hsr", "ocultar"), "/skin hsr espelhar <sim|nao> | <esconder|mostrar|apagar> <pontos> | limpar | desfazer | refazer",
            "pele escondida sob a roupa: espelhar os dois lados, ou corrigir à mão (o pincel da tela de criação)",
            SkinCommandHandler.hsr, {"espelhar": ["sim", "nao"], "esconder": [], "mostrar": [], "apagar": [], "limpar": [], "desfazer": [], "refazer": []}, "Roupas"),
    Command(("extra", "mais"), "/skin extra <nome|id|none>", "peça a mais, junto com as outras (polainas com saia)",
            SkinCommandHandler.extra, lambda: ["none"] + sorted(catalog_names()), "Roupas"),
    Command(("sapato", "shoes"), "/skin sapato <pacote|esquerdo,direito|none>", "calçado", SkinCommandHandler.shoes,
            ["none"], "Roupas"),
    Command(("arma", "tool"), "/skin arma <katana|id|none>", "item na mão", SkinCommandHandler.tool,
            ["katana", "none"], "Roupas"),
    Command(("tirar", "remove"), "/skin tirar <top|calca|jaqueta|sapato|cabelo|arma|tudo>", "remove uma peça",
            SkinCommandHandler.remove, ["top", "calca", "jaqueta", "sapato", "cabelo", "arma", "tudo"], "Roupas"),
    Command(("roupas", "outfit"), "/skin roupas", "mostra o que está vestido", SkinCommandHandler.outfit, [], "Roupas"),
    Command(("preset",), "/skin preset <nome>", "aparência pronta", SkinCommandHandler.preset, list(PRESETS), "Personagem"),
    Command(("reset",), "/skin reset", "volta ao padrão", SkinCommandHandler.reset, [], "Personagem"),
    Command(("interface", "editor", "criar"), "/skin interface", "abre a tela de criação de personagem",
            SkinCommandHandler.interface, [], "Personagem"),
    Command(("salvar", "save"), "/skin salvar", "grava o personagem para a próxima vez", SkinCommandHandler.save, [],
            "Personagem"),
    Command(("carregar", "load"), "/skin carregar", "volta ao personagem gravado", SkinCommandHandler.load, [],
            "Personagem"),
]

ROOT_COMMANDS: List[Command] = [
    Command(("skin",), "/skin <comando>", "muda o personagem", SkinCommandHandler.skin, None),
    Command(("ajuda", "help", "?"), "/ajuda [comando]", "lista os comandos", SkinCommandHandler.help, None),
    Command(("girar", "spin"), "/girar [on|off]", "rotação automática no visualizador", SkinCommandHandler.spin, ["on", "off"]),
]


def find_command(commands: List[Command], name: str) -> Optional[Command]:
    name = name.lower()
    return next((c for c in commands if name in c.names), None)


def _tree(commands: List[Command]) -> Dict[str, Any]:
    return {c.names[0]: c.options for c in commands}


# Árvore do autocompletar: só os nomes principais (os apelidos continuam aceitos ao executar).
COMMAND_TREE: Dict[str, Any] = {"skin": _tree(SKIN_COMMANDS), "ajuda": [c.names[0] for c in SKIN_COMMANDS], "girar": ["on", "off"]}


def expects_args(word: str) -> bool:
    """Se, depois de completar ``word``, o comando ainda espera mais palavras (então vem um espaço)."""
    word = word.lower().lstrip("/")
    if word in COMMAND_TREE:
        return True
    command = find_command(SKIN_COMMANDS, word)
    if command is not None:
        return bool(command.options) or callable(command.options)
    return word in ("posicao", "escala", "x", "y", "z", "folga", "puxar")
