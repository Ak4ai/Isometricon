"""Testes unitários para o módulo de versionamento e sincronização."""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.version import VersionInfo, get_local_version_info


def test_get_local_version_info():
    """Testa a extração de dados do Git local."""
    info = get_local_version_info()
    assert isinstance(info, VersionInfo)
    assert info.base_version == "0.1.0"
    assert info.commit_hash != "unknown"
    assert len(info.commit_hash) >= 4
    assert isinstance(info.branch, str) and len(info.branch) > 0
    assert "v0.1.0-" in info.full_version


def test_version_info_status_display():
    """Testa os textos de status de sincronização."""
    info = VersionInfo(commit_hash="abc1234", sync_status="synced")
    assert "✅" in info.status_display

    info.sync_status = "outdated"
    info.remote_commit = "def5678"
    assert "⚠️" in info.status_display
    assert "def5678" in info.status_display

    info.sync_status = "modified"
    assert "📝" in info.status_display

    info.sync_status = "offline"
    assert "🔌" in info.status_display
