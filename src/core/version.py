"""Sistema de Versionamento Automático e Checagem de Sincronização com o GitHub."""

from dataclasses import dataclass
import json
import os
import subprocess
import threading
from typing import Optional
import urllib.error
import urllib.request

def _load_base_version() -> str:
    """Lê a versão base a partir do arquivo VERSION.txt (ou VERSION) na raiz do projeto."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for filename in ["VERSION.txt", "VERSION", "version.txt"]:
        version_file = os.path.join(root_dir, filename)
        if os.path.exists(version_file):
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    ver = f.read().strip()
                    if ver:
                        return ver
            except Exception:
                pass
    return "0.1.0"


BASE_VERSION = _load_base_version()
DEFAULT_REPO = "Ak4ai/Isometricon"
DEFAULT_BRANCH = "main"



@dataclass
class VersionInfo:
    """Estrutura com as informações de build, commit e sincronização."""

    base_version: str = BASE_VERSION
    commit_hash: str = "unknown"
    branch: str = "unknown"
    is_dirty: bool = False
    commit_date: str = ""
    sync_status: str = "checking"  # "checking", "synced", "outdated", "offline", "modified"
    remote_commit: Optional[str] = None
    remote_message: Optional[str] = None

    @property
    def full_version(self) -> str:
        """Retorna versão completa formatada: ex: v0.1.0-d5bb890* (main)."""
        dirty_flag = "*" if self.is_dirty else ""
        return f"v{self.base_version}-{self.commit_hash}{dirty_flag} ({self.branch})"

    @property
    def status_display(self) -> str:
        """Retorna texto legível com emoji do status de sincronização."""
        if self.sync_status == "synced":
            return "✅ Sincronizado com origin/main"
        elif self.sync_status == "outdated":
            rem = self.remote_commit[:7] if self.remote_commit else "novo"
            return f"⚠️ Desatualizado (GitHub está em {rem} - faça git pull)"
        elif self.sync_status == "modified":
            return "📝 Modificado localmente (arquivos não commitados)"
        elif self.sync_status == "offline":
            return "🔌 Offline (não foi possível consultar o GitHub)"
        elif self.sync_status == "checking":
            return "🔄 Checando sincronização com o GitHub..."
        return "ℹ️ Status desconhecido"


def _run_git_cmd(args: list[str], cwd: Optional[str] = None) -> Optional[str]:
    """Executa um comando git com timeout e tratamento seguro de exceção."""
    try:
        if cwd is None:
            cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_local_version_info() -> VersionInfo:
    """Extrai informações da versão e commit a partir do repositório Git local."""
    info = VersionInfo()

    # 1. Commit Hash (short)
    commit = _run_git_cmd(["rev-parse", "--short", "HEAD"])
    if commit:
        info.commit_hash = commit

    # 2. Branch atual (com fallback para variáveis de ambiente de CI como GitHub Actions)
    ci_branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if ci_branch:
        info.branch = ci_branch
    else:
        branch = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])
        if branch:
            info.branch = branch

    # 3. Verificar se há alterações não commitadas (dirty)
    status = _run_git_cmd(["status", "--porcelain"])
    if status is not None:
        info.is_dirty = len(status.strip()) > 0

    # 4. Data do último commit
    date = _run_git_cmd(["log", "-1", "--format=%cd", "--date=short"])
    if date:
        info.commit_date = date

    return info


def _fetch_remote_commit(info: VersionInfo, repo: str, branch: str) -> None:
    """Consulta a API pública do GitHub em segundo plano para comparar hashes."""
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    headers = {
        "User-Agent": "Isometricon-Engine-Client",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                remote_sha = data.get("sha", "")
                remote_short_sha = remote_sha[: len(info.commit_hash)] if remote_sha else ""

                info.remote_commit = remote_sha
                if data.get("commit", {}).get("message"):
                    info.remote_message = data["commit"]["message"].splitlines()[0]

                # Comparação dos hashes
                if info.commit_hash == "unknown":
                    info.sync_status = "offline"
                elif info.is_dirty:
                    info.sync_status = "modified"
                elif (
                    info.commit_hash.lower() == remote_short_sha.lower()
                    or remote_sha.startswith(info.commit_hash)
                ):
                    info.sync_status = "synced"
                else:
                    info.sync_status = "outdated"
            else:
                info.sync_status = "offline"
    except (urllib.error.URLError, TimeoutError, Exception):
        info.sync_status = "offline"


def start_github_sync_check(
    info: VersionInfo,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
) -> threading.Thread:
    """Inicia a checagem com o GitHub em uma thread assíncrona (não-bloqueante)."""
    thread = threading.Thread(
        target=_fetch_remote_commit,
        args=(info, repo, branch),
        name="GitHubSyncChecker",
        daemon=True,
    )
    thread.start()
    return thread
