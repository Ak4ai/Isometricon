"""Valida o pacote Linux extraido em diretorio isolado com OpenGL."""
from argparse import ArgumentParser
import json
import os
from pathlib import Path
import shutil
import tempfile

from smoke_windows_package import WORLD_NAME, render


def validate(executable: Path, work_dir: Path) -> None:
    internal = executable.parent / "_internal"
    required = [
        internal / "VERSION.txt",
        internal / "assets" / "shaders" / "cloud.frag",
    ]
    if (any(not path.is_file() for path in required)
            or not list(internal.glob("glfw/**/*.so*"))
            or not list(internal.glob("DracoPy*.so"))):
        raise RuntimeError("Recursos ou dependencias obrigatorios ausentes do pacote Linux.")

    data_dir = work_dir / "data"
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "_PYI", "PYGLFW", "PYOPENGL"))
        and key not in {"VIRTUAL_ENV", "LD_LIBRARY_PATH", "LD_PRELOAD"}
    }
    env.update(PATH="/usr/bin:/bin", ISOMETRICON_DATA_DIR=str(data_dir),
               PYINSTALLER_RESET_ENVIRONMENT="1", LIBGL_ALWAYS_SOFTWARE="1")
    render(executable, work_dir, env, "menu", "--menu", "--frames=2")
    render(executable, work_dir, env, "create", "--package-smoke-world=create", "--frames=12")

    saves = list((data_dir / "saves" / "worlds").glob("*.json"))
    if len(saves) != 1:
        raise RuntimeError(f"Esperava um mundo salvo, encontrou {len(saves)}.")
    written = saves[0].read_bytes()
    world = json.loads(written)
    if (world.get("name") != WORLD_NAME or world.get("seed") != 42
            or world.get("id") != saves[0].stem or not world.get("position")
            or world.get("played", 0) <= 0):
        raise RuntimeError("O mundo salvo nao contem o estado esperado.")

    render(executable, work_dir, env, "reopen", "--package-smoke-world=reopen", "--frames=12")
    if saves[0].read_bytes() != written:
        raise RuntimeError("A reabertura de diagnostico modificou o save.")
    print("Menu, mundo 3D e persistencia validados fora do checkout.")


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="isometricon-linux-smoke-") as temporary:
        root = Path(temporary)
        package = root / "package"
        work = root / "work"
        package.mkdir()
        work.mkdir()
        shutil.unpack_archive(args.archive.resolve(), package, "gztar")
        validate(package / "isometricon" / "isometricon", work)


if __name__ == "__main__":
    main()
