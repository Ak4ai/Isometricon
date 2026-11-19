"""A ambientação do mundo que o mestre controla (``/mestre``): hora do dia, claridade, cor da luz, névoa, cores e
a luz do grupo.

A hora move o sol (a direção da luz, então as sombras andam com ela) e muda a cor do mundo: neutra de dia, dourada
perto do horizonte, azulada e escura à noite, quando a luz vem da lua. O resto é uma correção no fim do shader do
mundo (``envGrade``): um tom por cima de tudo, a saturação das cores, a névoa em volta do jogador e uma luz quente em
volta dele (a tocha do grupo), que não escurece à noite.

Nos valores padrão, tudo fica como sempre foi: a hora padrão (16h30) dá exatamente o sol de sempre do terreno
(``DEFAULT_SUN``) e o tom é branco.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Mapping, Optional, Tuple

Vec3 = Tuple[float, float, float]

DEFAULT_SUN: Vec3 = (0.55, 0.26, 0.7)   # o u_LightDir do terreno (espaço desenhado)
SUNRISE, SUNSET = 6.0, 18.0
DEFAULT_HOUR = 16.5
MIN_ELEVATION = math.radians(7.0)       # a luz nunca fica rente ao chão (o raio da sombra precisa subir)
CLOCK_SPEEDS = (0.0, 1.0, 10.0, 60.0)   # minutos de jogo por segundo de verdade
BACKGROUND: Vec3 = (0.08, 0.10, 0.13)   # o fundo do terreno

_SUN = tuple(v / math.sqrt(sum(c * c for c in DEFAULT_SUN)) for v in DEFAULT_SUN)
_SUN_ELEVATION = math.asin(_SUN[1])
_SUN_AZIMUTH = math.atan2(_SUN[2], _SUN[0])
# a altura do sol ao meio-dia, para que a hora padrão dê a altura de sempre
MAX_ELEVATION = _SUN_ELEVATION / math.sin(math.pi * (DEFAULT_HOUR - SUNRISE) / (SUNSET - SUNRISE))


@dataclass
class Ambience:
    hour: float = DEFAULT_HOUR    # 0 a 24
    clock: int = 0                # índice em CLOCK_SPEEDS (0: parado)
    brightness: int = 100         # claridade, 0 a 200 (%)
    temperature: int = 0          # -100 frio a 100 quente
    fog: int = 0                  # 0 a 100
    saturation: int = 100         # 0 a 200 (%)
    torch: int = 0                # a luz do grupo, 0 a 100
    fog_war: int = 0              # a névoa de guerra: 0 desligada, 1 revela ao explorar, 2 só em volta (fog_of_war)
    war_height: int = 2           # quantos blocos as nuvens da névoa de guerra sobem acima do relevo (0 a 16)
    war_objects: int = 1          # 1: as nuvens sobem também por cima das construções; 0: o que é mais alto aparece

    # ---- estado ----
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "Ambience":
        out = cls()
        out.load(data)
        return out

    def load(self, data: Optional[Mapping[str, Any]]) -> None:
        defaults = Ambience()
        for item in fields(self):
            value = (data or {}).get(item.name, getattr(defaults, item.name))
            try:
                setattr(self, item.name, float(value) if item.name == 'hour' else int(round(float(value))))
            except (TypeError, ValueError):
                setattr(self, item.name, getattr(defaults, item.name))
        self.clamp()

    def clamp(self) -> None:
        self.hour %= 24.0
        self.clock = max(0, min(len(CLOCK_SPEEDS) - 1, self.clock))
        self.brightness = max(0, min(200, self.brightness))
        self.temperature = max(-100, min(100, self.temperature))
        self.fog = max(0, min(100, self.fog))
        self.saturation = max(0, min(200, self.saturation))
        self.torch = max(0, min(100, self.torch))
        self.fog_war = max(0, min(2, self.fog_war))
        self.war_height = max(0, min(16, self.war_height))
        self.war_objects = max(0, min(1, self.war_objects))

    def reset(self) -> None:
        self.load(None)

    @property
    def is_default(self) -> bool:
        return self == Ambience()

    def update(self, dt: float) -> bool:
        """Anda o relógio (``CLOCK_SPEEDS``); devolve se a hora mudou."""
        speed = CLOCK_SPEEDS[self.clock]
        if speed <= 0 or dt <= 0:
            return False
        self.hour = (self.hour + speed * dt / 60.0) % 24.0
        return True

    # ---- a luz ----
    def sun_elevation(self, hour: Optional[float] = None) -> float:
        """A altura do sol (radianos; negativa à noite)."""
        h = self.hour if hour is None else hour
        day = (h - SUNRISE) / (SUNSET - SUNRISE)
        if 0.0 <= day <= 1.0:
            return MAX_ELEVATION * math.sin(math.pi * day)
        night = ((h - SUNSET) % 24.0) / (24.0 - (SUNSET - SUNRISE))
        return -MAX_ELEVATION * math.sin(math.pi * night)

    def light_direction(self) -> Vec3:
        """A direção da luz (para onde está o sol, ou a lua à noite), no espaço desenhado, unitária."""
        elevation = self.sun_elevation()
        hour = self.hour
        if elevation < 0:                    # à noite, a lua: do lado oposto do céu, numa altura parecida
            hour, elevation = (hour + 12.0) % 24.0, -elevation * 0.8
        if abs(hour - DEFAULT_HOUR) < 1e-9 and elevation == self.sun_elevation(DEFAULT_HOUR):
            return _SUN                      # a hora padrão é exatamente o sol de sempre
        azimuth = _SUN_AZIMUTH + math.radians((hour - DEFAULT_HOUR) * 15.0)
        elevation = max(elevation, MIN_ELEVATION)
        flat = math.cos(elevation)
        return (flat * math.cos(azimuth), math.sin(elevation), flat * math.sin(azimuth))

    def daylight(self) -> Vec3:
        """A cor da luz pela hora: branca de dia, dourada perto do horizonte, azul e escura à noite."""
        e = math.degrees(self.sun_elevation())
        stops = ((-12.0, (0.24, 0.28, 0.44)), (-4.0, (0.52, 0.48, 0.68)), (2.0, (1.06, 0.82, 0.64)),
                 (math.degrees(_SUN_ELEVATION), (1.0, 1.0, 1.0)), (40.0, (1.06, 1.06, 1.05)))
        if e <= stops[0][0]:
            return stops[0][1]
        for (e0, c0), (e1, c1) in zip(stops, stops[1:]):
            if e <= e1:
                t = (e - e0) / (e1 - e0)
                if t >= 1.0:
                    return c1
                t = t * t * (3 - 2 * t)
                return tuple(a + (b - a) * t for a, b in zip(c0, c1))
        return stops[-1][1]

    def tint(self) -> Vec3:
        """O tom por cima do mundo: a luz da hora x a claridade x a cor (frio a quente)."""
        warm = self.temperature / 100.0
        temperature = (1.0 + 0.14 * warm, 1.0 + 0.02 * warm, 1.0 - 0.18 * warm)
        bright = self.brightness / 100.0
        return tuple(d * t * bright for d, t in zip(self.daylight(), temperature))

    def fog_color(self) -> Vec3:
        """A cor da névoa: a luz da hora, e com muita névoa um cinza claro e frio (de dia quase branco; à noite, um
        cinza escuro), sem a cor forte do entardecer."""
        tint = self.tint()
        thin = tuple(min(1.0, 0.64 * c) for c in tint)
        luma = 0.299 * tint[0] + 0.587 * tint[1] + 0.114 * tint[2]
        grey = tuple(min(1.0, luma * c) for c in (0.80, 0.82, 0.82))
        t = max(0.0, min(1.0, (self.fog / 100.0 - 0.35) / 0.45))
        t = t * t * (3 - 2 * t)
        return tuple(a + (b - a) * t for a, b in zip(thin, grey))

    def war_color(self) -> Vec3:
        """A cor da névoa de guerra: o cinza claro e frio da névoa densa, na luz da hora."""
        tint = self.tint()
        luma = 0.299 * tint[0] + 0.587 * tint[1] + 0.114 * tint[2]
        return tuple(min(1.0, luma * c) for c in (0.80, 0.82, 0.82))

    def background(self) -> Vec3:
        """A cor de fundo da tela (o vazio em volta do terreno), no tom da hora e da névoa."""
        tint = self.tint()
        base = tuple(b * min(t, 1.4) for b, t in zip(BACKGROUND, tint))
        if self.fog_war:                           # o vazio em volta é a névoa de guerra
            return tuple(c * 0.96 for c in self.war_color())
        f = min(1.0, self.fog / 100.0 * 1.4)      # com muita névoa o vazio em volta é a própria névoa
        return tuple(a + (b - a) * f for a, b in zip(base, self.fog_color()))

    def clock_text(self) -> str:
        minutes = int(round(self.hour * 60)) % (24 * 60)
        return f'{minutes // 60:02d}:{minutes % 60:02d}'

    # ---- o shader ----
    def apply(self, shader, center: Vec3) -> None:
        """Os uniforms do ``envGrade`` (``center``: os pés do jogador, no espaço desenhado)."""
        shader.set_vec3("u_EnvTint", *self.tint())
        shader.set_float("u_EnvSaturation", self.saturation / 100.0)
        shader.set_float("u_FogAmount", self.fog / 100.0)
        shader.set_vec3("u_FogColor", *self.fog_color())
        shader.set_vec3("u_FogCenter", *(float(v) for v in center[:3]))
        shader.set_float("u_TorchAmount", self.torch / 100.0)

    @staticmethod
    def neutral(shader) -> None:
        """Sem ambientação (a tela de criação do personagem e o editor de mapa)."""
        shader.set_vec3("u_EnvTint", 1.0, 1.0, 1.0)
        shader.set_float("u_EnvSaturation", 1.0)
        shader.set_float("u_FogAmount", 0.0)
        shader.set_float("u_TorchAmount", 0.0)
        shader.set_int("u_FogWar", 0)


# (nome, valores): o mestre aplica de uma vez
PRESETS: Tuple[Tuple[str, Dict[str, Any]], ...] = (
    ('Amanhecer', dict(hour=6.6, brightness=95, temperature=35, fog=30, saturation=95, torch=0)),
    ('Meio-dia', dict(hour=12.0, brightness=108, temperature=0, fog=0, saturation=105, torch=0)),
    ('Entardecer', dict(hour=17.6, brightness=95, temperature=45, fog=10, saturation=110, torch=0)),
    ('Noite', dict(hour=23.0, brightness=100, temperature=-20, fog=10, saturation=80, torch=60)),
    ('Tempestade', dict(hour=14.0, brightness=62, temperature=-40, fog=55, saturation=45, torch=0)),
    ('Sombrio', dict(hour=20.0, brightness=70, temperature=-10, fog=40, saturation=35, torch=45)),
    ('Névoa densa', dict(hour=13.0, brightness=92, temperature=-15, fog=88, saturation=28, torch=0)),
    ('Pesadelo', dict(hour=0.5, brightness=110, temperature=-25, fog=80, saturation=20, torch=70)),
)
