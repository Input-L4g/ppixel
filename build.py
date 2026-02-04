import subprocess as sb
import sys
import platform
from pathlib import Path
from shutil import rmtree

SCRIPT_NAME = "run.py"
CORE_NAME = "image-cli"
APP_NAME = "image-cli"

COMMON_ARGS = [
    SCRIPT_NAME,
    "--onefile",  # Um único executável
    "--console",  # IMPORTANTE: Mantém o console (padrão para CLI)
    f"--name={APP_NAME}",  # Nome do executável
    "--log-level=WARN",
    "--clean",  # Limpa cache antes de buildar,
    "--noconfirm",
]

PLATFORM_ARGS: dict[str, list[str]] = {
    "Linux": [
        "--strip",  # Remove símbolos de debug
    ],
}

_TRASH_NAMES = ("./build", f"{CORE_NAME}.spec")

COMMON_ARGS.extend(PLATFORM_ARGS.get(platform.platform(), []))


def has_pyinstaller() -> bool:
    """Verifica se o Pyinstaller está instalado."""
    try:
        __import__("PyInstaller")
        return True
    except ImportError:
        return False


def get_installed_modules(error_ok: bool = False) -> list[str]:
    """Retorna uma lista do nomes dos módulos instalados."""

    def parse_freeze(freeze: str) -> list[str]:
        modules_name: list[str] = []
        for line in freeze.split("\n"):
            modules_name.append(line[: line.index("=")])
        return modules_name

    try:
        output = sb.run(["pip", "freeze"], capture_output=True, text=True, check=True)
        return parse_freeze(output.stdout)
    except sb.CalledProcessError:
        if error_ok:
            return []
        raise


def remove_module(module: str) -> bool:
    """Remove um módulo instalado pelo nome."""
    try:
        sb.check_call(["pip", "uninstall", module])
        return True
    except sb.CalledProcessError:
        return False


def install_pyinstaller() -> None:
    """Instala o Pyinstaller."""
    sb.call(["pip", "install", "pyinstaller"])


def _compile() -> None:
    """Compila o Pyinstaller."""
    sb.call(["pyinstaller", *COMMON_ARGS])


def remove_pyinstaller_trash():
    """Remove os arquivos"""
    for path in _TRASH_NAMES:
        path = Path(path).resolve()
        if path.is_dir():
            rmtree(path)
        else:
            path.unlink()


def build() -> None:
    """Compila o programa em um executável."""
    remove_modules: set[str] | None = None
    has_pyinstaller_installed = has_pyinstaller()
    if not has_pyinstaller_installed:
        print("Dependência não encontrada: 'Pyinstaller'")
        response = input("Deseja instala-la? (S/n)").lower()
        if response == "n":
            sys.exit(0)
        print("Instalando 'Pyinstaller'...")
        old_modules = get_installed_modules(True)
        install_pyinstaller()
        new_modules = get_installed_modules(True)
        remove_modules = set(new_modules) - set(old_modules)
    print("Iniciando compilação...")
    _compile()
    print("Compilação concluida!")
    if not has_pyinstaller_installed:
        response = input("Deseja excluir o Pyinstaller? (S/n)").lower()
        if response == "s":
            remove_module("pyinstaller")
            if remove_modules is not None:
                for module in remove_modules:
                    result = remove_module(module)
                    if not result:
                        print(f"Falha ao remover módulo: {module!r}")
    print("Removendo temporários...")
    remove_pyinstaller_trash()
    print(f"Verifique a pasta 'dist/{APP_NAME}', criada no mesmo diretório.")


build()
