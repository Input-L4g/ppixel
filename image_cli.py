"""
FAZER A DOCUMENTAÇÃO
"""

from typing import TYPE_CHECKING, TypeAlias
from enum import Enum
from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentTypeError
from functools import lru_cache
from PIL.Image import open as open_image
from PIL.Image import registered_extensions, Image, Resampling
from PIL.ImageFile import ImageFile
from numpy import array, uint8

if TYPE_CHECKING:
    from numpy.typing import NDArray

    StrOrPathOrImageOrImageFile: TypeAlias = str | Path | ImageFile | Image
    ResizeTuple: TypeAlias = tuple[int, int]
    OptionalResizeTuple: TypeAlias = tuple[int | None, int | None]
    RGBColor: TypeAlias = tuple[int, int, int]


class ResizeImage:
    """
    Aplica resize em imagens.

    Suporta objetos do tipo ImageFile ou caminhos puros
    dos arquivos de imagem.
    """

    class Sample(Enum):
        """Um sample para resize."""

        NEAREST = Resampling.NEAREST
        BILINEAR = Resampling.BILINEAR
        BICUBIC = Resampling.BICUBIC
        LANCZOS = Resampling.LANCZOS
        BOX = Resampling.BOX
        HAMMING = Resampling.HAMMING

    @classmethod
    def resize_in_proportion(
        cls,
        size: "ResizeTuple",
        new_width: int | None = None,
        new_height: int | None = None,
    ) -> "ResizeTuple":
        w, h = size
        if new_width is not None and new_height is None:
            fator = new_width / w
        elif new_height is not None and new_width is None:
            fator = new_height / h
        else:
            raise ValueError(
                "Era esperado que new_width ou new_height fosse None e ao menos um fosse int: "
                f"{new_width = }, {new_height = }"
            )
        return int(fator * w), int(h * fator)

    @classmethod
    def _normalize_resize(
        cls,
        image_size: "ResizeTuple",
        resize: "OptionalResizeTuple | None" = None,
        maintain_proportion: bool = True,
    ) -> tuple[int, int]:
        if resize is not None:
            w = resize[0]
            h = resize[1]
            if maintain_proportion and any(v is None for v in resize):
                resize = cls.resize_in_proportion(image_size, w, h)
            else:
                resize = (w or image_size[0], h or image_size[1])
        else:
            resize = (image_size[0], image_size[1])
        return resize

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        resize: "OptionalResizeTuple | None" = None,
        maintain_proportion: bool = True,
        sample: Sample = Sample.BILINEAR,
    ) -> "Image":
        """Aplica resize no caminho de um arquivo de imagem."""
        img = open_image(path)
        return cls.from_image_file(img, resize, maintain_proportion, sample)

    @classmethod
    def from_image_file(
        cls,
        image: "ImageFile | Image",
        resize: "OptionalResizeTuple | None" = None,
        maintain_proportion: bool = True,
        sample: Sample = Sample.BICUBIC,
    ) -> "Image":
        """Aplica resize em objeto ImageFile."""
        return image.resize(
            cls._normalize_resize(image.size, resize, maintain_proportion),
            resample=sample.value,
        )

    @classmethod
    def resize(
        cls,
        image: "StrOrPathOrImageOrImageFile",
        resize: "OptionalResizeTuple | None" = None,
        maintain_proportion: bool = True,
        sample: Sample = Sample.BICUBIC,
    ) -> "Image":
        """Aplica resize numa imagem."""
        if isinstance(image, (str, Path)):
            resized_image = cls.from_path(image, resize, maintain_proportion, sample)
        elif isinstance(image, (ImageFile, Image)):
            resized_image = cls.from_image_file(
                image, resize, maintain_proportion, sample
            )
        else:
            raise TypeError("O tipo da imagem é inválido.")
        return resized_image


def _image_to_array(image: "Image") -> "NDArray[uint8]":
    """Retorna um ImageFile convertido em um numpy.ndarray"""
    return array(image)


class RGBUtils:
    """Funções utilitárias para manipulação de RGB."""

    CACHE: dict["RGBColor", str] = {}
    LRU_MAXSIZE_ROUNDED_RGB = 4096
    LRU_MAXSIZE_CALC = LRU_MAXSIZE_ROUNDED_RGB // 3

    @staticmethod
    @lru_cache(maxsize=LRU_MAXSIZE_CALC)
    def round_channel(channel: int, step: int) -> int:
        """Arredonda um canal RGB para um step definido."""
        return channel // step * step

    @classmethod
    @lru_cache(maxsize=LRU_MAXSIZE_ROUNDED_RGB)
    def round_rgb(cls, rgb: "RGBColor", step: int = 4) -> "RGBColor":
        """Arredonda um RGB para um step."""
        r, g, b = rgb
        if step < 0:
            raise ValueError("step deve ser maior que 0.")
        return (
            cls.round_channel(r, step),
            cls.round_channel(g, step),
            cls.round_channel(b, step),
        )

    @classmethod
    def to_ansi(
        cls,
        text: str,
        rgb: "RGBColor",
        alpha_replacer: "RGBColor | None" = None,
        use_cache: bool = True,
        round_step: int | None = None,
    ) -> str:
        """Retorna um texto ANSI com RGB aplicado."""
        if alpha_replacer is not None and all(v == 0 for v in rgb):
            rgb = alpha_replacer
        if use_cache and rgb in cls.CACHE:
            return cls.CACHE[rgb]
        r, g, b = rgb if round_step is None else cls.round_rgb(rgb, round_step)
        ansi = f"\x1b[48;2;{r};{g};{b}m{text}"
        if use_cache:
            cls.CACHE[rgb] = ansi
        return ansi


class ImagePrinter:
    """Representa um printer de imagem em CLI."""

    RGB_ROUND_STEP = None

    @classmethod
    def from_path(cls, path: str | Path, show_pixel_index: bool = False) -> str:
        """
        Retorna a uma string que, quando imprimida,
        exibe a imagem carregada a partir de um caminho de imagem.
        """
        image = open_image(path)
        return cls.from_image_file(image, show_pixel_index)

    @classmethod
    def from_image_file(
        cls, image: ImageFile | Image, show_pixel_index: bool = False
    ) -> str:
        """
        Retorna a uma string que, quando imprimida, exibe a imagem carregada
        partir de um objeto ImageFile, do módulo PIL (pillow)."""
        pixels = _image_to_array(image)
        lines: list[str] = []
        for i, line in enumerate(pixels):
            for j, pixel in enumerate(line):
                text = "  "
                if show_pixel_index:
                    text = f"{(i + 1) * j} "
                ansi_pixel = RGBUtils.to_ansi(
                    text, tuple(pixel), round_step=cls.RGB_ROUND_STEP
                )
                lines.append(ansi_pixel)
            lines.append("\033[0m\n")
        printable_image = "".join(lines)
        return printable_image

    @classmethod
    def print(
        cls,
        image: "StrOrPathOrImageOrImageFile",
        *,
        show_pixel_index: bool = False,
        width: int | None = None,
        height: int | None = None,
        maintain_proportion: bool = True,
        only_output: bool = False,
        rgb_depth: int | None = None,
        resize_sample: ResizeImage.Sample = ResizeImage.Sample.BICUBIC,
    ) -> str:
        """
        Imprime uma imagem no CLI.

        Suporta objetos ImageFile ou caminhos para o arquivo de imagem.
        """
        resize = (width, height)
        resized_image = ResizeImage.resize(
            image, resize, maintain_proportion, resize_sample
        )
        cls.RGB_ROUND_STEP = rgb_depth
        output = cls.from_image_file(resized_image.convert("RGB"), show_pixel_index)
        if not only_output:
            print(output)
        return output


SUPPORTED_FORMATS = registered_extensions()
DEFAULT_RESIZE = (64, 64)


def resize_type(value: str) -> "ResizeTuple":
    """Normaliza o argumentos CLI de --resize."""
    error = ArgumentTypeError(
        f"O valor para --resize é inválido: {value}. "
        "De ser um número ou dois separados por vírgula sem espaços"
    )
    try:
        if not value.isdigit() and "," in value:
            a, b = value.split(",")
            return int(a), int(b)
        return int(value), int(value)
    except ValueError as e:
        raise error from e


def file_path_type(value: str) -> Path:
    """Normaliza o argumento CLI de path."""
    path = path_type(value)
    if path.is_dir():
        raise ArgumentTypeError(f"O caminho não é de um arquivo: {str(path)!r}")
    if path.suffix not in SUPPORTED_FORMATS:
        raise ArgumentTypeError(f"O arquivo de imagem não é suportado: {path.suffix!r}")
    return path


def path_type(value: str) -> Path:
    """Normaliza um argumo que representa um caminho."""
    path = Path(value).resolve()
    if not path.exists():
        raise ArgumentTypeError(f"O caminho não existe: {str(path)!r}")
    return path


def sample_resize_type(value: str) -> ResizeImage.Sample:
    try:
        return ResizeImage.Sample[value.upper()]
    except KeyError as e:
        raise ArgumentTypeError(f"O sample {value!r} não é válido.") from e


def apply_parse() -> tuple[ArgumentParser, Namespace]:
    """Cria e aplica os parsers CLI."""
    parser = ArgumentParser()
    subparser = parser.add_subparsers(dest="action")
    printer_parser = subparser.add_parser("print")
    printer_parser.add_argument(
        "path", type=file_path_type, help="Caminho do arquivo de uma imagem suportada."
    )
    printer_parser.add_argument(
        "--resize",
        type=resize_type,
        help="Valor de resize, deve ser um número para representar W e H (ex: 10 = 10x10) ou "
        "dois números separados por vírgula sem espaços (ex: 10,20 = 10x20).",
    )
    printer_parser.add_argument(
        "-W",
        "--width",
        help="Altera apenas a largura da imagem.",
        type=int,
        dest="width_resize",
    )

    printer_parser.add_argument(
        "-H",
        "--height",
        help="Altera apenas a altura da imagem.",
        type=int,
        dest="height_resize",
    )

    printer_parser.add_argument(
        "--no-proportional",
        action="store_true",
        default=False,
        dest="no_proportional",
        help="Aplica o resize sem manter proporcões.",
    )

    printer_parser.add_argument(
        "--debug", action="store_true", default=False, dest="debug"
    )

    printer_parser.add_argument("--rgb-depth", type=int, default=8, dest="rgb_depth")

    printer_parser.add_argument(
        "--resize-sample",
        type=sample_resize_type,
        default=ResizeImage.Sample.BICUBIC,
        dest="resize_sample",
    )

    misc_parser = subparser.add_parser("misc")
    misc_parser.add_argument(
        "--list-supported", action="store_true", default=False, dest="list_supported"
    )

    misc_parser.add_argument(
        "--list-samples", action="store_true", default=False, dest="list_samples"
    )
    misc_parser.add_argument("--list-dir", type=path_type, dest="list_dir")
    misc_parser.add_argument("--max-length", type=int, default=10, dest="max_length")

    return parser, parser.parse_args()


def list_images_in_dir(dir_: Path) -> list[Path]:
    """Retorna uma lista dos arquivos que são suportados pelo programa."""
    return [
        file
        for file in dir_.iterdir()
        if not file.is_file() or file.stem not in SUPPORTED_FORMATS
    ]


def process_args(args: Namespace) -> bool:
    """Processa os argumentos CLI parseados."""
    if args.action == "misc":
        if args.list_supported is True:
            for ext, name in SUPPORTED_FORMATS.items():
                print(f"\033[33m{ext!r}:\033[0m \033[32m{name!r}\033[0m")
            return True
        if args.list_dir is not None:
            from shutil import get_terminal_size

            terminal_width = get_terminal_size().columns
            line_width = 0
            right_retreat = args.max_length or 8
            for file in list_images_in_dir(args.list_dir):
                if not file.suffix or file.suffix not in SUPPORTED_FORMATS:
                    continue
                name = file.name
                line_width += len(name) + (4 * right_retreat)
                if line_width >= terminal_width:
                    print()
                    line_width = 0
                print(f"\033[33m{name!r}", end="\033[0m, ")
            print()
            return True
        if args.list_samples is True:
            for sample in ResizeImage.Sample:
                print(sample.name.upper())
            return True
        return False
    if args.action == "print":
        path = args.path
        if path is None:
            return False
        resize: "OptionalResizeTuple | None" = args.resize
        w, h = args.width_resize, args.height_resize
        if resize is not None:
            w = w or resize[0]
            h = h or resize[1]

        ImagePrinter.print(
            path,
            width=w,
            height=h,
            maintain_proportion=not args.no_proportional,
            show_pixel_index=args.debug,
            rgb_depth=args.rgb_depth,
            resize_sample=args.resize_sample,
        )
        return True
    return False


def main():
    """Entry Point"""
    parser, args = apply_parse()
    success = process_args(args)
    if not success:
        parser.print_help()
