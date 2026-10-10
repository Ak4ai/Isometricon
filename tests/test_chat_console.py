"""Testes do console de chat e dos comandos /skin."""
from types import SimpleNamespace

import pytest

from src.clothing.character_model import CharacterModel
from src.clothing.customization import (
    AvatarCustomization,
    BodyType,
    EyeStyle,
    HairColor,
    HairStyle,
    HeadType,
    IrisColor,
    MouthStyle,
)
from src.interactive.chat_console import ChatConsole, SkinCommandHandler
from src.interactive.skin_commands import COMMAND_TREE, ROOT_COMMANDS, SKIN_COMMANDS


@pytest.fixture
def model():
    m = CharacterModel(customization=AvatarCustomization(head_type=HeadType.ROUNDED), create_mesh=False)
    yield m
    m.delete()


def run(handler, line):
    return handler.execute(line, run_async=False)


def test_only_skin_help_and_spin_are_root_commands():
    assert sorted(COMMAND_TREE) == ["ajuda", "girar", "skin"]
    handler = SkinCommandHandler(character_model=None)
    for old in ("/top sweater", "/eyes blue", "/import 9240757332", "/cabelo rosa", "/manga largura 1.1", "/cintura alta"):
        ok, msg, _ = run(handler, old)
        assert not ok and "/ajuda" in msg


def test_every_skin_command_has_usage_and_a_unique_name():
    names = [n for c in SKIN_COMMANDS for n in c.names] + [n for c in ROOT_COMMANDS for n in c.names]
    assert len(names) == len(set(names))
    assert all(c.usage.startswith("/skin " + c.names[0]) for c in SKIN_COMMANDS)


def test_appearance_commands_in_portuguese_and_english(model):
    h = SkinCommandHandler(character_model=model)
    assert run(h, "/skin olhos vermelho")[0] and model.customization.iris_color == IrisColor.RED
    assert run(h, "/skin eyes green")[0] and model.customization.iris_color == IrisColor.GREEN
    assert run(h, "/skin olhos piscando")[0] and model.customization.eye_style == EyeStyle.ANIME_WINK
    assert run(h, "/skin olhos classico")[0] and model.customization.eye_style == EyeStyle.CLASSIC
    assert run(h, "/skin olhos azul")[0] and model.customization.eye_style == EyeStyle.ANIME  # a cor volta ao anime
    assert run(h, "/skin boca gato")[0] and model.customization.mouth_style == MouthStyle.CAT
    assert run(h, "/skin mouth smile")[0] and model.customization.mouth_style == MouthStyle.SMILE
    assert run(h, "/skin pele bronzeada")[0]
    assert run(h, "/skin tone dark")[0]
    assert run(h, "/skin cabeca quadrada")[0] and model.customization.head_type == HeadType.BLOCKY
    assert run(h, "/skin corpo feminino")[0] and model.customization.body_type == BodyType.FEMALE
    assert run(h, "/skin body male")[0] and model.customization.body_type == BodyType.MALE
    assert not run(h, "/skin olhos arcoiris")[0]
    assert not run(h, "/skin corpo")[0]


def test_hair_color_style_id_and_adjustments(model):
    h = SkinCommandHandler(character_model=model)
    assert run(h, "/skin cabelo rosa")[0] and model.customization.hair_color == HairColor.PINK
    assert run(h, "/skin hair blonde")[0] and model.customization.hair_color == HairColor.BLONDE
    assert run(h, "/skin cabelo careca")[0] and model.customization.hair_style == HairStyle.BALD and model.hair_id == "none"
    assert run(h, "/skin cabelo padrao")[0] and model.customization.hair_style == HairStyle.ANIME_LONG
    ok, msg, _ = run(h, "/skin cabelo 131607970996365")
    assert ok and "Cabelo 3D" in msg and model.hair_id == 131607970996365
    assert run(h, "/skin cabelo posicao y 2cm")[0] and model.hair_offset_y == pytest.approx(0.02)
    assert run(h, "/skin cabelo posicao y +1cm")[0] and model.hair_offset_y == pytest.approx(0.03)
    assert run(h, "/skin cabelo posicao 0 0 -1cm")[0] and model.hair_offset_z == pytest.approx(-0.01)
    assert run(h, "/skin cabelo escala 1.1")[0] and model.hair_scale_y == pytest.approx(1.1)
    assert run(h, "/skin cabelo escala x 90%")[0] and model.hair_scale_x == pytest.approx(0.9)
    assert run(h, "/skin cabelo reset")[0] and model.hair_offset_y == 0 and model.hair_scale_x == 1
    assert run(h, "/skin cabelo")[0]  # mostra o estado
    assert not run(h, "/skin cabelo posicao y")[0]


def test_clothing_slots(model):
    h = SkinCommandHandler(character_model=model)
    assert run(h, "/skin top boxy")[0] and model.top_id == 89475537632859
    assert run(h, "/skin top 9240757332")[0] and model.top_id == 9240757332
    assert run(h, "/skin calca skater")[0] and model.bottom_id == 137146416353285
    assert run(h, "/skin pants jeans")[0] and model.bottom_id == 109837605892174
    assert run(h, "/skin arma katana")[0] and model.tool_id == 12187348
    assert run(h, "/skin tirar arma")[0] and model.tool_id is None
    assert run(h, "/skin tirar top")[0] and model.top_id is None
    assert run(h, "/skin top none")[0]
    assert not run(h, "/skin top nao_existe")[0]
    ok, msg, _ = run(h, "/skin roupas")
    assert ok and "Calça" in msg


def test_remove_everything_keeps_the_hair(model):
    h = SkinCommandHandler(character_model=model)
    run(h, "/skin top boxy")
    hair = model.hair_id
    assert run(h, "/skin tirar tudo")[0]
    assert model.top_id is None and model.bottom_id is None and model.outer_top_id is None and model.shoes_id is None
    assert model.hair_id == hair
    assert not run(h, "/skin tirar")[0]


def test_wear_puts_each_item_in_its_place(model):
    h = SkinCommandHandler(character_model=model)
    ok, msg, _ = run(h, "/skin vestir")
    assert ok and "Uso" in msg
    assert run(h, "/skin vestir 109837605892174")[0] and model.bottom_id == 109837605892174
    assert run(h, "/skin vestir 9240757332")[0] and model.top_id == 9240757332
    url = "https://www.roblox.com/catalog/137146416353285/Vintage-Baggy-Skater-Pants-Light-Blue"
    assert run(h, f"/skin vestir {url}")[0] and model.bottom_id == 137146416353285
    assert run(h, "/skin vestir boxy")[0] and model.top_id == 89475537632859
    assert run(h, "/skin vestir 12187348")[0] and model.tool_id == 12187348
    assert run(h, "/skin wear 131607970996365")[0] and model.hair_id == 131607970996365
    assert run(h, "/skin import skater")[0] and model.bottom_id == 137146416353285
    ok, msg, _ = run(h, "/skin vestir item_que_nao_existe")
    assert not ok and "inválido" in msg
    assert not run(SkinCommandHandler(character_model=None), "/skin vestir 9240757332")[0]


def test_jacket_and_shoes():
    calls = []
    m = SimpleNamespace(outer_top_id=None, outer_top_gap_mm=0.0, outer_top_pull_mm=15.0, shoes_id=None,
                        reload=lambda: calls.append("reload"), update_customization=lambda **kw: calls.append(kw))
    h = SkinCommandHandler(character_model=m)
    assert run(h, "/skin jaqueta 72628400373948")[0] and calls[-1] == {"outer_top_id": 72628400373948}
    assert run(h, "/skin jaqueta folga 6")[0] and m.outer_top_gap_mm == 6.0 and calls[-1] == "reload"
    assert run(h, "/skin jacket puxar 20mm")[0] and m.outer_top_pull_mm == 20.0
    assert not run(h, "/skin jaqueta folga 80")[0]
    assert run(h, "/skin jaqueta none")[0] and m.outer_top_id is None
    assert run(h, "/skin sapato 101914651386350,131149613284268")[0]
    assert calls[-1] == {"shoes_id": "101914651386350,131149613284268"}
    assert not run(h, "/skin sapato tenis")[0]
    assert run(h, "/skin shoes none")[0] and m.shoes_id is None


def test_presets_and_reset_keep_the_body(model):
    h = SkinCommandHandler(character_model=model)
    run(h, "/skin corpo feminino")
    assert run(h, "/skin preset gato_loiro")[0]
    assert model.customization.mouth_style == MouthStyle.CAT and model.customization.body_type == BodyType.FEMALE
    assert run(h, "/skin preset cavaleiro")[0] and model.tool_id == 12187348
    assert run(h, "/skin reset")[0]
    assert model.customization.mouth_style == MouthStyle.ANIME_ORIGINAL and model.customization.body_type == BodyType.FEMALE
    assert not run(h, "/skin preset nao_existe")[0]


def test_help_lists_groups_and_explains_one_command():
    h = SkinCommandHandler(character_model=None)
    ok, msg, _ = run(h, "/ajuda")
    assert ok and "Aparência" in msg and "/skin vestir" in msg and "/girar" in msg
    ok, msg, _ = run(h, "/help cabelo")
    assert ok and msg.startswith("[Ajuda] /skin cabelo") and "hair" in msg
    ok, msg, _ = run(h, "/ajuda skin top")
    assert ok and "/skin top" in msg
    assert not run(h, "/ajuda voar")[0]


def test_spin_only_in_the_viewer():
    state = {"active": False}
    h = SkinCommandHandler(character_model=None, turntable_state=state)
    assert run(h, "/girar")[0] and state["active"] is True
    assert run(h, "/spin off")[0] and state["active"] is False
    assert not run(SkinCommandHandler(character_model=None), "/girar")[0]


def test_autocomplete_follows_the_command_table():
    import glfw
    chat = ChatConsole(create_gl=False)
    chat.open("/")
    assert chat.suggestions == ["/ajuda", "/girar", "/skin"]
    chat.handle_char(ord("s"))
    assert chat.suggestions == ["/skin"] and chat.ghost_text == "kin "
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin "
    assert {"olhos", "boca", "cabelo", "vestir", "top", "calca", "tirar"} <= set(chat.suggestions)
    assert "eyes" not in chat.suggestions  # os apelidos não poluem a lista
    chat.handle_char(ord("o"))
    assert chat.suggestions == ["olhos", "olho", "orelha"]  # os dois olhos, ou um só
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == "/skin olhos "
    assert "azul" in chat.suggestions and "vermelho" in chat.suggestions


def test_autocomplete_tab_cycles_and_reaches_nested_options():
    import glfw
    chat = ChatConsole(create_gl=False)
    chat.open("/skin olhos ")
    first, second = chat.suggestions[0], chat.suggestions[1]
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == f"/skin olhos {first}"
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert chat.input_text == f"/skin olhos {second}"
    chat.handle_key(glfw.KEY_TAB, glfw.PRESS, glfw.MOD_SHIFT)
    assert chat.input_text == f"/skin olhos {first}"
    chat.open("/skin cabelo posicao ")
    assert chat.suggestions == ["x", "y", "z"]
    chat.open("/skin cabelo posicao y ")
    assert "+1cm" in chat.suggestions
    chat.open("/skin vestir ")
    assert "sweater" in chat.suggestions and "skater" in chat.suggestions


def test_chat_console_mouse_click_chip():
    chat = ChatConsole(create_gl=False)
    chat.open("/skin ")
    chat.suggestions = ["olhos", "boca", "cabelo"]
    chat.suggestion_chips = [("olhos", 70, 500, 110, 524), ("boca", 116, 500, 160, 524)]
    assert chat.handle_mouse_click(125, 510) is True
    assert chat.input_text == "/skin boca "


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


def test_chat_console_clipboard_shortcuts(monkeypatch):
    """Verifica se Ctrl+V cola texto da área de transferência e Ctrl+C / Ctrl+A funcionam."""
    import glfw

    chat = ChatConsole(command_handler=None, create_gl=False)
    chat.open("/skin vestir ")

    # Mock da área de transferência com ID copiado do Roblox
    sample_id = "110437430397470"
    monkeypatch.setattr(chat, "_get_clipboard_string", lambda: sample_id)

    copied_buffer = []
    monkeypatch.setattr(chat, "_set_clipboard_string", lambda t: copied_buffer.append(t))

    # 1. Pressiona Ctrl+V
    consumed = chat.handle_key(glfw.KEY_V, glfw.PRESS, glfw.MOD_CONTROL)
    assert consumed is True
    assert chat.input_text == f"/skin vestir {sample_id}"
    assert chat.cursor_pos == len(f"/skin vestir {sample_id}")

    # 2. Ignora caractere de controle emitido pelo Windows durante Ctrl+V (codepoint 22 - SYN)
    consumed_char = chat.handle_char(22)
    assert consumed_char is True
    assert chat.input_text == f"/skin vestir {sample_id}"  # Não poluiu o texto

    # 3. Pressiona Ctrl+C
    consumed = chat.handle_key(glfw.KEY_C, glfw.PRESS, glfw.MOD_CONTROL)
    assert consumed is True
    assert copied_buffer == [f"/skin vestir {sample_id}"]

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


def test_busy_status_covers_imports_and_background_builds():
    """The loading badge shows for a running import and while the character is rebuilt."""
    model = CharacterModel(create_mesh=False)
    handler = SkinCommandHandler(character_model=model)
    assert handler.busy_status == ""

    model._dirty = True
    model.loading_status = "Ajustando roupas ao corpo..."
    assert handler.busy_status == "Ajustando roupas ao corpo..."

    handler.is_importing = True
    handler.import_status = "Importando 123..."
    assert handler.busy_status == "Importando 123..."

    chat = ChatConsole(command_handler=handler, create_gl=False)
    assert chat._generate_hud_image(800, 600, []) is not None
    model.delete()


def test_async_model_defers_reloads_to_poll():
    """With async loading a reload only marks the model; nothing is built on the caller's thread."""
    model = CharacterModel(create_mesh=False)
    model.create_mesh, model.async_loading = True, True
    model.reload()
    assert model.is_loading and model.parts == []
    assert model.loading_status
