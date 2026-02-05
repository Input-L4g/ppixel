import subprocess as sb
import platform
from threading import Thread
from sys import exit as sys_exit, stdout
from shutil import rmtree
from pathlib import Path
from typing import Sequence, Callable, Any
from time import sleep
from importlib.metadata import distributions


class MessageCLI:
    """Representa um impressor de mensagens para TUI."""

    DEFAULT_LOADING_CHARS = [
        "\033[33m[|]\033[0m",
        "\033[33m[/]\033[0m",
        "\033[33m[-]\033[0m",
        "\033[33m[\\]\033[0m",
    ]

    def __init__(
        self,
        loading_chars: Sequence[str] | None = None,
        on_stop_char: str | None = None,
    ) -> None:
        self.loading_chars: Sequence[str] = (
            loading_chars if loading_chars is not None else self.DEFAULT_LOADING_CHARS
        )
        """Sequência de caracteres representando uma animação de LOADING."""
        self.on_stop_char: str = on_stop_char if on_stop_char is not None else ""
        """Caractere imprimido a frente de um LOADING quando stop é chamado."""
        self.loading_enable = False
        """Estado de ativo do LOADING."""
        self.output_cache: list[Any] = []
        """Cache de saídas registradas ao terminar o LOADING."""

    def during_loading(self, call: Callable, *args, **kwargs) -> None:
        """
        Executa um Callable durante um LOADING,
        parando o LOADING assim que o Callable finalizar.

        Esse Callable será mantido numa Thread até finalizar naturalmente.
        """

        def main(*args_, **kwargs_):
            return_ = call(*args_, **kwargs_)
            if len(self.output_cache) > 5:
                self.output_cache.pop(0)
            self.output_cache.append(return_)
            self.stop()

        t = Thread(target=main, args=args, kwargs=kwargs)
        t.start()

    @property
    def last_output(self) -> Any:
        """Retorna o valor da última saída após um LOADING."""
        return self.output_cache[-1]

    def stop(self):
        """Para o loading ativo."""
        if not self.loading_enable:
            raise RuntimeError("O LOADING não está ativo.")
        self.loading_enable = False
        print(self.on_stop_char)

    def change_loading_chars(self, new_chars: Sequence[str]) -> None:
        """Troca os caracteres de loading."""
        self.loading_chars = new_chars

    def change_on_stop_char(self, new_char: str) -> None:
        """Troca o caractere imprimido ao parar um LOADING."""
        self.on_stop_char = new_char

    def loading(
        self,
        *text: str,
        char_per_second: float = 3,
        call: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        **call_kwargs,
    ) -> None:
        """
        Imprime uma animação de loading.

        Para para-la, deve usar MessageCLI.stop().
        """
        if self.loading_enable:
            raise RuntimeError("O LOADING já está ativo.")
        self.loading_enable = True
        index = 0
        printed_text = " ".join(text)
        print(printed_text, end="")
        loading_column = len(printed_text) + 2
        called = False
        while self.loading_enable:
            if called is False and call is not None:
                called = True
                self.during_loading(call, *(args or ()), **call_kwargs)
            char = self.loading_chars[index]
            stdout.write(f"\r\033[{loading_column}G")
            stdout.write("\033[K")
            stdout.write(char)
            stdout.flush()
            index = (index + 1) % len(self.loading_chars)
            sleep(1 / char_per_second)

    @staticmethod
    def ask_check(*text: str) -> bool:
        """Imprime uma pergunta de S/n e retorna se foi aceita ou não."""
        ask = input(f"{" ".join(text)} (S/n): ").lower()
        if ask not in ["s", "n"]:
            return MessageCLI.ask_check(*text)
        return ask == "s"


def execute(*args: str) -> tuple[str, str | None]:
    """Executa um comando com subprocess e retorna as saídas."""
    try:
        output = sb.run(
            args,
            capture_output=True,
            text=True,
            check=True,
        )
        return output.stdout, output.stderr or None
    except sb.CalledProcessError as e:
        return e.stdout, e.stderr or None


class Builder:
    """Representa um Builder da aplicação."""

    SCRIPT_NAME = "run.py"
    APP_NAME = "ppixel"

    COMPILER = "pyinstaller"

    MODULES = ("pyinstaller", "pillow", "numpy")

    COMMON_ARGS: tuple[str, ...] = (
        SCRIPT_NAME,
        "--onefile",  # Um único executável
        "--console",  # IMPORTANTE: Mantém o console (padrão para CLI)
        f"--name={APP_NAME}",  # Nome do executável
        "--log-level=WARN",
        "--clean",  # Limpa cache antes de buildar,
        "--noconfirm",
    )

    PLATFORM_ARGS: dict[str, list[str]] = {
        "Linux": [
            "--strip",  # Remove símbolos de debug
        ],
    }

    _TRASH_NAMES = ("./build", f"{APP_NAME}.spec")

    COMMON_ARGS = (*COMMON_ARGS, *PLATFORM_ARGS.get(platform.platform(), []))

    def __init__(self, extra_args: tuple[str, ...] | None = None) -> None:
        self.args: tuple[str, ...] = self.COMMON_ARGS
        if extra_args:
            self.args = tuple(set(*self.args, *extra_args))
        self.msg = MessageCLI(on_stop_char="\033[32m[✓]\033[0m")

    def get_modules(self) -> tuple[str, ...]:
        """Retorna os módulos instalados no ambiente."""
        return tuple(m.metadata["Name"] for m in distributions())

    def has_module(self, module: str) -> bool:
        """Verifica se um módulo está instalado."""
        return module in self.get_modules()

    def install_module(self, module: str) -> tuple[str, str | None]:
        """Instala um módulo. Retorna a saída obtida: (Saída, Erro)"""
        return execute("python", "-m", "pip", "install", module)

    def remove_module(self, module: str) -> tuple[str, str | None]:
        """Remove um módulo."""
        return execute("python", "-m", "pip", "uninstall", module)

    def compile(self) -> tuple[str, str | None]:
        """Compila o programa com pyinstaller."""
        return execute(self.COMPILER, *self.args)

    def remove_trash(self) -> None:
        """Remove cache e lixos locais da compilação."""
        for trash in self._TRASH_NAMES:
            path = Path(trash)
            if path.is_dir():
                rmtree(path)
            else:
                path.unlink()

    def check_depencies(self) -> tuple[str, ...]:
        """Retornas os módulos que faltam para a execução."""
        return tuple(m for m in self.MODULES if not self.has_module(m))

    def build(self) -> None:
        """Inicia o build de compilação e dependências."""
        remove_modules: tuple[str, ...] | None = None
        self.msg.loading("Verificando dependências", call=self.check_depencies)
        missing_dependencies: tuple[str, ...] = self.msg.last_output
        if missing_dependencies:
            print(
                "Estão faltando as seguintes dependências:",
                ", ".join(missing_dependencies),
            )
            if not MessageCLI.ask_check("Deseja instala-las?"):
                sys_exit("Instalação de dependências recusada.")
            before = self.get_modules()
            for m in missing_dependencies:
                print(f"Instalando {m!r}")
                output = self.install_module(m)
                if output[1] is not None:
                    print(f"Falha ao instalar a dependência: {m!r}")
            print("Instalação de dependências concluidas.")
            remove_modules = tuple(set(self.get_modules()) - set(before)) or None

        self.msg.loading("Compilando arquivos", call=self.compile)
        output = self.msg.last_output
        err = output[1]
        if err is not None and not err[: err.index(":")].endswith("WARNING"):
            print("Um erro ocorreu durante a compilação:")
            sys_exit(err)

        if remove_modules is not None and MessageCLI.ask_check(
            "Dependências temporárias foram instaladas no processo.",
            "Deseja remove-las?",
        ):
            for module in remove_modules:
                output = self.remove_module(module)
                if output[1] is not None:
                    print(f"Falha ao remover a dependência: {module!r}")
            print("Processo finalizado.")

        self.msg.loading("Removendo resíduos de compilação", call=self.remove_trash)

        print("Compilação finalizada.")
        print(f"Executável em ./dist/{self.APP_NAME}")


if __name__ == "__main__":
    builder = Builder()
    builder.build()
