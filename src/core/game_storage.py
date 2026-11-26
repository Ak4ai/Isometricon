"""Preferências e mundos locais, independentes da renderização."""
from __future__ import annotations
from dataclasses import fields
import base64
import hashlib
import json
import math
import os
import re
from pathlib import Path
import time
import uuid

from src.core.paths import saves_path
ACTIONS = {
    'forward': ('Mover para frente', 87), 'backward': ('Mover para trás', 83),
    'left': ('Mover para a esquerda', 65), 'right': ('Mover para a direita', 68),
    'rotate_left': ('Girar câmera à esquerda', 81), 'rotate_right': ('Girar câmera à direita', 69),
    'grid': ('Mostrar grade', 71), 'regenerate': ('Gerar outro mundo/seed', 82),
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
    'edge_fog': (True, (True, False)),                 # névoa na borda dos chunks carregados (esconde o fim do mundo)
    'shadows': ('high', ('off', 'low', 'medium', 'high')),  # qualidade da sombra do sol (raios por pixel)
    'shadow_range': (56, (16, 32, 56)),                # até quantas células o raio do sol procura o que tapa
    'shadow_detail': (2, (0, 1, 2, 3)),                # o que faz sombra pela forma: 0 leve (cubos) .. 3 com o mato do chão
    'shadow_strength': (1.0, (0.25, 0.5, 0.75, 1.0)),  # o quanto a sombra escurece
    'shadow_distance': (1, (1, 2, 3, 4, 5, 6)),        # até quantos chunks em volta do jogador há sombra do sol
    'shadow_accum': (True, (False, True)),             # a sombra do sol somada entre quadros (shadow_accum.py)
    'shadow_half': (False, (False, True)),             # sombra calculada em meia resolução (quadrados 2x2)
    'shadow_grain': (1, (1, 2, 4, 8)),                 # o bloco de pixels que gira o cone da penumbra junto
    'fps_limit': (0, (0, 30, 60, 120, 144)),           # 0 sem limite
    'gpu': ('high', ('high', 'low', 'auto')),          # a placa de vídeo (src/core/gpu_preference.py)
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
        with temporary.open('w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
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
        self.path = Path(path or saves_path('preferences.json'))
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
        self.directory = Path(directory or saves_path('worlds'))

    def list(self):
        worlds = []
        for path in self.directory.glob('*.json'):
            try:
                worlds.append(self._read(path.stem))
            except (OSError, ValueError):
                continue
        return sorted(worlds, key=lambda w: str(w.get('saved_at', '')), reverse=True)

    def _read(self, world_id):
        if not isinstance(world_id, str) or len(world_id) != 32 or any(c not in '0123456789abcdef' for c in world_id):
            raise ValueError('Identificador de mundo inválido.')
        try:
            data = json.loads((self.directory / (world_id + '.json')).read_text(encoding='utf-8'))
        except RecursionError as error:
            raise ValueError('O save tem dados aninhados em excesso.') from error
        if (not isinstance(data, dict) or data.get('version') != 1 or data.get('id') != world_id
                or type(data.get('seed')) is not int or not isinstance(data.get('name'), str)):
            raise ValueError('Cabeçalho do mundo inválido.')
        return data

    def load(self, world_id):
        world = self._read(world_id)
        validate_world_state(world)
        world['played'] = float(world.get('played', 0))
        return world

    def create(self, name, seed, terrain=None, *, write=True):
        """Um mundo novo; ``terrain``: as opções de criação (ver ``src.world.terrain_options``)."""
        if not name.strip():
            raise ValueError('Dê um nome ao mundo.')
        world = dict(version=1, id=uuid.uuid4().hex, name=name.strip()[:64],
                     seed=seed_value(seed), position=None, played=0.0, character=None)
        if terrain is not None:
            from src.world.terrain_options import clean
            world['terrain'] = clean(terrain)
        if write:
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


def _number(value):
    """Os saves anteriores também aceitam números em strings."""
    try:
        return not isinstance(value, bool) and math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _vector3(value, check):
    return isinstance(value, (list, tuple)) and len(value) == 3 and all(check(item) for item in value)


def _position(value, *, integral=False):
    # O render usa float32: fora desta faixa, nem os centros dos voxels são representáveis.
    limit = 2**23 - 1
    if integral:
        return _vector3(value, lambda item: type(item) is int and abs(item) <= limit)
    return _vector3(value, lambda item: _number(item) and abs(float(item)) <= limit)


def _validate_character(data):
    from src.clothing.character_save import HAIR_PLACEMENT, NOT_SAVED, WORN
    from src.clothing.customization import AvatarCustomization

    if not isinstance(data, dict) or data.get('versao', 1) != 1:
        raise ValueError('Personagem do mundo inválido.')
    for section in ('aparencia', 'veste', 'cabelo'):
        if data.get(section) is not None and not isinstance(data[section], dict):
            raise ValueError('Personagem do mundo inválido.')
    worn = data.get('veste') or {}
    for name in WORN:
        value = worn.get(name)
        if value is None:
            continue
        if name == 'extra_ids':
            if isinstance(value, list) and all(type(item) in (int, str) for item in value):
                continue
        elif type(value) in (int, str):
            continue
        elif name == 'shoes_id' and isinstance(value, list) and len(value) == 2:
            if all(type(item) in (int, str) for item in value):
                continue
        raise ValueError('Equipamento do personagem inválido.')

    known = {field.name for field in fields(AvatarCustomization)} - set(NOT_SAVED)
    appearance = data.get('aparencia') or {}
    for name, value in appearance.items():
        if name not in known:
            continue
        if name == 'skin_color_rgb' or name in ('hair_color', 'iris_color', 'iris_color_other', 'eyebrow_color'):
            if _vector3(value, lambda item: type(item) in (int, float) and _number(item)) or (name != 'skin_color_rgb' and (value is None or isinstance(value, str))):
                continue
        elif name in HAIR_PLACEMENT:
            if type(value) in (int, float) and _number(value):
                continue
        elif name in ('has_3d_nose', 'hsr_mirror'):
            if isinstance(value, bool) or (name == 'has_3d_nose' and value is None):
                continue
        elif name in ('hsr_hide', 'hsr_show'):
            if isinstance(value, list) and all(type(item) is int and item >= 0 for item in value):
                continue
        elif name in ('body_adjust', 'makeup'):
            check = (lambda item: type(item) in (int, float) and _number(item)) if name == 'body_adjust' else (
                lambda item: isinstance(item, str))
            if isinstance(value, dict) and all(check(item) for item in value.values()):
                continue
        elif value is None or isinstance(value, str):
            continue
        raise ValueError(f'Aparência do personagem inválida ({name}).')

    for name, value in (data.get('cabelo') or {}).items():
        if name in HAIR_PLACEMENT and not _number(value):
            raise ValueError('Posicionamento do cabelo inválido.')


def validate_world_state(world):
    """Valida o estado que os subsistemas vão consumir, antes de substituir o mundo ativo."""
    position = world.get('position')
    if ((position is not None and not _position(position)) or not _number(world.get('played', 0))
            or type(world.get('seed')) is not int):
        raise ValueError('Posição, seed ou tempo de jogo inválido.')
    for key in ('terrain', 'combat', 'ambiente', 'nevoa_explorada'):
        section = world.get(key)
        if section is not None and not isinstance(section, dict):
            raise ValueError(f'Seção inválida no mundo ({key}).')
    from src.world.terrain_options import BIOMES
    for key in ('terrain', 'ambiente'):
        for name, value in (world.get(key) or {}).items():
            if key == 'terrain' and name == 'bioma':
                if value not in BIOMES:      # o bioma é o único texto das opções do terreno
                    raise ValueError(f'Opções inválidas no mundo ({key}).')
            elif not _number(value):
                raise ValueError(f'Opções inválidas no mundo ({key}).')

    for cell, encoded in (world.get('nevoa_explorada') or {}).items():
        try:
            _, _ = (int(part) for part in cell.split(','))
            if not isinstance(encoded, str) or len(encoded) != 44 or len(base64.b64decode(encoded, validate=True)) != 32:
                raise ValueError
        except (ValueError, TypeError) as error:
            raise ValueError('Mapa explorado do mundo inválido.') from error

    combat = world.get('combat') or {}
    if (any(combat.get(key) is not None and not isinstance(combat[key], str) for key in ('weapon', 'armor'))
            or (combat.get('hp') is not None and not _number(combat['hp']))):
        raise ValueError('Ficha de combate do mundo inválida.')
    character = world.get('character')
    if character is not None:
        _validate_character(character)

    for key in ('npcs', 'structures'):
        items = world.get(key)
        if items is not None and (not isinstance(items, list) or any(not isinstance(item, dict) for item in items)):
            raise ValueError(f'Lista inválida no mundo ({key}).')
    for npc in world.get('npcs') or ():
        if ((npc.get('posicao') is not None and not _position(npc['posicao']))
                or (npc.get('yaw') is not None and not _number(npc['yaw']))
                or (npc.get('id') is not None and (not isinstance(npc['id'], str)
                    or re.fullmatch(r'[A-Za-z0-9_-]{1,96}', npc['id']) is None))):
            raise ValueError('NPC do mundo inválido.')
        if npc.get('personagem') is not None:
            _validate_character(npc['personagem'])
        choice = npc.get('modelo')
        if choice is not None and (not isinstance(choice, dict) or (choice and (
                not isinstance(choice.get('arquivo'), str) or not _number(choice.get('altura'))
                or type(choice.get('giro')) is not int
                or (choice.get('perfil') is not None and not isinstance(choice['perfil'], str))))):
            raise ValueError('Modelo do NPC inválido.')
    for structure in world.get('structures') or ():
        entry = structure.get('entry')
        doors = structure.get('open_doors', [])
        if (not isinstance(entry, dict) or not isinstance(entry.get('kind'), str)
                or not _position(structure.get('origin'), integral=True)
                or type(structure.get('rotation', 0)) is not int
                or not isinstance(doors, list) or not all(_position(door, integral=True) for door in doors)):
            raise ValueError('Construção do mundo inválida.')
