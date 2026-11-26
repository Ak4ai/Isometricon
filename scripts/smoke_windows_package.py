"""Exercita os executaveis Windows fora do checkout, com dados novos e descartaveis."""

from argparse import ArgumentParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image


WORLD_NAME = "Isometricon package smoke"
MESA_LIBRARIES = ("opengl32.dll", "libgallium_wgl.dll")


def isolated_environment(data_dir: Path, mesa_dir: Path | None) -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "_PYI", "PYGLFW", "PYOPENGL"))
        and key not in {"VIRTUAL_ENV", "GALLIUM_DRIVER"}
    }
    system = Path(env["SYSTEMROOT"])
    search_paths = [system / "System32", system]
    if mesa_dir is not None:
        # O PyOpenGL acha opengl32.dll com ctypes.util.find_library, que consulta o PATH.
        search_paths.insert(0, mesa_dir)
    env["PATH"] = os.pathsep.join(map(str, search_paths))
    env["ISOMETRICON_DATA_DIR"] = str(data_dir)
    # Permite chamar o binario pelo smoke de outro pacote PyInstaller sem herdar sua extracao.
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    if mesa_dir is not None:
        env["GALLIUM_DRIVER"] = "llvmpipe"
    return env


def render(executable: Path, work_dir: Path, env: dict[str, str], label: str, *args: str) -> None:
    screenshot = work_dir / f"{label}.png"
    log_path = work_dir / f"{label}.log"
    command = [
        str(executable), "--gl-debug", f"--screenshot={screenshot}", *args,
    ]
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, cwd=work_dir, env=env, stdout=log, stderr=log)
        try:
            status = process.wait(timeout=120)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                # Em OneFile o bootloader tem um processo filho que tambem precisa encerrar.
                taskkill = Path(env["SYSTEMROOT"]) / "System32" / "taskkill.exe"
                subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, timeout=10, check=False)
            else:
                process.kill()
            process.wait(timeout=10)
            raise RuntimeError(f"{label}: aplicativo excedeu 120 s ({log_path})") from exc
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if status or not screenshot.is_file():
        raise RuntimeError(f"{label}: codigo {status}, imagem ausente ou falha\n{log_text[-3000:]}")
    with Image.open(screenshot) as rendered:
        rendered = rendered.convert("RGB")
        if not any(low < high for low, high in rendered.getextrema()):
            raise RuntimeError(f"{label}: quadro uniforme em {screenshot}")
    if env.get("GALLIUM_DRIVER") == "llvmpipe" and "llvmpipe" not in log_text.lower():
        raise RuntimeError(f"{label}: o processo nao usou o OpenGL por software esperado.\n{log_text[-3000:]}")
    print(f"{label}: quadro OpenGL capturado, processo encerrou com codigo 0.")


def validate(executable: Path, work_dir: Path, mesa_dir: Path | None) -> None:
    if mesa_dir is not None:
        for name in MESA_LIBRARIES:
            shutil.copy2(mesa_dir / name, executable.parent / name)
    data_dir = work_dir / "data"
    env = isolated_environment(data_dir, executable.parent if mesa_dir is not None else None)
    render(executable, work_dir, env, "menu", "--menu", "--frames=2")
    render(executable, work_dir, env, "create", "--package-smoke-world=create", "--frames=12")
    saves = list((data_dir / "saves" / "worlds").glob("*.json"))
    if len(saves) != 1:
        raise RuntimeError(f"Esperava um mundo salvo em {data_dir}, encontrou {len(saves)}.")
    written = saves[0].read_bytes()
    world = json.loads(written)
    if (world.get("name") != WORLD_NAME or world.get("seed") != 42 or world.get("id") != saves[0].stem
            or not world.get("position") or world.get("played", 0) <= 0):
        raise RuntimeError(f"O save {saves[0].name} nao tem o estado gravado ao fechar.")
    render(executable, work_dir, env, "reopen", "--package-smoke-world=reopen", "--frames=12")
    if saves[0].read_bytes() != written:
        raise RuntimeError("A reabertura de diagnostico modificou o save.")
    print(f"Persistencia validada entre processos para o mundo {world['id']}.")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("portable", type=Path, help="ZIP do pacote portatil.")
    parser.add_argument("onefile", type=Path, help="Executavel OneFile.")
    parser.add_argument("--mesa-dir", type=Path, help="DLLs de OpenGL por software para o runner de CI.")
    parser.add_argument("--evidence-dir", type=Path, help="Diretorio novo para reter capturas e saves de teste.")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("A verificacao exige Windows nativo.")

    with tempfile.TemporaryDirectory(prefix="isometricon-smoke-") as temp:
        output = args.evidence_dir.resolve() if args.evidence_dir else Path(temp) / "evidence"
        output.mkdir()
        portable = Path(temp) / "portable"
        standalone = Path(temp) / "standalone"
        standalone.mkdir()
        shutil.unpack_archive(args.portable, portable, "zip")
        standalone_exe = Path(shutil.copy2(args.onefile, standalone))
        mesa = args.mesa_dir.resolve() if args.mesa_dir else None
        for name, executable in (("portable", portable / "Isometricon" / "Isometricon.exe"),
                                 ("onefile", standalone_exe)):
            print(f"Verificando {name} a partir de uma pasta sem checkout ou Python.")
            work_dir = output / name
            work_dir.mkdir()
            validate(executable, work_dir, mesa)


if __name__ == "__main__":
    main()

