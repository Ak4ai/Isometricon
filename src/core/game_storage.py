"""Preferências e mundos locais, independentes da renderização."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = {
    'forward': ('Mover para frente', 87), 'backward': ('Mover para trás', 83),
    'left': ('Mover para a esquerda', 65), 'right': ('Mover para a direita', 68),
    'rotate_left': ('Girar câmera à esquerda', 81), 'rotate_right': ('Girar câmera à direita', 69),
    'grid': ('Mostrar grade', 71), 'regenerate': ('Gerar outra seed', 82),
    'chat': ('Abrir chat', 84), 'command': ('Abrir comandos', 47),
    'pan_modifier': ('Arrastar câmera (com clique)', 340),
    'zoom_in': ('Aproximar câmera', 61), 'zoom_out': ('Afastar câmera', 45),
    'interact': ('Interagir (portas, escadas)', 70),
}
# Gráficos: cada opção só aceita os valores da lista (o primeiro item do par é o padrão).
GRAPHICS = {
    'msaa': (4, (0, 2, 4, 8)),                         # amostras do antisserrilhado da cena (0 desligado)
    'fxaa': (False, (False, True)),                    # antisserrilhado rápido, uma passada sobre a imagem pronta
    'render_scale': (1.0, (0.5, 0.67, 0.75, 0.85, 1.0)),  # resolução interna da cena (a interface fica nítida)
    'render_distance': (2, (1, 2, 3, 4, 5, 6)),        # chunks carregados em volta do jogador
    'shadows': ('high', ('off', 'low', 'medium', 'high')),  # qualidade da sombra do sol (raios por pixel)
    'shadow_range': (56, (16, 32, 56)),                # até quantas células o raio do sol procura o que tapa
    'shadow_detail': (2, (0, 1, 2, 3)),                # o que faz sombra pela forma: 0 leve (cubos) .. 3 com o capim
    'shadow_strength': (1.0, (0.25, 0.5, 0.75, 1.0)),  # o quanto a sombra escurece
    'shadow_distance': (1, (1, 2, 3, 4, 5, 6)),        # até quantos chunks em volta do jogador há sombra do sol
    'fps_limit': (0, (0, 30, 60, 120, 144)),           # 0 sem limite
}
DEFAULTS = {'bindings': {k: v[1] for k, v in ACTIONS.items()}, 'vsync': True,
            'sensitivity': 1.0, 'invert_rotation': False, 'reduce_motion': False,
            'text_scale': 1.0, 'show_fps': False, 'show_coords': True, **{key: default for key, (default, _) in GRAPHICS.items()}}


def cycle(key, value, step):
    """O valor seguinte (ou anterior) da lista da opção gráfica, sem dar a volta."""
    options = GRAPHICS[key][1]
    index = options.index(value) if value in options else options.index(GRAPHICS[key][0])
    return options[max(0, min(len(options) - 1, index + step))]


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        # Windows pode manter o destino aberto brevemente durante indexação/antivírus.
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(.025 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def seed_value(text):
    text = str(text).strip()
    if not text:
        return int.from_bytes(os.urandom(4), 'big') & 0x7fffffff
    try:
        return int(text) % (2 ** 31)
    except ValueError:
        return int.from_bytes(hashlib.sha256(text.encode('utf-8')).digest()[:4], 'big') & 0x7fffffff


class Preferences:
    def __init__(self, path=None):
        self.path = Path(path or ROOT / 'saves' / 'preferences.json')
        self.reset()
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            for key in ('vsync', 'invert_rotation', 'reduce_motion', 'show_fps', 'show_coords'):
                if isinstance(data.get(key), bool):
                    self.data[key] = data[key]
            for key, low, high in [('sensitivity', .25, 2), ('text_scale', 1, 1.25)]:
                value = data.get(key)
                if isinstance(value, (int, float)) and math.isfinite(value):
                    self.data[key] = max(low, min(high, value))
            for key, (_, options) in GRAPHICS.items():
                value = data.get(key)
                # bool é int no Python: True não pode valer como 1 nem 1 como True
                if any(value == option and type(value) is type(option) for option in options):
                    self.data[key] = value
                elif (isinstance(value, int) and not isinstance(value, bool) and float(value) in options
                      and all(type(option) is float for option in options)):
                    self.data[key] = float(value)
            bindings = dict(self.data['bindings'])
            for action, key in data.get('bindings', {}).items():
                if action in ACTIONS and isinstance(key, int) and 32 <= key <= 348 and key != 256:
                    bindings[action] = key
            if len(set(bindings.values())) == len(bindings):
                self.data['bindings'] = bindings
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def reset(self):
        self.data = {**DEFAULTS, 'bindings': dict(DEFAULTS['bindings'])}

    def bind(self, action, key):
        if action not in ACTIONS or key == 256 or not 32 <= key <= 348:
            raise ValueError('Tecla reservada ou inválida.')
        if any(k != action and v == key for k, v in self.data['bindings'].items()):
            raise ValueError('Essa tecla já está atribuída a outra ação.')
        self.data['bindings'][action] = key

    def canonical(self, key):
        for action, physical in self.data['bindings'].items():
            if key == physical:
                return ACTIONS[action][1]
        # A tecla padrão remapeada não deve continuar acionando a ação antiga.
        if key in DEFAULTS['bindings'].values():
            return -1
        return key

    def save(self):
        atomic_json(self.path, self.data)


class WorldLibrary:
    """Terreno é regenerado pela seed; posição, tempo e personagem são persistidos."""
    def __init__(self, directory=None):
        self.directory = Path(directory or ROOT / 'saves' / 'worlds')

    def list(self):
        worlds = []
        for path in self.directory.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if data.get('version') != 1 or data.get('id') != path.stem:
                    continue
                if len(path.stem) != 32 or any(c not in '0123456789abcdef' for c in path.stem):
                    continue
                if not isinstance(data.get('seed'), int) or not isinstance(data.get('name'), str):
                    continue
                position = data.get('position')
                if position is not None and (len(position) != 3 or not all(math.isfinite(float(v)) for v in position)):
                    continue
                if not math.isfinite(float(data.get('played', 0))):
                    continue
                worlds.append(data)
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        return sorted(worlds, key=lambda w: str(w.get('saved_at', '')), reverse=True)

    def create(self, name, seed, terrain=None):
        """Um mundo novo; ``terrain``: as opções de criação do relevo (``src.world.terrain_options``)."""
        if not name.strip():
            raise ValueError('Dê um nome ao mundo.')
        world = dict(version=1, id=uuid.uuid4().hex, name=name.strip()[:64],
                     seed=seed_value(seed), position=None, played=0.0, character=None)
        if terrain is not None:
            from src.world.terrain_options import clean
            world['terrain'] = clean(terrain)
        self.save(world)
        return world

    def save(self, world):
        if not isinstance(world.get('id'), str) or len(world['id']) != 32 or any(c not in '0123456789abcdef' for c in world['id']):
            raise ValueError('Identificador de mundo inválido.')
        world['saved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        atomic_json(self.directory / (world['id'] + '.json'), world)

    def delete(self, world_id):
        """Exclui somente o arquivo do mundo identificado pelo UUID."""
        if not isinstance(world_id, str) or len(world_id) != 32 or any(c not in '0123456789abcdef' for c in world_id):
            raise ValueError('Identificador de mundo inválido.')
        (self.directory / (world_id + '.png')).unlink(missing_ok=True)
        (self.directory / (world_id + '.json')).unlink()
