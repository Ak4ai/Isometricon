from src.clothing import model_paths
from src.core import paths


def test_source_saves_stay_in_checkout(monkeypatch, tmp_path):
    monkeypatch.delenv("ISOMETRICON_DATA_DIR", raising=False)
    monkeypatch.setattr(paths.sys, "frozen", False, raising=False)
    monkeypatch.setattr(paths, "RESOURCE_ROOT", tmp_path)
    assert paths.saves_path("worlds") == tmp_path / "saves" / "worlds"


def test_frozen_windows_saves_ignore_extraction_path(monkeypatch, tmp_path):
    monkeypatch.delenv("ISOMETRICON_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "platform", "win32")
    for extraction in ("_internal", "_MEI123"):
        monkeypatch.setattr(paths, "RESOURCE_ROOT", tmp_path / extraction)
        assert paths.saves_path("worlds") == tmp_path / "profile" / "Isometricon" / "saves" / "worlds"


def test_app_data_override_isolates_worlds(monkeypatch, tmp_path):
    monkeypatch.setenv("ISOMETRICON_DATA_DIR", str(tmp_path))
    assert paths.saves_path("worlds") == tmp_path / "saves" / "worlds"


def test_clothing_resources_and_user_files_are_independent(monkeypatch, tmp_path):
    bundled = tmp_path / "bundle"
    generated = tmp_path / "user"
    monkeypatch.setattr(model_paths, "RESOURCE_MODELS", bundled)
    monkeypatch.setattr(model_paths, "GENERATED_MODELS", generated)
    relative = "clothing", "item_123456.rbxm"
    bundled_item = bundled.joinpath(*relative)
    bundled_item.parent.mkdir(parents=True)
    bundled_item.write_bytes(b"bundled")
    assert model_paths.model_file(*relative) == str(bundled_item)
    assert model_paths.garment_cache_dir(str(bundled_item), "wrap_cages") == str(generated / "clothing" / "wrap_cages")

    generated_item = generated.joinpath(*relative)
    generated_item.parent.mkdir(parents=True)
    generated_item.write_bytes(b"generated")
    assert model_paths.model_file(*relative) == str(generated_item)
    assert model_paths.clothing_files("*.rbxm") == [generated_item]

