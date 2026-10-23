"""Порты: то, что прикладной слой ожидает от внешнего мира."""

from pathlib import Path
from typing import Protocol, Sequence

from textuniq.domain.models import TextBlock


class Translator(Protocol):
    """Машинный переводчик. Каждый текст списка переводится независимо."""

    def translate_batch(self, texts: Sequence[str], source: str, target: str) -> list[str]: ...


class TextTranslator(Protocol):
    """Переводит один текст целиком (например, по всей цепочке языков)."""

    def translate(self, text: str) -> str: ...


class EditableDocument(Protocol):
    def blocks(self) -> list[TextBlock]: ...

    def replace_text(self, block_id: int, text: str) -> None: ...

    def save(self, path: Path) -> None: ...


class DocumentLoader(Protocol):
    def load(self, path: Path) -> EditableDocument: ...
