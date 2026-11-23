from src.editor.export_dialog import ExportDialog


def test_export_dialog_name_and_path_are_live():
    dialog = ExportDialog(create_gl=False)
    dialog.open("Casa do João", (7, 7, 7), 123, 4)
    assert dialog.is_open and not dialog.done
    assert dialog.filename == "casa_do_joao.json"
    assert dialog.path.endswith("saves/objetos/casa_do_joao.json")
    dialog.handle_char(ord("X"))
    assert dialog.name == "X"
    assert dialog.filename == "x.json"


def test_export_dialog_shortcuts():
    import glfw

    dialog = ExportDialog(create_gl=False)
    dialog.open("casa")
    assert dialog.handle_key(glfw.KEY_BACKSPACE, 0) is None
    assert dialog.handle_key(glfw.KEY_ESCAPE, 0) == "cancel"
    dialog.open("casa")
    assert dialog.handle_key(glfw.KEY_ENTER, 0) == "export"
    dialog.mark_done("/tmp/casa.json")
    assert dialog.done and dialog.handle_key(glfw.KEY_ENTER, 0) == "continue"


def test_export_dialog_scaled_hit_test():
    dialog = ExportDialog(create_gl=False)
    dialog.open("casa")
    dialog._scale = 0.5
    dialog._origin = (100.0, 50.0)
    assert dialog.local_point(100 + 300 * 0.5, 50 + 150 * 0.5) == (300.0, 150.0)
    assert dialog.local_point(0, 0) is None
