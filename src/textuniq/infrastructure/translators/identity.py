from typing import Sequence


class IdentityTranslator:
    """Ничего не переводит. Нужен для отладки обработки docx без моделей."""

    max_text_chars = None  # без ограничения длины, абзац не режется

    def translate_batch(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        return list(texts)
