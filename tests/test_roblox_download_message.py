"""Quando o Roblox não entrega o item, o chat diz o motivo (e não um erro de None)."""
import io
import urllib.error

import pytest

from scripts import import_roblox_clothing as roblox


def test_sem_cookie_pede_o_env():
    text = roblox.download_failure_message(123456, (401, "HTTP Error 401"), cookie=None)
    assert "123456" in text and ".env" in text and "ROBLOSECURITY" in text


def test_cookie_recusado_diz_que_venceu():
    text = roblox.download_failure_message(123456, (401, "HTTP Error 401"), cookie="abc")
    assert "venceu" in text and ".env" in text


def test_outros_motivos():
    assert "não existe" in roblox.download_failure_message(7, (404, "x"), cookie="abc")
    assert "esperar" in roblox.download_failure_message(7, (429, "x"), cookie="abc")
    assert "internet" in roblox.download_failure_message(7, (None, "timed out"), cookie="abc")


def test_o_download_guarda_o_motivo(monkeypatch):
    def refuse(request):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(roblox.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(roblox, "load_roblox_cookie", lambda: None)
    assert roblox.fetch_roblox_asset(85579762519031) is None
    assert roblox.last_fetch_error[0] == 401
    assert ".env" in roblox.download_failure_message(85579762519031)


def test_fetch_asset_levanta_o_motivo_e_nao_none(monkeypatch, tmp_path):
    from src.clothing import wear_engine

    class Details:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"Name": "Camisa", "AssetTypeId": 11}'

    monkeypatch.setattr(wear_engine.urllib.request, "urlopen", lambda *a, **k: Details())
    monkeypatch.setattr(wear_engine, "fetch_roblox_asset", lambda asset_id: None)
    monkeypatch.setattr(wear_engine, "download_failure_message", lambda asset_id: f"motivo claro {asset_id}")
    engine = wear_engine.RobloxWearEngine.__new__(wear_engine.RobloxWearEngine)
    with pytest.raises(RuntimeError, match="motivo claro 99999"):
        engine.fetch_asset(99999, output_dir=str(tmp_path))
