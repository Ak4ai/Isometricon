"""Acesso ao catalogo distribuido e aos arquivos de modelos gerados pelo jogo."""

import os
from pathlib import Path

from src.core.paths import RESOURCE_ROOT, data_root


RESOURCE_MODELS = RESOURCE_ROOT / "assets" / "models"
GENERATED_MODELS = data_root() / "assets" / "models"


def model_file(*parts: str) -> str:
    """Le o arquivo local se existir, com fallback para o recurso distribuido."""
    local = GENERATED_MODELS.joinpath(*parts)
    if local.is_file():
        return os.fspath(local)
    bundled = RESOURCE_MODELS.joinpath(*parts)
    return os.fspath(bundled if bundled.is_file() else local)


def clothing_files(pattern: str) -> list[Path]:
    """Lista os itens dos dois catalogos, usando uma so entrada por nome de arquivo."""
    files = {path.name: path for path in (RESOURCE_MODELS / "clothing").glob(pattern)}
    if GENERATED_MODELS != RESOURCE_MODELS:
        files.update({path.name: path for path in (GENERATED_MODELS / "clothing").glob(pattern)})
    return [files[name] for name in sorted(files)]


def garment_cache_dir(source: str, folder: str) -> str:
    """Grava subprodutos de malhas distribuidas na pasta do usuario."""
    directory = Path(source).parent
    if directory == RESOURCE_MODELS / "clothing":
        directory = GENERATED_MODELS / "clothing"
    return os.fspath(directory / folder)
