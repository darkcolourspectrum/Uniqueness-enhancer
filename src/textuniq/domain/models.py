from dataclasses import dataclass
from enum import Enum


class BlockRole(Enum):
    MAIN = "main"            # основной текст: переводится и чистится
    AUXILIARY = "auxiliary"  # колонтитулы, сноски и т.п.: только чистится


@dataclass(frozen=True)
class TextBlock:
    """Абзац документа, независимо от формата файла."""

    id: int
    text: str
    role: BlockRole = BlockRole.MAIN


@dataclass(frozen=True)
class TranslationChain:
    """Цепочка языков, например ru → en → de → ru."""

    languages: tuple[str, ...]

    def __post_init__(self) -> None:
        langs = self.languages
        if len(langs) < 3:
            raise ValueError("Цепочка должна содержать хотя бы один промежуточный язык")
        if langs[0] != langs[-1]:
            raise ValueError("Цепочка должна возвращаться к исходному языку")
        if any(a == b for a, b in zip(langs, langs[1:])):
            raise ValueError("Соседние языки цепочки не должны совпадать")

    @classmethod
    def default(cls) -> "TranslationChain":
        return cls(("ru", "en", "de", "ru"))

    @classmethod
    def parse(cls, raw: str) -> "TranslationChain":
        return cls(tuple(part.strip().lower() for part in raw.split(",") if part.strip()))

    @property
    def source(self) -> str:
        return self.languages[0]

    @property
    def steps(self) -> list[tuple[str, str]]:
        return list(zip(self.languages, self.languages[1:]))

    def __str__(self) -> str:
        return " → ".join(self.languages)
