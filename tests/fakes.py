"""Тестовые двойники для портов прикладного слоя."""

from pathlib import Path

from textuniq.domain.errors import DocumentError, TranslationError
from textuniq.domain.models import TextBlock


class SpyTranslator:
    """Помечает перевод кодом языка и запоминает каждый вызов.

    inject — строка, которую «переводчик» дописывает в результат (например, тире),
    fail_on — подстрока, на которой переводчик падает с TranslationError.
    """

    def __init__(self, inject: str = "", fail_on: str | None = None, empty_on: str | None = None):
        self.inject = inject
        self.fail_on = fail_on
        self.empty_on = empty_on
        self.calls: list[tuple[tuple[str, ...], str, str]] = []

    def translate_batch(self, texts, source, target):
        self.calls.append((tuple(texts), source, target))
        out = []
        for text in texts:
            if self.fail_on and self.fail_on in text:
                raise TranslationError("сбой фейкового переводчика")
            if self.empty_on and self.empty_on in text:
                out.append("   ")
                continue
            out.append(f"[{target}]{self.inject} {text}")
        return out


class InMemoryDocument:
    def __init__(self, blocks: list[TextBlock]):
        self._blocks = {b.id: b for b in blocks}
        self.saved_to: Path | None = None
        self.replacements: list[tuple[int, str]] = []

    def blocks(self) -> list[TextBlock]:
        return list(self._blocks.values())

    def replace_text(self, block_id: int, text: str) -> None:
        old = self._blocks[block_id]
        self._blocks[block_id] = TextBlock(old.id, text, old.role)
        self.replacements.append((block_id, text))

    def save(self, path: Path) -> None:
        self.saved_to = Path(path)
        Path(path).write_text("\n".join(b.text for b in self.blocks()), encoding="utf-8")

    def text_of(self, block_id: int) -> str:
        return self._blocks[block_id].text


class InMemoryLoader:
    def __init__(self, document: InMemoryDocument):
        self.document = document
        self.loaded_from: Path | None = None

    def load(self, path: Path) -> InMemoryDocument:
        path = Path(path)
        if not path.exists():
            raise DocumentError(f"Файл не найден: {path}")
        self.loaded_from = path
        return self.document
