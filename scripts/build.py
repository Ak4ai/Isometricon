#!/usr/bin/env python3
"""Script utilitário unificado para compilação multiplataforma local do Isometricon."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "src", "main.py")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")


def get_version() -> str:
    """Obtém a versão base do projeto a partir do VERSION.txt."""
    version_file = os.path.join(PROJECT_ROOT, "VERSION.txt")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    return "0.1.0"


def clean() -> None:
    """Remove pastas de compilação anteriores."""
    print("🧹 Limpando diretórios temporários (build/, dist/, *.spec)...")
    for d in [BUILD_DIR, DIST_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)

    for item in os.listdir(PROJECT_ROOT):
        if item.endswith(".spec"):
            try:
                os.remove(os.path.join(PROJECT_ROOT, item))
            except Exception:
                pass
    print("✨ Limpeza concluída com sucesso.\n")


def ensure_pyinstaller() -> None:
    """Garante que o PyInstaller está disponível."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("📦 Instalando PyInstaller no ambiente Python...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)


def build_windows(version: str, onefile: bool = False, make_zip: bool = True) -> None:
    """Compila o executável do Windows localmente."""
    print("=" * 65)
    print(f"🪟 Compilando Isometricon v{version} para Windows...")
    print("=" * 65)

    ensure_pyinstaller()
    os.chdir(PROJECT_ROOT)

    # 1. Build Portable (OneDir)
    portable_name = f"Isometricon-v{version}"
    cmd_portable = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onedir",
        "--add-data",
        f"{ASSETS_DIR};assets",
        "--name",
        portable_name,
        MAIN_SCRIPT,
    ]

    start_time = time.time()
    subprocess.run(cmd_portable, check=True)

    out_folder = os.path.join(DIST_DIR, portable_name)
    print(f"✅ Executável Portable gerado em: {out_folder}")

    if make_zip:
        zip_path = os.path.join(DIST_DIR, f"{portable_name}-Windows-Portable")
        print(f"📦 Criando arquivo compactado: {zip_path}.zip...")
        shutil.make_archive(zip_path, "zip", out_folder)
        print(f"🎉 Pacote Zip criado: {zip_path}.zip")

    # 2. Build Standalone Installer (OneFile) se solicitado
    if onefile:
        installer_name = f"Isometricon-v{version}-Windows-Installer"
        print(f"\n💿 Compilando versão Standalone OneFile ({installer_name}.exe)...")
        cmd_onefile = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconsole",
            "--onefile",
            "--add-data",
            f"{ASSETS_DIR};assets",
            "--name",
            installer_name,
            MAIN_SCRIPT,
        ]
        subprocess.run(cmd_onefile, check=True)
        print(f"✅ Instalador Standalone gerado em: {os.path.join(DIST_DIR, installer_name + '.exe')}")

    elapsed = time.time() - start_time
    print(f"\n⚡ Compilação para Windows concluída em {elapsed:.1f}s!\n")


def build_linux(version: str, make_tar: bool = True) -> None:
    """Compila o executável do Linux."""
    current_os = platform.system()

    if current_os == "Linux":
        print("=" * 65)
        print(f"🐧 Compilando Isometricon v{version} nativamente no Linux...")
        print("=" * 65)

        ensure_pyinstaller()
        os.chdir(PROJECT_ROOT)

        portable_name = f"Isometricon-v{version}-linux"
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onedir",
            "--add-data",
            f"{ASSETS_DIR}:assets",
            "--name",
            "isometricon",
            MAIN_SCRIPT,
        ]

        start_time = time.time()
        subprocess.run(cmd, check=True)

        out_folder = os.path.join(DIST_DIR, "isometricon")
        print(f"✅ Binário Linux gerado em: {out_folder}")

        if make_tar:
            tar_path = os.path.join(DIST_DIR, f"Isometricon-v{version}-Linux-Portable")
            print(f"📦 Criando arquivo compactado: {tar_path}.tar.gz...")
            shutil.make_archive(tar_path, "gztar", out_folder)
            print(f"🎉 Pacote Linux criado: {tar_path}.tar.gz")

        elapsed = time.time() - start_time
        print(f"\n⚡ Compilação para Linux concluída em {elapsed:.1f}s!\n")

    elif current_os == "Windows":
        print("=" * 65)
        print(f"🐧 Compilando Isometricon v{version} para Linux a partir do Windows...")
        print("=" * 65)

        # Verificar se WSL está disponível
        has_wsl = False
        try:
            wsl_check = subprocess.run(["wsl", "uname"], capture_output=True, text=True, check=False)
            if wsl_check.returncode == 0 and "Linux" in wsl_check.stdout:
                has_wsl = True
        except Exception:
            pass

        if has_wsl:
            print("🚀 WSL detectado! Executando compilação Linux dentro do subsistema...")
            wsl_proj_path = subprocess.run(
                ["wsl", "wslpath", "-a", PROJECT_ROOT.replace("\\", "/")],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            wsl_cmd = (
                f"cd '{wsl_proj_path}' && "
                "pip install -q -r requirements.txt pyinstaller && "
                "pyinstaller --onedir --add-data 'assets:assets' --name 'isometricon' src/main.py"
            )
            subprocess.run(["wsl", "bash", "-c", wsl_cmd], check=True)

            out_folder = os.path.join(DIST_DIR, "isometricon")
            if make_tar and os.path.exists(out_folder):
                tar_path = os.path.join(DIST_DIR, f"Isometricon-v{version}-Linux-Portable")
                shutil.make_archive(tar_path, "gztar", out_folder)
                print(f"🎉 Pacote Linux gerado via WSL: {tar_path}.tar.gz")
        else:
            print("⚠️  Aviso: O PyInstaller precisa de um ambiente Linux para compilar binários ELF com OpenGL.")
            print("💡 Como compilar para Linux no Windows:")
            print("   1. Instale o WSL digitando: wsl --install")
            print("   2. Ou envie suas alterações para o GitHub, onde o GitHub Actions compila automaticamente.")
            print("      (Acesse https://github.com/Ak4ai/Isometricon/actions)")


def main() -> None:
    """Ponto de entrada do script de build unificado."""
    parser = argparse.ArgumentParser(
        description="Isometricon - Script Unificado de Compilação Multiplataforma",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--windows", action="store_true", help="Força a compilação para Windows (.exe)")
    parser.add_argument("--linux", action="store_true", help="Força a compilação para Linux (ELF/tar.gz)")
    parser.add_argument("--all", action="store_true", help="Compila para Windows e Linux simultaneamente")
    parser.add_argument("--onefile", action="store_true", help="Gera também executável standalone OneFile")
    parser.add_argument("--clean", action="store_true", help="Limpa as pastas build/ e dist/ antes de compilar")
    parser.add_argument("--no-zip", action="store_true", help="Não comprime os binários em arquivos .zip/.tar.gz")

    args = parser.parse_args()

    if args.clean:
        clean()
        if not (args.windows or args.linux or args.all):
            return

    version = get_version()
    current_os = platform.system()
    make_zip = not args.no_zip

    if args.all:
        build_windows(version, onefile=args.onefile, make_zip=make_zip)
        build_linux(version, make_tar=make_zip)
    elif args.windows:
        build_windows(version, onefile=args.onefile, make_zip=make_zip)
    elif args.linux:
        build_linux(version, make_tar=make_zip)
    else:
        # Detecção automática do SO
        if current_os == "Windows":
            build_windows(version, onefile=args.onefile, make_zip=make_zip)
        elif current_os == "Linux":
            build_linux(version, make_tar=make_zip)
        else:
            print(f"Sistema operacional detectado: {current_os}. Compilando modo padrão...")
            build_windows(version, onefile=args.onefile, make_zip=make_zip)


if __name__ == "__main__":
    main()
