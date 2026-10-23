import logging
from typing import Sequence

from textuniq.application.ports import Translator
from textuniq.domain.errors import TranslationError
from textuniq.domain.models import TranslationChain
from textuniq.domain.text import split_into_chunks

log = logging.getLogger(__name__)


class ChainTranslator:
    """Прогоняет один текст по цепочке языков: каждый шаг — отдельный запрос."""

    def __init__(self, translator: Translator, chain: TranslationChain):
        self._translator = translator
        self._chain = chain

    @property
    def chain(self) -> TranslationChain:
        return self._chain

    def translate(self, text: str) -> str:
        current = text
        for source, target in self._chain.steps:
            (result,) = self._translator.translate_batch([current], source, target)
            result = result.strip()
            if not result:
                raise TranslationError(f"Шаг {source}→{target} вернул пустой результат")
            log.debug("%s→%s: %s", source, target, result)
            current = result
        return current


class SegmentingTranslator:
    """Декоратор: режет длинные тексты по предложениям под лимит модели.

    Куски одного абзаца переводятся пачкой, но независимо друг от друга,
    затем склеиваются обратно через пробел.
    """

    def __init__(self, inner: Translator, max_chars: int = 600):
        self._inner = inner
        self._max_chars = max_chars

    def translate_batch(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        layout: list[int] = []
        flat: list[str] = []
        for text in texts:
            chunks = split_into_chunks(text, self._max_chars) or [text]
            layout.append(len(chunks))
            flat.extend(chunks)

        translated = self._inner.translate_batch(flat, source, target)
        if len(translated) != len(flat):
            raise TranslationError("Переводчик вернул неверное число результатов")

        result, pos = [], 0
        for count in layout:
            parts = [part.strip() for part in translated[pos:pos + count]]
            result.append(" ".join(p for p in parts if p))
            pos += count
        return result
