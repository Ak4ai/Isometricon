"""Testes unitários para o ChatConsole e SkinCommandHandler."""

import pytest
from src.clothing.character_model import CharacterModel
from src.clothing.customization import (
    AvatarCustomization,
    EyeStyle,
    HeadType,
    IrisColor,
    MouthStyle,
    HairColor,
    HairStyle,
)
from src.interactive.chat_console import ChatConsole, SkinCommandHandler


def test_skin_command_eyes():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # Cor da íris
    success, msg, _ = handler.execute("/skin eyes red")
    assert success is True
    assert model.customization.iris_color == IrisColor.RED

    # Suporte com 'change'
    success, msg, _ = handler.execute("/skin change eyes green")
    assert success is True
    assert model.customization.iris_color == IrisColor.GREEN

    # Estilo de olhos: wink
    success, msg, _ = handler.execute("/skin eyes wink")
    assert success is True
    assert model.customization.eye_style == EyeStyle.ANIME_WINK

    # Estilo de olhos: classic
    success, msg, _ = handler.execute("/skin eyes classic")
    assert success is True
    assert model.customization.eye_style == EyeStyle.CLASSIC


def test_skin_command_mouth():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    success, msg, _ = handler.execute("/skin mouth cat")
    assert success is True
    assert model.customization.mouth_style == MouthStyle.CAT

    success, msg, _ = handler.execute("/skin change mouth anime_original")
    assert success is True
    assert model.customization.mouth_style == MouthStyle.ANIME_ORIGINAL

    success, msg, _ = handler.execute("/mouth smile")
    assert success is True
    assert model.customization.mouth_style == MouthStyle.SMILE


def test_skin_command_hair():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    success, msg, _ = handler.execute("/skin hair blonde")
    assert success is True
    assert model.customization.hair_color == HairColor.BLONDE

    success, msg, _ = handler.execute("/skin hair bald")
    assert success is True
    assert model.customization.hair_style == HairStyle.BALD

    success, msg, _ = handler.execute("/skin hair pink")
    assert success is True
    assert model.customization.hair_color == HairColor.PINK
    # Automático: se pediu cor enquanto careca, restaura anime_long
    assert model.customization.hair_style == HairStyle.ANIME_LONG


def test_skin_command_skin_tone():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    success, msg, _ = handler.execute("/skin skin dark")
    assert success is True
    assert model.customization.skin_color_rgb == (0.40, 0.28, 0.22)

    success, msg, _ = handler.execute("/skin tone tan")
    assert success is True
    assert model.customization.skin_color_rgb == (0.82, 0.65, 0.52)


def test_skin_command_head_type():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    success, msg, _ = handler.execute("/skin head blocky")
    assert success is True
    assert model.customization.head_type == HeadType.BLOCKY

    success, msg, _ = handler.execute("/skin head rounded")
    assert success is True
    assert model.customization.head_type == HeadType.ROUNDED


def test_skin_command_clothing_and_tools():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    success, msg, _ = handler.execute("/skin top boxy")
    assert success is True
    assert model.top_id == 89475537632859

    success, msg, _ = handler.execute("/skin top sweater")
    assert success is True
    assert model.top_id == 9240757332

    success, msg, _ = handler.execute("/skin tool katana")
    assert success is True
    assert model.tool_id == 12187348

    success, msg, _ = handler.execute("/skin tool none")
    assert success is True
    assert model.tool_id is None


def test_skin_command_turntable():
    turntable = {"active": True, "yaw": 0.0}
    handler = SkinCommandHandler(turntable_state=turntable)

    success, msg, _ = handler.execute("/spin off")
    assert success is True
    assert turntable["active"] is False

    success, msg, _ = handler.execute("/spin on")
    assert success is True
    assert turntable["active"] is True

    success, msg, _ = handler.execute("/spin")
    assert success is True
    assert turntable["active"] is False


def test_skin_command_presets_and_help():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    success, msg, _ = handler.execute("/skin preset dark_knight")
    assert success is True
    assert model.customization.skin_color_rgb == (0.40, 0.28, 0.22)
    assert model.customization.hair_color == HairColor.SILVER
    assert model.customization.iris_color == IrisColor.PURPLE
    assert model.tool_id == 12187348

    success, msg, _ = handler.execute("/help")
    assert success is True
    assert "Comandos" in msg

    success, msg, _ = handler.execute("/skin reset")
    assert success is True
    assert model.customization.resolved_mouth_style == "anime_original"


def test_chat_console_flow():
    import glfw
    chat = ChatConsole(create_gl=False)
    assert chat.is_open is False

    # Pressionar T abre o chat
    consumed = chat.handle_key(glfw.KEY_T, glfw.PRESS, 0)
    assert consumed is True
    assert chat.is_open is True
    assert chat.input_text == ""

    # Digitar caracteres
    chat.handle_char(ord("/"))
    chat.handle_char(ord("s"))
    chat.handle_char(ord("k"))
    chat.handle_char(ord("i"))
    chat.handle_char(ord("n"))
    assert chat.input_text == "/skin"

    # Backspace
    chat.handle_key(glfw.KEY_BACKSPACE, glfw.PRESS, 0)
    assert chat.input_text == "/ski"

    # ESC fecha o chat
    consumed = chat.handle_key(glfw.KEY_ESCAPE, glfw.PRESS, 0)
    assert consumed is True
    assert chat.is_open is False

    # Abrir com barra '/'
    consumed = chat.handle_key(glfw.KEY_SLASH, glfw.PRESS, 0)
    assert consumed is True
    assert chat.is_open is True
    assert chat.input_text == "/"

    # Enter submete e fecha
    chat.handle_key(glfw.KEY_ENTER, glfw.PRESS, 0)
    assert chat.is_open is False


def test_chat_console_open_ignore_char():
    import glfw
    chat = ChatConsole(create_gl=False)

    # Ao pressionar 'T', o chat abre vazio e o evento de caractere subsequente 't' é ignorado
    chat.handle_key(glfw.KEY_T, glfw.PRESS, 0)
    assert chat.is_open is True
    chat.handle_char(ord("t"))  # Char callback do próprio 't' que abriu
    assert chat.input_text == ""  # Não digita 't'!

    chat.close()

    # Ao pressionar '/', o chat abre com '/' e o evento subsequente de char '/' não duplica '//'
    chat.handle_key(glfw.KEY_SLASH, glfw.PRESS, 0)
    assert chat.is_open is True
    assert chat.input_text == "/"
    chat.handle_char(ord("/"))  # Char callback do próprio '/'
    assert chat.input_text == "/"  # Continua sendo '/', não vira '//'


def test_chat_console_autocomplete_suggestions():
    import glfw
    chat = ChatConsole(create_gl=False)
    chat.open("/")
    assert "/skin" in chat.suggestions
    assert "/eyes" in chat.suggestions

    # Digita 'sk' -> sugestão vira '/skin'
    chat.handle_char(ord("s"))
    chat.handle_char(ord("k"))
    assert chat.input_text == "/sk"
    assert chat.suggestions == ["/skin"]
    assert chat.ghost_text == "in "

    # Pressiona TAB -> completa '/skin '
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin "
    assert "eyes" in chat.suggestions
    assert "mouth" in chat.suggestions
    assert "hair" in chat.suggestions

    # Digita 'e' -> sugestão vira 'eyes'
    chat.handle_char(ord("e"))
    assert chat.suggestions == ["eyes"]
    assert chat.ghost_text == "yes "

    # Pressiona TAB -> completa '/skin eyes '
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin eyes "
    assert "blue" in chat.suggestions
    assert "red" in chat.suggestions
    assert "green" in chat.suggestions

    # Digita 'r' -> sugestão vira 'red'
    chat.handle_char(ord("r"))
    assert chat.suggestions == ["red"]
    assert chat.ghost_text == "ed"

    # TAB completa 'red'
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin eyes red"


def test_chat_console_tab_cycling():
    import glfw
    chat = ChatConsole(create_gl=False)
    chat.open("/skin eyes ")
    assert chat.suggestions[0] == "blue"

    # 1º TAB -> completa 'blue'
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin eyes blue"

    # 2º TAB consecutivo -> cicla para 'green'
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin eyes green"

    # 3º TAB consecutivo -> cicla para 'brown'
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin eyes brown"

    # Shift+TAB -> cicla de volta para 'green'
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, glfw.MOD_SHIFT)
    assert chat.input_text == "/skin eyes green"


def test_chat_console_mouse_click_chip():
    chat = ChatConsole(create_gl=False)
    chat.open("/skin ")
    chat.suggestions = ["eyes", "mouth", "hair"]
    # Simula um chip retangular para "mouth"
    chat.suggestion_chips = [
        ("eyes", 70, 500, 110, 524),
        ("mouth", 116, 500, 160, 524),
    ]

    # Clicar dentro da caixa de "mouth"
    clicked = chat.handle_mouse_click(125, 510)
    assert clicked is True
    assert chat.input_text == "/skin mouth "


def test_skin_command_sleeve():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # Largura absoluta
    success, msg, _ = handler.execute("/manga largura 1.2")
    assert success is True
    assert pytest.approx(model.sleeve_width_scale, 0.01) == 1.20

    # Largura relativa com +
    success, msg, _ = handler.execute("/manga largura +0.1")
    assert success is True
    assert pytest.approx(model.sleeve_width_scale, 0.01) == 1.30

    # Comprimento relativo em metros
    success, msg, _ = handler.execute("/manga comprimento +0.03")
    assert success is True
    assert pytest.approx(model.sleeve_length_offset, 0.001) == 0.030

    # Comprimento em centímetros (relativo: estava +0.030, subtrai 0.020 -> fica +0.010)
    success, msg, _ = handler.execute("/manga comprimento -2cm")
    assert success is True
    assert pytest.approx(model.sleeve_length_offset, 0.001) == 0.010

    # Em inglês: /sleeve width e /sleeve length absoluto
    success, msg, _ = handler.execute("/sleeve width 0.85")
    assert success is True
    assert pytest.approx(model.sleeve_width_scale, 0.01) == 0.85

    success, msg, _ = handler.execute("/sleeve length 0.04")
    assert success is True
    assert pytest.approx(model.sleeve_length_offset, 0.001) == 0.040

    # Reset
    success, msg, _ = handler.execute("/manga reset")
    assert success is True
    assert model.sleeve_width_scale == 1.0
    assert model.sleeve_length_offset == 0.0


def test_skin_command_arm():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # Largura do braço
    success, msg, _ = handler.execute("/braco largura 0.90")
    assert success is True
    assert pytest.approx(model.arm_width_scale, 0.01) == 0.90

    # Comprimento do braço
    success, msg, _ = handler.execute("/braco comprimento 1.08")
    assert success is True
    assert pytest.approx(model.arm_length_scale, 0.01) == 1.08

    # Em inglês: /arm width e /arm length
    success, msg, _ = handler.execute("/arm width 1.15")
    assert success is True
    assert pytest.approx(model.arm_width_scale, 0.01) == 1.15

    success, msg, _ = handler.execute("/arm length 0.95")
    assert success is True
    assert pytest.approx(model.arm_length_scale, 0.01) == 0.95

    # Reset
    success, msg, _ = handler.execute("/braco reset")
    assert success is True
    assert model.arm_width_scale == 1.0
    assert model.arm_length_scale == 1.0


def test_sleeve_and_arm_suggestions():
    chat = ChatConsole(create_gl=False)
    # Autocomplete do comando raiz
    chat.open("/man")
    assert "/manga" in chat.suggestions

    chat.open("/bra")
    assert "/braco" in chat.suggestions

    # Subcomandos
    chat.open("/manga ")
    assert "largura" in chat.suggestions
    assert "comprimento" in chat.suggestions
    assert "reset" in chat.suggestions

    chat.open("/braco ")
    assert "largura" in chat.suggestions
    assert "comprimento" in chat.suggestions
    assert "reset" in chat.suggestions

    # Chips de sugestão de valores numéricos
    chat.open("/manga largura ")
    assert "1.2" in chat.suggestions

    chat.open("/manga comprimento ")
    assert "+2cm" in chat.suggestions

    chat.open("/manga horizontal ")
    assert "+2cm" in chat.suggestions

    chat.open("/manga vertical ")
    assert "+1cm" in chat.suggestions

    chat.open("/braco largura ")
    assert "1.1" in chat.suggestions

    chat.open("/braco comprimento ")
    assert "1.05" in chat.suggestions


def test_skin_command_sleeve_shift():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Deslocamento horizontal (+ fora, - dentro)
    success, msg, _ = handler.execute("/manga horizontal +2cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_x, 0.001) == 0.020

    success, msg, _ = handler.execute("/manga fora 3cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_x, 0.001) == 0.030

    success, msg, _ = handler.execute("/manga dentro 1.5cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_x, 0.001) == -0.015

    # 2. Deslocamento vertical (+ sobe, - desce)
    success, msg, _ = handler.execute("/manga vertical +1cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_z, 0.001) == 0.010

    # 3. Profundidade frente/trás
    success, msg, _ = handler.execute("/manga frente 2cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_y, 0.001) == 0.020

    # 4. Deslocar composto / multi-eixo
    success, msg, _ = handler.execute("/manga deslocar 2cm -1cm 0.5cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_x, 0.001) == 0.020
    assert pytest.approx(model.sleeve_shift_y, 0.001) == -0.010
    assert pytest.approx(model.sleeve_shift_z, 0.001) == 0.005

    # 5. Atalhos diretos de raiz (/horizontal, /vertical, /fora, /dentro)
    success, msg, _ = handler.execute("/horizontal 2.5cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_x, 0.001) == 0.025

    success, msg, _ = handler.execute("/vertical -2cm")
    assert success is True
    assert pytest.approx(model.sleeve_shift_z, 0.001) == -0.020

    # 6. Reset restaura todos os deslocamentos
    success, msg, _ = handler.execute("/manga reset")
    assert success is True
    assert model.sleeve_shift_x == 0.0
    assert model.sleeve_shift_y == 0.0
    assert model.sleeve_shift_z == 0.0
    assert model.sleeve_width_scale == 1.0
    assert model.sleeve_length_offset == 0.0


def test_body_command():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    assert model.customization.is_female is False

    success, msg, _ = handler.execute("/body feminino")
    assert success is True
    assert model.customization.is_female is True

    success, msg, _ = handler.execute("/skin body masculino")
    assert success is True
    assert model.customization.is_female is False

    success, msg, _ = handler.execute("/corpo female")
    assert success is True
    assert model.customization.is_female is True


def test_bottom_command_and_autocomplete():
    import glfw
    from src.clothing.character_model import BOTTOM_PRESETS

    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Comandos diretos de calça
    success, msg, _ = handler.execute("/calca skater")
    assert success is True
    assert model.bottom_id == BOTTOM_PRESETS["skater"]
    assert model.bottom_id == 137146416353285

    success, msg, _ = handler.execute("/calca jeans")
    assert success is True
    assert model.bottom_id == BOTTOM_PRESETS["jeans"]
    assert model.bottom_id == 109837605892174

    success, msg, _ = handler.execute("/calca none")
    assert success is True
    assert model.bottom_id is None

    success, msg, _ = handler.execute("/skin bottom vintage")
    assert success is True
    assert model.bottom_id == 137146416353285

    # 2. Autocomplete de /calca
    chat = ChatConsole(command_handler=handler, create_gl=False)
    chat.open("/calca ")
    assert "skater" in chat.suggestions
    assert "vintage" in chat.suggestions
    assert "baggy" in chat.suggestions
    assert "jeans" in chat.suggestions
    assert "none" in chat.suggestions

    # 3. Autocomplete de /skin bottom
    chat.open("/skin bottom ")
    assert "skater" in chat.suggestions
    assert "vintage" in chat.suggestions
    assert "baggy" in chat.suggestions
    assert "jeans" in chat.suggestions
    assert "none" in chat.suggestions

    # 4. TAB em raiz sugere /calca
    chat.open("/c")
    assert "/calca" in chat.suggestions
    assert "/corpo" in chat.suggestions
    assert "/cintura" in chat.suggestions


def test_cintura_commands_and_autocomplete():
    """Valida a execução de comandos de ajuste de altura da cintura e o autocompletar."""
    from src.clothing.customization import AvatarCustomization, BodyType
    cust = AvatarCustomization(body_type=BodyType.FEMALE)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    assert model.waist_height_offset == pytest.approx(0.0)

    # 1. Comandos relativos com unidade
    success, msg, _ = handler.execute("/cintura +2cm")
    assert success is True
    assert model.waist_height_offset == pytest.approx(0.02)

    # 2. Descer com /cintura desce
    success, msg, _ = handler.execute("/cintura desce 3cm")
    assert success is True
    assert model.waist_height_offset == pytest.approx(-0.01)

    # 3. Comandos semânticos (alta, baixa, meio)
    success, msg, _ = handler.execute("/cintura alta")
    assert success is True
    assert model.waist_height_offset == pytest.approx(0.07)  # 1.07m

    success, msg, _ = handler.execute("/cintura baixa")
    assert success is True
    assert model.waist_height_offset == pytest.approx(-0.06)  # 0.94m

    success, msg, _ = handler.execute("/cintura meio")
    assert success is True
    assert model.waist_height_offset == pytest.approx(0.0)  # 1.00m (meio do declive)

    # 4. Altura absoluta em metros
    success, msg, _ = handler.execute("/cintura 1.03")
    assert success is True
    assert model.waist_height_offset == pytest.approx(0.03)

    # 5. Reset
    success, msg, _ = handler.execute("/cintura reset")
    assert success is True
    assert model.waist_height_offset == pytest.approx(0.0)

    # 6. Roteamento a partir de /calca altura
    success, msg, _ = handler.execute("/calca altura +2cm")
    assert success is True
    assert model.waist_height_offset == pytest.approx(0.02)

    # 7. Autocomplete de /cintura
    chat = ChatConsole(command_handler=handler, create_gl=False)
    chat.open("/cintura ")
    assert "altura" in chat.suggestions
    assert "sobe" in chat.suggestions
    assert "desce" in chat.suggestions
    assert "meio" in chat.suggestions
    assert "alta" in chat.suggestions
    assert "baixa" in chat.suggestions
    assert "reset" in chat.suggestions

    chat.open("/cintura altura ")
    assert "+1cm" in chat.suggestions
    assert "+2cm" in chat.suggestions
    assert "-1cm" in chat.suggestions


def test_barra_commands_and_autocomplete():
    from src.clothing.customization import AvatarCustomization, BodyType

    cust = AvatarCustomization(body_type=BodyType.FEMALE)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Consulta inicial
    success, msg, _ = handler.execute("/barra")
    assert success is True
    assert "Altura base: 0.985m" in msg

    # 2. Sobe e desce
    success, msg, _ = handler.execute("/barra sobe 2cm")
    assert success is True
    assert model.top_hem_offset == pytest.approx(0.02)

    success, msg, _ = handler.execute("/barra desce 1cm")
    assert success is True
    assert model.top_hem_offset == pytest.approx(0.01)

    # 3. Presets semânticos: cropped, alta, meio, longa
    success, msg, _ = handler.execute("/barra cropped")
    assert success is True
    assert (0.985 + model.top_hem_offset) == pytest.approx(1.090)

    success, msg, _ = handler.execute("/barra alta")
    assert success is True
    assert (0.985 + model.top_hem_offset) == pytest.approx(1.070)

    success, msg, _ = handler.execute("/barra meio")
    assert success is True
    assert model.top_hem_offset == pytest.approx(0.0)

    success, msg, _ = handler.execute("/barra longa")
    assert success is True
    assert (0.985 + model.top_hem_offset) == pytest.approx(0.950)

    # 4. Valores relativos e absolutos
    success, msg, _ = handler.execute("/barra +3cm")
    assert success is True
    assert model.top_hem_offset == pytest.approx(-0.005)

    success, msg, _ = handler.execute("/barra 1.05")
    assert success is True
    assert (0.985 + model.top_hem_offset) == pytest.approx(1.05)

    # 5. Reset
    success, msg, _ = handler.execute("/barra reset")
    assert success is True
    assert model.top_hem_offset == pytest.approx(0.0)

    # 6. Roteamento a partir de /top barra e /blusa barra
    success, msg, _ = handler.execute("/top barra cropped")
    assert success is True
    assert (0.985 + model.top_hem_offset) == pytest.approx(1.090)

    # 7. Autocomplete de /barra
    chat = ChatConsole(command_handler=handler, create_gl=False)
    chat.open("/barra ")
    assert "altura" in chat.suggestions
    assert "sobe" in chat.suggestions
    assert "desce" in chat.suggestions
    assert "cropped" in chat.suggestions
    assert "alta" in chat.suggestions
    assert "meio" in chat.suggestions
    assert "longa" in chat.suggestions
    assert "reset" in chat.suggestions

    # 8. Modelo Masculino: padrão -2cm (-0.02m) e base 0.890m
    cust_male = AvatarCustomization(body_type=BodyType.MALE)
    model_male = CharacterModel(customization=cust_male, create_mesh=False)
    handler_male = SkinCommandHandler(character_model=model_male)

    assert model_male.top_hem_offset == pytest.approx(-0.02)
    success, msg, _ = handler_male.execute("/barra")
    assert success is True
    assert "Altura base: 0.890m" in msg
    assert "Deslocamento: -0.020m (-2.0cm)" in msg

    success, msg, _ = handler_male.execute("/barra sobe 5cm")
    assert success is True
    assert model_male.top_hem_offset == pytest.approx(0.03)

    success, msg, _ = handler_male.execute("/barra reset")
    assert success is True
    assert model_male.top_hem_offset == pytest.approx(-0.02)

    success, msg, _ = handler_male.execute("/barra meio")
    assert success is True
    assert model_male.top_hem_offset == pytest.approx(-0.02)


def test_skin_command_cintura_radius():
    model = CharacterModel(create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Status inclui informação de raio
    success, msg, _ = handler.execute("/cintura")
    assert success is True
    assert "Raio Torso:" in msg

    # 2. /cintura radius status
    success, msg, _ = handler.execute("/cintura radius")
    assert success is True
    assert "Raio/Afunilamento do torso:" in msg

    # 3. /cintura radius -2cm
    success, msg, _ = handler.execute("/cintura radius -2cm")
    assert success is True
    assert model.waist_radius_offset == pytest.approx(-0.02)
    assert "afunilado" in msg

    # 4. /cintura radius +2cm
    success, msg, _ = handler.execute("/cintura radius +2cm")
    assert success is True
    assert model.waist_radius_offset == pytest.approx(0.02)
    assert "alargado" in msg

    # 5. /cintura radius reset
    success, msg, _ = handler.execute("/cintura radius reset")
    assert success is True
    assert model.waist_radius_offset == pytest.approx(0.0)

    # 6. Atalho direto /radius -1.5cm
    success, msg, _ = handler.execute("/radius -1.5cm")
    assert success is True
    assert model.waist_radius_offset == pytest.approx(-0.015)

    # 7. Atalho direto /raio reset
    success, msg, _ = handler.execute("/raio reset")
    assert success is True
    assert model.waist_radius_offset == pytest.approx(0.0)

    # 8. Roteamento a partir de /calca radius -2cm
    success, msg, _ = handler.execute("/calca radius -2cm")
    assert success is True
    assert model.waist_radius_offset == pytest.approx(-0.02)

    # 9. Reset global de cintura restaura altura e raio
    model.waist_height_offset = 0.05
    model.waist_radius_offset = -0.02
    success, msg, _ = handler.execute("/cintura reset")
    assert success is True
    assert model.waist_height_offset == pytest.approx(0.0)
    assert model.waist_radius_offset == pytest.approx(0.0)

    # 10. Autocomplete
    chat = ChatConsole(command_handler=handler, create_gl=False)
    chat.open("/cintura rad")
    assert "radius" in chat.suggestions
    chat.open("/cintura radius ")
    assert "-2cm" in chat.suggestions
    assert "+2cm" in chat.suggestions
    assert "reset" in chat.suggestions
    chat.open("/radius ")
    assert "-2cm" in chat.suggestions
    model.delete()


def test_skin_command_cintura_chanfro():
    model = CharacterModel(create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Status inclui informação de chanfro
    success, msg, _ = handler.execute("/cintura")
    assert success is True
    assert "Chanfro: 1.5cm" in msg

    # 2. /cintura chanfro status
    success, msg, _ = handler.execute("/cintura chanfro")
    assert success is True
    assert "Chanfro atual das quinas:" in msg

    # 3. /cintura chanfro 0 (quadrado)
    success, msg, _ = handler.execute("/cintura chanfro 0")
    assert success is True
    assert model.waist_chamfer == pytest.approx(0.0)
    assert "quadrado" in msg

    # 4. /cintura chanfro 2cm
    success, msg, _ = handler.execute("/cintura chanfro 2cm")
    assert success is True
    assert model.waist_chamfer == pytest.approx(0.02)

    # 5. /cintura chanfro forte
    success, msg, _ = handler.execute("/cintura chanfro forte")
    assert success is True
    assert model.waist_chamfer == pytest.approx(0.035)
    assert "arredondado" in msg

    # 6. Atalho direto /chanfro 1.5cm
    success, msg, _ = handler.execute("/chanfro 1.5cm")
    assert success is True
    assert model.waist_chamfer == pytest.approx(0.015)

    # 7. Atalho direto /bevel reset
    success, msg, _ = handler.execute("/bevel reset")
    assert success is True
    assert model.waist_chamfer == pytest.approx(0.015)

    # 8. Roteamento via /calca chanfro 3cm
    success, msg, _ = handler.execute("/calca chanfro 3cm")
    assert success is True
    assert model.waist_chamfer == pytest.approx(0.03)

    # 9. Reset global de cintura restaura chanfro para 1.5cm
    model.waist_chamfer = 0.035
    success, msg, _ = handler.execute("/cintura reset")
    assert success is True
    assert model.waist_chamfer == pytest.approx(0.015)

    # 10. Autocomplete
    chat = ChatConsole(command_handler=handler, create_gl=False)
    chat.open("/cintura chan")
    assert "chanfro" in chat.suggestions
    chat.open("/cintura chanfro ")
    assert "0" in chat.suggestions
    assert "1cm" in chat.suggestions
    assert "1.5cm" in chat.suggestions
    assert "2cm" in chat.suggestions
    assert "quadrado" in chat.suggestions
    assert "forte" in chat.suggestions
    assert "reset" in chat.suggestions
    chat.open("/chanfro ")
    assert "1.5cm" in chat.suggestions
    model.delete()


def test_skin_command_postura():
    from src.clothing.customization import AvatarCustomization, BodyType

    # Modelo feminino
    cust_fem = AvatarCustomization(body_type=BodyType.FEMALE)
    model_fem = CharacterModel(customization=cust_fem, create_mesh=False)
    handler_fem = SkinCommandHandler(character_model=model_fem)

    assert model_fem.head_z_offset == pytest.approx(-0.040)

    # 1. Status / consulta
    success, msg, _ = handler_fem.execute("/postura")
    assert success is True
    assert "-0.040m" in msg
    assert "-4.0cm" in msg

    # 2. Ajuste com cm
    success, msg, _ = handler_fem.execute("/postura -3cm")
    assert success is True
    assert model_fem.head_z_offset == pytest.approx(-0.030)
    assert "recuada" in msg

    # 3. Zerar
    success, msg, _ = handler_fem.execute("/postura 0")
    assert success is True
    assert model_fem.head_z_offset == pytest.approx(0.0)
    assert "zerado" in msg

    # 4. Restaurar para o padrão feminino (-4cm)
    success, msg, _ = handler_fem.execute("/postura reset")
    assert success is True
    assert model_fem.head_z_offset == pytest.approx(-0.040)

    # 5. Roteamento a partir de /cabeca postura
    success, msg, _ = handler_fem.execute("/cabeca postura -5cm")
    assert success is True
    assert model_fem.head_z_offset == pytest.approx(-0.050)

    # 6. Modelo masculino
    cust_male = AvatarCustomization(body_type=BodyType.MALE)
    model_male = CharacterModel(customization=cust_male, create_mesh=False)
    handler_male = SkinCommandHandler(character_model=model_male)

    assert model_male.head_z_offset == pytest.approx(0.0)

    success, msg, _ = handler_male.execute("/postura -2cm")
    assert success is True
    assert model_male.head_z_offset == pytest.approx(-0.020)

    success, msg, _ = handler_male.execute("/postura reset")
    assert success is True
    assert model_male.head_z_offset == pytest.approx(0.0)

    # 7. Autocomplete e sugestões
    chat = ChatConsole(command_handler=handler_fem, create_gl=False)
    chat.open("/pos")
    assert "/postura" in chat.suggestions
    chat.open("/postura ")
    assert "-4cm" in chat.suggestions
    assert "-3cm" in chat.suggestions
    assert "0" in chat.suggestions
    assert "reset" in chat.suggestions

    chat.open("/skin head ")
    assert "postura" in chat.suggestions

    model_fem.delete()
    model_male.delete()


def test_skin_command_import():
    model = CharacterModel(create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Sem argumentos: exibe ajuda com exemplos e o equipamento atual
    success, msg, _ = handler.execute("/import")
    assert success is True
    assert "[Import] Uso:" in msg
    assert "9240757332" in msg
    assert "Equipado atual:" in msg

    # 2. Importar calça existente por ID
    success, msg, _ = handler.execute("/import 109837605892174")
    assert success is True
    assert model.bottom_id == 109837605892174
    assert "vestida com sucesso" in msg

    # 3. Importar camisa existente por ID
    success, msg, _ = handler.execute("/import 9240757332")
    assert success is True
    assert model.top_id == 9240757332
    assert "Roupa Superior" in msg

    # 4. Importar via URL completa do catálogo do Roblox
    url = "https://www.roblox.com/catalog/137146416353285/Vintage-Baggy-Skater-Pants-Light-Blue"
    success, msg, _ = handler.execute(f"/import {url}")
    assert success is True
    assert model.bottom_id == 137146416353285

    # 5. Importar por nome de preset semântico
    success, msg, _ = handler.execute("/import boxy")
    assert success is True
    assert model.top_id == 89475537632859

    # 6. Importar ferramenta / katana
    success, msg, _ = handler.execute("/import 12187348")
    assert success is True
    assert model.tool_id == 12187348

    # 7. Aliases de comando (/importar, /wear, /vestir, /roblox)
    success, msg, _ = handler.execute("/importar 9240757332")
    assert success is True
    assert model.top_id == 9240757332

    success, msg, _ = handler.execute("/wear 109837605892174")
    assert success is True
    assert model.bottom_id == 109837605892174

    success, msg, _ = handler.execute("/vestir skater")
    assert success is True
    assert model.bottom_id == 137146416353285

    # 8. Roteamento a partir de /skin import
    success, msg, _ = handler.execute("/skin import 9240757332")
    assert success is True
    assert model.top_id == 9240757332

    # 9. ID ou string inválida
    success, msg, _ = handler.execute("/import invalid_token_xyz")
    assert success is False
    assert "inválido" in msg or "invalido" in msg

    # 10. Sem modelo 3D
    empty_handler = SkinCommandHandler(character_model=None)
    success, msg, _ = empty_handler.execute("/import 9240757332")
    assert success is False
    assert "não disponível" in msg or "nao disponivel" in msg

    # 11. Autocomplete
    chat = ChatConsole(command_handler=handler, create_gl=False)
    chat.open("/imp")
    assert "/import" in chat.suggestions
    assert "/importar" in chat.suggestions

    chat.open("/wea")
    assert "/wear" in chat.suggestions

    chat.open("/ves")
    assert "/vestir" in chat.suggestions

    chat.open("/import ")
    assert "9240757332" in chat.suggestions
    assert "109837605892174" in chat.suggestions
    assert "137146416353285" in chat.suggestions
    assert "sweater" in chat.suggestions
    assert "jeans" in chat.suggestions

    model.delete()


def test_chat_console_clipboard_shortcuts(monkeypatch):
    """Verifica se Ctrl+V cola texto da área de transferência e Ctrl+C / Ctrl+A funcionam."""
    import glfw

    chat = ChatConsole(command_handler=None, create_gl=False)
    chat.open("/import ")

    # Mock da área de transferência com ID copiado do Roblox
    sample_id = "110437430397470"
    monkeypatch.setattr(chat, "_get_clipboard_string", lambda: sample_id)

    copied_buffer = []
    monkeypatch.setattr(chat, "_set_clipboard_string", lambda t: copied_buffer.append(t))

    # 1. Pressiona Ctrl+V
    consumed = chat.handle_key(glfw.KEY_V, glfw.PRESS, glfw.MOD_CONTROL)
    assert consumed is True
    assert chat.input_text == f"/import {sample_id}"
    assert chat.cursor_pos == len(f"/import {sample_id}")

    # 2. Ignora caractere de controle emitido pelo Windows durante Ctrl+V (codepoint 22 - SYN)
    consumed_char = chat.handle_char(22)
    assert consumed_char is True
    assert chat.input_text == f"/import {sample_id}"  # Não poluiu o texto

    # 3. Pressiona Ctrl+C
    consumed = chat.handle_key(glfw.KEY_C, glfw.PRESS, glfw.MOD_CONTROL)
    assert consumed is True
    assert copied_buffer == [f"/import {sample_id}"]

    # 4. Pressiona Home e depois Ctrl+A
    chat.handle_key(glfw.KEY_HOME, glfw.PRESS, 0)
    assert chat.cursor_pos == 0
    chat.handle_key(glfw.KEY_A, glfw.PRESS, glfw.MOD_CONTROL)
    assert chat.cursor_pos == len(chat.input_text)

    # 5. Testa se retornar bytes (como pyglfw faz nativamente) não causa TypeError/crash
    chat.open("")
    monkeypatch.setattr(chat, "_get_clipboard_string", lambda: b"bytes_test_123")
    consumed = chat.handle_key(glfw.KEY_V, glfw.PRESS, glfw.MOD_CONTROL)
    assert consumed is True
    assert chat.input_text == "bytes_test_123"


def test_chat_console_async_callbacks_and_spinner():
    """Verifica a fila de callbacks thread-safe e a animação do badge de loading."""
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)
    chat = ChatConsole(command_handler=handler, create_gl=False)

    # Simula estado de importação em segundo plano
    handler.is_importing = True
    handler.import_asset_id = 9240757332
    handler.import_status = "Baixando Suéter #9240757332..."

    assert chat.loading_frame == 0
    chat.update(0.15)
    assert chat.loading_frame == 1  # Spinner avançou

    # Agenda callback simulado de conclusão de download/mesh
    called = []
    with handler._callback_lock:
        handler._pending_main_thread_callbacks.append(lambda: called.append("ok"))

    assert len(called) == 0
    chat.update(0.01)  # Dispara process_pending_callbacks
    assert called == ["ok"]

    # Testa geração do HUD com o badge de loading ativo
    hud_img = chat._generate_hud_image(800, 600, [])
    assert hud_img is not None
    assert hud_img.size == (800, 600)

    model.delete()


def test_import_hair_auto_classification():
    """Verifica que cabelos do Roblox (ex: 131607970996365) são auto-classificados como cabelo e equipados instantaneamente."""
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # Importa o cabelo popstar
    success, feedback, color = handler.execute("/import 131607970996365", run_async=False)
    assert success is True
    assert "Cabelo 3D" in feedback
    assert "equipado" in feedback.lower()
    assert model.hair_id == 131607970996365
    assert model.customization.custom_hair_obj is not None
    assert "Hair_fitted_131607970996365.obj" in model.customization.custom_hair_obj
    assert model.customization.resolved_hair_2d_style == "none"

    model.delete()


def test_skin_hair_numeric_id():
    """Verifica que /skin hair <ID> equipa diretamente o cabelo sem necessidade de /import."""
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    success, feedback, color = handler.execute("/skin hair 131607970996365")
    assert success is True
    assert "Cabelo 3D" in feedback
    assert model.hair_id == 131607970996365

    # Testa alternância para careca
    success, feedback, color = handler.execute("/skin hair bald")
    assert success is True
    assert model.customization.hair_style == HairStyle.BALD
    assert model.hair_id == "none"
    assert model.customization.custom_hair_obj is None

    # Testa restauração para anime_long padrão
    success, feedback, color = handler.execute("/skin hair default")
    assert success is True
    assert model.customization.hair_style == HairStyle.ANIME_LONG
    assert model.hair_id == "116773763268018"

    model.delete()


def test_hair_position_commands():
    """Testa comandos manuais de ajuste de posição do cabelo (X, Y, Z, sobe, desce, frente, tras, etc.)."""
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Status inicial
    success, msg, _ = handler.execute("/cabelo status")
    assert success is True
    assert "Offset (Posição)" in msg

    # 2. Comando composto /cabelo pos <x> <y> <z>
    success, msg, _ = handler.execute("/cabelo pos +1cm +2cm -1.5cm")
    assert success is True
    assert pytest.approx(model.hair_offset_x, 0.001) == 0.010
    assert pytest.approx(model.hair_offset_y, 0.001) == 0.020
    assert pytest.approx(model.hair_offset_z, 0.001) == -0.015

    # 3. Ajuste por eixo individual: /cabelo pos x, y, z
    success, msg, _ = handler.execute("/cabelo pos x +2cm")
    assert success is True
    assert pytest.approx(model.hair_offset_x, 0.001) == 0.030

    # 4. Eixos diretos: /cabelo x, /cabelo y, /cabelo z
    success, msg, _ = handler.execute("/cabelo x 0")
    assert success is True
    assert pytest.approx(model.hair_offset_x, 0.001) == 0.000

    success, msg, _ = handler.execute("/cabelo y 3cm")
    assert success is True
    assert pytest.approx(model.hair_offset_y, 0.001) == 0.030

    success, msg, _ = handler.execute("/cabelo z 0")
    assert success is True
    assert pytest.approx(model.hair_offset_z, 0.001) == 0.000

    # 5. Sobe e desce
    success, msg, _ = handler.execute("/cabelo sobe 1cm")
    assert success is True
    assert pytest.approx(model.hair_offset_y, 0.001) == 0.040

    success, msg, _ = handler.execute("/cabelo desce 2cm")
    assert success is True
    assert pytest.approx(model.hair_offset_y, 0.001) == 0.020

    # 6. Frente e trás
    success, msg, _ = handler.execute("/cabelo frente 1.5cm")
    assert success is True
    assert pytest.approx(model.hair_offset_z, 0.001) == 0.015

    success, msg, _ = handler.execute("/cabelo tras 1cm")
    assert success is True
    assert pytest.approx(model.hair_offset_z, 0.001) == 0.005

    # 7. Direita e esquerda
    success, msg, _ = handler.execute("/cabelo direita 2cm")
    assert success is True
    assert pytest.approx(model.hair_offset_x, 0.001) == 0.020

    success, msg, _ = handler.execute("/cabelo esquerda 1cm")
    assert success is True
    assert pytest.approx(model.hair_offset_x, 0.001) == 0.010

    # 8. Reset de posição apenas
    success, msg, _ = handler.execute("/cabelo reset pos")
    assert success is True
    assert model.hair_offset_x == 0.0
    assert model.hair_offset_y == 0.0
    assert model.hair_offset_z == 0.0

    # 9. Comando raiz /pos
    success, msg, _ = handler.execute("/pos 0 +2.5cm 0")
    assert success is True
    assert pytest.approx(model.hair_offset_y, 0.001) == 0.025

    model.delete()


def test_hair_scale_commands():
    """Testa comandos manuais de ajuste de escala/tamanho do cabelo (X, Y, Z, largura, altura, etc.)."""
    cust = AvatarCustomization(head_type=HeadType.ROUNDED)
    model = CharacterModel(customization=cust, create_mesh=False)
    handler = SkinCommandHandler(character_model=model)

    # 1. Escala uniforme /cabelo scale 1.1
    success, msg, _ = handler.execute("/cabelo scale 1.1")
    assert success is True
    assert pytest.approx(model.hair_scale_x, 0.01) == 1.10
    assert pytest.approx(model.hair_scale_y, 0.01) == 1.10
    assert pytest.approx(model.hair_scale_z, 0.01) == 1.10

    # 2. Escala 3 eixos /cabelo scale <sx> <sy> <sz>
    success, msg, _ = handler.execute("/cabelo scale 1.05 0.95 1.15")
    assert success is True
    assert pytest.approx(model.hair_scale_x, 0.01) == 1.05
    assert pytest.approx(model.hair_scale_y, 0.01) == 0.95
    assert pytest.approx(model.hair_scale_z, 0.01) == 1.15

    # 3. Escala por eixo individual: /cabelo scale x, /cabelo scale y, /cabelo scale z
    success, msg, _ = handler.execute("/cabelo scale x 1.20")
    assert success is True
    assert pytest.approx(model.hair_scale_x, 0.01) == 1.20

    # 4. Atalhos de dimensão: largura, altura, profundidade
    success, msg, _ = handler.execute("/cabelo largura 1.08")
    assert success is True
    assert pytest.approx(model.hair_scale_x, 0.01) == 1.08

    success, msg, _ = handler.execute("/cabelo altura 0.92")
    assert success is True
    assert pytest.approx(model.hair_scale_y, 0.01) == 0.92

    success, msg, _ = handler.execute("/cabelo profundidade 1.06")
    assert success is True
    assert pytest.approx(model.hair_scale_z, 0.01) == 1.06

    # 5. Reset de escala apenas
    success, msg, _ = handler.execute("/cabelo reset scale")
    assert success is True
    assert model.hair_scale_x == 1.0
    assert model.hair_scale_y == 1.0
    assert model.hair_scale_z == 1.0

    # 6. Comando raiz /scale e /tamanho
    success, msg, _ = handler.execute("/scale 1.05")
    assert success is True
    assert pytest.approx(model.hair_scale_x, 0.01) == 1.05

    success, msg, _ = handler.execute("/tamanho x 1.12")
    assert success is True
    assert pytest.approx(model.hair_scale_x, 0.01) == 1.12

    # 7. Reset geral
    success, msg, _ = handler.execute("/cabelo reset")
    assert success is True
    assert model.hair_offset_x == 0.0
    assert model.hair_offset_y == 0.0
    assert model.hair_offset_z == 0.0
    assert model.hair_scale_x == 1.0
    assert model.hair_scale_y == 1.0
    assert model.hair_scale_z == 1.0

    model.delete()


def test_hair_autocomplete_suggestions():
    """Verifica autocompletar e sugestões dos novos comandos de cabelo."""
    chat = ChatConsole(create_gl=False)
    chat.open("/cab")
    assert "/cabelo" in chat.suggestions

    chat.open("/cabelo ")
    assert "pos" in chat.suggestions
    assert "scale" in chat.suggestions
    assert "tamanho" in chat.suggestions
    assert "x" in chat.suggestions
    assert "y" in chat.suggestions
    assert "z" in chat.suggestions
    assert "sobe" in chat.suggestions
    assert "desce" in chat.suggestions
    assert "largura" in chat.suggestions
    assert "reset" in chat.suggestions

    chat.open("/cabelo pos ")
    assert "+1cm" in chat.suggestions
    assert "+2cm" in chat.suggestions

    chat.open("/cabelo scale ")
    assert "1.0" in chat.suggestions
    assert "1.1" in chat.suggestions
